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


# ── Body: v0.63 双源规则变更提取 + 顶层锚 FR-xxx ─────────────────────────────


class TestImpactV063DualSourceExtraction:
    """v0.63 3.4: impact 步骤 1 规则变更提取改为双源设计——权威源 =
    spec.md `### Functional Requirements` 段（FR-001）优先 / `## Business Rules`
    段（R\\d+）兼容回落 + 代码侧 @Spec 差分补充信号；affected_rules 统一顶层锚
    FR-xxx 格式（子编号不进入）。"""

    def test_body_declares_dual_source_design(self):
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "### Functional Requirements" in body, "权威源必须指向 FR 段"
        assert "优先" in body, "FR 段必须标注为优先取用"

    def test_body_fr_section_is_primary_authority(self):
        """权威源 = spec.md ### Functional Requirements 段（FR-001）优先。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "### Functional Requirements" in body, "权威源必须指向 FR 段"
        assert "优先" in body, "FR 段必须标注为优先取用"

    def test_body_business_rules_fallback(self):
        """## Business Rules 段兼容回落（老项目 v0.6 行为）。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "Business Rules" in body
        assert "回落" in body, "Business Rules 段必须标注为兼容回落路径"

    def test_body_code_side_spec_diff(self):
        """增补代码侧 @Spec 差分信号（新增/删除/移动注解）。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "@Spec 差分" in body, "v0.63 3.4.3: 必须含代码侧 @Spec 差分信号"
        assert "合并去重" in body, "@Spec 差分结果必须与权威源 diff 合并去重"

    def test_body_subscenario_excluded_from_affected(self):
        """子场景编号（FR-001-R1）不进入 affected_rules——只到顶层锚。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "不进入 affected_rules" in body, (
            "v0.63 3.4.1: 子场景编号必须声明不进入 affected_rules"
        )

    def test_body_affected_rules_top_level_anchor(self):
        """affected_rules 统一顶层锚 FR-xxx 格式（不用子编号）。"""
        body = _read_body(IMPACT_MD.read_text(encoding="utf-8"))
        assert "顶层锚 FR-xxx" in body or "顶层锚粒度" in body, (
            "affected_rules 必须统一顶层锚 FR-xxx 格式"
        )
        assert "子场景编号" in body, "必须声明子场景编号（FR-001-R1）相关约束"
