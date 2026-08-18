#!/usr/bin/env python3
"""门禁编排脚本 run_gate（Python 版）。

v0.4 核心改造：把 ``speckit.testing.gate`` 门禁的全部确定性逻辑下沉到脚本，
AI 仅读 stdout 判定 JSON，**不能改判、不能补写 gate-result.md、不能跳过步骤**
（直击试点 P0 #1：Agent 伪造覆盖率）。

职责（v0.4 第五章 5.2 的 9 步 + v0.5 步骤 5.5 关键路径对抗校验 + v0.6 改进项）:

0. 检查 ``specs/<feature>/docs/impact-report.md`` 存在（不存在 -> FAIL，堵 P0 #3）
1. ``mvn clean test``（强制 clean，杜绝 target 残留污染，堵 P0 #2；v0.6 在
   ``collect_environment`` 定位的 ``mvn_dir`` 执行）
2. 调 ``scan_test_stack``（forbidden_findings 非空 -> FAIL）
3. 调 ``parse_test_results``（jacoco.xml/surefire-reports 缺失 -> FAIL，不降级；
   v0.6 9.4 消费其 class 级覆盖率做作用域判定）
4. 调 ``scan_spec_annotations``（unimplemented_rules/orphan_annotations 非空 -> FAIL；
   v0.6 9.6 读取其 ``unspec_codes`` 漂移告警，MEDIUM 不阻断）
5. 内联解析 test 源码 ``@DisplayName("Rn-...")`` 算对齐数
5.5. 关键路径对抗校验（v0.5 新增）：读 impact-report 逐规则 risk + 检测
    ``@DisplayName("Rn-对抗-...")``；``critical_path_required=true`` 且 high
    风险规则 0 对抗用例 -> FAIL（configurable，false 降级跳过）
6. 读 ``impact-report.md`` 的 ``risk_level`` + 读 ``testing-config.yml`` 套风险档阈值
7. 逐项比对覆盖率/通过率/Spec 覆盖率与阈值（v0.6 9.4：非 all 时按作用域内 class
   逐个判定，作用域外类只统计不 FAIL；越界/空作用域 -> FAIL；baseline 增量退化 -> FAIL）
8. **脚本直接写 ``specs/<feature>/docs/gate-result.md``** + stdout 输出判定 JSON
   （v0.6 5.1/9.3：写前只读正则检查 SOFT 段标题，缺失 WARN + soft_missing=true 不改判）

降级模式（v0.4 5.5 + v0.6 4.1/9.2）：``collect_environment`` 判定——无
``java``/``mvn`` 可执行，**或项目无根 ``pom.xml`` 且无深度<=2 候选子模块 pom**时，
降级为仅做 ``@Spec`` 静态扫描（步骤 4 + 6 的 Spec 覆盖率阈值判定），跳过步骤 1-3/5。
唯一候选模块不降级（WARN + suggestion 建议命令，``--auto-locate`` 供 CI 自动采用）；
多候选视为用法错误（exit 2，提示显式 ``--project``）。这是唯一降级场景；Java 项目
缺 JaCoCo/surefire 报告**不降级，直接 FAIL**。

``--check-only`` 子模式：供 implement 第 4.5 阶段（对抗测试）调用，只跑步骤 1-8
（含 5.5 对抗校验）不写 gate-result.md，输出当前覆盖率与阈值差距 JSON，
供 AI 决定补测方向。

用法::

    python run_gate.py --source <java_dir> --test-source <test_dir> --spec <spec.md> \
        --project <root> --feature-dir <specs/<feature>> --config <testing-config.yml> \
        [--check-only] [--auto-locate] [--coverage-scope auto|<pkg,...>|all] \
        [--baseline <file>] --json

三语言（py/sh/ps）等价：本脚本的 ``run()`` 是**唯一确定性核心**（阈值比对 + 判定
+ 写 gate-result.md + JSON 序列化）；``collect_environment()`` 是环境收集的唯一
实现（java/mvn 检测 + 模块定位），bash/PowerShell 版本负责调用/透传；通过
``python3 -c`` 导入本模块调用 ``run()``，输出与 Python 版字节级等价（复用
``json.dumps(result, ensure_ascii=False, indent=2)`` 格式）。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# @DisplayName 内联解析正则：@DisplayName("Rn-<描述>")，提取规则编号
DISPLAYNAME_RE = re.compile(r'@DisplayName\s*\(\s*"R(\d+)-')

# 对抗用例识别：@DisplayName("Rn-对抗-...")，提取规则编号（v0.5 步骤 5.5）
ADVERSARIAL_RE = re.compile(r'@DisplayName\s*\(\s*"R(\d+)-对抗')

# class 级覆盖率指标 -> 阈值键（v0.6 9.4 作用域判定）
_METRIC_THRESHOLD_MAP = {
    "line_coverage": "line_coverage_min",
    "branch_coverage": "branch_coverage_min",
    "method_coverage": "method_coverage_min",
    "instruction_coverage": "instruction_coverage_min",
    "complexity_coverage": "complexity_coverage_min",
}

# class 级覆盖率指标 -> 聚合 coverage dict 键（threshold_results 展示用）
_COVERAGE_KEY_MAP = {
    "line_coverage": "line",
    "branch_coverage": "branch",
    "method_coverage": "method",
    "instruction_coverage": "instruction",
    "complexity_coverage": "complexity",
}

# 模块定位跳过的目录（_locate_module）
_MODULE_SKIP_DIRS = {".git", "node_modules", "target", "dist", "build"}

# 顶层包提取：package com.example; -> "com"
_PACKAGE_TOP_RE = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)


def _top_level_package(java_file: Path) -> str | None:
    """从 java 文件内容解析 ``package x.y.z;`` 的第一个标识符（顶层包）。

    解析失败（文件不存在/无 package 声明）返回 None。
    """
    try:
        text = java_file.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _PACKAGE_TOP_RE.search(text)
    return m.group(1) if m else None


def _git_diff_packages(mvn_dir: str) -> tuple[bool, set[str], set[str]]:
    """git diff --name-only HEAD 提取改动 Java 文件的顶层包。

    返回 (has_git, main_pkgs, all_pkgs)：
    - main_pkgs：排除 ``src/test/`` 路径的 java 文件顶层包（auto 作用域推导用）；
    - all_pkgs：全部改动 java 文件（含测试）顶层包（越界检测用）；
    - git 不可用/非 git 仓库/超时返回 (False, set(), set())，调用方回退 all 语义
      （保守方向，宁严勿松，不得静默降级为空作用域）。
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=mvn_dir, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, set(), set()
    if proc.returncode != 0:
        return False, set(), set()
    main_pkgs: set[str] = set()
    all_pkgs: set[str] = set()
    for line in proc.stdout.splitlines():
        rel = line.strip()
        if not rel.endswith(".java"):
            continue
        pkg = _top_level_package(Path(mvn_dir) / rel)
        if pkg is None:
            continue
        all_pkgs.add(pkg)
        # 排除测试路径（src/test/...）：统一加前导斜杠再匹配，兼容相对路径
        if "/src/test/" not in "/" + rel:
            main_pkgs.add(pkg)
    return True, main_pkgs, all_pkgs


def _locate_module(project: str) -> tuple[str | None, str]:
    """递归扫描 project 下深度 <= 2 的 pom.xml，返回 (module_relpath|None, status)。

    status ∈ ``unique`` | ``ambiguous`` | ``none``。
    深度 1 匹配 ``*/pom.xml``，深度 2 匹配 ``*/*/pom.xml``；路径任一段命中
    ``.git/node_modules/target/dist/build`` 的目录跳过。候选保持 glob 排序。
    """
    root = Path(project)
    candidates: list[str] = []
    if root.is_dir():
        for depth in (1, 2):
            pattern = "/".join(["*"] * depth + ["pom.xml"])
            for pom in sorted(root.glob(pattern)):
                parts = pom.relative_to(root).parts
                if any(part in _MODULE_SKIP_DIRS for part in parts[:-1]):
                    continue
                candidates.append(str(Path(*parts[:-1])))
    if len(candidates) == 1:
        return candidates[0], "unique"
    if len(candidates) >= 2:
        return None, "ambiguous"
    return None, "none"


def collect_environment(project: str, auto_locate: bool) -> dict:
    """环境收集（v0.6 4.1/9.2，三语言共享的唯一实现）。

    返回 ``{"degraded": bool, "located_module": str|None, "degraded_reason": str,
    "suggestion": str, "mvn_dir": str}``。

    语义（与文档 4.1 一致）：
    - 无 java/mvn（shutil.which）：degraded=True，degraded_reason="no java/mvn on PATH"；
    - 有 java+mvn 且根 pom.xml 存在：degraded=False，degraded_reason=""；
    - 有 java+mvn 且无根 pom：``_locate_module`` 定位
      - unique：不降级，located_module=模块相对路径，suggestion=完整重跑命令
        （``run_gate --project <module> --source ... --test-source ... --spec ...
        --feature-dir ... --config ...``）；mvn_dir：auto_locate 时=候选模块
        （CI 自动采用，mvn 可跑），否则=project（mvn 不跑，由 main 决定）；
      - ambiguous：不降级但 located_module=None，suggestion=多模块提示，
        main() 判为用法错误 exit 2（不产 gate 结果）；
      - none：degraded=True，degraded_reason="pom.xml not found at <project>"。
    """
    has_java = shutil.which("java") is not None
    has_mvn = shutil.which("mvn") is not None
    if not (has_java and has_mvn):
        return {
            "degraded": True,
            "located_module": None,
            "degraded_reason": "no java/mvn on PATH",
            "suggestion": "",
            "mvn_dir": project,
        }
    if (Path(project) / "pom.xml").is_file():
        return {
            "degraded": False,
            "located_module": None,
            "degraded_reason": "",
            "suggestion": "",
            "mvn_dir": project,
        }
    module, status = _locate_module(project)
    if status == "unique":
        assert module is not None, "unique 状态必有候选模块"
        return {
            "degraded": False,
            "located_module": module,
            "degraded_reason": "",
            "suggestion": (
                f"run_gate --project {module} --source ... --test-source ... "
                f"--spec ... --feature-dir ... --config ..."
            ),
            "mvn_dir": str(Path(project) / module) if auto_locate else project,
        }
    if status == "ambiguous":
        return {
            "degraded": False,
            "located_module": None,
            "degraded_reason": "",
            "suggestion": (
                "多模块候选：project 下存在多个 pom.xml 子模块，"
                "请用 --project 显式指定模块（可先 find . -name pom.xml -maxdepth 3）"
            ),
            "mvn_dir": project,
        }
    return {
        "degraded": True,
        "located_module": None,
        "degraded_reason": f"pom.xml not found at {project}",
        "suggestion": "",
        "mvn_dir": project,
    }


def _parse_affected_rules(impact_path: Path) -> dict[str, str]:
    """从 impact-report.md 解析逐规则 risk（rule -> high/medium/low）。

    容错：解析失败返回空 dict（不致 gate FAIL，仅跳过对抗硬判）。
    逐行扫描 "- rule: Rn" 与后续 "risk: level" 配对。
    """
    try:
        text = impact_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    rules: dict[str, str] = {}
    current_rule = None
    for line in text.splitlines():
        m = re.match(r'\s*-\s*rule:\s*(R\d+)', line)
        if m:
            current_rule = m.group(1)
            continue
        if current_rule:
            m = re.match(r'\s*risk:\s*(high|medium|low)', line)
            if m:
                rules[current_rule] = m.group(1)
                current_rule = None
    return rules


def _count_adversarial_tests(test_source: str) -> dict[str, int]:
    """扫描测试源码，统计每规则的对抗用例数（@DisplayName("Rn-对抗-...")）。"""
    counts: dict[str, int] = {}
    src = Path(test_source)
    if not src.is_dir():
        return counts
    for java_file in sorted(src.rglob("*.java")):
        try:
            text = java_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in ADVERSARIAL_RE.finditer(text):
            rule = "R" + m.group(1)
            counts[rule] = counts.get(rule, 0) + 1
    return counts

# 默认阈值（与 config/testing-config.template.yml 的 gate 段一致，配置缺失时兜底）
_DEFAULT_UNIT = {
    "line_coverage_min": 80,
    "branch_coverage_min": 70,
    "method_coverage_min": 80,
    "instruction_coverage_min": 85,
    "complexity_coverage_min": 70,
    "pass_rate_min": 100,
}
_DEFAULT_CONTRACT_PASS_RATE = 95
_DEFAULT_SPEC_RULE_COVERAGE_MIN = 100
_DEFAULT_REQUIRE_DISPLAYNAME_MATCH = True


# ── 配置与风险等级解析 ───────────────────────────────────────────────────────


def _load_config(path: Path) -> dict:
    """最小 YAML 子集解析（嵌套 map + 标量 int/bool/str）。

    只解析 testing-config.yml 用到的结构：两空格缩进的嵌套键值对 + 注释（#）。
    不依赖 PyYAML，保证 py/sh/ps 三语言执行环境一致。
    """
    cfg: dict = {}
    stack: list[tuple[int, dict]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return cfg
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        m = re.match(r"^(\S+?):\s*(.*)$", line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if val == "":
            node: dict = {}
            parent = stack[-1][1] if stack else None
            if parent is not None:
                parent[key] = node
            else:
                cfg[key] = node
            stack.append((indent, node))
        else:
            low = val.lower()
            if low == "true":
                v = True
            elif low == "false":
                v = False
            elif re.fullmatch(r"-?\d+", val):
                v = int(val)
            elif re.fullmatch(r"-?\d+\.\d+", val):
                v = float(val)
            else:
                v = val.strip('"\'')
            parent = stack[-1][1] if stack else None
            if parent is not None:
                parent[key] = v
            else:
                cfg[key] = v
    return cfg


def _parse_risk_level(impact_path: Path) -> str:
    """从 impact-report.md 提取整体 risk_level（high/medium/low），缺省 default。"""
    try:
        text = impact_path.read_text(encoding="utf-8")
    except OSError:
        return "default"
    m = re.search(r"risk_level\s*[:=]\s*(high|medium|low)", text)
    return m.group(1) if m else "default"


def _resolve_thresholds(cfg: dict, risk_level: str) -> dict:
    """合并 gate 默认阈值与 risk_overrides.<risk> 覆盖（覆盖值优先），返回生效阈值。"""
    gate = cfg.get("gate", {}) if isinstance(cfg.get("gate"), dict) else {}
    unit = gate.get("unit_test", {}) if isinstance(gate.get("unit_test"), dict) else {}
    contract = (
        gate.get("contract_test", {}) if isinstance(gate.get("contract_test"), dict) else {}
    )
    trace = (
        gate.get("spec_traceability", {})
        if isinstance(gate.get("spec_traceability"), dict)
        else {}
    )
    thr = {
        "line_coverage_min": unit.get("line_coverage_min", _DEFAULT_UNIT["line_coverage_min"]),
        "branch_coverage_min": unit.get("branch_coverage_min", _DEFAULT_UNIT["branch_coverage_min"]),
        "method_coverage_min": unit.get("method_coverage_min", _DEFAULT_UNIT["method_coverage_min"]),
        "instruction_coverage_min": unit.get(
            "instruction_coverage_min", _DEFAULT_UNIT["instruction_coverage_min"]
        ),
        "complexity_coverage_min": unit.get(
            "complexity_coverage_min", _DEFAULT_UNIT["complexity_coverage_min"]
        ),
        "unit_pass_rate_min": unit.get("pass_rate_min", _DEFAULT_UNIT["pass_rate_min"]),
        "contract_pass_rate_min": contract.get(
            "pass_rate_min", _DEFAULT_CONTRACT_PASS_RATE
        ),
        "spec_rule_coverage_min": trace.get(
            "spec_rule_coverage_min", _DEFAULT_SPEC_RULE_COVERAGE_MIN
        ),
        "require_displayname_match": trace.get(
            "require_displayname_match", _DEFAULT_REQUIRE_DISPLAYNAME_MATCH
        ),
    }
    overrides = cfg.get("risk_overrides", {})
    if isinstance(overrides, dict) and risk_level in overrides:
        ov = overrides[risk_level]
        if isinstance(ov, dict):
            ov_unit = ov.get("unit_test", {}) if isinstance(ov.get("unit_test"), dict) else {}
            ov_contract = (
                ov.get("contract_test", {}) if isinstance(ov.get("contract_test"), dict) else {}
            )
            key_map = {
                "line_coverage_min": "line_coverage_min",
                "branch_coverage_min": "branch_coverage_min",
                "method_coverage_min": "method_coverage_min",
                "instruction_coverage_min": "instruction_coverage_min",
                "complexity_coverage_min": "complexity_coverage_min",
                "pass_rate_min": "unit_pass_rate_min",
            }
            for k, dk in key_map.items():
                if k in ov_unit:
                    thr[dk] = ov_unit[k]
            if "pass_rate_min" in ov_contract:
                thr["contract_pass_rate_min"] = ov_contract["pass_rate_min"]
    return thr


def _parse_displayname_match(test_source: str, spec_coverage: dict) -> dict:
    """内联解析 test 源码 @DisplayName("Rn-...")，与 @Spec 已注解规则交叉对齐（双向）。

    正向（DisplayName->@Spec）：total = @DisplayName 中带规则编号的条数；
    aligned = 其中规则已出现在 @Spec annotated_rules 的条数；
    mismatch_count = total - aligned（测试指向不存在的 @Spec 规则）。
    反向（@Spec->DisplayName）：untested_spec_rules = 有 @Spec 注解但无任何
    @DisplayName 测试的规则（按 spec_rules 顺序，保证输出确定性）。
    """
    annotated = set((spec_coverage.get("annotated_rules") or {}).keys())
    spec_rules = spec_coverage.get("spec_rules") or []
    total = 0
    aligned = 0
    displayname_rules: set[str] = set()
    src = Path(test_source)
    if src.is_dir():
        for java_file in sorted(src.rglob("*.java")):
            try:
                text = java_file.read_text(encoding="utf-8")
            except OSError:
                continue
            for m in DISPLAYNAME_RE.finditer(text):
                rule = "R" + m.group(1)
                total += 1
                displayname_rules.add(rule)
                if rule in annotated:
                    aligned += 1
    untested_spec_rules = [
        r for r in spec_rules if r in annotated and r not in displayname_rules
    ]
    return {
        "aligned": aligned,
        "total": total,
        "mismatch_count": total - aligned,
        "untested_spec_rules": untested_spec_rules,
    }


# ── gate-result.md 渲染 ──────────────────────────────────────────────────────


def _format_gate_result_md(result: dict) -> str:
    """按 v0.4 5.4 格式生成 gate-result.md 内容（脚本直接写，AI 不能改判）。

    v0.6 增补：执行环境段补模块定位/建议（4.3），单测明细段补覆盖作用域行
    （6.3），末尾加漂移告警段（9.6，MEDIUM 不阻断）与 SOFT 状态行（5.1/9.3）。
    """
    status = result["status"]
    mode = result["mode"]
    mvn = result["mvn_clean_test"]
    risk = result["risk_level"]
    unit = result["unit_tests"]
    contract = result["contract_tests"]
    cov = result["coverage"]
    spec = result["spec_coverage"]
    disp = result["displayname_match"]
    thr = {t["metric"]: t["threshold"] for t in result["threshold_results"]}

    lines: list[str] = []
    lines.append(f"## Gate Result: {status}")
    lines.append("")
    lines.append("### 执行环境")
    lines.append(f"- mvn clean test: {mvn}")
    if mode == "degraded":
        lines.append("- 降级模式: 降级模式（无 java/mvn 或项目无 pom.xml 且无候选模块）")
        lines.append("- 说明: 无 java/mvn 或项目无 pom.xml 且无候选模块，跳过单测/契约测试执行，仅做 @Spec 静态扫描")
        lines.append(f"- 模块定位: 未找到（degraded_reason: {result.get('degraded_reason', '')}）")
    else:
        lines.append("- target 清理: 已清理（杜绝残留污染）")
        located = result.get("located_module") or "（根目录）"
        lines.append(f"- 模块定位: {located}")
    if result.get("suggestion"):
        lines.append(f"- 建议: {result['suggestion']}")
    lines.append("")
    lines.append("### 单测明细")
    lines.append(f"- 总数: {unit['total']} | 通过: {unit['passed']} | 失败: {unit['failed']}")
    lines.append(
        f"- 行覆盖率: {cov['line']}% (阈值 >= {thr.get('line_coverage', 0)}%)"
        f" | 分支: {cov['branch']}% | 方法: {cov['method']}%"
        f" | 指令: {cov['instruction']}% | 复杂度: {cov['complexity']}%"
    )
    lines.append(f"- 通过率: {unit['pass_rate']}% (阈值 >= {thr.get('unit_pass_rate', 0)}%)")
    lines.append(
        f"- 覆盖作用域: {result.get('coverage_scope', 'all')}"
        f" | 作用域内类: {result.get('scope_total', 0)}"
        f" | 达标: {result.get('scope_covered', 0)}"
        f" | 作用域外类: {result.get('scope_outside_total', 0)}"
    )
    lines.append("")
    lines.append("### 契约测试明细")
    lines.append(
        f"- 总数: {contract['total']} | 通过: {contract['passed']}"
        f" | 失败: {contract['failed']} | 通过率: {contract['pass_rate']}%"
    )
    lines.append("")
    lines.append("### Spec 规则覆盖矩阵")
    lines.append(
        f"- 规则总数: {len(spec.get('spec_rules', []))}"
        f" | 已注解数: {len(spec.get('annotated_rules', {}))}"
        f" | 未实现规则: {spec.get('unimplemented_rules', [])}"
        f" | 孤儿注解: {spec.get('orphan_annotations', [])}"
    )
    lines.append(f"- DisplayName 对齐数: {disp['aligned']} / {disp['total']}")
    if disp.get("untested_spec_rules"):
        lines.append(f"- 有 @Spec 无 @DisplayName 测试的规则: {disp['untested_spec_rules']}")
    lines.append("")
    lines.append("### 关键路径对抗覆盖")
    if result.get("mode") == "degraded":
        lines.append("- 未启用（降级模式，无 Java 环境跳过对抗校验）")
    else:
        adv = result["adversarial_coverage"]
        lines.append(f"- critical_path_required: {adv['critical_path_required']}")
        lines.append(f"- high 风险规则: {adv['high_risk_rules']}")
        lines.append(f"- 对抗用例分布: {adv['adversarial_counts']}")
        if adv["missing"]:
            lines.append(f"- 缺对抗用例的 high 风险规则: {adv['missing']}")
    lines.append("")
    # 漂移告警段（v0.6 9.6：UNSPEC_CODE，MEDIUM 不阻断）
    spec_cov = result.get("spec_coverage")
    spec_cov = spec_cov if isinstance(spec_cov, dict) else {}
    unspec = spec_cov.get("unspec_codes")
    if isinstance(unspec, list) and unspec:
        lines.append("### 漂移告警（MEDIUM，不阻断）")
        for item in unspec:
            lines.append(f"- {item}")
        lines.append("")
    # SOFT 状态行（v0.6 5.1/9.3：只读检查，缺段 WARN 不改判）
    # 注意：WARN 文案禁止包含完整 SOFT 标题行，避免脚本写出的文本被
    # 自身 re.search 命中（自满足 bug -> soft_missing 二次运行翻转）。
    if result.get("soft_missing"):
        lines.append("### SOFT 检查")
        lines.append(
            "- WARN: SOFT 交叉验证标题缺失（现有 gate-result.md 无 AI 手写"
            " 步骤 3 交叉验证段；不影响判定，请 AI 补段后重跑，仅补段不重跑 mvn）"
        )
        lines.append("")
    lines.append("### 判定依据")
    lines.append(f"- risk_level: {risk}")
    if risk in ("high", "medium", "low"):
        lines.append(f"- 套用阈值来源: testing-config.yml risk_overrides.{risk}")
    else:
        lines.append("- 套用阈值来源: testing-config.yml gate 默认阈值")
    if result["fail_reasons"]:
        lines.append("")
        lines.append("### 失败原因与修复建议（仅 FAIL 时）")
        for reason in result["fail_reasons"]:
            lines.append(f"- [FAIL] {reason}")
    lines.append("")
    return "\n".join(lines)


# ── 确定性核心（唯一实现，三语言共享） ─────────────────────────────────────


def run(inputs: dict) -> dict:
    """确定性核心：输入已收集的环境数据，返回完整判定 JSON，并按需写 gate-result.md。

    inputs 键：
      source / test_source / spec / project / feature_dir / config：路径
      check_only：bool，为 True 时不写 gate-result.md
      degraded：bool（环境收集时已判定）
      mvn_status：'SUCCESS' | 'FAIL' | 'SKIPPED'
      impact_ok：bool
      scan_stack / parse_results / scan_spec：子脚本输出 dict（或 None）
      v0.6 新增（bash/ps 透传，缺省有兜底值）：
        auto_locate / located_module / degraded_reason / suggestion / mvn_dir
        coverage_scope：'auto'（默认）| '<pkg,...>' | 'all'（默认取 config
          gate.coverage_scope，main() 已解析）
        baseline：baseline 快照文件路径（None 不启用；与 all 互斥，main() 已校验）
    """
    source = inputs.get("source", "")
    test_source = inputs.get("test_source", "")
    project = inputs.get("project", "")
    feature_dir = inputs.get("feature_dir", "")
    config_path = inputs.get("config", "")
    check_only = bool(inputs.get("check_only", False))
    degraded = bool(inputs.get("degraded", False))
    mvn_status = inputs.get("mvn_status", "SKIPPED")
    impact_ok = bool(inputs.get("impact_ok", False))
    scan_stack = inputs.get("scan_stack")
    parse_results = inputs.get("parse_results")
    scan_spec = inputs.get("scan_spec")
    mvn_dir = str(inputs.get("mvn_dir") or project)
    coverage_scope = str(inputs.get("coverage_scope") or "auto")
    baseline = inputs.get("baseline") or None
    located_module = inputs.get("located_module")
    degraded_reason = str(inputs.get("degraded_reason") or "")
    suggestion = str(inputs.get("suggestion") or "")

    # 覆盖率作用域统计默认值（degraded / all / 回退路径兜底）
    scope_desc = "N/A（降级模式）" if degraded else coverage_scope
    scope_total = 0
    scope_covered = 0
    scope_outside_total = 0

    fail_reasons: list[str] = []

    # 步骤 0：impact-report.md 存在性（堵 P0 #3：钩子链断裂）
    if not impact_ok:
        fail_reasons.append(
            "impact 未执行，请先运行 speckit.testing.impact"
            "（缺少 specs/<feature>/docs/impact-report.md）"
        )

    impact_path = Path(feature_dir) / "docs" / "impact-report.md"
    risk_level = _parse_risk_level(impact_path)
    cfg = _load_config(Path(config_path))
    thr = _resolve_thresholds(cfg, risk_level)

    # 步骤 4：@Spec 扫描（full 与 degraded 都执行）
    spec_coverage = scan_spec if isinstance(scan_spec, dict) else {}
    for rule in spec_coverage.get("unimplemented_rules", []):
        fail_reasons.append(f'unimplemented_rules: {rule} -> 在实现方法上补 @Spec(rule="{rule}")')
    for ann in spec_coverage.get("orphan_annotations", []):
        fail_reasons.append(
            f"orphan_annotations: {ann.get('rule', '?')} @ {ann.get('location', '?')}"
            " -> 修正规则编号或删除该注解"
        )

    # 空数据默认值（degraded 模式全为 0）
    unit_tests = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}
    contract_tests = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}
    coverage = {"line": 0, "branch": 0, "method": 0, "instruction": 0, "complexity": 0}
    displayname_match = {"aligned": 0, "total": 0, "mismatch_count": 0, "untested_spec_rules": []}

    if not degraded:
        # 步骤 1：mvn clean test
        if mvn_status == "FAIL":
            fail_reasons.append("mvn clean test 失败 -> 修复编译/测试错误后重新运行门禁")
        elif mvn_status == "SKIPPED":
            fail_reasons.append(
                "mvn clean test 未执行（SKIPPED）-> 多模块项目请用 --auto-locate"
                " 自动采用候选模块，或 --project <模块> 显式指定含 pom.xml 的模块后重跑"
            )

        # 步骤 3：报告存在性（不降级；缺失即 FAIL；v0.6 基于 mvn_dir 的 target/）
        surefire_dir = Path(mvn_dir) / "target" / "surefire-reports"
        jacoco_file = Path(mvn_dir) / "target" / "site" / "jacoco" / "jacoco.xml"
        if not (surefire_dir.is_dir() and any(surefire_dir.glob("*.xml"))):
            fail_reasons.append(
                "surefire-reports 缺失（未配置 maven-surefire-plugin?）"
                " -> 在 pom.xml 的 <plugins> 添加 maven-surefire-plugin 后重跑"
            )
        if not jacoco_file.is_file():
            fail_reasons.append(
                "jacoco.xml 缺失（未配置 jacoco-maven-plugin?）"
                " -> 在 pom.xml 的 <plugins> 添加 jacoco-maven-plugin"
                "（prepare-agent + report）后重跑"
            )

        # 步骤 2：技术栈硬校验
        if isinstance(scan_stack, dict):
            findings = scan_stack.get("forbidden_findings", [])
            if findings:
                detail = "; ".join(
                    f"{f.get('file', '?')}:{f.get('line', '?')} {f.get('type', '?')}"
                    for f in findings
                )
                fail_reasons.append(f"forbidden_findings: {len(findings)} 项 -> {detail}")

        # 填充 parse_test_results 数据
        if isinstance(parse_results, dict):
            unit_tests = parse_results.get("unit_tests") or unit_tests
            contract_tests = parse_results.get("contract_tests") or contract_tests
            pr_cov = parse_results.get("coverage") or {}
            coverage = {
                "line": pr_cov.get("line_coverage", 0),
                "branch": pr_cov.get("branch_coverage", 0),
                "method": pr_cov.get("method_coverage", 0),
                "instruction": pr_cov.get("instruction_coverage", 0),
                "complexity": pr_cov.get("complexity_coverage", 0),
            }

        # 步骤 5：@DisplayName 对齐（degraded 无单测可读，跳过）
        displayname_match = _parse_displayname_match(test_source, spec_coverage)
        if thr["require_displayname_match"]:
            if displayname_match["mismatch_count"] > 0:
                fail_reasons.append(
                    f"displayname_mismatch: {displayname_match['mismatch_count']}"
                    " 个 @DisplayName 未与 @Spec 规则对齐"
                )
            untested = displayname_match.get("untested_spec_rules", [])
            if untested:
                fail_reasons.append(
                    f"spec_rules_without_test: {len(untested)} 条规则有 @Spec"
                    f" 但无 @DisplayName 测试 -> {untested}"
                )

    # 步骤 5.5：关键路径对抗校验（v0.5 新增，configurable）
    adversarial_cfg = cfg.get("adversarial", {}) if isinstance(cfg.get("adversarial"), dict) else {}
    critical_path_required = bool(adversarial_cfg.get("critical_path_required", True))
    affected_rules = _parse_affected_rules(impact_path) if not degraded else {}
    adversarial_counts = _count_adversarial_tests(test_source) if not degraded else {}
    high_risk_rules = [r for r, risk in affected_rules.items() if risk == "high"]
    missing_adversarial = [r for r in high_risk_rules if adversarial_counts.get(r, 0) == 0]

    adversarial_coverage = {
        "critical_path_required": critical_path_required,
        "high_risk_rules": high_risk_rules,
        "adversarial_counts": adversarial_counts,
        "missing": missing_adversarial,
    }

    if critical_path_required and not degraded and missing_adversarial:
        fail_reasons.append(
            f"critical_path_adversarial: high 风险规则 {missing_adversarial}"
            " 无对抗用例（@DisplayName(\"Rn-对抗-...\")) -> 补对抗用例"
            " 或设 critical_path_required: false 降级"
        )

    # 步骤 7：阈值逐项比对
    threshold_results: list[dict] = []
    if degraded:
        # 降级模式仅校验 Spec 覆盖率阈值（v0.4 5.5）
        spec_actual = spec_coverage.get("coverage_percent", 0)
        spec_pass = spec_actual >= thr["spec_rule_coverage_min"]
        threshold_results.append({
            "metric": "spec_coverage",
            "actual": spec_actual,
            "threshold": thr["spec_rule_coverage_min"],
            "pass": spec_pass,
        })
        if not spec_pass:
            fail_reasons.append(
                f"spec_coverage {spec_actual}% < {thr['spec_rule_coverage_min']}%"
                " -> 补齐 @Spec 注解"
            )
    else:
        # ── v0.6 9.4：覆盖率作用域解析（auto | <pkg,...> | all）──
        # 原则：作用域管阈值不管执行（全量 mvn clean test 永远跑）；非 all 时
        # 按作用域内 class 逐类判定，作用域外类只统计（INFO）不 FAIL。
        scope_mode = "all"
        scope_pkgs: set[str] = set()
        scope_desc = "all"
        has_git = False
        main_pkgs: set[str] = set()
        all_pkgs: set[str] = set()
        if coverage_scope != "all":
            has_git, main_pkgs, all_pkgs = _git_diff_packages(mvn_dir)
        if coverage_scope == "auto":
            if not has_git:
                scope_mode = "all"  # 无 git/失败 -> 回退全量（保守，宁严勿松）
                scope_desc = "all（auto 无 git，回退全量）"
            else:
                scope_mode = "auto"
                scope_pkgs = main_pkgs
        elif coverage_scope == "all":
            scope_mode = "all"
        else:
            scope_mode = "explicit"
            scope_pkgs = {p.strip() for p in coverage_scope.split(",") if p.strip()}
        # 越界检测（声明即承诺）：git diff 的 java 文件顶层包不在作用域内 -> FAIL
        if scope_mode in ("auto", "explicit") and scope_pkgs and has_git:
            outside = all_pkgs - scope_pkgs
            if outside:
                fail_reasons.append(
                    "coverage scope 越界: git diff 的 Java 文件顶层包 "
                    + ", ".join(sorted(outside))
                    + " 不在作用域内（声明即承诺）-> 补充作用域后重跑"
                )
        # 空作用域 -> FAIL（无法承诺任何改动被覆盖）
        if scope_mode in ("auto", "explicit") and not scope_pkgs:
            fail_reasons.append("coverage scope 为空：git diff 无 Java 改动文件")
        if scope_mode == "auto":
            scope_desc = "auto（git diff: " + (", ".join(sorted(scope_pkgs)) or "空") + "）"
        elif scope_mode == "explicit":
            scope_desc = ", ".join(sorted(scope_pkgs)) if scope_pkgs else coverage_scope

        classes = parse_results.get("classes") if isinstance(parse_results, dict) else None
        if not isinstance(classes, list):
            classes = None

        if scope_mode == "all" or classes is None:
            # 全量聚合判定（all 语义，或 parse_results 无 classes 字段时回退）
            metrics = [
                ("line_coverage", coverage["line"], thr["line_coverage_min"]),
                ("branch_coverage", coverage["branch"], thr["branch_coverage_min"]),
                ("method_coverage", coverage["method"], thr["method_coverage_min"]),
                ("instruction_coverage", coverage["instruction"], thr["instruction_coverage_min"]),
                ("complexity_coverage", coverage["complexity"], thr["complexity_coverage_min"]),
                ("unit_pass_rate", unit_tests["pass_rate"], thr["unit_pass_rate_min"]),
                ("contract_pass_rate", contract_tests["pass_rate"], thr["contract_pass_rate_min"]),
            ]
            for metric, actual, threshold in metrics:
                ok = actual >= threshold
                threshold_results.append({
                    "metric": metric, "actual": actual, "threshold": threshold, "pass": ok,
                })
                if not ok:
                    fail_reasons.append(f"{metric} {actual}% < {threshold}% ({risk_level})")
        else:
            # 作用域判定：作用域内类逐个按 5 项覆盖率阈值判定 FAIL；
            # 作用域外类只统计（scope_outside_total）不 FAIL。
            for metric, actual, threshold in [
                ("unit_pass_rate", unit_tests["pass_rate"], thr["unit_pass_rate_min"]),
                ("contract_pass_rate", contract_tests["pass_rate"], thr["contract_pass_rate_min"]),
            ]:
                ok = actual >= threshold
                threshold_results.append({
                    "metric": metric, "actual": actual, "threshold": threshold, "pass": ok,
                })
                if not ok:
                    fail_reasons.append(f"{metric} {actual}% < {threshold}% ({risk_level})")
            # jacoco.xml 的 package name 用 "/" 分隔（com/example），作用域用 "."
            # （com.example），先归一化再匹配——否则真实 jacoco 数据永远匹配不上
            # （作用域内类恒为空 -> 判定空转，bug 修复：9.4）。
            scope_classes = [
                c for c in classes
                if (c.get("package") or "").replace("/", ".") in scope_pkgs
            ]
            outside_classes = [
                c for c in classes
                if (c.get("package") or "").replace("/", ".") not in scope_pkgs
            ]
            scope_total = len(scope_classes)
            scope_outside_total = len(outside_classes)
            scope_covered = 0
            # baseline 加载（--baseline <file>，未启用时为空 dict）
            baseline_data: dict = {}
            baseline_first_run = False
            if baseline is not None:
                bp = Path(baseline)
                if bp.is_file():
                    try:
                        loaded = json.loads(bp.read_text(encoding="utf-8"))
                        if isinstance(loaded, dict):
                            baseline_data = loaded
                    except (OSError, json.JSONDecodeError):
                        baseline_data = {}
                else:
                    baseline_first_run = True
            metric_fail: dict[str, bool] = {m: False for m in _METRIC_THRESHOLD_MAP}
            for c in scope_classes:
                cname = c.get("name", "?")
                base = baseline_data.get(cname) if baseline_data else None
                class_ok = True
                if base is not None:
                    # baseline 模式：绝对值不判，只查增量退化（当前 < baseline - 5.0）
                    for metric in _METRIC_THRESHOLD_MAP:
                        cur = c.get(metric)
                        bval = base.get(metric)
                        if cur is None or bval is None:
                            continue  # 缺失指标跳过
                        if cur < bval - 5.0:
                            fail_reasons.append(
                                f"baseline 退化: {cname} {metric}"
                                f" ({cur}% < baseline {bval}% - 5%)"
                            )
                            class_ok = False
                            metric_fail[metric] = True
                elif baseline is None:
                    # 绝对值阈值判定（baseline 启用时绝对值不判）
                    for metric, key in _METRIC_THRESHOLD_MAP.items():
                        cur = c.get(metric)
                        if cur is None:
                            continue  # 缺失指标跳过
                        if cur < thr[key]:
                            fail_reasons.append(
                                f"{cname} {metric} {cur}% < {thr[key]}% (作用域内)"
                            )
                            class_ok = False
                            metric_fail[metric] = True
                if class_ok:
                    scope_covered += 1
            # baseline 首次运行：写当前作用域内 class 覆盖率快照
            if baseline_first_run:
                assert baseline is not None, "首次运行必有 baseline 路径"
                snap: dict[str, dict] = {}
                for c in scope_classes:
                    cname = c.get("name", "?")
                    entry = {
                        m: c.get(m) for m in _METRIC_THRESHOLD_MAP if c.get(m) is not None
                    }
                    if entry:
                        snap[cname] = entry
                bp = Path(baseline)
                bp.parent.mkdir(parents=True, exist_ok=True)
                bp.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
            # threshold_results 补 coverage 5 项（聚合值展示 + 作用域判定结果汇总）
            for metric, key in _METRIC_THRESHOLD_MAP.items():
                threshold_results.append({
                    "metric": metric,
                    "actual": coverage[_COVERAGE_KEY_MAP[metric]],
                    "threshold": thr[key],
                    "pass": (not metric_fail[metric]) and scope_total > 0,
                })
        # spec 覆盖率判定（full 模式共用，作用域不作用于 spec 判定）
        spec_actual = spec_coverage.get("coverage_percent", 0)
        spec_pass = spec_actual >= thr["spec_rule_coverage_min"]
        threshold_results.append({
            "metric": "spec_coverage",
            "actual": spec_actual,
            "threshold": thr["spec_rule_coverage_min"],
            "pass": spec_pass,
        })
        if not spec_pass:
            fail_reasons.append(
                f"spec_coverage {spec_actual}% < {thr['spec_rule_coverage_min']}%"
                " -> 补齐 @Spec 注解"
            )

    status = "FAIL" if fail_reasons else "PASS"

    # v0.6 9.6：UNSPEC_CODE 漂移告警（scan_spec 的 MEDIUM 告警，不参与判定）
    unspec_codes: list = []
    if isinstance(scan_spec, dict):
        raw = scan_spec.get("unspec_codes")
        if isinstance(raw, list):
            unspec_codes = raw

    # ── v0.6 5.1/9.3：SOFT 段只读检查（判定完成后、写 gate-result.md 前）──
    # 只读正则检查现有 gate-result.md 是否含 AI 交叉验证标题；缺失 -> WARN +
    # soft_missing=true（不加入 fail_reasons，不改判——脚本不代写 SOFT 段）。
    # 正则锚定行首（MULTILINE）：只认独立标题行，杜绝脚本 WARN 文案自命中
    # （脚本写出的文本不含完整标题行 -> 同 fixture 二次运行 soft_missing 稳定）。
    soft_missing = True
    gate_result_path = Path(feature_dir) / "docs" / "gate-result.md"
    try:
        existing_md = gate_result_path.read_text(encoding="utf-8")
    except OSError:
        existing_md = ""
    if re.search(r"^##\s+AI 交叉验证（SOFT，不影响判定）\s*$", existing_md, re.MULTILINE):
        soft_missing = False
    if soft_missing:
        print(
            "WARN: gate-result.md 缺少 AI 手写 SOFT 交叉验证段"
            "（soft_missing=true，不参与判定）",
            file=sys.stderr,
        )

    result = {
        "status": status,
        "mode": "degraded" if degraded else "full",
        "gate_result_path": str(gate_result_path),
        "risk_level": risk_level,
        "mvn_clean_test": mvn_status,
        "unit_tests": unit_tests,
        "contract_tests": contract_tests,
        "coverage": coverage,
        "spec_coverage": spec_coverage,
        "displayname_match": displayname_match,
        "adversarial_coverage": adversarial_coverage,
        "threshold_results": threshold_results,
        "fail_reasons": fail_reasons,
        # v0.6 新增字段
        "degraded_reason": degraded_reason,
        "suggestion": suggestion,
        "located_module": located_module,
        "soft_missing": soft_missing,
        "coverage_scope": scope_desc,
        "scope_total": scope_total,
        "scope_covered": scope_covered,
        "scope_outside_total": scope_outside_total,
        "unspec_codes_count": len(unspec_codes),
        "baseline_file": baseline or "",
        "mvn_dir": mvn_dir,
    }

    # 步骤 8：脚本直接写 gate-result.md（--check-only 不写）
    if not check_only:
        out_dir = Path(feature_dir) / "docs"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "gate-result.md").write_text(
            _format_gate_result_md(result), encoding="utf-8"
        )

    return result


# ── 子脚本调用 ───────────────────────────────────────────────────────────────


def _call_script(script: Path, args: list[str]) -> dict | None:
    """调用子脚本（复用其解析逻辑，避免契约漂移），返回解析后的 JSON dict。"""
    try:
        proc = subprocess.run(
            [sys.executable, str(script)] + args,
            capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="门禁编排脚本 run_gate：全确定性逻辑下沉脚本，AI 仅读判定 JSON。"
    )
    parser.add_argument("--source", required=True, help="Java 业务源码根目录")
    parser.add_argument("--test-source", required=True, help="测试源码根目录")
    parser.add_argument("--spec", required=True, help="spec.md 路径")
    parser.add_argument("--project", required=True, help="项目根目录（执行 mvn / 找 target 报告）")
    parser.add_argument("--feature-dir", required=True, help="feature 目录（如 specs/001-bank-transfer）")
    parser.add_argument("--config", required=True, help="testing-config.yml 路径")
    parser.add_argument("--check-only", action="store_true", help="只跑步骤 1-7，不写 gate-result.md")
    parser.add_argument("--auto-locate", action="store_true", help="v0.6 9.2：唯一候选模块自动采用（CI 用）")
    parser.add_argument(
        "--coverage-scope",
        default=None,
        help="v0.6 9.4：覆盖率判定作用域 auto | <pkg,...> | all（默认取 config gate.coverage_scope，再缺省 auto）",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="v0.6 9.4：baseline 快照文件（作用域内类覆盖率增量退化判定；与 coverage_scope=all 互斥）",
    )
    parser.add_argument("--json", action="store_true", help="输出判定 JSON 到 stdout（固定开启）")
    args = parser.parse_args()

    feature_dir = Path(args.feature_dir)
    impact_ok = (feature_dir / "docs" / "impact-report.md").is_file()

    # 配置读取：coverage_scope 默认值 + scan 排除模式
    cfg = _load_config(Path(args.config))
    gate_cfg = cfg.get("gate", {}) if isinstance(cfg.get("gate"), dict) else {}
    coverage_scope = args.coverage_scope or gate_cfg.get("coverage_scope") or "auto"
    baseline = args.baseline or gate_cfg.get("baseline_file") or None
    # 互斥校验（文档 6.4）：--baseline 与 coverage_scope=all 不能同时启用
    if baseline and coverage_scope == "all":
        print(
            "错误: --baseline 与 coverage_scope=all 互斥（文档 6.4：all 已全量，"
            "无需 baseline 增量判定）",
            file=sys.stderr,
        )
        return 2

    # v0.6 4.1/9.2：环境收集（模块定位替代旧降级判定）——三语言共享的唯一实现
    env = collect_environment(args.project, args.auto_locate)
    degraded = env["degraded"]
    mvn_dir = env["mvn_dir"]
    root_has_pom = (Path(args.project) / "pom.xml").is_file()
    if not degraded and not root_has_pom and env["located_module"] is None:
        # ambiguous：多候选 -> 用法错误（exit 2），不产 gate 结果
        print(env["suggestion"], file=sys.stderr)
        return 2

    mvn_status = "SKIPPED"
    scan_stack = None
    parse_results = None
    scripts_dir = Path(__file__).resolve().parent

    # 步骤 1：mvn clean test（强制 clean；v0.6 仅在 root 有 pom 或 auto-locate
    # 唯一候选时执行，cwd=mvn_dir；其余非降级路径 mvn_status 保持 SKIPPED）
    run_mvn = not degraded and (
        root_has_pom or (args.auto_locate and env["located_module"] is not None)
    )
    if run_mvn:
        try:
            proc = subprocess.run(
                ["mvn", "clean", "test"],
                cwd=mvn_dir,
                capture_output=True, text=True, timeout=1800,
            )
            mvn_status = "SUCCESS" if proc.returncode == 0 else "FAIL"
        except (OSError, subprocess.TimeoutExpired):
            mvn_status = "FAIL"

    # 步骤 2/3：技术栈 + 测试结果（报告路径基于 mvn_dir 的 target/）
    if not degraded:
        scan_stack = _call_script(
            scripts_dir / "scan_test_stack.py",
            ["--source", args.test_source, "--json"],
        )
        surefire = str(Path(mvn_dir) / "target" / "surefire-reports")
        jacoco = str(Path(mvn_dir) / "target" / "site" / "jacoco" / "jacoco.xml")
        parse_results = _call_script(
            scripts_dir / "parse_test_results.py",
            ["--surefire", surefire, "--jacoco", jacoco, "--json"],
        )

    # 步骤 4：@Spec 扫描（full 与 degraded 都执行；v0.6 9.6 透传 test-source 与
    # scan.unspec_exclude_patterns 额外排除模式）
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
    exclude_arg = ",".join(patterns)
    scan_spec_args = [
        "--source", args.source,
        "--spec", args.spec,
        "--test-source", args.test_source,
        "--json",
    ]
    if exclude_arg:
        scan_spec_args += ["--exclude-patterns", exclude_arg]
    scan_spec = _call_script(scripts_dir / "scan_spec_annotations.py", scan_spec_args)

    inputs = {
        "source": args.source,
        "test_source": args.test_source,
        "spec": args.spec,
        "project": args.project,
        "feature_dir": args.feature_dir,
        "config": args.config,
        "check_only": args.check_only,
        "degraded": degraded,
        "mvn_status": mvn_status,
        "impact_ok": impact_ok,
        "scan_stack": scan_stack,
        "parse_results": parse_results,
        "scan_spec": scan_spec,
        # v0.6 新增
        "auto_locate": args.auto_locate,
        "coverage_scope": coverage_scope,
        "baseline": baseline,
        "located_module": env["located_module"],
        "degraded_reason": env["degraded_reason"],
        "suggestion": env["suggestion"],
        "mvn_dir": mvn_dir,
    }
    result = run(inputs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
