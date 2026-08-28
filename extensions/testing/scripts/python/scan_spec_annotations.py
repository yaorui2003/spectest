#!/usr/bin/env python3
"""@Spec 注解扫描脚本（Python 版）。

解析 ``.java`` 源文件提取 ``@Spec`` 注解，并解析 ``spec.md`` 的
``business_rules`` 规则编号，输出 JSON 供 ``speckit.testing.gate`` 命令消费。

v0.6（9.6 节）新增 **UNSPEC_CODE 漂移检测**（T1 结构性 MEDIUM 告警，不阻断
PASS/FAIL 判定）：比对"生产类清单 vs @Spec 标注"，对（非排除、未标注 @Spec、
未被测试引用）的业务类输出 ``unspec_codes`` 告警列表。

用法::

    python scan_spec_annotations.py --source <java_dir> --spec <spec.md> --json
    python scan_spec_annotations.py --source <java_dir> --spec <spec.md> \
        --test-source <test_dir> --exclude-patterns "legacy,*Helper" --json
    python scan_spec_annotations.py --source <java_dir> --spec <spec.md> \
        --test-source <test_dir> --config <testing-config.yml> --json
        # --config 读 scan.unspec_exclude_patterns；--exclude-patterns 优先

输出 JSON schema 见
``specs/001-speckit-testing-ext/contracts/spec-annotation.md`` 的"扫描契约"段。

三语言（py/sh/ps）等价：本脚本定义输出格式（``json.dumps`` +
``ensure_ascii=False`` + ``indent=2``），bash/PowerShell 版本输出字节级等价。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# @Spec 注解正则：@Spec(capability="...", rule="FR-001", description="...")
# description 可选；字段间允许任意空白；rule 支持顶层锚 FR-\d+（新体系，默认）
# 与纯 R\d+（老项目 Business Rules 回落）；子编号 -R\d+ 被剥离、永不进入比对
# （@Spec 永远只写顶层锚）。
SPEC_ANNOTATION_RE = re.compile(
    r'@Spec\s*\(\s*capability\s*=\s*"([^"]+)"\s*,\s*rule\s*=\s*'
    r'"(?:(FR-\d+)|(R\d+))(?:-R\d+)?"'
    r'(?:\s*,\s*description\s*=\s*"([^"]*)")?\s*\)'
)

# 包名：package com.example;
PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;")

# 类名：class AccountService / interface / enum / record
CLASS_RE = re.compile(r"\b(?:class|interface|enum|record)\s+(\w+)")

# 方法签名：public|protected|private [返回类型] methodName(
# 返回类型可选，捕获方法名（紧跟左括号前的标识符）。
METHOD_SIG_RE = re.compile(
    r"\b(?:public|protected|private)\s+(?:[\w<>,\s\[\]]+?\s+)?(\w+)\s*\("
)

# spec.md 权威源段标题：
# ① ### Functional Requirements 段（FR 顶层锚，新项目默认/唯一必选路径，v0.63 起）
# ② ## Business Rules 段（R\d+，老项目兼容回落，v0.6 行为）
FR_HEADER_RE = re.compile(r"^#{1,6}\s+Functional Requirements", re.IGNORECASE)
BUSINESS_RULES_HEADER_RE = re.compile(r"^#{1,6}\s+.*business[\s_-]+rules", re.IGNORECASE)

# 章节内行首规则编号：- FR-001: / - **FR-001** / - R1: / * **R1** / R1: ...
# 同时认 FR 顶层锚与新体系；只提取顶层锚（FR-\d+ / R\d+），FR 的 -R 不做（段内无）
RULE_LINE_RE = re.compile(r"^\s*[-*]?\s*\**?(FR-\d+|R\d+)\b")

# 查找方法名的最大向后扫描行数
_METHOD_SCAN_WINDOW = 20

# 默认排除：包名含这些段 或 类名匹配这些后缀的类不参与漂移告警
DEFAULT_UNSPEC_EXCLUDE_PACKAGES = (
    "dto", "vo", "entity", "config", "exception", "util", "helper",
)
DEFAULT_UNSPEC_EXCLUDE_CLASS_SUFFIXES = ("Mapper", "Config", "Factory", "Constants")


def parse_spec_rules(spec_path: Path) -> list[str]:
    """解析 spec.md 的 business_rules 章节，提取规则编号（保持出现顺序，去重）。"""
    text = spec_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_section = False
    rules: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            # 进入新章节
            if BUSINESS_RULES_HEADER_RE.match(stripped):
                in_section = True
            else:
                if in_section:
                    break  # 离开 business_rules 章节
            continue
        if not in_section:
            continue
        m = RULE_LINE_RE.match(line)
        if m:
            rule = m.group(1)
            if rule not in seen:
                rules.append(rule)
                seen.add(rule)
    return rules


def parse_fr_section(spec_path: Path) -> list[str]:
    """解析 spec.md 的 ``### Functional Requirements`` 段，提取 FR 顶层锚（去重保序）。

    v0.66（v0.63 六章 6.1）：新项目规则权威源 = spec.md 原生 FR 段
    （``FR-001`` 编号，上游原版模板 REQUIRED 段，无 ``## Business Rules`` 段）。
    行格式兼容 ``- **FR-001**: System MUST ...`` / ``- FR-001: ...`` 等。
    """
    text = spec_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_section = False
    rules: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if FR_HEADER_RE.match(stripped):
                in_section = True
            else:
                if in_section:
                    break  # 离开 Functional Requirements 段
            continue
        if not in_section:
            continue
        m = RULE_LINE_RE.match(line)
        if m:
            rule = m.group(1)
            if rule not in seen:
                rules.append(rule)
                seen.add(rule)
    return rules


def _resolve_rule_source(spec_path: Path) -> tuple[str, list[str]]:
    """按优先级解析 spec.md 规则权威源（v0.63 2.3 / 3.4.1 契约）。

    返回 ``(rule_source, rules)``：
    - ``"fr-section"``：spec.md ``### Functional Requirements`` 段（FR-001，优先）；
    - ``"business-rules"``：spec.md ``## Business Rules`` 段（R\\d+，老项目兼容回
      落，仅在 FR 段缺失时启用）；
    - ``"none"``：两者皆无 -> 空规则集。
    """
    fr_rules = parse_fr_section(spec_path)
    if fr_rules:
        return "fr-section", fr_rules
    br_rules = parse_spec_rules(spec_path)
    if br_rules:
        return "business-rules", br_rules
    return "none", []


def _find_method_name(lines: list[str], spec_line_idx: int) -> str | None:
    """从 @Spec 行（含）向下查找方法名，跳过其他注解行。

    传入的 ``lines`` 必须是注释剥离后的有效行列表（与原始行等长），
    以保证与包名/类名/@Spec 查找共用同一份"有效行集"。
    """
    upper = min(spec_line_idx + _METHOD_SCAN_WINDOW, len(lines))
    for j in range(spec_line_idx, upper):
        line = lines[j]
        if j != spec_line_idx and line.strip().startswith("@"):
            continue  # 跳过 @Spec 之后的其他注解（如 @Transactional）
        m = METHOD_SIG_RE.search(line)
        if m:
            return m.group(1)
    return None


def _strip_comments(lines: list[str]) -> list[str]:
    """对 Java 源码行做注释剥离（方案 4.1 状态机），返回与输入**等长**的有效行列表。

    块注释 ``/* ... */`` 可跨行持续（``in_block`` 在单文件内贯穿）；
    行注释 ``//`` 截断到行尾。剥离只改变行内容、不改变行数，因此返回列表的
    索引与原始行号一一对应 —— 调用方后续查找用 ``stripped[i]`` 取内容、
    用原始 ``i + 1`` 作 location 行号，行号不会错位。
    """
    stripped: list[str] = []
    in_block = False
    for line in lines:
        if in_block:
            if "*/" in line:
                in_block = False
                line = line[line.index("*/") + 2:]
            else:
                stripped.append("")
                continue
        if "/*" in line:
            idx = line.index("/*")
            before = line[:idx]
            rest = line[idx + 2:]
            if "*/" in rest:
                line = before + rest[rest.index("*/") + 2:]
            else:
                in_block = True
                line = before
        if "//" in line:
            line = line[: line.index("//")]
        stripped.append(line)
    return stripped


def _extract_class_identity(stripped: list[str]) -> tuple[str, str]:
    """从注释剥离后的有效行中提取 (包名, 类名)，分别复用 PACKAGE_RE / CLASS_RE。"""
    package = ""
    for line in stripped:
        m = PACKAGE_RE.match(line)
        if m:
            package = m.group(1)
            break

    class_name = ""
    for line in stripped:
        m = CLASS_RE.search(line)
        if m:
            class_name = m.group(1)
            break

    return package, class_name


def _parse_java_file_full(java_path: Path) -> tuple[list[dict], str, str]:
    """解析单个 .java 文件：返回 (annotations, package, class_name)。

    先对整个文件做注释剥离（方案 4.1）生成有效行列表，包名/类名/@Spec/方法名
    查找全部基于有效行；但 location 的 ``:i + 1`` 仍指向原始文件行号。
    """
    text = java_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    stripped = _strip_comments(lines)

    package, class_name = _extract_class_identity(stripped)

    annotations: list[dict] = []
    for i, line in enumerate(stripped):
        for m in SPEC_ANNOTATION_RE.finditer(line):
            capability = m.group(1)
            # rule 归一为顶层锚：FR-\d+（新体系）优先，R\d+（老项目回落）兜底；
            # 误带 -R 子编号会被正则剥离，永不进入比对
            rule = m.group(2) if m.group(2) is not None else m.group(3)
            description = m.group(4) or ""
            method_name = _find_method_name(stripped, i)
            if method_name is None:
                method_name = class_name  # 类级注解兜底用类名
            if package:
                location = f"{package}.{class_name}.{method_name}:{i + 1}"
            else:
                location = f"{class_name}.{method_name}:{i + 1}"
            annotations.append({
                "rule": rule,
                "capability": capability,
                "description": description,
                "location": location,
            })
    return annotations, package, class_name


def parse_java_file(java_path: Path) -> list[dict]:
    """解析单个 .java 文件，提取 @Spec 注解（含 location）。兼容薄封装。"""
    annotations, _, _ = _parse_java_file_full(java_path)
    return annotations


def _collect_test_texts(test_source_dir: Path | None) -> list[str]:
    """收集测试源码目录下所有 .java 文件全文（用于测试引用判定）。

    不传 ``test_source_dir`` 时视为无测试引用。遍历顺序与 source 目录一致
    （``sorted(rglob("*.java"))``）。
    """
    if test_source_dir is None:
        return []
    texts: list[str] = []
    for java_file in sorted(test_source_dir.rglob("*.java")):
        texts.append(java_file.read_text(encoding="utf-8"))
    return texts


def _is_referenced_by_tests(class_name: str, test_texts: list[str]) -> bool:
    """判定业务类是否被测试引用：测试文本中存在 ``\\b<class_name>\\b`` 完整词。"""
    if not test_texts:
        return False
    pattern = re.compile(rf"\b{re.escape(class_name)}\b")
    return any(pattern.search(text) for text in test_texts)


def _build_extra_excludes(exclude_patterns: str) -> tuple[list[str], list[re.Pattern]]:
    """解析逗号分隔的额外排除模式，返回 (额外包段列表, 额外类名正则列表)。

    模式同时覆盖包段/类名后缀两种语义：不含通配符的段按包段匹配
    （package 任一段 == 该段）；含 ``*`` 的模式把 ``*`` 展开为 ``.*`` 后
    转成正则 fullmatch 类名（即类名后缀匹配，如 ``*Mapper`` -> ``.*Mapper``）。
    """
    pkg_segments: list[str] = []
    class_regexes: list[re.Pattern] = []
    for raw in exclude_patterns.split(","):
        pattern = raw.strip()
        if not pattern:
            continue
        if "*" in pattern:
            regex_src = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
            class_regexes.append(re.compile(regex_src))
        else:
            pkg_segments.append(pattern)
    return pkg_segments, class_regexes


def _is_unspec_excluded(
    package: str,
    class_name: str,
    extra_pkg_segments: list[str],
    extra_class_regexes: list[re.Pattern],
) -> bool:
    """判定 (package, class_name) 是否命中漂移排除表。

    命中即排除：内置包段（package 任一段 in DEFAULT_UNSPEC_EXCLUDE_PACKAGES）、
    内置类名后缀（endswith DEFAULT_UNSPEC_EXCLUDE_CLASS_SUFFIXES）、
    以及额外模式（不含 ``*`` 按包段、含 ``*`` 按类名正则）。
    """
    if any(seg in DEFAULT_UNSPEC_EXCLUDE_PACKAGES for seg in package.split(".")):
        return True
    if any(class_name.endswith(suffix) for suffix in DEFAULT_UNSPEC_EXCLUDE_CLASS_SUFFIXES):
        return True
    if any(seg in extra_pkg_segments for seg in package.split(".")):
        return True
    if any(rx.fullmatch(class_name) for rx in extra_class_regexes):
        return True
    return False


def scan(
    source_dir: Path,
    spec_path: Path,
    test_source_dir: Path | None = None,
    exclude_patterns: str = "",
) -> dict:
    """扫描源码目录与 spec.md，组装扫描契约 JSON 对象。

    ``test_source_dir`` 可选（新增）：被测试引用的生产类不参与 UNSPEC_CODE
    漂移告警；不传视为无测试引用。

    ``exclude_patterns`` 可选（新增）：逗号分隔的额外排除模式，来自 run_gate
    透传的 config ``scan.unspec_exclude_patterns``；不含 ``*`` 的段按包段匹配，
    含 ``*`` 的模式转成正则匹配类名后缀。

    ``unspec_codes`` 为 MEDIUM 结构性告警，不参与 PASS/FAIL 判定。
    """
    rule_source, spec_rules = _resolve_rule_source(spec_path)

    annotations: list[dict] = []
    # 生产类清单（保持文件遍历顺序）：{package, class_name, annotated}
    class_infos: list[dict] = []
    # 按 Path 字符串排序，保证三语言一致的文件遍历顺序
    for java_file in sorted(source_dir.rglob("*.java")):
        file_annotations, package, class_name = _parse_java_file_full(java_file)
        annotations.extend(file_annotations)
        if class_name:
            class_infos.append({
                "package": package,
                "class_name": class_name,
                "annotated": bool(file_annotations),  # 文件级有任意 @Spec 即已标注
            })

    # annotated_rules：规则 -> 位置清单（按 annotations 出现顺序构建）
    annotated_rules: dict[str, list[str]] = {}
    for ann in annotations:
        annotated_rules.setdefault(ann["rule"], []).append(ann["location"])

    spec_set = set(spec_rules)
    annotated_set = set(annotated_rules.keys())

    # unimplemented_rules：spec.md 有但代码无 @Spec（保持 spec_rules 顺序）
    unimplemented_rules = [r for r in spec_rules if r not in annotated_set]

    # orphan_annotations：代码有 @Spec 但 spec.md 无对应规则（保持 annotations 顺序）
    orphan_annotations = [ann for ann in annotations if ann["rule"] not in spec_set]

    # coverage_percent：已注解规则数 / spec 规则总数 * 100
    if spec_rules:
        covered = sum(1 for r in spec_rules if r in annotated_set)
        coverage_percent = round(covered / len(spec_rules) * 100)
    else:
        coverage_percent = 0

    # UNSPEC_CODE 漂移检测（9.6，T1 结构性 MEDIUM，不阻断判定）：
    # 非排除、未标注 @Spec、且未被测试引用的业务类 -> 完整类名告警列表
    extra_pkg_segments, extra_class_regexes = _build_extra_excludes(exclude_patterns)
    test_texts = _collect_test_texts(test_source_dir)
    unspec_codes: list[str] = []
    for info in class_infos:
        package, class_name, annotated = (
            info["package"], info["class_name"], info["annotated"],
        )
        if annotated:
            continue
        if _is_unspec_excluded(package, class_name, extra_pkg_segments, extra_class_regexes):
            continue
        if _is_referenced_by_tests(class_name, test_texts):
            continue
        unspec_codes.append(f"{package}.{class_name}" if package else class_name)

    return {
        "rule_source": rule_source,
        "spec_rules": spec_rules,
        "annotations": annotations,
        "annotated_rules": annotated_rules,
        "unimplemented_rules": unimplemented_rules,
        "orphan_annotations": orphan_annotations,
        "coverage_percent": coverage_percent,
        "unspec_codes": unspec_codes,
    }


def _config_exclude_patterns(config_path: Path) -> str:
    """从 testing-config.yml 读 ``scan.unspec_exclude_patterns`` 并规整为逗号分隔字符串。

    复用 run_gate._load_config（同一最小 YAML 解析，保证与 run_gate 行为一致；
    延迟 import 避免本脚本独立使用时引入 run_gate 模块）。值可为内联列表字符串
    （``[legacy, "*Helper"]``）或逗号分隔字符串；[]/None/空 -> ""。config 文件
    缺失/不可读 -> ""（_load_config 容错返回空 dict）。
    """
    try:
        from run_gate import _load_config
    except ImportError:
        return ""
    cfg = _load_config(config_path)
    scan_cfg = cfg.get("scan", {}) if isinstance(cfg.get("scan"), dict) else {}
    patterns = scan_cfg.get("unspec_exclude_patterns", [])
    if isinstance(patterns, str):
        patterns = [
            p.strip()
            for p in patterns.strip("[]").replace('"', "").replace("'", "").split(",")
            if p.strip()
        ]
    elif not isinstance(patterns, list):
        patterns = []
    return ",".join(patterns)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="@Spec 注解扫描脚本：解析 .java 提取 @Spec 注解并比对 spec.md 规则。"
    )
    parser.add_argument("--source", required=True, help="Java 源文件根目录")
    parser.add_argument("--spec", required=True, help="spec.md 文件路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    parser.add_argument(
        "--test-source",
        help="测试源码根目录（可选）：被测试引用的生产类不参与 UNSPEC_CODE 漂移告警",
    )
    parser.add_argument(
        "--exclude-patterns",
        default="",
        help="额外排除模式（逗号分隔，可选）：不含 * 的段按包段匹配，含 * 的"
             "模式转成正则匹配类名后缀；UNSPEC_CODE 漂移告警为 MEDIUM，不阻断"
             "PASS/FAIL 判定",
    )
    parser.add_argument(
        "--config",
        default="",
        help="testing-config.yml 路径（可选）：存在时读 scan.unspec_exclude_patterns"
             "作为额外排除模式的 config 默认；--exclude-patterns 显式提供时以 CLI 为准",
    )
    args = parser.parse_args()

    # v0.6 6.5/9.6 语义：CLI 非空用 CLI，否则回落 config scan.unspec_exclude_patterns
    exclude_patterns = args.exclude_patterns
    if not exclude_patterns and args.config:
        exclude_patterns = _config_exclude_patterns(Path(args.config))

    result = scan(
        Path(args.source),
        Path(args.spec),
        Path(args.test_source) if args.test_source else None,
        exclude_patterns,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
