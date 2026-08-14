"""T030: validate_spec_format 脚本输出 JSON 契约校验。

校验 ``extensions/testing/scripts/python/validate_spec_format.py`` 输出：
- valid (bool) / errors (list) / warnings (list) / rules_found (list) / error_codes_found (list)

测试场景：
- 有效 spec.md（Business Rules + 连续 R1-R3）-> valid=true
- 缺 Business Rules 段 -> valid=false
- 规则编号断裂（R1, R3 缺 R2）-> valid=false
- 有 Error Code Definitions 段 -> error_codes_found 非空
- 无 Error Code Definitions 段 -> warnings 非空，valid 仍 true
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PY_SCRIPT = (
    PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python"
    / "validate_spec_format.py"
)


def _run_py(spec_path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(PY_SCRIPT),
         "--spec", str(spec_path),
         "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"validate_spec_format 退出码 {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return json.loads(result.stdout)


def _write_spec(tmp_path: Path, content: str) -> Path:
    spec = tmp_path / "spec.md"
    spec.write_text(content, encoding="utf-8")
    return spec


# ── 脚本存在性 ──────────────────────────────────────────────────────────────


def test_script_exists():
    assert PY_SCRIPT.is_file(), f"脚本不存在: {PY_SCRIPT}"


# ── 有效 spec.md ────────────────────────────────────────────────────────────


def test_valid_spec_with_sequential_rules(tmp_path: Path):
    """有效 spec.md：Business Rules + 连续 R1-R3 -> valid=true。"""
    spec = _write_spec(tmp_path, """\
# Feature

## Business Rules

- R1: 金额校验
- R2: 余额校验
- R3: 冻结校验

## API

POST /api/v1/transfer
""")
    data = _run_py(spec)
    assert data["valid"] is True
    assert data["errors"] == []
    assert data["rules_found"] == ["R1", "R2", "R3"]


def test_missing_business_rules_section(tmp_path: Path):
    """缺 Business Rules 段 -> valid=false，errors 含 Business Rules。"""
    spec = _write_spec(tmp_path, """\
# Feature

## API

POST /api/v1/transfer
""")
    data = _run_py(spec)
    assert data["valid"] is False
    assert any("Business Rules" in e for e in data["errors"])
    assert data["rules_found"] == []


def test_rule_numbering_gap(tmp_path: Path):
    """规则编号断裂（R1, R3 缺 R2）-> valid=false，errors 含 gap / R2。"""
    spec = _write_spec(tmp_path, """\
# Feature

## Business Rules

- R1: 金额校验
- R3: 冻结校验
""")
    data = _run_py(spec)
    assert data["valid"] is False
    assert any("R2" in e for e in data["errors"])


def test_with_error_code_definitions(tmp_path: Path):
    """有 Error Code Definitions 段 -> error_codes_found 非空。"""
    spec = _write_spec(tmp_path, """\
# Feature

## Business Rules

- R1: 金额校验

### Error Code Definitions

| Error Code | HTTP Status | Description |
|------------|------------|-------------|
| INVALID_AMOUNT | 400 | 金额非法 |
| ACCOUNT_NOT_FOUND | 404 | 账号不存在 |
""")
    data = _run_py(spec)
    assert data["valid"] is True
    assert "INVALID_AMOUNT" in data["error_codes_found"]
    assert "ACCOUNT_NOT_FOUND" in data["error_codes_found"]
    # 有 Error Code Definitions 段 -> 无 warning
    assert all("Error Code Definitions" not in w for w in data["warnings"])


def test_error_codes_no_noise(tmp_path: Path):
    """错误码提取不混入噪音（Bug #1）。

    ECD 段含 (a) HTML 注释行 <!-- OPTIONAL API errors -->、
    (b) Related Rule 列（R1..R7 值）、(c) HTTP Status 列、
    (d) 描述含全大写单词（HTTP/API）-> error_codes_found 恰好等于
    ["INVALID_AMOUNT", "ACCOUNT_NOT_FOUND"]，valid 仍 true。
    """
    spec = _write_spec(tmp_path, """\
# Feature

## Business Rules

- R1: 金额校验
- R2: 余额校验
- R3: 冻结校验

### Error Code Definitions

<!-- OPTIONAL API errors -->

| Error Code | HTTP Status | Description | Related Rule |
|------------|------------|-------------|--------------|
| INVALID_AMOUNT | 400 | 金额非法 HTTP | R1, R2, R3 |
| ACCOUNT_NOT_FOUND | 404 | 账号不存在 API | R4, R5, R6, R7 |
""")
    data = _run_py(spec)
    assert data["valid"] is True
    assert data["error_codes_found"] == ["INVALID_AMOUNT", "ACCOUNT_NOT_FOUND"]
    # 无噪音：不收集 HTTP / OPTIONAL / API / R1..R7
    assert all(c not in data["error_codes_found"] for c in ("HTTP", "OPTIONAL", "API"))
    assert all(not c.startswith("R") for c in data["error_codes_found"])


def test_without_error_code_definitions(tmp_path: Path):
    """无 Error Code Definitions 段 -> warnings 非空，valid 仍 true。"""
    spec = _write_spec(tmp_path, """\
# Feature

## Business Rules

- R1: 金额校验
""")
    data = _run_py(spec)
    assert data["valid"] is True
    assert any("Error Code Definitions" in w for w in data["warnings"])
    assert data["error_codes_found"] == []
