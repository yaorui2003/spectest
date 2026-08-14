"""run_gate 门禁编排脚本输出契约测试（v0.4 新增）。

用 subprocess 调用 ``run_gate.py``（降级模式：fixture 无 pom.xml，且环境可能
无 java/mvn），喂入 tmp 样本工程，断言 stdout 判定 JSON 契约与 gate-result.md
写出行为：

- (a) 脚本存在且 ``--json`` 输出合法 JSON（含全部契约字段）
- (b) 降级模式（fixture 无 pom.xml）：status PASS / mode=degraded /
  risk_level=high / mvn_clean_test=SKIPPED / spec_coverage 100% / gate-result.md
  写出且标注"降级模式（无 Java 环境）"
- (c) FAIL 场景：删 @Spec -> unimplemented_rules 非空 -> FAIL（exit 1）
- (d) FAIL 场景：加孤儿注解（rule=R9）-> orphan_annotations 非空 -> FAIL
- (e) FAIL 场景：impact-report.md 缺失 -> "impact 未执行"（堵 P0 #3）
- (f) ``--check-only`` 不写 gate-result.md
- (g) 确定性核心 ``run()`` 直接单测：full 模式阈值比对（high 档阈值套用）+
  mvn 失败 + surefire/jacoco 报告缺失 + gate-result.md 内容格式
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# 仓库根：tests/extensions/test_run_gate.py -> parents[2] = spec-kit/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PY_SCRIPT = (
    PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python" / "run_gate.py"
)

# 规则 -> 实现方法名 / 描述（样本工程用，与 test_scan_spec_annotations.py 一致）
RULE_TO_METHOD = {
    "R1": "transfer",
    "R2": "checkBalance",
    "R3": "isFrozen",
    "R4": "withinLimit",
    "R5": "logAudit",
    "R6": "commit",
    "R7": "checkSelfTransfer",
}
RULE_TO_DESC = {
    "R1": "金额校验",
    "R2": "余额校验",
    "R3": "冻结校验",
    "R4": "额度上限",
    "R5": "审计日志",
    "R6": "原子操作",
    "R7": "自转账校验",
}
ALL_RULES = ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]

SPEC_MD = """\
# Transfer

## Business Rules

- R1: 转账金额必须大于0
- R2: 转账账户必须有足够余额
- R3: 不可向冻结账户转账
- R4: 单笔转账不超过10万
- R5: 转账需记录审计日志
- R6: 转账为原子操作
- R7: 不可自转账

## API

POST /api/v1/accounts/transfer
"""

IMPACT_REPORT_MD = """\
## ImpactReport

### 影响范围
- com.example.AccountService.transfer (R1, R6, R7)

### 风险等级
risk_level: high

### 受影响规则编号清单
affected_rules:
  - rule: R1
    change_type: modified
    risk: high

### 建议测试策略
strategy: full
"""

TESTING_CONFIG_YML = """\
# Speckit Testing 扩展配置
gate:
  unit_test:
    line_coverage_min: 80
    branch_coverage_min: 70
    method_coverage_min: 80
    instruction_coverage_min: 85
    complexity_coverage_min: 70
    pass_rate_min: 100
  contract_test:
    pass_rate_min: 95
  spec_traceability:
    spec_rule_coverage_min: 100
    require_displayname_match: true

test_stack:
  forbid_powermock: true
  forbid_springboottest: true

risk_overrides:
  high:
    unit_test:
      line_coverage_min: 90
      method_coverage_min: 90
      instruction_coverage_min: 90
      complexity_coverage_min: 80
      pass_rate_min: 100
    contract_test:
      pass_rate_min: 100
  medium:
    unit_test:
      line_coverage_min: 80
      method_coverage_min: 80
      instruction_coverage_min: 85
      complexity_coverage_min: 70
  low:
    unit_test:
      line_coverage_min: 70
      method_coverage_min: 70
      instruction_coverage_min: 80
      complexity_coverage_min: 60
"""

SUREFIRE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.AccountServiceTest" tests="7" failures="0" errors="0">
  <testcase name="shouldRejectZeroAmount" classname="com.example.AccountServiceTest"/>
</testsuite>
"""

JACOCO_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<report>
  <counter type="LINE" missed="5" covered="95"/>
  <counter type="BRANCH" missed="10" covered="80"/>
  <counter type="METHOD" missed="2" covered="20"/>
  <counter type="INSTRUCTION" missed="10" covered="90"/>
  <counter type="COMPLEXITY" missed="3" covered="17"/>
</report>
"""


# ── 样本 Java 生成 ──────────────────────────────────────────────────────────


def _make_java_source(rules: list[str]) -> str:
    """生成样本 Java 源码，为给定规则列表各放一个 @Spec 方法级注解。"""
    lines = [
        "package com.example;",
        "",
        "import java.math.BigDecimal;",
        "import com.speckit.testing.Spec;",
        "",
        "@org.springframework.stereotype.Service",
        "public class AccountService {",
        "",
    ]
    for rule in rules:
        method = RULE_TO_METHOD[rule]
        desc = RULE_TO_DESC[rule]
        lines.append(
            f'    @Spec(capability = "transfer", rule = "{rule}", description = "{desc}")'
        )
        lines.append(f"    public void {method}() {{")
        lines.append("    }")
        lines.append("")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _make_test_java(rules: list[str]) -> str:
    """生成样本测试源码：每条规则一个 @DisplayName("Rn-<描述>") 标注。"""
    lines = [
        "package com.example;",
        "",
        "import org.junit.jupiter.api.Test;",
        "import org.junit.jupiter.api.DisplayName;",
        "",
        "class AccountServiceTest {",
        "",
    ]
    for rule in rules:
        desc = RULE_TO_DESC[rule]
        lines.append("    @Test")
        lines.append(f'    @DisplayName("{rule}-{desc}")')
        lines.append(f"    void test{rule}() {{")
        lines.append("    }")
        lines.append("")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ── fixture 工厂 ────────────────────────────────────────────────────────────


@pytest.fixture
def gate_fixture(tmp_path: Path) -> dict:
    """创建完整 fixture（无 pom.xml -> 降级模式）。

    目录：spec.md + src(@Spec) + test-src(@DisplayName) +
    specs/001-bank-transfer/docs/impact-report.md + testing-config.yml。
    """
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(SPEC_MD, encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "AccountService.java").write_text(
        _make_java_source(ALL_RULES), encoding="utf-8"
    )

    test_dir = tmp_path / "test-src"
    test_dir.mkdir()
    (test_dir / "AccountServiceTest.java").write_text(
        _make_test_java(ALL_RULES), encoding="utf-8"
    )

    feature_dir = tmp_path / "specs" / "001-bank-transfer"
    docs_dir = feature_dir / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "impact-report.md").write_text(IMPACT_REPORT_MD, encoding="utf-8")

    config_path = tmp_path / "testing-config.yml"
    config_path.write_text(TESTING_CONFIG_YML, encoding="utf-8")

    return {
        "tmp_path": tmp_path,
        "spec": spec_path,
        "src": src_dir,
        "test_src": test_dir,
        "feature_dir": feature_dir,
        "docs_dir": docs_dir,
        "config": config_path,
    }


# ── 脚本执行辅助 ────────────────────────────────────────────────────────────


def _run_py(args: list[str]) -> tuple[int, str, str]:
    """调用 run_gate.py，返回 (returncode, stdout, stderr)。"""
    result = subprocess.run(
        [sys.executable, str(PY_SCRIPT)] + args,
        capture_output=True, text=True, timeout=60,
    )
    return result.returncode, result.stdout, result.stderr


def _run_gate(fx: dict, *extra: str) -> tuple[int, dict]:
    """用 fixture 调用 run_gate（降级模式），返回 (returncode, 解析后 JSON)。"""
    rc, stdout, stderr = _run_py([
        "--source", str(fx["src"]),
        "--test-source", str(fx["test_src"]),
        "--spec", str(fx["spec"]),
        "--project", str(fx["tmp_path"]),
        "--feature-dir", str(fx["feature_dir"]),
        "--config", str(fx["config"]),
        "--json",
        *extra,
    ])
    data = json.loads(stdout)
    return rc, data


def _load_run_gate_module():
    """用 importlib 加载 run_gate.py（直接单测确定性核心 run()）。"""
    spec = importlib.util.spec_from_file_location("_run_gate_under_test", PY_SCRIPT)
    assert spec is not None and spec.loader is not None, "无法加载 run_gate.py"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 用例 (a): 脚本存在 + JSON 合法 ───────────────────────────────────────


def test_script_exists():
    assert PY_SCRIPT.is_file(), f"missing run_gate.py: {PY_SCRIPT}"


def test_json_output_has_all_contract_fields(gate_fixture):
    """stdout 输出合法 JSON，含全部契约字段。"""
    rc, data = _run_gate(gate_fixture)
    assert rc == 0
    for field in [
        "status", "mode", "gate_result_path", "risk_level", "mvn_clean_test",
        "unit_tests", "contract_tests", "coverage", "spec_coverage",
        "displayname_match", "threshold_results", "fail_reasons",
    ]:
        assert field in data, f"缺少契约字段: {field}"


# ── 用例 (b): 降级模式 PASS ─────────────────────────────────────────────


def test_degraded_mode_pass(gate_fixture):
    """降级模式（无 pom.xml）：@Spec 全覆盖 -> status PASS，gate-result.md 写出。"""
    rc, data = _run_gate(gate_fixture)
    assert rc == 0, f"PASS 场景应退出码 0, fail_reasons={data['fail_reasons']}"
    assert data["status"] == "PASS"
    assert data["mode"] == "degraded"
    assert data["risk_level"] == "high"
    assert data["mvn_clean_test"] == "SKIPPED"
    assert data["spec_coverage"]["coverage_percent"] == 100
    assert data["spec_coverage"]["unimplemented_rules"] == []
    assert data["spec_coverage"]["orphan_annotations"] == []
    # 降级模式仅校验 Spec 覆盖率阈值
    assert [t["metric"] for t in data["threshold_results"]] == ["spec_coverage"]
    assert data["threshold_results"][0]["pass"] is True
    assert data["fail_reasons"] == []

    # gate-result.md 由脚本写出，且明确标注降级模式
    gate_result = gate_fixture["docs_dir"] / "gate-result.md"
    assert gate_result.is_file(), "run_gate 应写出 gate-result.md"
    md = gate_result.read_text(encoding="utf-8")
    assert "## Gate Result: PASS" in md
    assert "降级模式（无 Java 环境）" in md
    assert "risk_level: high" in md


# ── 用例 (c): 删 @Spec -> FAIL ──────────────────────────────────────────


def test_fail_unimplemented_rule(gate_fixture):
    """删除 R7 的 @Spec -> unimplemented_rules 非空 -> FAIL（exit 1）。"""
    (gate_fixture["src"] / "AccountService.java").write_text(
        _make_java_source(ALL_RULES[:-1]), encoding="utf-8"
    )
    rc, data = _run_gate(gate_fixture)
    assert rc != 0, "FAIL 场景应退出码非 0"
    assert data["status"] == "FAIL"
    assert data["spec_coverage"]["unimplemented_rules"] == ["R7"]
    assert any("unimplemented_rules" in r for r in data["fail_reasons"])


# ── 用例 (d): 孤儿注解 -> FAIL ──────────────────────────────────────────


def test_fail_orphan_annotation(gate_fixture):
    """把 R7 的 @Spec 改成 spec.md 不存在的 R9 -> orphan_annotations 非空 -> FAIL。"""
    orphan_java = _make_java_source(ALL_RULES).replace('rule = "R7"', 'rule = "R9"')
    (gate_fixture["src"] / "AccountService.java").write_text(
        orphan_java, encoding="utf-8"
    )
    rc, data = _run_gate(gate_fixture)
    assert rc != 0, "FAIL 场景应退出码非 0"
    assert data["status"] == "FAIL"
    orphan_rules = [a["rule"] for a in data["spec_coverage"]["orphan_annotations"]]
    assert "R9" in orphan_rules
    assert any("orphan_annotations" in r for r in data["fail_reasons"])


# ── 用例 (e): impact-report.md 缺失 -> FAIL（堵 P0 #3） ──────────────────


def test_fail_missing_impact_report(gate_fixture):
    """删除 impact-report.md -> 提示先运行 speckit.testing.impact。"""
    (gate_fixture["docs_dir"] / "impact-report.md").unlink()
    rc, data = _run_gate(gate_fixture)
    assert rc != 0, "FAIL 场景应退出码非 0"
    assert data["status"] == "FAIL"
    assert any("impact 未执行" in r for r in data["fail_reasons"]), data["fail_reasons"]


# ── 用例 (f): --check-only 不写 gate-result.md ──────────────────────────


def test_check_only_does_not_write_gate_result(gate_fixture):
    """--check-only：只跑步骤 1-7，不写 gate-result.md。"""
    gate_result = gate_fixture["docs_dir"] / "gate-result.md"
    assert not gate_result.exists()
    rc, data = _run_gate(gate_fixture, "--check-only")
    assert rc == 0
    assert data["status"] == "PASS"
    # 仍输出判定 JSON（含预期产物路径），但不落盘
    assert data["gate_result_path"].endswith("docs/gate-result.md")
    assert not gate_result.exists(), "--check-only 不应写 gate-result.md"


# ── 用例 (g): 确定性核心 run() 直接单测（full 模式） ─────────────────────


def _make_full_mode_reports(fx: dict) -> None:
    """在 fixture 中创建假 surefire/jacoco 报告，支撑 full 模式核心单测。"""
    surefire = fx["tmp_path"] / "target" / "surefire-reports"
    surefire.mkdir(parents=True)
    (surefire / "TEST-AccountServiceTest.xml").write_text(SUREFIRE_XML, encoding="utf-8")
    jacoco = fx["tmp_path"] / "target" / "site" / "jacoco" / "jacoco.xml"
    jacoco.parent.mkdir(parents=True)
    jacoco.write_text(JACOCO_XML, encoding="utf-8")


def _full_mode_inputs(fx: dict, **overrides) -> dict:
    """构造 full 模式 run() 输入（基于 fixture，可覆盖字段）。"""
    rg = _load_run_gate_module()
    import subprocess as _sp
    proc = _sp.run(
        [sys.executable,
         str(PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python"
             / "scan_spec_annotations.py"),
         "--source", str(fx["src"]), "--spec", str(fx["spec"]), "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    scan_spec = json.loads(proc.stdout)
    inputs = {
        "source": str(fx["src"]),
        "test_source": str(fx["test_src"]),
        "spec": str(fx["spec"]),
        "project": str(fx["tmp_path"]),
        "feature_dir": str(fx["feature_dir"]),
        "config": str(fx["config"]),
        "check_only": False,
        "degraded": False,
        "mvn_status": "SUCCESS",
        "impact_ok": True,
        "scan_stack": {"forbidden_findings": []},
        "parse_results": {
            "unit_tests": {"total": 7, "passed": 7, "failed": 0, "pass_rate": 100},
            "contract_tests": {"total": 2, "passed": 2, "failed": 0, "pass_rate": 100},
            "coverage": {
                "line_coverage": 95, "branch_coverage": 80,
                "method_coverage": 92, "instruction_coverage": 90,
                "complexity_coverage": 85,
            },
        },
        "scan_spec": scan_spec,
    }
    inputs.update(overrides)
    return inputs


def test_run_full_mode_pass(gate_fixture):
    """full 模式核心：high 风险档阈值全部达标 -> PASS，gate-result.md 格式正确。"""
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    result = rg.run(_full_mode_inputs(gate_fixture))

    assert result["status"] == "PASS"
    assert result["mode"] == "full"
    assert result["mvn_clean_test"] == "SUCCESS"
    assert result["risk_level"] == "high"
    # high 档阈值：line 90 / branch 70 / method 90 / instruction 90 / complexity 80
    thr = {t["metric"]: t for t in result["threshold_results"]}
    assert thr["line_coverage"]["threshold"] == 90
    assert thr["method_coverage"]["threshold"] == 90
    assert thr["complexity_coverage"]["threshold"] == 80
    assert all(t["pass"] for t in result["threshold_results"])
    # @DisplayName 双向对齐：test-src 7 条全部对齐
    assert result["displayname_match"] == {"aligned": 7, "total": 7, "mismatch_count": 0, "untested_spec_rules": []}
    assert result["fail_reasons"] == []

    # gate-result.md full 格式（含执行环境/单测明细/契约测试明细/Spec 矩阵/判定依据）
    md = (gate_fixture["docs_dir"] / "gate-result.md").read_text(encoding="utf-8")
    assert "## Gate Result: PASS" in md
    assert "- mvn clean test: SUCCESS" in md
    assert "target 清理: 已清理" in md
    assert "行覆盖率: 95% (阈值 >= 90%)" in md
    assert "DisplayName 对齐数: 7 / 7" in md
    assert "risk_overrides.high" in md


def test_run_full_mode_low_coverage_fail(gate_fixture):
    """full 模式核心：行覆盖率低于 high 档阈值 -> FAIL 且含修复建议。"""
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    # 把行覆盖率压到 65%（high 档阈值 90）
    inputs["parse_results"]["coverage"]["line_coverage"] = 65
    result = rg.run(inputs)

    assert result["status"] == "FAIL"
    assert any("line_coverage 65% < 90%" in r for r in result["fail_reasons"]), (
        result["fail_reasons"]
    )
    thr = {t["metric"]: t for t in result["threshold_results"]}
    assert thr["line_coverage"]["pass"] is False

    md = (gate_fixture["docs_dir"] / "gate-result.md").read_text(encoding="utf-8")
    assert "## Gate Result: FAIL" in md
    assert "失败原因与修复建议" in md


def test_run_full_mode_mvn_fail(gate_fixture):
    """full 模式核心：mvn clean test 失败 -> FAIL。"""
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture, mvn_status="FAIL")
    result = rg.run(inputs)
    assert result["status"] == "FAIL"
    assert any("mvn clean test 失败" in r for r in result["fail_reasons"])


def test_run_full_mode_missing_reports_fail(gate_fixture):
    """full 模式核心：surefire/jacoco 报告缺失 -> FAIL（不降级）。"""
    # 不创建 target 报告目录
    rg = _load_run_gate_module()
    result = rg.run(_full_mode_inputs(gate_fixture))
    assert result["status"] == "FAIL"
    reasons = " ".join(result["fail_reasons"])
    assert "surefire-reports 缺失" in reasons
    assert "jacoco.xml 缺失" in reasons


def test_run_full_mode_forbidden_stack(gate_fixture):
    """full 模式核心：scan_test_stack 检出 PowerMock -> FAIL。"""
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["scan_stack"] = {
        "forbidden_findings": [
            {"type": "powermock", "file": "XTest.java", "line": 3, "detail": "import ..."}
        ]
    }
    result = rg.run(inputs)
    assert result["status"] == "FAIL"
    assert any("forbidden_findings" in r for r in result["fail_reasons"])


def test_run_full_mode_displayname_mismatch(gate_fixture):
    """full 模式核心：@DisplayName 含未对齐规则 -> FAIL。"""
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    # 把 test-src 中 R1 的 DisplayName 改成 R99（孤儿编号）
    (gate_fixture["test_src"] / "AccountServiceTest.java").write_text(
        _make_test_java(ALL_RULES).replace('@DisplayName("R1-', '@DisplayName("R99-'),
        encoding="utf-8",
    )
    result = rg.run(_full_mode_inputs(gate_fixture))
    assert result["status"] == "FAIL"
    assert result["displayname_match"]["mismatch_count"] == 1
    assert any("displayname_mismatch" in r for r in result["fail_reasons"])


def test_run_full_mode_spec_without_test(gate_fixture):
    """full 模式核心：@Spec 规则无对应 @DisplayName 测试 -> FAIL（反向对齐，审计 F1）。

    删掉 R7 的测试方法 -> R7 有 @Spec 但无 @DisplayName 测试；
    mismatch_count 仍为 0（无孤儿 DisplayName），但反向检查检出 R7 无测试 -> FAIL。
    """
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    (gate_fixture["test_src"] / "AccountServiceTest.java").write_text(
        _make_test_java(ALL_RULES[:-1]), encoding="utf-8",
    )
    result = rg.run(_full_mode_inputs(gate_fixture))
    assert result["status"] == "FAIL"
    assert result["displayname_match"]["untested_spec_rules"] == ["R7"]
    assert result["displayname_match"]["mismatch_count"] == 0
    assert any("spec_rules_without_test" in r for r in result["fail_reasons"]), (
        result["fail_reasons"]
    )


def test_check_only_core_does_not_write(gate_fixture):
    """核心 run() 的 check_only=True 不写 gate-result.md（full 模式）。"""
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    gate_result = gate_fixture["docs_dir"] / "gate-result.md"
    assert not gate_result.exists()
    inputs = _full_mode_inputs(gate_fixture, check_only=True)
    result = rg.run(inputs)
    assert result["status"] == "PASS"
    assert not gate_result.exists(), "check_only 不应写 gate-result.md"
