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
