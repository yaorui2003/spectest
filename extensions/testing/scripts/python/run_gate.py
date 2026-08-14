#!/usr/bin/env python3
"""门禁编排脚本 run_gate（Python 版）。

v0.4 核心改造：把 ``speckit.testing.gate`` 门禁的全部确定性逻辑下沉到脚本，
AI 仅读 stdout 判定 JSON，**不能改判、不能补写 gate-result.md、不能跳过步骤**
（直击试点 P0 #1：Agent 伪造覆盖率）。

职责（v0.4 第五章 5.2 的 9 步）:

0. 检查 ``specs/<feature>/docs/impact-report.md`` 存在（不存在 -> FAIL，堵 P0 #3）
1. ``mvn clean test``（强制 clean，杜绝 target 残留污染，堵 P0 #2）
2. 调 ``scan_test_stack``（forbidden_findings 非空 -> FAIL）
3. 调 ``parse_test_results``（jacoco.xml/surefire-reports 缺失 -> FAIL，不降级）
4. 调 ``scan_spec_annotations``（unimplemented_rules/orphan_annotations 非空 -> FAIL）
5. 内联解析 test 源码 ``@DisplayName("Rn-...")`` 算对齐数
6. 读 ``impact-report.md`` 的 ``risk_level`` + 读 ``testing-config.yml`` 套风险档阈值
7. 逐项比对覆盖率/通过率/Spec 覆盖率与阈值
8. **脚本直接写 ``specs/<feature>/docs/gate-result.md``** + stdout 输出判定 JSON

降级模式（v0.4 5.5）：检测无 ``java``/``mvn`` 可执行，**或项目非 Maven（根目录无
``pom.xml``，即非 Java 项目）**时，降级为仅做 ``@Spec`` 静态扫描（步骤 4 + 6 的
Spec 覆盖率阈值判定），跳过步骤 1-3/5。降级时 gate-result.md 明确标注
"降级模式（无 Java 环境）"。这是唯一降级场景；Java 项目缺 JaCoCo/surefire
报告**不降级，直接 FAIL**。

``--check-only`` 子模式：供 implement 第 4.5 阶段（对抗测试）调用，只跑步骤 1-7
不写 gate-result.md，输出当前覆盖率与阈值差距 JSON，供 AI 决定补测方向。

用法::

    python run_gate.py --source <java_dir> --test-source <test_dir> --spec <spec.md> \
        --project <root> --feature-dir <specs/<feature>> --config <testing-config.yml> \
        [--check-only] --json

三语言（py/sh/ps）等价：本脚本的 ``run()`` 是**唯一确定性核心**（阈值比对 + 判定
+ 写 gate-result.md + JSON 序列化）；bash/PowerShell 版本负责环境编排（java/mvn
检测、mvn clean test、调用各自语言子脚本收集数据）后，通过 ``python3 -c`` 导入本
模块调用 ``run()``，输出与 Python 版字节级等价（复用 ``json.dumps(result,
ensure_ascii=False, indent=2)`` 格式）。
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
    """按 v0.4 5.4 格式生成 gate-result.md 内容（脚本直接写，AI 不能改判）。"""
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
        lines.append("- 降级模式: 降级模式（无 Java 环境）")
        lines.append("- 说明: 未检测到 java/mvn 或项目无 pom.xml，跳过单测/契约测试执行，仅做 @Spec 静态扫描")
    else:
        lines.append("- target 清理: 已清理（杜绝残留污染）")
    lines.append("")
    lines.append("### 单测明细")
    lines.append(f"- 总数: {unit['total']} | 通过: {unit['passed']} | 失败: {unit['failed']}")
    lines.append(
        f"- 行覆盖率: {cov['line']}% (阈值 >= {thr.get('line_coverage', 0)}%)"
        f" | 分支: {cov['branch']}% | 方法: {cov['method']}%"
        f" | 指令: {cov['instruction']}% | 复杂度: {cov['complexity']}%"
    )
    lines.append(f"- 通过率: {unit['pass_rate']}% (阈值 >= {thr.get('unit_pass_rate', 0)}%)")
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

        # 步骤 3：报告存在性（不降级；缺失即 FAIL）
        surefire_dir = Path(project) / "target" / "surefire-reports"
        jacoco_file = Path(project) / "target" / "site" / "jacoco" / "jacoco.xml"
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

    result = {
        "status": status,
        "mode": "degraded" if degraded else "full",
        "gate_result_path": str(Path(feature_dir) / "docs" / "gate-result.md"),
        "risk_level": risk_level,
        "mvn_clean_test": mvn_status,
        "unit_tests": unit_tests,
        "contract_tests": contract_tests,
        "coverage": coverage,
        "spec_coverage": spec_coverage,
        "displayname_match": displayname_match,
        "threshold_results": threshold_results,
        "fail_reasons": fail_reasons,
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
    parser.add_argument("--json", action="store_true", help="输出判定 JSON 到 stdout（固定开启）")
    args = parser.parse_args()

    feature_dir = Path(args.feature_dir)
    impact_ok = (feature_dir / "docs" / "impact-report.md").is_file()

    # 降级检测：无 java/mvn 可执行，或项目非 Maven（根目录无 pom.xml）
    has_java = shutil.which("java") is not None
    has_mvn = shutil.which("mvn") is not None
    has_pom = (Path(args.project) / "pom.xml").is_file()
    degraded = not (has_java and has_mvn and has_pom)

    mvn_status = "SKIPPED"
    scan_stack = None
    parse_results = None
    scripts_dir = Path(__file__).resolve().parent

    if not degraded:
        # 步骤 1：mvn clean test（强制 clean，杜绝 target 残留污染）
        try:
            proc = subprocess.run(
                ["mvn", "clean", "test"],
                cwd=args.project,
                capture_output=True, text=True, timeout=1800,
            )
            mvn_status = "SUCCESS" if proc.returncode == 0 else "FAIL"
        except (OSError, subprocess.TimeoutExpired):
            mvn_status = "FAIL"

        # 步骤 2/3：技术栈 + 测试结果
        scan_stack = _call_script(
            scripts_dir / "scan_test_stack.py",
            ["--source", args.test_source, "--json"],
        )
        surefire = str(Path(args.project) / "target" / "surefire-reports")
        jacoco = str(Path(args.project) / "target" / "site" / "jacoco" / "jacoco.xml")
        parse_results = _call_script(
            scripts_dir / "parse_test_results.py",
            ["--surefire", surefire, "--jacoco", jacoco, "--json"],
        )

    # 步骤 4：@Spec 扫描（full 与 degraded 都执行）
    scan_spec = _call_script(
        scripts_dir / "scan_spec_annotations.py",
        ["--source", args.source, "--spec", args.spec, "--json"],
    )

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
    }
    result = run(inputs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
