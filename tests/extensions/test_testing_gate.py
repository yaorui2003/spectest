"""
T009 - Tests for the speckit.testing.gate command markdown.

Validates that `extensions/testing/commands/speckit.testing.gate.md`:
- exists
- has frontmatter with a description
- declares the `scripts:` block referencing the run_gate orchestrator
  (sh / ps / py three keys, all pointing at run-gate.*)
- body covers the four gate checks: unit-test execution, contract-test
  execution, @Spec annotation scanning, DisplayName consistency
- body references the scanner JSON output fields (unimplemented_rules /
  orphan_annotations)
- body carries the risk-tiered threshold application logic
  (high / medium / low -> thresholds)
- body contains FAIL commit-blocking instruction and the no-Java
  degradation (static @Spec scan only)
- v0.4: gate-result 产物路径统一到 specs/<feature>/docs/gate-result.md
  （由 run_gate 脚本写入，AI 仅读结果）

Reference: specs/001-speckit-testing-ext/contracts/commands.md (command 3)
           specs/001-speckit-testing-ext/contracts/testing-config.md
           specs/001-speckit-testing-ext/contracts/spec-annotation.md
"""

from pathlib import Path

import pytest

# spec-kit/ repository root (tests/extensions/ -> tests/ -> spec-kit/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = PROJECT_ROOT / "extensions" / "testing" / "commands"
GATE_MD = COMMANDS_DIR / "speckit.testing.gate.md"


def _read_frontmatter(text: str) -> str:
    """Return the raw frontmatter block (between leading `---` fences)."""
    assert text.startswith("---"), "command file must start with frontmatter"
    # find the closing `---`
    end = text.find("\n---", 3)
    assert end != -1, "frontmatter must be closed by a `---` fence"
    return text[3:end]


def _read_body(text: str) -> str:
    """Return the markdown body after the frontmatter."""
    end = text.find("\n---", 3)
    return text[end + 4 :]


# ── File & frontmatter ────────────────────────────────────────────────────────


class TestGateCommandExists:
    def test_file_exists(self):
        assert GATE_MD.is_file(), f"missing command file: {GATE_MD}"

    def test_frontmatter_has_description(self):
        text = GATE_MD.read_text(encoding="utf-8")
        fm = _read_frontmatter(text)
        assert "description:" in fm, "frontmatter must declare a description"
        # description value must be non-empty
        desc_line = next(line for line in fm.splitlines() if line.strip().startswith("description:"))
        assert len(desc_line.split(":", 1)[1].strip().strip('"').strip()) > 0


# ── scripts: frontmatter block ────────────────────────────────────────────────


class TestGateScriptsFrontmatter:
    """The gate command invokes the @Spec annotation scanner via the
    `scripts:` frontmatter block (sh/ps/py three keys, behaviorally
    equivalent)."""

    def test_scripts_block_present(self):
        fm = _read_frontmatter(GATE_MD.read_text(encoding="utf-8"))
        assert "scripts:" in fm, "gate must declare a scripts: block"

    def test_scripts_sh_key(self):
        fm = _read_frontmatter(GATE_MD.read_text(encoding="utf-8"))
        assert "sh:" in fm, "scripts: must contain sh: key"

    def test_scripts_ps_key(self):
        fm = _read_frontmatter(GATE_MD.read_text(encoding="utf-8"))
        assert "ps:" in fm, "scripts: must contain ps: key"

    def test_scripts_py_key(self):
        fm = _read_frontmatter(GATE_MD.read_text(encoding="utf-8"))
        assert "py:" in fm, "scripts: must contain py: key"

    def test_scripts_reference_run_gate(self):
        """All three script keys must point at the run_gate orchestrator
        (v0.4: 门禁全逻辑下沉脚本，AI 仅读结果；file name stems may differ
        by language convention)."""
        fm = _read_frontmatter(GATE_MD.read_text(encoding="utf-8"))
        # at least the python entry must reference run_gate.py
        assert "run_gate.py" in fm, (
            "scripts.py: must reference scripts/python/run_gate.py"
        )

    def test_scripts_sh_references_run_gate_sh(self):
        fm = _read_frontmatter(GATE_MD.read_text(encoding="utf-8"))
        assert "run-gate.sh" in fm

    def test_scripts_ps_references_run_gate_ps1(self):
        fm = _read_frontmatter(GATE_MD.read_text(encoding="utf-8"))
        assert "run-gate.ps1" in fm


# ── Body: gate-result artifact path (v0.4) ───────────────────────────────────


class TestGateArtifactPath:
    """v0.4: gate-result 产物路径统一到 specs/<feature>/docs/gate-result.md
    （由 run_gate 脚本直接写入，AI 仅读结果不能补写）。"""

    def test_body_gate_result_path_in_docs(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "docs/gate-result.md" in body, (
            "gate body 必须声明 specs/<feature>/docs/gate-result.md 产物路径"
        )

    def test_body_gate_result_docs_dir_under_specs(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "specs/<feature>/docs/" in body, (
            "gate body 必须声明 specs/<feature>/docs/ 目录产物路径"
        )


# ── Body: four gate checks ────────────────────────────────────────────────────


class TestGateFourChecks:
    """contracts/commands.md command 3 processing logic enumerates four
    checks the gate must perform."""

    BODY_MARKERS = [
        # unit-test execution (mvn test + JaCoCo)
        "mvn test",
        # contract-test execution
        "契约测试",
        # @Spec annotation scanning
        "@Spec",
        # DisplayName consistency check
        "@DisplayName",
    ]

    def test_body_mentions_all_four_checks(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        missing = [m for m in self.BODY_MARKERS if m not in body]
        assert not missing, f"gate body missing check markers: {missing}"


# ── Body: scanner JSON output fields ─────────────────────────────────────────


class TestGateScannerJsonFields:
    """The gate command must consume the scanner's output JSON, in
    particular the unimplemented_rules and orphan_annotations fields
    (see contracts/spec-annotation.md)."""

    def test_body_references_unimplemented_rules(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "unimplemented_rules" in body

    def test_body_references_orphan_annotations(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "orphan_annotations" in body


# ── Body: risk-tiered thresholds ─────────────────────────────────────────────


class TestGateRiskThresholds:
    """contracts/testing-config.md risk_overrides: high / medium / low each
    map to a distinct threshold set the gate must apply."""

    def test_body_mentions_high_risk(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "high" in body

    def test_body_mentions_medium_risk(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "medium" in body

    def test_body_mentions_low_risk(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "low" in body

    def test_body_applies_thresholds(self):
        """The body must contain logic that maps risk level -> threshold
        (high >=90% line, medium >=80%, low >=70% per testing-config.md)."""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "90" in body, "high risk line coverage threshold 90% missing"
        assert "80" in body, "medium risk line coverage threshold 80% missing"
        assert "70" in body, "low risk line coverage threshold 70% missing"


# ── Body: FAIL commit-blocking & degradation ─────────────────────────────────


class TestGateFailBlocking:
    def test_body_emits_fail_blocking_instruction(self):
        """On FAIL, gate must output an instruction that blocks the commit
        (after_implement hook, optional:false)."""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "FAIL" in body
        # blocking instruction must mention commit / 阻断 / 提交
        assert ("阻断" in body) or ("block" in body.lower())

    def test_body_describes_no_java_degradation(self):
        """When no Java env is available, gate degrades to static @Spec
        scanning only and must say so explicitly."""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        # degradation clause must reference Java env + static @Spec scan
        assert "降级" in body or "degradation" in body.lower()
        assert "静态" in body or "static" in body.lower()


# ── Body: sibling command token ──────────────────────────────────────────────


class TestGateSiblingCommandToken:
    """Per research.md decision 4: cross-agent references to sibling commands
    must use the `__SPECKIT_COMMAND_TESTING_<NAME>__` token rather than
    hardcoding `/speckit.testing.<name>`. On PASS, gate should hint at
    running report."""

    def test_body_uses_report_token(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "__SPECKIT_COMMAND_TESTING_REPORT__" in body

    def test_body_does_not_hardcode_report_path(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        # token must be used; hardcoding /speckit.testing.report is forbidden
        assert "/speckit.testing.report" not in body


# ── v0.5: 步骤 3 AI 语义交叉验证（SOFT）+ 步骤 5.5 对抗硬判 ─────────────────


class TestGateV05AI:

    def test_body_has_step_3_cross_validation(self):
        """gate.md 必须含步骤 3（AI 语义交叉验证，SOFT）。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "步骤 3" in body
        assert "AI 语义交叉验证" in body

    def test_body_marks_soft_and_no_override(self):
        """交叉验证是 SOFT 层，AI 不能改判 HARD 判定。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "SOFT" in body
        assert "不能改判" in body
        assert "不改判" in body

    def test_body_ai_cross_validation_governed_by_config(self):
        """gate.md 必须引用 testing-config 的 ai_cross_validation 配置。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "ai_cross_validation" in body

    def test_body_mentions_four_dimensions(self):
        """四维语义检查必须出现在 gate.md。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        for marker in ["规则-测试语义对齐", "断言质量", "覆盖率真实性", "@Spec 放置"]:
            assert marker in body, f"缺四维检查维度: {marker}"

    def test_body_only_appends_soft_section(self):
        """AI 仅追加 SOFT 段到 gate-result.md，不删除/修改脚本 HARD 段。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "仅追加" in body
        assert "AI 交叉验证（SOFT，不影响判定）" in body


class TestGateV05Adversarial:

    def test_body_has_step_5_5(self):
        """gate.md 步骤表必须含步骤 5.5（关键路径对抗校验）。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "5.5" in body
        assert "关键路径对抗校验" in body

    def test_body_references_critical_path_required(self):
        """步骤 5.5 由 critical_path_required 配置控制（可降级）。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "critical_path_required" in body

    def test_body_fail_condition_adversarial(self):
        """判定 FAIL 条件必须含：high 风险规则 0 对抗用例 -> FAIL。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert r"R(\d+)-对抗" in body or "Rn-对抗" in body
        assert "high 风险规则" in body

    def test_body_adversarial_degradation_table(self):
        """降级模式段必须解释 adversarial.enabled / critical_path_required 组合。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "对抗门禁降级模式" in body
        assert "adversarial.enabled" in body


# ── v0.5: config（testing-config.template.yml）新语义 ──────────────────────


class TestGateV05Config:

    CONFIG_PATH = PROJECT_ROOT / "extensions" / "testing" / "config" / "testing-config.template.yml"

    def test_config_has_ai_cross_validation(self):
        text = self.CONFIG_PATH.read_text(encoding="utf-8")
        assert "ai_cross_validation: true" in text

    def test_config_critical_path_required_new_semantics(self):
        text = self.CONFIG_PATH.read_text(encoding="utf-8")
        assert "critical_path_required" in text
        # v0.5 新语义注释：gate 硬判 / 降级
        assert "hard FAIL" in text or "硬判" in text
        assert "降级" in text

    def test_config_adversarial_enabled_comment(self):
        text = self.CONFIG_PATH.read_text(encoding="utf-8")
        assert "enabled" in text


# ── v0.6: 步骤 1 模块定位（9.2）+ 第 5 维直接测试覆盖（8.4）──────────────────


class TestGateV06ModuleLocate:
    """beta 简化: 步骤 1 模块定位——AI MUST 先 find . -name pom.xml 将
    --project 指向含 pom.xml 的模块目录；run_gate 不做模块自动探测。"""

    def test_body_has_project_flag_instruction(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "--project" in body, "gate 步骤 1 必须说明 --project 指向模块目录"
        assert "pom.xml" in body

    def test_body_has_find_probe_instruction(self):
        """AI MUST 先 find . -name pom.xml 定位模块目录。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "find . -name pom.xml" in body, "缺少 find . -name pom.xml 探测指令"

    def test_body_ai_must_locate_module(self):
        """AI MUST 先 find 定位含 pom.xml 的模块目录再传 --project。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "MUST" in body, "模块定位必须是 MUST 级指令"
        assert "find . -name pom.xml" in body
        assert "--project" in body

    def test_body_run_gate_no_auto_probe(self):
        """run_gate 不做模块自动探测（POM 定位由 AI 负责）。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "不做模块自动探测" in body, "必须声明 run_gate 不做模块自动探测"
        assert "_locate_module" not in body, "已删除 _locate_module 模块自动定位"
        assert "--auto-locate" not in body, "已删除 --auto-locate 参数"


class TestGateV06FifthDimension:
    """v0.6 8.4: AI 交叉验证第 5 维——直接测试覆盖（每条规则至少一个直接单测）。"""

    def test_body_has_fifth_dimension(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "直接测试覆盖" in body, "交叉验证必须含第 5 维直接测试覆盖（8.4）"

    def test_body_fifth_dimension_direct_unit_test_rule(self):
        """第 5 维语义：每条规则至少一个直接单测，仅间接覆盖 -> WARN。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "直接单测" in body
        assert "WARN" in body, "仅间接覆盖时应 WARN 建议补直接单测"

    def test_body_fifth_dimension_in_dimension_table(self):
        """第 5 维必须与四维同处交叉验证维度表中。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        for marker in ["规则-测试语义对齐", "断言质量", "覆盖率真实性", "@Spec 放置", "直接测试覆盖"]:
            assert marker in body, f"交叉验证维度表缺: {marker}"


# ── v0.6: 漂移处置决策矩阵（9.8）─────────────────────────────────────────────


class TestGateV06DriftDecisionMatrix:
    """v0.6 9.8: gate FAIL 后归因与处置——铁律 + 归因三问 + 决策矩阵
    （AI 在 SOFT 段给建议归因，不自动改判）。"""

    def test_body_has_iron_rule(self):
        """铁律：永远不允许直接改 test 适配 code。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "铁律" in body
        assert "改 test 适配 code" in body, "铁律必须显式禁止改 test 适配 code"

    def test_body_has_attribution_three_questions(self):
        """归因三问：差异定位 / 谁主张谁复核 / 改 spec/code/test 哪个。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "归因三问" in body
        assert "差异在哪个文件" in body, "归因一问：差异在哪个文件/行/字段"
        assert "谁主张谁复核" in body, "归因二问：谁主张谁复核"
        assert "改 spec/code/test" in body, "归因三问：改 spec/code/test 哪个"

    def test_body_has_decision_matrix_table(self):
        """决策矩阵四行：code 不满足 spec / test 漏场景 / spec 有歧义 / code 多于 spec。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "决策矩阵" in body
        for row in ["code 不满足 spec", "test 漏场景", "spec 有歧义", "code 多于 spec"]:
            assert row in body, f"决策矩阵缺漂移类型行: {row}"

    def test_body_decision_matrix_test_fix_driven_by_spec(self):
        """test 漏场景行：补测试由 spec 派生逻辑驱动，非适配 code。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "由 spec 派生逻辑驱动" in body, "补测试必须由 spec 派生逻辑驱动"

    def test_body_drift_framework_does_not_override(self):
        """漂移处置框架在 SOFT 段给建议归因，不自动改判 HARD 判定。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "不自动改判" in body, "决策矩阵不得自动改判（SOFT 层）"


# ── beta 简化: diff coverage 语义（替换 v0.6 9.4 作用域） ────────────────────


class TestGateBetaDiffCoverage:
    """beta 简化: diff coverage 语义——--diff-threshold（默认 80）与
    --diff-base（MR merge-base，默认工作区 vs HEAD）；全量 mvn clean test
    永远跑；无 git 回退全量阈值判定；无 Java 变更跳过。"""

    def test_body_has_diff_threshold(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "--diff-threshold" in body, "必须声明 --diff-threshold 参数"

    def test_body_diff_threshold_default_80(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "默认 80" in body, "diff-threshold 默认值必须为 80"

    def test_body_has_diff_base(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "--diff-base" in body, "必须声明 --diff-base 参数"

    def test_body_diff_base_merge_base(self):
        """--diff-base 用于 MR 场景（merge-base 对比）。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "merge-base" in body, "diff-base 必须说明 merge-base 对比"

    def test_body_diff_base_default_worktree_vs_head(self):
        """默认工作区 vs HEAD（gate.md 中 '工作区 vs' 与 'HEAD' 可能跨行）。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "工作区 vs" in body, "diff-base 默认必须为工作区 vs HEAD"
        assert "HEAD" in body

    def test_body_full_mvn_clean_test_always_runs(self):
        """全量 mvn clean test 永远跑（回归盲区兜底）。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "全量" in body and "永远跑" in body, "必须声明全量 mvn clean test 永远跑"

    def test_body_no_git_fallback_all(self):
        """无 git 仓库时回退全量聚合阈值判定。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "无 git" in body, "必须声明无 git 回退全量阈值判定"
        assert "回退全量" in body

    def test_body_no_java_change_skip(self):
        """无 Java 变更时该维度跳过（不 FAIL）。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "无 Java 变更" in body, "必须声明无 Java 变更时跳过"
        assert "跳过" in body

    def test_body_removed_coverage_scope(self):
        """已删除 --coverage-scope / --baseline 作用域方案。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "--coverage-scope" not in body, "已删除 --coverage-scope 参数"
        assert "--baseline" not in body, "已删除 --baseline 参数"


# ── beta 简化: 降级新语义（无 java/mvn 或 --project 无 pom.xml） ─────────────


class TestGateBetaDegradation:
    """beta 简化: 降级语义 = 无 java/mvn 可执行 或 --project 指向目录无
    pom.xml（AI 定位错误）。"""

    def test_body_degraded_no_java_mvn(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "无 java/mvn" in body, "降级语义必须含无 java/mvn"

    def test_body_degraded_project_no_pom(self):
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "无 pom.xml" in body, "降级语义必须含 --project 目录无 pom.xml"

    def test_body_degraded_ai_locate_error(self):
        """--project 传错（目录无 pom.xml）即降级并提示。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "定位错误" in body, "降级语义必须说明 --project 传错（AI 定位错误）"

    def test_body_degraded_reason_field(self):
        """降级时输出 degraded_reason。"""
        body = _read_body(GATE_MD.read_text(encoding="utf-8"))
        assert "degraded_reason" in body, "降级时必须输出 degraded_reason"
