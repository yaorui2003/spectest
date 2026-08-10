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
