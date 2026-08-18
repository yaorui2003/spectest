"""
T018 - Tests for the speckit.testing.impact command markdown.

Validates that `extensions/testing/commands/speckit.testing.impact.md`:
- exists
- has frontmatter with a description
- body covers:
  - spec.md diff parsing (changed business_rules)
  - repository code-structure dependency analysis
  - risk tiering (high / medium / low)
  - affected-rules list output
  - suggested test strategy

Reference: specs/001-speckit-testing-ext/contracts/commands.md (command 1)
"""

from pathlib import Path

# spec-kit/ repository root (tests/extensions/ -> tests/ -> spec-kit/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = PROJECT_ROOT / "extensions" / "testing" / "commands"
IMPACT_MD = COMMANDS_DIR / "speckit.testing.impact.md"


def _read_frontmatter(text: str) -> str:
    assert text.startswith("---"), "command file must start with frontmatter"
    end = text.find("\n---", 3)
    assert end != -1, "frontmatter must be closed by a `---` fence"
    return text[3:end]


def _read_body(text: str) -> str:
    end = text.find("\n---", 3)
    return text[end + 4 :]


# ── File & frontmatter ────────────────────────────────────────────────────────


class TestImpactCommandExists:
    def test_file_exists(self):
        assert IMPACT_MD.is_file(), f"missing command file: {IMPACT_MD}"

    def test_frontmatter_has_description(self):
        text = IMPACT_MD.read_text(encoding="utf-8")
        fm = _read_frontmatter(text)
        assert "description:" in fm
        desc_line = next(
            line for line in fm.splitlines() if line.strip().startswith("description:")
        )
        assert len(desc_line.split(":", 1)[1].strip().strip('"').strip()) > 0


# ── Body: change parsing / dependency analysis / risk / output ───────────────


class TestImpactBodySections:
    """contracts/commands.md command 1 processing logic."""

    def test_body_parses_spec_changes(self):
        """Step 1: parse spec.md diff -> extract changed business_rules."""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert ("business_rules" in body) or ("business rule" in body.lower())

    def test_body_does_dependency_analysis(self):
        """Step 2: scan repo code structure -> identify affected code
        locations (class/method)."""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert ("依赖" in body) or ("dependency" in body.lower())
        assert ("代码结构" in body) or ("code structure" in body.lower())

    def test_body_assigns_risk_levels(self):
        """Step 3: risk tiering - high (funds/permission/data integrity),
        medium (business flow), low (validation)."""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "high" in body
        assert "medium" in body
        assert "low" in body

    def test_body_outputs_affected_rules_list(self):
        """Step 4 (output): affected rule-id list."""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert ("受影响规则" in body) or ("affected_rules" in body)

    def test_body_outputs_test_strategy(self):
        """Output: suggested test strategy (full / incremental +
        contract-test/unit-test count suggestions)."""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert ("建议测试策略" in body) or ("test strategy" in body.lower())

    def test_body_mentions_impact_report_artifact(self):
        """Output artifact name is ImpactReport."""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "ImpactReport" in body


# ── Body: functional case set (TC, e2e planning, v0.6) ───────────────────────


class TestImpactE2ECaseSet:
    """v0.6: impact 生成功能测试案例集（TC-xx，供前端 e2e 测试 AI 使用）。

    断言只检查内容关键词，不检查表格框线字符（避免冗余）。
    """

    def test_body_generates_functional_case_set(self):
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "功能测试案例集" in body
        assert "TC-" in body

    def test_body_case_set_has_type_categories(self):
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "正向" in body
        assert "异常" in body
        assert "交互" in body

    def test_body_case_set_is_self_contained(self):
        """每条用例自包含（前置/步骤/预期），可独立转发给 e2e AI。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "自包含" in body
        assert "前置" in body
        assert "预期" in body

    def test_body_case_set_traces_rules(self):
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "关联" in body
        assert "business_rules" in body

    def test_body_case_set_has_e2e_ai_guidance(self):
        """面向 e2e 测试 AI 的提示：具体测试数据/精确文案，禁含糊表述。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "e2e" in body.lower()
        assert "测试数据" in body
        assert "禁止" in body

    def test_body_case_set_not_in_gate(self):
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "不进门槛" in body or "不进门禁" in body

    def test_body_case_set_uses_given_when_then(self):
        """v0.6: 案例集按 Given-When-Then 编写（e2e AI 易解析）。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "**Given**" in body
        assert "**When**" in body
        assert "**Then**" in body

    def test_body_case_set_references_e2e_template(self):
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "e2e-case-template" in body

    def test_body_case_set_no_ascii_table(self):
        """不再用 ASCII 表格（冗余），改结构化 markdown 块。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "┌" not in body, "v0.6: 功能测试案例集应弃用 ASCII 框线表格"


# ── Body: risk tiering rules (v0.6 9.7) ──────────────────────────────────────


class TestImpactRiskTieringRules:
    """v0.6 9.7: 风险分级规则化（替代 AI 自由裁量，判定可复现、可测试）。

    命中方式评分（直接命中->high / 间接命中->medium / 边缘->low）+ 提升规则
    （Mapper/SQL/Flyway、pom/package.json、application*.yml 各升一级，high
    封顶）+ 输出固定三档。
    """

    def test_body_has_ruleized_scoring(self):
        """风险分级必须是规则化评分（非自由裁量）。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "规则化" in body, "v0.6 9.7: 风险分级必须规则化（替代自由裁量）"
        assert "评分" in body

    def test_body_has_three_hit_types(self):
        """命中方式三档：直接命中 / 间接命中 / 边缘。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "直接命中" in body
        assert "间接命中" in body
        assert "边缘" in body

    def test_body_maps_hit_types_to_risk_levels(self):
        """直接命中->high / 间接命中->medium / 边缘->low 的映射必须出现。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        # 三档风险词 + 命中方式词同段出现（表格：| 直接命中 | `high` | ...）
        for marker in ["直接命中", "间接命中", "边缘", "high", "medium", "low"]:
            assert marker in body, f"风险分级规则缺关键词: {marker}"

    def test_body_has_boost_rules(self):
        """提升规则：*Mapper.java / *.sql / Flyway / pom.xml / package.json /
        application*.yml 各升一级。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "提升规则" in body
        for marker in [
            "*Mapper.java",
            "*.sql",
            "Flyway",
            "pom.xml",
            "package.json",
            "application*.yml",
            "升一级",
        ]:
            assert marker in body, f"提升规则缺关键词: {marker}"

    def test_body_high_capped_and_fixed_three_tiers(self):
        """high 封顶 + 输出固定三档，与 gate 步骤 5.5 对抗硬判对接。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "封顶" in body, "v0.6 9.7: 提升规则必须声明 high 封顶"
        assert "固定三档" in body, "v0.6 9.7: 输出必须固定三档 high/medium/low"


# ── Body: functional case set covered_rules (v0.6 9.9) ───────────────────────


class TestImpactCaseSetCoveredRules:
    """v0.6 9.9: functional case set 的关联规则字段即 covered_rules，供 gate
    步骤 1 e2e 用例选择执行求交消费。"""

    def test_body_declares_covered_rules_field(self):
        """步骤 5.2 必须声明关联规则字段即 covered_rules。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "covered_rules" in body
        assert "关联规则" in body

    def test_body_covered_rules_consumed_by_gate(self):
        """covered_rules 必须说明供 gate 求交 + e2e 选择执行消费（9.9）。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "求交" in body, "covered_rules 必须说明与受影响规则求交"
        assert "选择执行" in body, "covered_rules 必须说明 e2e 用例选择执行"

    def test_body_covered_rules_must_per_case(self):
        """契约不变量：每条 TC MUST 携带 covered_rules，缺失降级手工。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "MUST 携带" in body, "契约不变量必须要求每条 TC 携带 covered_rules"
        assert "降级手工" in body or "自动降级" in body


# ── Body: artifact path (v0.4) ───────────────────────────────────────────────


class TestImpactArtifactPath:
    """v0.4: impact-report 产物路径统一到 specs/<feature>/docs/impact-report.md
    （废弃 .specify/extensions/testing/）。"""

    def test_body_impact_report_path_in_docs(self):
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "specs/<feature>/docs/impact-report.md" in body, (
            "impact body 必须声明 specs/<feature>/docs/impact-report.md 产物路径"
        )

    def test_body_no_legacy_specify_path(self):
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert ".specify/extensions/testing/" not in body, (
            "v0.4: 废弃 .specify/extensions/testing/ 产物路径，应改为 "
            "specs/<feature>/docs/"
        )
