"""run_gate 门禁编排脚本输出契约测试（v0.4 新增，v0.6 diff coverage 重写）。

用 subprocess 调用 ``run_gate.py``（降级模式：fixture 无 pom.xml，且环境可能
无 java/mvn），喂入 tmp 样本工程，断言 stdout 判定 JSON 契约与 gate-result.md
写出行为：

- (a) 脚本存在且 ``--json`` 输出合法 JSON（含全部契约字段）
- (b) 降级模式（fixture 无 pom.xml）：status PASS / mode=degraded /
  risk_level=high / mvn_clean_test=SKIPPED / spec_coverage 100% / gate-result.md
  写出且标注"降级模式（无 java/mvn 或 --project 目录无 pom.xml）"
- (c) FAIL 场景：删 @Spec -> unimplemented_rules 非空 -> FAIL（exit 1）
- (d) FAIL 场景：加孤儿注解（rule=R9）-> orphan_annotations 非空 -> FAIL
- (e) FAIL 场景：impact-report.md 缺失 -> "impact 未执行"（堵 P0 #3）
- (f) ``--check-only`` 不写 gate-result.md
- (g) 确定性核心 ``run()`` 直接单测：full 模式阈值比对（high 档阈值套用）+
  mvn 失败 + surefire/jacoco 报告缺失 + gate-result.md 内容格式
- (i) v0.6 降级判定（collect_environment 新语义：无 java/mvn 或 --project 无 pom）
- (j) v0.6 SOFT 段只读检查 + 写文件保留 AI 手写段（防覆盖回归）
- (k) v0.6 diff coverage（真实 git 仓库）：diff 判定 / 阈值边界 / 无 jacoco 数据 /
  fallback_all / no_changes / --diff-base / degraded N/A / config 阈值回落
- (l) v0.6 UNSPEC_CODE 漂移告警对接（MEDIUM 不阻断）
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
  spec_traceability:
    spec_rule_coverage_min: 100
    require_displayname_match: true

test_stack:
  forbid_powermock: true
  forbid_springboottest: true
  forbid_autowired: true

risk_overrides:
  high:
    unit_test:
      line_coverage_min: 90
      method_coverage_min: 90
      instruction_coverage_min: 90
      complexity_coverage_min: 80
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

# diff coverage 用例的 git 样本：V1 commit 后改 V2，新增 2 行（新文件行 5-6）
_JAVA_V1 = (
    "package com.example;\n"
    "\n"
    "public class AccountService {\n"
    "    public void a() {}\n"
    "}\n"
)
_JAVA_V2 = (
    "package com.example;\n"
    "\n"
    "public class AccountService {\n"
    "    public void a() {}\n"
    "    public void b() {}\n"
    "    public void c() {}\n"
    "}\n"
)

# 多 hunk 场景样本：V1 commit 后改 V2，两处不相邻各加 1 行（新文件行 6 与 25）
_MULTI_HUNK_V1 = (
    "package com.example;\n"
    "\n"
    "public class Multi {\n"
    "    public void a() {}\n"
    "    public void b() {}\n"
    "    public void c() {}\n"
    "    public void d() {}\n"
    "    public void e() {}\n"
    "    public void f() {}\n"
    "    public void g() {}\n"
    "    public void h() {}\n"
    "    public void i() {}\n"
    "    public void j() {}\n"
    "    public void k() {}\n"
    "    public void l() {}\n"
    "    public void m() {}\n"
    "    public void n() {}\n"
    "    public void o() {}\n"
    "    public void p() {}\n"
    "    public void q() {}\n"
    "    public void r() {}\n"
    "    public void s() {}\n"
    "    public void t() {}\n"
    "}\n"
)
_MULTI_HUNK_V2 = (
    "package com.example;\n"
    "\n"
    "public class Multi {\n"
    "    public void a() {}\n"
    "    public void b() {}\n"
    "    public void b2() {}\n"
    "    public void c() {}\n"
    "    public void d() {}\n"
    "    public void e() {}\n"
    "    public void f() {}\n"
    "    public void g() {}\n"
    "    public void h() {}\n"
    "    public void i() {}\n"
    "    public void j() {}\n"
    "    public void k() {}\n"
    "    public void l() {}\n"
    "    public void m() {}\n"
    "    public void n() {}\n"
    "    public void o() {}\n"
    "    public void p() {}\n"
    "    public void q() {}\n"
    "    public void r() {}\n"
    "    public void s() {}\n"
    "    public void t() {}\n"
    "    public void t2() {}\n"
    "}\n"
)


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


# ── git 仓库辅助（diff coverage 用例） ──────────────────────────────────────


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """在 cwd 执行 git 命令；失败即断言（测试前置 git 操作必须成功）。"""
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f"git {' '.join(args)} 失败: {proc.stderr}"
    return proc


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """在 tmp_path 初始化真实 git 仓库（main 分支 + user 配置），返回 tmp_path。"""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "test")
    return tmp_path


def _commit_java_file(repo: Path, rel: str, content: str, msg: str = "init") -> Path:
    """在 repo 下写 java 文件并 commit，返回文件路径。"""
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return f


def _make_diff_repo(fx: dict) -> None:
    """建 diff 场景 git 仓库：commit 初始 java（V1），再修改新增 2 行（变更行 5-6）。

    变更行 = 新文件第 5、6 行（``git diff --unified=0`` 输出 ``@@ -4,0 +5,2 @@``）。
    """
    _make_full_mode_reports(fx)
    f = _commit_java_file(fx["tmp_path"], "com/example/AccountService.java", _JAVA_V1)
    f.write_text(_JAVA_V2, encoding="utf-8")


def _make_jacoco_source_lines(key: str, covered: list[int], total: list[int]) -> list[dict]:
    """构造 parse_results.source_lines 条目（与 parse_test_results 输出格式一致）。

    key 形如 ``com/example/AccountService.java``（package 点转斜杠 + / + 文件名）；
    covered 为已覆盖行号（ci=1），total 为全部行号（nr 升序）。
    """
    lines = [
        {"nr": nr, "mi": 0 if nr in covered else 1, "ci": 1 if nr in covered else 0}
        for nr in sorted(total)
    ]
    pkg = key.rsplit("/", 1)[0].replace("/", ".")
    return [{"key": key, "package": pkg, "file": key.rsplit("/", 1)[1], "lines": lines}]


# ── 用例 (a): 脚本存在 + JSON 合法 ───────────────────────────────────────


def test_script_exists():
    assert PY_SCRIPT.is_file(), f"missing run_gate.py: {PY_SCRIPT}"


def test_json_output_has_all_contract_fields(gate_fixture):
    """stdout 输出合法 JSON，含全部契约字段。"""
    rc, data = _run_gate(gate_fixture)
    assert rc == 0
    for field in [
        "status", "mode", "gate_result_path", "risk_level", "mvn_clean_test",
        "unit_tests", "coverage", "spec_coverage",
        "displayname_match", "adversarial_coverage", "threshold_results",
        "fail_reasons",
        # v0.6 契约字段（降级原因 / SOFT / unspec / diff coverage）
        "degraded_reason", "soft_missing", "unspec_codes_count",
        "diff_coverage", "diff_threshold",
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
    # 降级模式 diff coverage 为 N/A
    assert data["diff_coverage"]["mode"] == "N/A"

    # gate-result.md 由脚本写出，且明确标注降级模式
    gate_result = gate_fixture["docs_dir"] / "gate-result.md"
    assert gate_result.is_file(), "run_gate 应写出 gate-result.md"
    md = gate_result.read_text(encoding="utf-8")
    assert "## Gate Result: PASS" in md
    assert "降级模式（无 java/mvn 或 --project 目录无 pom.xml）" in md
    assert "risk_level: high" in md

    # v0.5：降级模式仍构造 adversarial_coverage（affected_rules/counts 为空，
    # missing 空），但降级跳过对抗硬判 -> 不 FAIL
    assert "adversarial_coverage" in data
    assert data["adversarial_coverage"]["high_risk_rules"] == []
    assert data["adversarial_coverage"]["missing"] == []


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
    # v0.5：给 R1（high 风险规则）补对抗用例，满足步骤 5.5（独立文件，
    # 不受各用例对 AccountServiceTest.java 的 .replace/.write 影响）
    (fx["test_src"] / "AdversarialTest.java").write_text(
        "package com.example;\n"
        "import org.junit.jupiter.api.Test;\n"
        "import org.junit.jupiter.api.DisplayName;\n"
        "class AdversarialTest {\n"
        '    @Test\n'
        '    @DisplayName("R1-对抗-边界")\n'
        "    void testR1Adversarial() {}\n"
        "}\n",
        encoding="utf-8",
    )


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
            "coverage": {
                "line_coverage": 95, "branch_coverage": 80,
                "method_coverage": 92, "instruction_coverage": 90,
                "complexity_coverage": 85,
            },
            "source_lines": [],
        },
        "scan_spec": scan_spec,
    }
    inputs.update(overrides)
    return inputs


def _degraded_inputs(fx: dict, **overrides) -> dict:
    """构造 degraded 模式 run() 输入（基于 fixture，可覆盖字段）。

    降级模式跳过 mvn/报告/对齐，仅判 @Spec 覆盖率阈值——SOFT 检查等
    v0.6 通用逻辑在两种模式下都执行，degraded 输入最轻量。
    """
    inputs = _full_mode_inputs(fx)
    inputs.update({
        "degraded": True,
        "mvn_status": "SKIPPED",
        "scan_stack": None,
        "parse_results": None,
    })
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
    # 非 git 目录 -> fallback_all，走全量聚合阈值（high 档：line 90 / branch 70 /
    # method 90 / instruction 90 / complexity 80）
    assert result["diff_coverage"]["mode"] == "fallback_all"
    thr = {t["metric"]: t for t in result["threshold_results"]}
    assert thr["line_coverage"]["threshold"] == 90
    assert thr["method_coverage"]["threshold"] == 90
    assert thr["complexity_coverage"]["threshold"] == 80
    assert all(t["pass"] for t in result["threshold_results"])
    # @DisplayName 双向对齐：test-src 7 条 + AdversarialTest 1 条（R1-对抗）= 8 条全部对齐
    assert result["displayname_match"] == {"aligned": 8, "total": 8, "mismatch_count": 0, "untested_spec_rules": []}
    assert result["fail_reasons"] == []

    # gate-result.md full 格式（含执行环境/单测明细/Spec 矩阵/判定依据）
    md = (gate_fixture["docs_dir"] / "gate-result.md").read_text(encoding="utf-8")
    assert "## Gate Result: PASS" in md
    assert "- mvn clean test: SUCCESS" in md
    assert "target 清理: 已清理" in md
    assert "- diff coverage: 无 git，回退全量阈值判定" in md
    assert "DisplayName 对齐数: 8 / 8" in md
    assert "risk_overrides.high" in md
    # v0.5：gate-result.md 含关键路径对抗覆盖段
    assert "关键路径对抗覆盖" in md
    assert "R1" in md


def test_run_full_mode_low_coverage_fail(gate_fixture):
    """full 模式核心：行覆盖率低于 high 档阈值 -> FAIL 且含修复建议。"""
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    # 把行覆盖率压到 65%（high 档阈值 90）；非 git -> fallback_all 全量聚合判定
    inputs["parse_results"]["coverage"]["line_coverage"] = 65
    result = rg.run(inputs)

    assert result["status"] == "FAIL"
    assert result["diff_coverage"]["mode"] == "fallback_all"
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


# ── 用例 (h): 对抗性门禁（v0.5 步骤 5.5） ────────────────────────────────


def test_run_full_mode_adversarial_pass(gate_fixture):
    """v0.5：high 风险规则 R1 有对抗用例 -> 步骤 5.5 PASS，不影响整体 PASS。"""
    _make_full_mode_reports(gate_fixture)  # 已含 R1 对抗用例
    rg = _load_run_gate_module()
    result = rg.run(_full_mode_inputs(gate_fixture))
    assert result["status"] == "PASS"
    adv = result["adversarial_coverage"]
    assert adv["critical_path_required"] is True
    assert "R1" in adv["high_risk_rules"]
    assert adv["adversarial_counts"].get("R1", 0) >= 1
    assert adv["missing"] == []


def test_run_full_mode_adversarial_fail(gate_fixture):
    """v0.5：high 风险规则无对抗用例 -> critical_path_required=true -> FAIL。"""
    _make_full_mode_reports(gate_fixture)
    # 删除对抗用例文件
    (gate_fixture["test_src"] / "AdversarialTest.java").unlink()
    rg = _load_run_gate_module()
    result = rg.run(_full_mode_inputs(gate_fixture))
    assert result["status"] == "FAIL"
    assert any("critical_path_adversarial" in r for r in result["fail_reasons"]), result["fail_reasons"]
    adv = result["adversarial_coverage"]
    assert "R1" in adv["missing"]


def test_run_full_mode_adversarial_degraded_by_config(gate_fixture):
    """v0.5：critical_path_required=false -> high 风险无对抗也不 FAIL（advisory 降级）。"""
    _make_full_mode_reports(gate_fixture)
    (gate_fixture["test_src"] / "AdversarialTest.java").unlink()  # 无对抗
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    # 改 config 设 critical_path_required=false
    cfg_path = gate_fixture["tmp_path"] / "testing-config-degraded.yml"
    cfg_path.write_text(
        gate_fixture["config"].read_text(encoding="utf-8")
        + "\nadversarial:\n  enabled: true\n  critical_path_required: false\n",
        encoding="utf-8",
    )
    inputs["config"] = str(cfg_path)
    result = rg.run(inputs)
    assert result["status"] == "PASS"  # 降级：不硬判
    adv = result["adversarial_coverage"]
    assert adv["critical_path_required"] is False
    assert "R1" in adv["missing"]  # 仍统计，但不阻断


# ── 用例 (i): v0.6 降级判定（collect_environment 新语义） ─────────────────


def test_collect_environment_no_java_mvn_degraded(monkeypatch, tmp_path):
    """无 java/mvn 环境 -> degraded，degraded_reason="no java/mvn on PATH"。

    monkeypatch shutil.which 模拟（本机若装了 java/mvn 则走不到该分支，
    必须显式模拟才能覆盖此语义）。
    """
    rg = _load_run_gate_module()
    monkeypatch.setattr(rg.shutil, "which", lambda name: None)
    env = rg.collect_environment(str(tmp_path))
    assert env["degraded"] is True
    assert env["degraded_reason"] == "no java/mvn on PATH"


def test_collect_environment_no_pom_degraded(monkeypatch, tmp_path):
    """--project 目录无 pom.xml -> degraded，reason 提示 AI 先 find pom。"""
    rg = _load_run_gate_module()
    monkeypatch.setattr(rg.shutil, "which", lambda name: f"/fake/bin/{name}")
    env = rg.collect_environment(str(tmp_path))
    assert env["degraded"] is True
    assert "pom.xml not found" in env["degraded_reason"]
    assert "find . -name pom.xml" in env["degraded_reason"]


def test_collect_environment_with_pom_not_degraded(monkeypatch, tmp_path):
    """--project 目录有 pom.xml -> 不降级。"""
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    rg = _load_run_gate_module()
    monkeypatch.setattr(rg.shutil, "which", lambda name: f"/fake/bin/{name}")
    env = rg.collect_environment(str(tmp_path))
    assert env["degraded"] is False
    assert env["degraded_reason"] == ""


# ── 用例 (j): v0.6 SOFT 段只读检查 + 保留 AI 手写段 ──────────────────────


SOFT_HEADER = "## AI 交叉验证（SOFT，不影响判定）"


def test_run_soft_missing_true_when_header_absent(gate_fixture):
    """gate-result.md 无 SOFT 标题 -> soft_missing=true，status 仍 PASS（不 FAIL）。"""
    rg = _load_run_gate_module()
    gate_result = gate_fixture["docs_dir"] / "gate-result.md"
    gate_result.write_text("## Gate Result: PASS\n\n（无 AI 交叉验证段）\n", encoding="utf-8")
    result = rg.run(_degraded_inputs(gate_fixture))
    assert result["status"] == "PASS", result["fail_reasons"]
    assert result["soft_missing"] is True
    assert not any("SOFT" in r for r in result["fail_reasons"]), "soft_missing 不得进入 fail_reasons"


def test_run_soft_present_false_when_header_exists(gate_fixture):
    """gate-result.md 含独立 SOFT 标题行 -> soft_missing=false。"""
    rg = _load_run_gate_module()
    gate_result = gate_fixture["docs_dir"] / "gate-result.md"
    gate_result.write_text(f"{SOFT_HEADER}\n\n人工交叉验证记录：无漂移\n", encoding="utf-8")
    result = rg.run(_degraded_inputs(gate_fixture))
    assert result["status"] == "PASS"
    assert result["soft_missing"] is False


def test_run_soft_missing_stable_across_runs(gate_fixture):
    """soft_missing 不翻转：脚本写出的 WARN 行不构成标题 -> 二次运行仍 true（防自满足回归）。"""
    rg = _load_run_gate_module()
    inputs = _degraded_inputs(gate_fixture)
    gate_result = gate_fixture["docs_dir"] / "gate-result.md"
    assert not gate_result.exists()
    first = rg.run(inputs)
    assert first["status"] == "PASS"
    assert first["soft_missing"] is True
    md = gate_result.read_text(encoding="utf-8")
    assert "WARN: SOFT 交叉验证标题缺失" in md  # 脚本写出 WARN 行（不含完整标题）
    second = rg.run(inputs)  # 读第一次写出的 gate-result.md 再判
    assert second["status"] == "PASS"
    assert second["soft_missing"] is True, "WARN 文案不得被自身正则命中（自满足 bug）"


def test_run_soft_section_preserved_after_rewrite(gate_fixture):
    """gate-result.md 含 AI 手写 SOFT 段 -> 重跑后该段保留且 soft_missing=false（防覆盖回归）。"""
    rg = _load_run_gate_module()
    gate_result = gate_fixture["docs_dir"] / "gate-result.md"
    ai_section = (
        f"{SOFT_HEADER}\n\n"
        "人工交叉验证：无漂移\n"
        "- 归因：无\n"
    )
    gate_result.write_text("## Gate Result: FAIL\n\n旧内容\n\n" + ai_section, encoding="utf-8")
    result = rg.run(_degraded_inputs(gate_fixture))
    assert result["status"] == "PASS"
    assert result["soft_missing"] is False
    md = gate_result.read_text(encoding="utf-8")
    assert SOFT_HEADER in md
    assert "人工交叉验证：无漂移" in md  # AI 手写内容不被覆盖抹掉
    assert "归因：无" in md


# ── 用例 (k): v0.6 diff coverage（真实 git 仓库） ─────────────────────────


def test_run_full_mode_diff_coverage_percent_and_threshold(gate_fixture, git_repo):
    """diff 模式：变更 2 行 1 行覆盖 -> percent=50；阈值 80 FAIL / 40 PASS。"""
    _make_diff_repo(gate_fixture)
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["source_lines"] = _make_jacoco_source_lines(
        "com/example/AccountService.java", covered=[5], total=[5, 6]
    )
    # 阈值 80（默认）-> FAIL
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "diff"
    assert result["diff_coverage"]["base"] == "HEAD"
    assert result["diff_coverage"]["total_lines"] == 2
    assert result["diff_coverage"]["covered_lines"] == 1
    assert result["diff_coverage"]["percent"] == 50
    assert result["diff_threshold"] == 80
    assert result["status"] == "FAIL"
    assert any("diff coverage 50% < 80%" in r for r in result["fail_reasons"]), (
        result["fail_reasons"]
    )
    # 阈值 40 -> PASS（同一 git 状态重跑）
    inputs["diff_threshold"] = 40
    result2 = rg.run(inputs)
    assert result2["status"] == "PASS", result2["fail_reasons"]
    thr = {t["metric"]: t for t in result2["threshold_results"]}
    assert thr["diff_coverage"]["pass"] is True


def test_run_full_mode_diff_coverage_threshold_boundary(gate_fixture, git_repo):
    """阈值边界：percent == threshold -> PASS。"""
    _make_diff_repo(gate_fixture)
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["source_lines"] = _make_jacoco_source_lines(
        "com/example/AccountService.java", covered=[5], total=[5, 6]
    )
    inputs["diff_threshold"] = 50  # percent 50 == 阈值 50
    result = rg.run(inputs)
    assert result["status"] == "PASS", result["fail_reasons"]
    thr = {t["metric"]: t for t in result["threshold_results"]}
    assert thr["diff_coverage"]["actual"] == 50
    assert thr["diff_coverage"]["pass"] is True


def test_run_full_mode_diff_coverage_no_jacoco_data_fail(gate_fixture, git_repo):
    """diff 文件不在 source_lines（无 jacoco 行级数据）-> 变更行全未覆盖 percent=0 -> FAIL。"""
    _make_diff_repo(gate_fixture)
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["source_lines"] = []  # 无行级数据（声明即承诺，保守方向）
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "diff"
    assert result["diff_coverage"]["total_lines"] == 2
    assert result["diff_coverage"]["covered_lines"] == 0
    assert result["diff_coverage"]["percent"] == 0
    assert result["status"] == "FAIL"
    assert any("diff coverage 0% < 80%" in r for r in result["fail_reasons"]), (
        result["fail_reasons"]
    )


def test_run_full_mode_diff_fallback_all_no_git(gate_fixture):
    """非 git 目录 -> mode=fallback_all，全量聚合阈值判定生效（低聚合覆盖 -> FAIL）。"""
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["coverage"]["line_coverage"] = 65  # 聚合低覆盖
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "fallback_all"
    assert result["status"] == "FAIL"
    assert any("line_coverage 65% < 90%" in r for r in result["fail_reasons"]), (
        result["fail_reasons"]
    )


def test_run_full_mode_diff_no_changes_pass(gate_fixture, git_repo):
    """只改非 java 文件 -> mode=no_changes 且 PASS（无承诺，不判）。"""
    _make_full_mode_reports(gate_fixture)
    readme = gate_fixture["tmp_path"] / "README.md"
    readme.write_text("v1\n", encoding="utf-8")
    _git(gate_fixture["tmp_path"], "add", "-A")
    _git(gate_fixture["tmp_path"], "commit", "-q", "-m", "init")
    readme.write_text("v2\n", encoding="utf-8")  # 只改非 java
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["source_lines"] = []
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "no_changes"
    assert result["status"] == "PASS", result["fail_reasons"]
    thr = {t["metric"]: t for t in result["threshold_results"]}
    assert thr["diff_coverage"]["pass"] is True


def test_run_full_mode_diff_base_branch(gate_fixture, git_repo):
    """--diff-base：feature 分支 vs main（merge-base 定位）-> mode=diff 且 percent 合理。"""
    _make_full_mode_reports(gate_fixture)
    f = _commit_java_file(gate_fixture["tmp_path"], "com/example/AccountService.java", _JAVA_V1)
    _git(gate_fixture["tmp_path"], "checkout", "-q", "-b", "feature")
    f.write_text(_JAVA_V2, encoding="utf-8")
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["source_lines"] = _make_jacoco_source_lines(
        "com/example/AccountService.java", covered=[5], total=[5, 6]
    )
    inputs["diff_base"] = "main"
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "diff"
    assert result["diff_coverage"]["percent"] == 50
    assert result["diff_coverage"]["base"] != "HEAD"  # merge-base 定位的 commit 前缀


def test_run_degraded_diff_coverage_na(gate_fixture):
    """degraded 模式 -> diff_coverage.mode=N/A，diff_threshold 仍输出（默认 80）。"""
    rg = _load_run_gate_module()
    result = rg.run(_degraded_inputs(gate_fixture))
    assert result["status"] == "PASS"
    assert result["diff_coverage"]["mode"] == "N/A"
    assert result["diff_threshold"] == 80


def test_run_full_mode_diff_threshold_from_config(gate_fixture, git_repo):
    """config gate.diff_coverage_threshold=30 -> 不传 CLI，50% -> PASS（阈值回落）。"""
    _make_diff_repo(gate_fixture)
    cfg_path = gate_fixture["tmp_path"] / "testing-config-diff.yml"
    cfg_path.write_text(
        TESTING_CONFIG_YML.replace(
            "  spec_traceability:",
            "  diff_coverage_threshold: 30\n  spec_traceability:",
        ),
        encoding="utf-8",
    )
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["config"] = str(cfg_path)
    inputs["parse_results"]["source_lines"] = _make_jacoco_source_lines(
        "com/example/AccountService.java", covered=[5], total=[5, 6]
    )
    result = rg.run(inputs)
    assert result["diff_threshold"] == 30
    assert result["diff_coverage"]["percent"] == 50
    assert result["status"] == "PASS", result["fail_reasons"]


def test_run_full_mode_diff_multi_module_subdir(gate_fixture, git_repo):
    """多模块子目录（修复 1 回归锁）：--project=backend/ 时 diff 以仓库根为基准。

    git 仓库根下建 backend/pom.xml + backend/src/main/java/.../AccountService.java，
    commit 后改文件加 2 行；--project=<repo>/backend -> diff_coverage.percent=50。
    修复前 pathspec 相对 cwd 解析为 backend/backend/... 不匹配 -> percent=None 静默跳过。
    """
    _make_full_mode_reports(gate_fixture)
    # 模块子目录：backend/pom.xml + 生产代码
    backend_dir = gate_fixture["tmp_path"] / "backend"
    backend_dir.mkdir(parents=True, exist_ok=True)
    (backend_dir / "pom.xml").write_text("<project/>", encoding="utf-8")
    f = _commit_java_file(
        gate_fixture["tmp_path"],
        "backend/src/main/java/com/example/AccountService.java",
        _JAVA_V1,
    )
    f.write_text(_JAVA_V2, encoding="utf-8")  # 新增 2 行（新文件行 5-6）
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["project"] = str(gate_fixture["tmp_path"] / "backend")  # --project=backend/
    inputs["parse_results"]["source_lines"] = _make_jacoco_source_lines(
        "com/example/AccountService.java", covered=[5], total=[5, 6]
    )
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "diff"
    assert result["diff_coverage"]["total_lines"] == 2
    assert result["diff_coverage"]["covered_lines"] == 1
    assert result["diff_coverage"]["percent"] == 50
    assert result["status"] == "FAIL"  # 阈值 80
    assert any("diff coverage 50% < 80%" in r for r in result["fail_reasons"]), (
        result["fail_reasons"]
    )


def test_run_full_mode_diff_multi_hunk(gate_fixture, git_repo):
    """多 hunk 场景：同一文件两处不相邻修改各加 1 行，jacoco 覆盖其中 1 行 -> percent=50。

    验证 hunk 解析多段累加正确（@@ -5,0 +6 @@ 与 @@ -23,0 +25 @@ 各 1 行）。
    """
    _make_full_mode_reports(gate_fixture)
    f = _commit_java_file(gate_fixture["tmp_path"], "com/example/Multi.java", _MULTI_HUNK_V1)
    f.write_text(_MULTI_HUNK_V2, encoding="utf-8")  # 新文件行 6 与 25 各加 1 行
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["source_lines"] = _make_jacoco_source_lines(
        "com/example/Multi.java", covered=[6], total=[6, 25]
    )
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "diff"
    assert result["diff_coverage"]["total_lines"] == 2
    assert result["diff_coverage"]["covered_lines"] == 1
    assert result["diff_coverage"]["percent"] == 50
    assert result["status"] == "FAIL"  # 阈值 80
    assert any("diff coverage 50% < 80%" in r for r in result["fail_reasons"]), (
        result["fail_reasons"]
    )


def test_run_full_mode_diff_only_test_files_no_changes(gate_fixture, git_repo):
    """只改测试文件（修复 2 回归）：src/test/... 路径不参与 diff coverage -> no_changes 且 PASS。"""
    _make_full_mode_reports(gate_fixture)
    # 先 commit 一个生产文件（保证仓库有基线），再只改测试文件
    _commit_java_file(gate_fixture["tmp_path"], "com/example/AccountService.java", _JAVA_V1)
    test_f = _commit_java_file(
        gate_fixture["tmp_path"],
        "src/test/java/com/example/AccountServiceTest.java",
        "package com.example;\n\nclass AccountServiceTest {}\n",
        msg="add test",
    )
    test_f.write_text(
        "package com.example;\n\nclass AccountServiceTest {\n    void t() {}\n}\n",
        encoding="utf-8",
    )  # 只改测试文件
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["source_lines"] = []
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "no_changes"
    assert result["status"] == "PASS", result["fail_reasons"]
    thr = {t["metric"]: t for t in result["threshold_results"]}
    assert thr["diff_coverage"]["pass"] is True


def test_run_full_mode_diff_untracked_new_file(gate_fixture, git_repo):
    """未跟踪新文件（修复 3 回归）：新建未跟踪 java 文件，jacoco 覆盖 1/6 行 -> percent=17。"""
    _make_full_mode_reports(gate_fixture)
    # 先 commit 一个基线文件建立 HEAD（git diff --name-only HEAD 需要 HEAD 存在）
    _commit_java_file(gate_fixture["tmp_path"], "com/example/Base.java", _JAVA_V1)
    # 未跟踪新文件：不 commit，直接写文件（git ls-files --others 捕获）
    new_file = gate_fixture["tmp_path"] / "com/example/NewService.java"
    new_file.parent.mkdir(parents=True, exist_ok=True)
    new_file.write_text(
        "package com.example;\n\npublic class NewService {\n    public void a() {}\n"
        "    public void b() {}\n}\n",
        encoding="utf-8",
    )  # 6 行（1..6 全视为变更行）
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["source_lines"] = _make_jacoco_source_lines(
        "com/example/NewService.java", covered=[4], total=[1, 2, 3, 4, 5, 6]
    )
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "diff"
    assert result["diff_coverage"]["total_lines"] == 6
    assert result["diff_coverage"]["covered_lines"] == 1
    assert result["diff_coverage"]["percent"] == round(1 / 6 * 100)
    assert result["status"] == "FAIL"  # 阈值 80


def test_run_full_mode_diff_untracked_new_file_no_jacoco_fail(gate_fixture, git_repo):
    """未跟踪新文件无 jacoco 数据 -> 变更行全未覆盖 percent=0 -> FAIL。"""
    _make_full_mode_reports(gate_fixture)
    _commit_java_file(gate_fixture["tmp_path"], "com/example/Base.java", _JAVA_V1)
    new_file = gate_fixture["tmp_path"] / "com/example/NewService.java"
    new_file.parent.mkdir(parents=True, exist_ok=True)
    new_file.write_text(
        "package com.example;\n\npublic class NewService {\n    public void a() {}\n"
        "    public void b() {}\n}\n",
        encoding="utf-8",
    )
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["source_lines"] = []  # 无行级数据
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "diff"
    assert result["diff_coverage"]["total_lines"] == 6
    assert result["diff_coverage"]["covered_lines"] == 0
    assert result["diff_coverage"]["percent"] == 0
    assert result["status"] == "FAIL"
    assert any("diff coverage 0% < 80%" in r for r in result["fail_reasons"]), (
        result["fail_reasons"]
    )


def test_run_full_mode_diff_deleted_file_fallback_all(gate_fixture, git_repo):
    """纯删除 java 文件（修复 5 语义）：仅 - 行（count=0）-> changed 为空 -> fallback_all。"""
    _make_full_mode_reports(gate_fixture)
    f = _commit_java_file(gate_fixture["tmp_path"], "com/example/AccountService.java", _JAVA_V1)
    _git(gate_fixture["tmp_path"], "rm", "-q", str(f.relative_to(gate_fixture["tmp_path"])))
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    inputs["parse_results"]["source_lines"] = []
    result = rg.run(inputs)
    assert result["diff_coverage"]["mode"] == "fallback_all"
    assert result["status"] == "PASS", result["fail_reasons"]  # 全量聚合达标


def test_cli_diff_threshold_out_of_range_exit_2(gate_fixture):
    """--diff-threshold 越界（150）-> exit 2，stderr 报错。"""
    rc, stdout, stderr = _run_py([
        "--source", str(gate_fixture["src"]),
        "--test-source", str(gate_fixture["test_src"]),
        "--spec", str(gate_fixture["spec"]),
        "--project", str(gate_fixture["tmp_path"]),
        "--feature-dir", str(gate_fixture["feature_dir"]),
        "--config", str(gate_fixture["config"]),
        "--diff-threshold", "150",
        "--json",
    ])
    assert rc == 2
    assert "0-100" in stderr
    assert stdout.strip() == "", "越界不应输出判定 JSON"


def test_cli_diff_threshold_non_int_exit_2(gate_fixture):
    """--diff-threshold 非整数（abc）-> argparse type=int 报错 exit 2。"""
    rc, stdout, stderr = _run_py([
        "--source", str(gate_fixture["src"]),
        "--test-source", str(gate_fixture["test_src"]),
        "--spec", str(gate_fixture["spec"]),
        "--project", str(gate_fixture["tmp_path"]),
        "--feature-dir", str(gate_fixture["feature_dir"]),
        "--config", str(gate_fixture["config"]),
        "--diff-threshold", "abc",
        "--json",
    ])
    assert rc == 2
    assert "invalid int value" in stderr
    assert stdout.strip() == "", "非法值不应输出判定 JSON"


# ── 用例 (l): v0.6 UNSPEC_CODE 漂移告警对接 ───────────────────────────────


def test_run_full_mode_unspec_codes_count_and_gate_md(gate_fixture):
    """scan_spec 含 unspec_codes -> result["unspec_codes_count"]==len 且不 FAIL，
    gate-result.md 含"漂移告警"段（MEDIUM 不阻断）。"""
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    inputs = _full_mode_inputs(gate_fixture)
    scan_spec = dict(inputs["scan_spec"])
    scan_spec["unspec_codes"] = ["com.example.OrphanService", "com.example.LegacyDao"]
    inputs["scan_spec"] = scan_spec
    result = rg.run(inputs)
    assert result["status"] == "PASS", result["fail_reasons"]  # MEDIUM 告警不阻断
    assert result["unspec_codes_count"] == 2
    assert not any("unspec" in r.lower() for r in result["fail_reasons"])
    md = (gate_fixture["docs_dir"] / "gate-result.md").read_text(encoding="utf-8")
    assert "### 漂移告警（MEDIUM，不阻断）" in md
    assert "com.example.OrphanService" in md
    assert "com.example.LegacyDao" in md


def test_run_full_mode_unspec_codes_default_zero(gate_fixture):
    """scan_spec 无 unspec_codes（真实扫描输出）-> unspec_codes_count==0。"""
    _make_full_mode_reports(gate_fixture)
    rg = _load_run_gate_module()
    result = rg.run(_full_mode_inputs(gate_fixture))
    assert result["status"] == "PASS"
    assert result["unspec_codes_count"] == 0
    md = (gate_fixture["docs_dir"] / "gate-result.md").read_text(encoding="utf-8")
    assert "漂移告警" not in md  # 空列表不写告警段


# ── 用例 (m): v0.66 FR 段规则源（spec.md ### Functional Requirements，FR-001）─


FR_RULES = [f"FR-{n:03d}" for n in range(1, 8)]
FR_TO_METHOD = {f"FR-{n:03d}": RULE_TO_METHOD[f"R{n}"] for n in range(1, 8)}
FR_TO_DESC = {f"FR-{n:03d}": RULE_TO_DESC[f"R{n}"] for n in range(1, 8)}

FR_SPEC_MD = """\
# Transfer

### Functional Requirements

- **FR-001**: System MUST validate amount > 0
- **FR-002**: System MUST check sufficient balance
- **FR-003**: System MUST reject frozen transfer
- **FR-004**: System MUST enforce single transfer limit
- **FR-005**: System MUST log audit trail
- **FR-006**: System MUST commit atomically
- **FR-007**: System MUST reject self transfer

## API

POST /api/v1/accounts/transfer
"""

FR_IMPACT_REPORT_MD = """\
# ImpactReport

### 影响范围
- com.example.AccountService.transfer (FR-001)

### 风险等级
risk_level: high

### 受影响规则编号清单
affected_rules:
  - rule: FR-001
    change_type: modified
    risk: high
"""


def _make_fr_java_source(rules: list[str]) -> str:
    """FR 体系样本：@Spec(rule="FR-00x") 顶层锚。"""
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
        desc = FR_TO_DESC[rule]
        lines.append(
            f'    @Spec(capability = "transfer", rule = "{rule}", description = "{desc}")'
        )
        lines.append(f"    public void {FR_TO_METHOD[rule]}() {{")
        lines.append("    }")
        lines.append("")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _make_fr_test_java(rules: list[str]) -> str:
    """FR 体系样本测试：@DisplayName("FR-00x-R1-<描述>") 子场景编号。"""
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
        desc = FR_TO_DESC[rule]
        lines.append("    @Test")
        lines.append(f'    @DisplayName("{rule}-R1-{desc}")')
        lines.append(f"    void test{rule.replace('-', 'R')}() {{")
        lines.append("    }")
        lines.append("")
    lines.append("}")
    return "\n".join(lines) + "\n"


@pytest.fixture
def fr_gate_fixture(tmp_path: Path) -> dict:
    """FR 体系完整 fixture（与 gate_fixture 同构，仅规则编号换 FR-001 顶层锚）。

    impact 受影响规则为 FR-001（high）；test-src 含 FR-001 对抗用例
    @DisplayName("FR-001-R1-对抗-边界")，满足 critical_path_required。
    """
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(FR_SPEC_MD, encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "AccountService.java").write_text(
        _make_fr_java_source(FR_RULES), encoding="utf-8"
    )

    test_dir = tmp_path / "test-src"
    test_dir.mkdir()
    (test_dir / "AccountServiceTest.java").write_text(
        _make_fr_test_java(FR_RULES), encoding="utf-8"
    )
    (test_dir / "AdversarialTest.java").write_text(
        "package com.example;\n"
        "import org.junit.jupiter.api.Test;\n"
        "import org.junit.jupiter.api.DisplayName;\n"
        "class AdversarialTest {\n"
        "    @Test\n"
        '    @DisplayName("FR-001-R1-对抗-边界")\n'
        "    void testFR001Adversarial() {}\n"
        "}\n",
        encoding="utf-8",
    )

    feature_dir = tmp_path / "specs" / "001-bank-transfer"
    docs_dir = feature_dir / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "impact-report.md").write_text(FR_IMPACT_REPORT_MD, encoding="utf-8")

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


def test_degraded_fr_section_pass(fr_gate_fixture):
    """v0.66 降级：FR 段 spec + FR-001 @Spec 全覆盖 -> PASS，rule_source=fr-section。"""
    rc, data = _run_gate(fr_gate_fixture)
    assert rc == 0, f"FAIL: {data['fail_reasons']}"
    assert data["status"] == "PASS"
    assert data["spec_coverage"]["rule_source"] == "fr-section"
    assert set(data["spec_coverage"]["spec_rules"]) == set(FR_RULES)
    assert data["spec_coverage"]["unimplemented_rules"] == []
    assert data["spec_coverage"]["orphan_annotations"] == []


def test_run_full_mode_fr_displayname_grouping(fr_gate_fixture):
    """v0.66 6.3: FR-001-R1- 按前缀 FR 分组与 @Spec 顶层锚对齐 ->
    displayname 7/7 对齐、无 mismatch、无 untested；影响规则 FR-001 解析为顶层锚；
    FR-001-R1-对抗 计入 adversarial_counts；gate-result.md 输出规则来源行。"""
    _make_full_mode_reports(fr_gate_fixture)
    # _make_full_mode_reports 会重写 AdversarialTest.java 为 R1-对抗，重写回 FR 版
    (fr_gate_fixture["test_src"] / "AdversarialTest.java").write_text(
        "package com.example;\n"
        "import org.junit.jupiter.api.Test;\n"
        "import org.junit.jupiter.api.DisplayName;\n"
        "class AdversarialTest {\n"
        "    @Test\n"
        '    @DisplayName("FR-001-R1-对抗-边界")\n'
        "    void testFR001Adversarial() {}\n"
        "}\n",
        encoding="utf-8",
    )
    rg = _load_run_gate_module()
    result = rg.run(_full_mode_inputs(fr_gate_fixture))

    assert result["status"] == "PASS", result["fail_reasons"]

    # 规则来源：FR 段
    assert result["spec_coverage"]["rule_source"] == "fr-section"
    assert result["spec_coverage"]["spec_rules"] == FR_RULES

    # DisplayName 前缀分组对齐：7 条 FR-xxx-R1- 全部归属对应 FR 顶层锚
    # + 1 条对抗 FR-001-R1-对抗 = total 8 全对齐
    dm = result["displayname_match"]
    assert dm["aligned"] == 8 and dm["total"] == 8, dm
    assert dm["mismatch_count"] == 0
    assert dm["untested_spec_rules"] == []

    # 影响规则解析顶层锚 FR-001 + 对抗按 FR 前缀分组
    adv = result["adversarial_coverage"]
    assert adv["high_risk_rules"] == ["FR-001"]
    assert adv["adversarial_counts"].get("FR-001") == 1
    assert adv["missing"] == []

    # gate-result.md：规则来源行 + DisplayName 对齐行
    md = (fr_gate_fixture["docs_dir"] / "gate-result.md").read_text(encoding="utf-8")
    assert "### Spec 规则覆盖矩阵" in md
    assert "规则来源: fr-section" in md
    assert "DisplayName 对齐数: 8 / 8" in md


def test_run_full_mode_fr_displayname_mismatch(fr_gate_fixture):
    """v0.66 6.3: @DisplayName 指向不存在的 FR 顶层锚 -> mismatch -> FAIL。"""
    _make_full_mode_reports(fr_gate_fixture)
    # _make_full_mode_reports 重写 AdversarialTest 为 R1-对抗，改回 FR 版避免额外 mismatch
    (fr_gate_fixture["test_src"] / "AdversarialTest.java").write_text(
        "package com.example;\n"
        "import org.junit.jupiter.api.Test;\n"
        "import org.junit.jupiter.api.DisplayName;\n"
        "class AdversarialTest {\n"
        "    @Test\n"
        '    @DisplayName("FR-001-R1-对抗-边界")\n'
        "    void testFR001Adversarial() {}\n"
        "}\n",
        encoding="utf-8",
    )
    (fr_gate_fixture["test_src"] / "AccountServiceTest.java").write_text(
        _make_fr_test_java(FR_RULES).replace(
            '@DisplayName("FR-001-R1-金额校验")',
            '@DisplayName("FR-099-R1-孤儿场景")',
        ),
        encoding="utf-8",
    )
    rg = _load_run_gate_module()
    result = rg.run(_full_mode_inputs(fr_gate_fixture))

    assert result["status"] == "FAIL"
    assert result["displayname_match"]["mismatch_count"] == 1
    assert any("displayname_mismatch" in r for r in result["fail_reasons"])

# ── v1.5: JUnit4 双通道（测试方法级 @Spec）+ @Autowired 扫描 ──────────────────


def _make_fr_junit4_test_java(rules: list[str]) -> str:
    """JUnit4 通道样本：测试方法上标 @Spec（与 JUnit 版本无关，静态扫描）。"""
    lines = [
        "package com.example;",
        "",
        "import org.junit.Test;",
        "import com.speckit.testing.Spec;",
        "",
        "public class AccountServiceTest {",
        "",
    ]
    for rule in rules:
        desc = FR_TO_DESC[rule]
        lines.append("    @Test")
        lines.append(
            f'    @Spec(capability = "transfer", rule = "{rule}", description = "{desc}")'
        )
        lines.append(f"    public void test{rule.replace('-', 'R')}() {{")
        lines.append("    }")
        lines.append("")
    lines.append("}")
    return "\n".join(lines) + "\n"


def test_run_full_mode_junit4_spec_channel(fr_gate_fixture):
    """v1.5 JUnit4 双通道：测试方法级 @Spec(rule="FR-xxx") 视为对齐信号
    （@Spec 为自定义注解与 JUnit 版本无关），7 条全部对齐 -> PASS。"""
    _make_full_mode_reports(fr_gate_fixture)
    # 替换测试源码为 JUnit4 通道版本（无 @DisplayName）
    (fr_gate_fixture["test_src"] / "AccountServiceTest.java").write_text(
        _make_fr_junit4_test_java(FR_RULES), encoding="utf-8"
    )
    # 对抗用例也走 JUnit4 通道：@Spec(rule="FR-001", description="对抗-...")
    (fr_gate_fixture["test_src"] / "AdversarialTest.java").write_text(
        "package com.example;\n"
        "import org.junit.Test;\n"
        "import com.speckit.testing.Spec;\n"
        "public class AdversarialTest {\n"
        "    @Test\n"
        '    @Spec(capability = "transfer", rule = "FR-001", description = "对抗-边界")\n'
        "    public void testFR001Adversarial() {}\n"
        "}\n",
        encoding="utf-8",
    )
    rg = _load_run_gate_module()
    result = rg.run(_full_mode_inputs(fr_gate_fixture))

    assert result["status"] == "PASS", result["fail_reasons"]
    dm = result["displayname_match"]
    assert dm["aligned"] == 8 and dm["total"] == 8, dm
    assert dm["mismatch_count"] == 0
    assert dm["untested_spec_rules"] == []
    # JUnit4 通道对抗识别：FR-001 description 含"对抗"
    adv = result["adversarial_coverage"]
    assert adv["adversarial_counts"].get("FR-001") == 1
    assert adv["missing"] == []


def test_run_full_mode_junit4_spec_orphan_fail(fr_gate_fixture):
    """v1.5 JUnit4 通道反向约束：测试方法级 @Spec 指向不存在的规则 -> mismatch -> FAIL。"""
    _make_full_mode_reports(fr_gate_fixture)
    (fr_gate_fixture["test_src"] / "AccountServiceTest.java").write_text(
        _make_fr_junit4_test_java(FR_RULES).replace(
            'rule = "FR-001"',
            'rule = "FR-099"',
        ),
        encoding="utf-8",
    )
    (fr_gate_fixture["test_src"] / "AdversarialTest.java").write_text(
        "package com.example;\n"
        "import org.junit.Test;\n"
        "import com.speckit.testing.Spec;\n"
        "public class AdversarialTest {\n"
        "    @Test\n"
        '    @Spec(capability = "transfer", rule = "FR-001", description = "对抗-边界")\n'
        "    public void testFR001Adversarial() {}\n"
        "}\n",
        encoding="utf-8",
    )
    rg = _load_run_gate_module()
    result = rg.run(_full_mode_inputs(fr_gate_fixture))

    assert result["status"] == "FAIL"
    assert result["displayname_match"]["mismatch_count"] == 1
    assert any("displayname_mismatch" in r for r in result["fail_reasons"])
