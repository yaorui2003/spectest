"""
T024 - Tests for the speckit.testing.report command markdown.

Validates that `extensions/testing/commands/speckit.testing.report.md`:
- exists
- has frontmatter with a description
- body covers:
  - reject when gate has not been executed
  - aggregate test results (coverage + pass rate)
  - generate traceability matrix
  - reference (not regenerate) impact artifacts
- references the spec-trace-matrix template

Reference: specs/001-speckit-testing-ext/contracts/commands.md (command 4)
"""

from pathlib import Path

# spec-kit/ repository root (tests/extensions/ -> tests/ -> spec-kit/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = PROJECT_ROOT / "extensions" / "testing" / "commands"
REPORT_MD = COMMANDS_DIR / "speckit.testing.report.md"


def _read_frontmatter(text: str) -> str:
    assert text.startswith("---"), "command file must start with frontmatter"
    end = text.find("\n---", 3)
    assert end != -1, "frontmatter must be closed by a `---` fence"
    return text[3:end]


def _read_body(text: str) -> str:
    end = text.find("\n---", 3)
    return text[end + 4 :]


# ── File & frontmatter ────────────────────────────────────────────────────────


class TestReportCommandExists:
    def test_file_exists(self):
        assert REPORT_MD.is_file(), f"missing command file: {REPORT_MD}"

    def test_frontmatter_has_description(self):
        text = REPORT_MD.read_text(encoding="utf-8")
        fm = _read_frontmatter(text)
        assert "description:" in fm
        desc_line = next(
            line for line in fm.splitlines() if line.strip().startswith("description:")
        )
        assert len(desc_line.split(":", 1)[1].strip().strip('"').strip()) > 0


# ── Body: gate-not-run rejection / aggregation / matrix / impact ref ─────────


class TestReportBodySections:
    """contracts/commands.md command 4 processing logic."""

    def test_body_rejects_when_gate_not_run(self):
        """Step 1: refuse to generate report if gate has not been run, prompt
        to run the gate first."""
        body = _read_body(REPORT_MD.read_text(encoding="utf-8"))
        assert ("门禁" in body) or ("gate" in body.lower())
        assert ("未执行" in body) or ("not run" in body.lower()) or ("refuse" in body.lower())

    def test_body_aggregates_test_results(self):
        """Step 2: summarize test execution results (coverage + pass rate)."""
        body = _read_body(REPORT_MD.read_text(encoding="utf-8"))
        assert ("覆盖率" in body) or ("coverage" in body.lower())
        assert ("通过率" in body) or ("pass rate" in body.lower()) or ("pass_rate" in body)

    def test_body_generates_traceability_matrix(self):
        """Step 3: build Spec traceability matrix
        (R1..Rn -> @Spec code location -> unit-test @DisplayName ->
        contract-test CT id)."""
        body = _read_body(REPORT_MD.read_text(encoding="utf-8"))
        assert ("追溯矩阵" in body) or ("traceability" in body.lower())
        assert "TraceabilityMatrix" in body

    def test_body_references_impact_artifacts(self):
        """Step 4: reference (not regenerate) ImpactReport artifacts."""
        body = _read_body(REPORT_MD.read_text(encoding="utf-8"))
        assert "ImpactReport" in body
        assert ("引用" in body) or ("reference" in body.lower()) or ("不重复" in body)


# ── Body: spec-trace-matrix template reference ────────────────────────────────


class TestReportTemplateReference:
    def test_body_references_spec_trace_matrix_template(self):
        body = _read_body(REPORT_MD.read_text(encoding="utf-8"))
        assert "spec-trace-matrix" in body


# ── Body: sibling command token ──────────────────────────────────────────────


class TestReportSiblingCommandToken:
    """Per research.md decision 4: cross-agent references to sibling
    commands must use `__SPECKIT_COMMAND_TESTING_<NAME>__` tokens rather
    than hardcoding `/speckit.testing.<name>`."""

    def test_body_does_not_hardcode_impact_path(self):
        body = _read_body(REPORT_MD.read_text(encoding="utf-8"))
        assert "/speckit.testing.impact" not in body

    def test_body_does_not_hardcode_gate_path(self):
        body = _read_body(REPORT_MD.read_text(encoding="utf-8"))
        assert "/speckit.testing.gate" not in body
