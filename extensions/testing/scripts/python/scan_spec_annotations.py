#!/usr/bin/env python3
"""@Spec 注解扫描脚本（Python 版）。

解析 ``.java`` 源文件提取 ``@Spec`` 注解，并解析 ``spec.md`` 的
``business_rules`` 规则编号，输出 JSON 供 ``speckit.testing.gate`` 命令消费。

用法::

    python scan_spec_annotations.py --source <java_dir> --spec <spec.md> --json

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

# @Spec 注解正则：@Spec(capability="...", rule="Rn", description="...")
# description 可选；字段间允许任意空白；rule 必须为 R\d+。
SPEC_ANNOTATION_RE = re.compile(
    r'@Spec\s*\(\s*capability\s*=\s*"([^"]+)"\s*,\s*rule\s*=\s*"(R\d+)"'
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

# spec.md business_rules 章节标题（含 "business rules" 或 "business_rules"）
BUSINESS_RULES_HEADER_RE = re.compile(r"^#{1,6}\s+.*business[\s_-]+rules", re.IGNORECASE)

# 章节内行首规则编号：- R1: / * **R1** / R1: ...
RULE_LINE_RE = re.compile(r"^\s*[-*]?\s*\**?(R\d+)\b")

# 查找方法名的最大向后扫描行数
_METHOD_SCAN_WINDOW = 20


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


def _find_method_name(lines: list[str], spec_line_idx: int) -> str | None:
    """从 @Spec 行（含）向下查找方法名，跳过其他注解行。"""
    upper = min(spec_line_idx + _METHOD_SCAN_WINDOW, len(lines))
    for j in range(spec_line_idx, upper):
        line = lines[j]
        if j != spec_line_idx and line.strip().startswith("@"):
            continue  # 跳过 @Spec 之后的其他注解（如 @Transactional）
        m = METHOD_SIG_RE.search(line)
        if m:
            return m.group(1)
    return None


def parse_java_file(java_path: Path) -> list[dict]:
    """解析单个 .java 文件，提取 @Spec 注解（含 location）。"""
    text = java_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 提取包名
    package = ""
    for line in lines:
        m = PACKAGE_RE.match(line)
        if m:
            package = m.group(1)
            break

    # 提取类名
    class_name = ""
    for line in lines:
        m = CLASS_RE.search(line)
        if m:
            class_name = m.group(1)
            break

    annotations: list[dict] = []
    for i, line in enumerate(lines):
        for m in SPEC_ANNOTATION_RE.finditer(line):
            capability, rule, description = m.group(1), m.group(2), m.group(3) or ""
            method_name = _find_method_name(lines, i)
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
    return annotations


def scan(source_dir: Path, spec_path: Path) -> dict:
    """扫描源码目录与 spec.md，组装扫描契约 JSON 对象。"""
    spec_rules = parse_spec_rules(spec_path)

    annotations: list[dict] = []
    # 按 Path 字符串排序，保证三语言一致的文件遍历顺序
    for java_file in sorted(source_dir.rglob("*.java")):
        annotations.extend(parse_java_file(java_file))

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

    return {
        "spec_rules": spec_rules,
        "annotations": annotations,
        "annotated_rules": annotated_rules,
        "unimplemented_rules": unimplemented_rules,
        "orphan_annotations": orphan_annotations,
        "coverage_percent": coverage_percent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="@Spec 注解扫描脚本：解析 .java 提取 @Spec 注解并比对 spec.md 规则。"
    )
    parser.add_argument("--source", required=True, help="Java 源文件根目录")
    parser.add_argument("--spec", required=True, help="spec.md 文件路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    args = parser.parse_args()

    result = scan(Path(args.source), Path(args.spec))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
