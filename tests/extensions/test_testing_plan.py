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

    def test_body_generates_contract_test_cases(self):
        """Step 2: each contract -> contract test cases (1 positive + 1 per
        error code)."""
        body = _read_body(PLAN_MD.read_text(encoding="utf-8"))
        assert "契约测试" in body
        assert "CT-" in body or "CT" in body

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
