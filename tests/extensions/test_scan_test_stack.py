"""T032: scan_test_stack 脚本输出 JSON 契约校验。

校验 ``extensions/testing/scripts/python/scan_test_stack.py`` 输出：
- forbidden_findings: list of {type, file, line, detail}

测试场景：
- 干净测试文件（无禁用项）-> forbidden_findings 空
- 含 PowerMock 导入 -> type=powermock
- 含 @SpringBootTest -> type=springboottest
- 多文件多违规 -> 正确计数与排序
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PY_SCRIPT = (
    PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python"
    / "scan_test_stack.py"
)


def _run_py(source_dir: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(PY_SCRIPT),
         "--source", str(source_dir),
         "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"scan_test_stack 退出码 {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return json.loads(result.stdout)


CLEAN_JAVA = """\
package com.example;

import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;

class AccountServiceTest {
    @Test
    void shouldPass() { }
}
"""

POWERMOCK_JAVA = """\
package com.example;

import org.powermock.api.mockito.PowerMockito;
import org.junit.jupiter.api.Test;

class PowerMockTest {
    @Test
    void test() { }
}
"""

SPRINGBOOT_JAVA = """\
package com.example;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
class IntegrationTest {
    @Test
    void test() { }
}
"""


def test_script_exists():
    assert PY_SCRIPT.is_file(), f"脚本不存在: {PY_SCRIPT}"


def test_clean_files_no_findings(tmp_path: Path):
    """干净测试文件（无禁用项）-> forbidden_findings 空。"""
    src = tmp_path / "src"
    src.mkdir()
    (src / "AccountServiceTest.java").write_text(CLEAN_JAVA, encoding="utf-8")

    data = _run_py(src)
    assert data["forbidden_findings"] == []


def test_powermock_import_detected(tmp_path: Path):
    """含 PowerMock 导入 -> finding with type=powermock。"""
    src = tmp_path / "src"
    src.mkdir()
    (src / "PowerMockTest.java").write_text(POWERMOCK_JAVA, encoding="utf-8")

    data = _run_py(src)
    assert len(data["forbidden_findings"]) == 1
    finding = data["forbidden_findings"][0]
    assert finding["type"] == "powermock"
    assert "PowerMockTest.java" in finding["file"]
    assert finding["line"] == 3
    assert "powermock" in finding["detail"].lower()


def test_springboottest_detected(tmp_path: Path):
    """含 @SpringBootTest -> finding with type=springboottest。"""
    src = tmp_path / "src"
    src.mkdir()
    (src / "IntegrationTest.java").write_text(SPRINGBOOT_JAVA, encoding="utf-8")

    data = _run_py(src)
    assert len(data["forbidden_findings"]) == 1
    finding = data["forbidden_findings"][0]
    assert finding["type"] == "springboottest"
    assert "IntegrationTest.java" in finding["file"]
    assert "@SpringBootTest" in finding["detail"]


def test_multiple_findings_sorted(tmp_path: Path):
    """多文件多违规 -> 正确计数与文件排序。"""
    src = tmp_path / "src"
    src.mkdir()
    # ATest.java 含 powermock（排序在前）
    (src / "ATest.java").write_text(POWERMOCK_JAVA, encoding="utf-8")
    # ZTest.java 含 @SpringBootTest（排序在后）
    (src / "ZTest.java").write_text(SPRINGBOOT_JAVA, encoding="utf-8")

    data = _run_py(src)
    assert len(data["forbidden_findings"]) == 2
    # 按文件路径排序，ATest 在前
    assert "ATest.java" in data["forbidden_findings"][0]["file"]
    assert data["forbidden_findings"][0]["type"] == "powermock"
    assert "ZTest.java" in data["forbidden_findings"][1]["file"]
    assert data["forbidden_findings"][1]["type"] == "springboottest"
