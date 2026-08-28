"""
T021 - Tests for the speckit.testing.plan command markdown.

Validates that `extensions/testing/commands/speckit.testing.plan.md`:
- exists
- has frontmatter with a description
- body covers:
  - reads ImpactReport + contracts/ to generate test case list
  - applies risk-tiered acceptance thresholds
  - produces schedule / sequencing recommendation
- references the test-plan-template

Reference: specs/001-speckit-testing-ext/contracts/commands.md (command 2)
"""

from pathlib import Path

# spec-kit/ repository root (tests/extensions/ -> tests/ -> spec-kit/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = PROJECT_ROOT / "extensions" / "testing" / "commands"
PLAN_MD = COMMANDS_DIR / "speckit.testing.plan.md"


def _read_frontmatter(text: str) -> str:
    assert text.startswith("---"), "command file must start with frontmatter"
    end = text.find("\n---", 3)
    assert end != -1, "frontmatter must be closed by a `---` fence"
    return text[3:end]


def _read_body(text: str) -> str:
    end = text.find("\n---", 3)
    return text[end + 4 :]


# ── File & frontmatter ────────────────────────────────────────────────────────


class TestPlanCommandExists:
    def test_file_exists(self):
        assert PLAN_MD.is_file(), f"missing command file: {PLAN_MD}"

    def test_frontmatter_has_description(self):
        text = PLAN_MD.read_text(encoding="utf-8")
        fm = _read_frontmatter(text)
        assert "description:" in fm
        desc_line = next(
            line for line in fm.splitlines() if line.strip().startswith("description:")
        )
        assert len(desc_line.split(":", 1)[1].strip().strip('"').strip()) > 0


# ── Body: inputs / case generation / thresholds / scheduling ─────────────────


class TestPlanBodySections:
    """contracts/commands.md command 2 processing logic."""

    def test_body_reads_impact_report(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "ImpactReport" in body

    def test_body_reads_contracts(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "contracts" in body

    def test_body_reads_spec_md(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "spec.md" in body

    def test_body_generates_unit_test_cases(self):
        """Step 3: each business rule -> unit test cases (normal/abnormal/
        boundary)."""
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "单测" in body or "单元测试" in body
        assert "UT-" in body or "UT" in body

    def test_body_applies_risk_thresholds(self):
        """Step 1: read risk level -> apply acceptance threshold
        (high 90/100, medium 80/95, low 70/95)."""
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "high" in body
        assert "medium" in body
        assert "low" in body
        # at least the high-risk line coverage threshold (90) must appear
        assert "90" in body

    def test_body_emits_schedule_recommendation(self):
        """Step 4: scheduling recommendation (contract tests first, unit
        tests after)."""
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert ("排期" in body) or ("schedule" in body.lower())


# ── Body: test-plan-template reference ────────────────────────────────────────


class TestPlanTemplateReference:
    def test_body_references_test_plan_template(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "test-plan-template" in body


# ── Body: artifact path (v0.4) ───────────────────────────────────────────────


class TestPlanArtifactPath:
    """v0.4: test-plan 产物路径统一到 specs/<feature>/docs/test-plan.md
    （废弃 .specify/extensions/testing/）。"""

    def test_body_test_plan_path_in_docs(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "specs/<feature>/docs/test-plan.md" in body, (
            "plan body 必须声明 specs/<feature>/docs/test-plan.md 产物路径"
        )

    def test_body_no_legacy_specify_path(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert ".specify/extensions/testing/" not in body, (
            "v0.4: 废弃 .specify/extensions/testing/ 产物路径，应改为 "
            "specs/<feature>/docs/"
        )


# ── Body: v0.63 业务规则细分（可选参考层）+ 单测质量规范 ─────────────────────


class TestPlanV063QualityAndBreakdown:
    """v0.63: plan 步骤 2.75 业务规则细分（可选参考层，不承载权威）+ 部门
    单测规范落地（BCDE/独立性/命名/DB/禁 System.out）+ 覆盖率推荐目标。"""

    def test_body_uses_bcde_dimensions(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "BCDE" in body, "v0.63: 用例维度必须显式 BCDE 四原则"
        assert "D" in body, "BCDE 须补 D（结合设计文档）"

    def test_body_enforces_test_independence(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "独立性" in body, "v0.63 4.1: 必须含用例独立性条目（AIR-I）"
        assert "禁止 test A 调用 test B" in body, (
            "独立性须禁止用例间互相调用/依赖执行次序"
        )

    def test_body_enforces_naming_standards(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "命名规范" in body, "v0.63 4.1: 必须含测试命名规范条目"
        assert "被测类" in body and "Test" in body, (
            "命名规范须覆盖测试类 = 被测类 + Test"
        )

    def test_body_enforces_db_test_hygiene(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "DB 测试" in body, "v0.63 4.1: 必须含 DB 测试条目"
        assert "自动回滚" in body, "DB 测试须要求自动回滚机制"

    def test_body_forbids_system_out_verification(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "System.out" in body, "v0.63 4.1: 必须禁止 System.out 人肉验证"

    def test_body_emits_coverage_recommendation(self):
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "覆盖率推荐目标" in body, "v0.63 4.1: 步骤 1 必须补覆盖率推荐目标注"
        assert "方法覆盖率 50%" in body, "推荐目标须含方法 50% / 语句 30% / 核心 100%"
        assert "核心模块" in body, "推荐目标须含核心模块语句+分支 100%"
