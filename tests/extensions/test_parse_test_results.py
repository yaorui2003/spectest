"""T031: parse_test_results 脚本输出 JSON 契约校验。

校验 ``extensions/testing/scripts/python/parse_test_results.py`` 输出：
- unit_tests (total/passed/failed/pass_rate)
- contract_tests (total/passed/failed/pass_rate)
- coverage (line/branch/method/instruction/complexity_coverage)

测试场景：
- 有效 surefire + jacoco -> 正确分类与计数
- 缺 surefire 目录 -> 测试计数全 0
- 缺 jacoco 文件 -> 覆盖率全 0
- 空 surefire 目录（无 XML）-> 测试计数全 0
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PY_SCRIPT = (
    PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python"
    / "parse_test_results.py"
)


def _run_py(surefire_dir: Path, jacoco_file: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(PY_SCRIPT),
         "--surefire", str(surefire_dir),
         "--jacoco", str(jacoco_file),
         "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"parse_test_results 退出码 {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return json.loads(result.stdout)


SUREFIRE_UNIT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.AccountServiceTest" tests="3" failures="0" errors="0">
  <testcase name="shouldRejectZeroAmount" classname="com.example.AccountServiceTest" time="0.001"/>
  <testcase name="shouldPassValidTransfer" classname="com.example.AccountServiceTest" time="0.002"/>
  <testcase name="shouldRejectSelfTransfer" classname="com.example.AccountServiceTest" time="0.001"/>
</testsuite>
"""

SUREFIRE_CONTRACT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.TransferContractTest" tests="2" failures="1" errors="0">
  <testcase name="shouldReturnSuccessOnValidRequest" classname="com.example.TransferContractTest" time="0.005"/>
  <testcase name="shouldReturn400OnInvalidAmount" classname="com.example.TransferContractTest" time="0.003">
    <failure message="expected 400 but was 200"/>
  </testcase>
</testsuite>
"""

JACOCO_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<report>
  <counter type="LINE" missed="5" covered="50"/>
  <counter type="BRANCH" missed="3" covered="15"/>
  <counter type="METHOD" missed="2" covered="20"/>
  <counter type="INSTRUCTION" missed="10" covered="90"/>
  <counter type="COMPLEXITY" missed="3" covered="10"/>
</report>
"""


def test_script_exists():
    assert PY_SCRIPT.is_file(), f"脚本不存在: {PY_SCRIPT}"


def test_parse_valid_surefire_and_jacoco(tmp_path: Path):
    """有效 surefire（1 unit + 1 ContractTest）+ jacoco -> 正确分类与计数。"""
    sf_dir = tmp_path / "surefire-reports"
    sf_dir.mkdir()
    (sf_dir / "TEST-AccountServiceTest.xml").write_text(SUREFIRE_UNIT_XML, encoding="utf-8")
    (sf_dir / "TEST-TransferContractTest.xml").write_text(SUREFIRE_CONTRACT_XML, encoding="utf-8")
    jacoco = tmp_path / "jacoco.xml"
    jacoco.write_text(JACOCO_XML, encoding="utf-8")

    data = _run_py(sf_dir, jacoco)
    # unit: 3 tests, 3 passed, 0 failed
    assert data["unit_tests"]["total"] == 3
    assert data["unit_tests"]["passed"] == 3
    assert data["unit_tests"]["failed"] == 0
    assert data["unit_tests"]["pass_rate"] == 100
    # contract: 2 tests, 1 passed, 1 failed
    assert data["contract_tests"]["total"] == 2
    assert data["contract_tests"]["passed"] == 1
    assert data["contract_tests"]["failed"] == 1
    assert data["contract_tests"]["pass_rate"] == 50
    # coverage: LINE 50/55=91%, BRANCH 15/18=83%, METHOD 20/22=91%, INSTRUCTION 90/100=90%, COMPLEXITY 10/13=77%
    assert data["coverage"]["line_coverage"] == 91
    assert data["coverage"]["branch_coverage"] == 83
    assert data["coverage"]["method_coverage"] == 91
    assert data["coverage"]["instruction_coverage"] == 90
    assert data["coverage"]["complexity_coverage"] == 77


def test_missing_surefire_dir(tmp_path: Path):
    """缺 surefire 目录 -> 测试计数全 0。"""
    sf_dir = tmp_path / "no-such-dir"
    jacoco = tmp_path / "jacoco.xml"
    jacoco.write_text(JACOCO_XML, encoding="utf-8")

    data = _run_py(sf_dir, jacoco)
    assert data["unit_tests"]["total"] == 0
    assert data["unit_tests"]["pass_rate"] == 0
    assert data["contract_tests"]["total"] == 0
    assert data["contract_tests"]["pass_rate"] == 0
    # jacoco 仍能解析
    assert data["coverage"]["line_coverage"] == 91


def test_missing_jacoco_file(tmp_path: Path):
    """缺 jacoco 文件 -> 覆盖率全 0。"""
    sf_dir = tmp_path / "surefire-reports"
    sf_dir.mkdir()
    (sf_dir / "TEST-AccountServiceTest.xml").write_text(SUREFIRE_UNIT_XML, encoding="utf-8")
    jacoco = tmp_path / "no-such-file.xml"

    data = _run_py(sf_dir, jacoco)
    # surefire 仍能解析
    assert data["unit_tests"]["total"] == 3
    # coverage 全 0
    for key in ("line_coverage", "branch_coverage", "method_coverage",
                "instruction_coverage", "complexity_coverage"):
        assert data["coverage"][key] == 0


def test_empty_surefire_dir(tmp_path: Path):
    """空 surefire 目录（无 XML）-> 测试计数全 0。"""
    sf_dir = tmp_path / "empty-surefire"
    sf_dir.mkdir()
    jacoco = tmp_path / "jacoco.xml"
    jacoco.write_text(JACOCO_XML, encoding="utf-8")

    data = _run_py(sf_dir, jacoco)
    assert data["unit_tests"]["total"] == 0
    assert data["contract_tests"]["total"] == 0
