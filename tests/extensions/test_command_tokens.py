"""T028: 命令 .md 文件兄弟命令引用令牌校验。

校验 4 个命令 .md 文件（``commands/speckit.testing.{gate,impact,plan,report}.md``）：

- 引用兄弟命令时使用令牌 ``__SPECKIT_COMMAND_TESTING_*__``
  （如 ``__SPECKIT_COMMAND_TESTING_REPORT__``、``__SPECKIT_COMMAND_TESTING_IMPACT__``）
- **不**硬编码字面调用路径（如 ``/speckit.testing.report`` 或
  ``EXECUTE_COMMAND: speckit.testing.report``），应通过令牌渲染
- 允许在 frontmatter 的 description 字段或说明性文字中出现命令名
  （如 description: "测试报告"、正文中的描述性提及），但正文指令中
  引用"运行某命令"（EXECUTE_COMMAND 指令）必须用令牌
- 只校验 ``commands/*.md``，不校验 ``contracts/commands.md`` 等文档

对每个命令文件写独立测试函数。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# 仓库根：tests/extensions/test_command_tokens.py -> parents[2] = spec-kit/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = PROJECT_ROOT / "extensions" / "testing" / "commands"

# 4 个命令的短名（去 speckit.testing. 前缀）
COMMAND_NAMES = ["gate", "impact", "plan", "report"]

# 令牌格式：__SPECKIT_COMMAND_TESTING_{NAME}__
TOKEN_PREFIX = "__SPECKIT_COMMAND_TESTING_"
TOKEN_SUFFIX = "__"


# ── 辅助函数 ──────────────────────────────────────────────────────────────


def _command_file(name: str) -> Path:
    """返回命令 .md 文件路径，如 COMMANDS_DIR / 'speckit.testing.gate.md'。"""
    return COMMANDS_DIR / f"speckit.testing.{name}.md"


def _read_body(path: Path) -> str:
    """读取 .md 文件正文（frontmatter 之后的部分）。

    frontmatter 是首尾由 ``---`` 围起来的 YAML 块；本函数返回闭合
    ``---`` 之后的所有内容（含一个前导换行，不影响子串匹配）。
    """
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{path.name} 必须以 frontmatter (---) 开头"
    end = text.find("\n---", 3)
    assert end != -1, f"{path.name} frontmatter 必须有闭合 ---"
    return text[end + 4 :]


def _siblings(name: str) -> list[str]:
    """返回除自身外的兄弟命令短名列表。"""
    return [n for n in COMMAND_NAMES if n != name]


def _token_for(name: str) -> str:
    """返回命令短名对应的令牌字符串，如 'report' -> __SPECKIT_COMMAND_TESTING_REPORT__。"""
    return f"{TOKEN_PREFIX}{name.upper()}{TOKEN_SUFFIX}"


def _assert_no_literal_sibling_invocation(body: str, self_name: str, filename: str) -> None:
    """断言正文中不出现兄弟命令的字面调用路径。

    检查两种硬编码形式（均应改用令牌）：

    1. **斜杠形式**：``/speckit.testing.{sibling}``
       （slash-command 风格调用，任何位置都不允许出现兄弟命令的此形式）
    2. **EXECUTE_COMMAND 指令形式**：``EXECUTE_COMMAND: speckit.testing.{sibling}``
       （指令中字面引用兄弟命令名，应改用 ``EXECUTE_COMMAND: __SPECKIT_COMMAND_TESTING_*__``）

    自身命令的 EXECUTE_COMMAND 引用允许（如 gate.md 中
    ``EXECUTE_COMMAND: speckit.testing.gate`` 是自引用，非兄弟命令）。
    描述性文字中的命令名提及也允许（如"供后续 speckit.testing.plan 读取"）。
    """
    for sibling in _siblings(self_name):
        token = _token_for(sibling)
        # 1. 斜杠形式调用路径（兄弟命令的 slash-command 风格）
        slash_form = f"/speckit.testing.{sibling}"
        assert slash_form not in body, (
            f"{filename}: 正文中有字面调用路径 {slash_form!r}，"
            f"应使用令牌 {token!r}"
        )
        # 2. EXECUTE_COMMAND 指令中的兄弟命令字面引用（非令牌）
        #    允许 EXECUTE_COMMAND: __SPECKIT_COMMAND_TESTING_*__（令牌形式）
        #    允许 EXECUTE_COMMAND: speckit.testing.{self}（自引用）
        exec_pattern = re.compile(
            rf"EXECUTE_COMMAND:\s*speckit\.testing\.{sibling}\b"
        )
        assert exec_pattern.search(body) is None, (
            f"{filename}: EXECUTE_COMMAND 中字面引用兄弟命令 "
            f"speckit.testing.{sibling}，应使用令牌 {token!r}"
        )


# ── gate.md ────────────────────────────────────────────────────────────────


def test_gate_file_exists():
    """gate.md 命令文件必须存在。"""
    path = _command_file("gate")
    assert path.exists(), f"命令文件不存在: {path}"


def test_gate_uses_token_for_report():
    """gate.md 引用 report 命令时必须使用令牌 __SPECKIT_COMMAND_TESTING_REPORT__。

    gate 的 PASS 后续动作提示"门禁通过后运行 report 命令"，应通过令牌渲染，
    不能硬编码 /speckit.testing.report 或 EXECUTE_COMMAND: speckit.testing.report。
    """
    path = _command_file("gate")
    body = _read_body(path)
    assert _token_for("report") in body, (
        f"gate.md: 应使用令牌 {_token_for('report')!r} 引用 report 命令"
    )


def test_gate_no_literal_sibling_invocation():
    """gate.md 正文中不得字面出现兄弟命令（impact/plan/report）的调用路径。"""
    path = _command_file("gate")
    body = _read_body(path)
    _assert_no_literal_sibling_invocation(body, "gate", "speckit.testing.gate.md")


# ── impact.md ──────────────────────────────────────────────────────────────


def test_impact_file_exists():
    """impact.md 命令文件必须存在。"""
    path = _command_file("impact")
    assert path.exists(), f"命令文件不存在: {path}"


def test_impact_uses_token_for_plan():
    """impact.md 引用 plan 命令时必须使用令牌 __SPECKIT_COMMAND_TESTING_PLAN__。

    impact 的后续动作提到"建议运行测试计划命令"，应通过令牌渲染，
    不能硬编码 /speckit.testing.plan 或 EXECUTE_COMMAND: speckit.testing.plan。
    """
    path = _command_file("impact")
    body = _read_body(path)
    assert _token_for("plan") in body, (
        f"impact.md: 应使用令牌 {_token_for('plan')!r} 引用 plan 命令"
    )


def test_impact_no_literal_sibling_invocation():
    """impact.md 正文中不得字面出现兄弟命令（gate/plan/report）的调用路径。"""
    path = _command_file("impact")
    body = _read_body(path)
    _assert_no_literal_sibling_invocation(body, "impact", "speckit.testing.impact.md")


# ── plan.md ────────────────────────────────────────────────────────────────


def test_plan_file_exists():
    """plan.md 命令文件必须存在。"""
    path = _command_file("plan")
    assert path.exists(), f"命令文件不存在: {path}"


def test_plan_no_literal_sibling_invocation():
    """plan.md 正文中不得字面出现兄弟命令（gate/impact/report）的调用路径。

    plan.md 无需引用兄弟命令的令牌（它不指令用户运行其他 testing 命令），
    但仍不得硬编码斜杠形式或 EXECUTE_COMMAND 字面兄弟调用路径。
    描述性文字中提及命令名（如"作为后续 speckit.testing.gate 判定的依据"）允许。
    """
    path = _command_file("plan")
    body = _read_body(path)
    _assert_no_literal_sibling_invocation(body, "plan", "speckit.testing.plan.md")


# ── report.md ──────────────────────────────────────────────────────────────


def test_report_file_exists():
    """report.md 命令文件必须存在。"""
    path = _command_file("report")
    assert path.exists(), f"命令文件不存在: {path}"


def test_report_uses_token_for_gate():
    """report.md 引用 gate 命令时必须使用令牌 __SPECKIT_COMMAND_TESTING_GATE__。

    report 校验门禁已执行时提示"可运行门禁命令"，应通过令牌渲染，
    不能硬编码 /speckit.testing.gate 或 EXECUTE_COMMAND: speckit.testing.gate。
    """
    path = _command_file("report")
    body = _read_body(path)
    assert _token_for("gate") in body, (
        f"report.md: 应使用令牌 {_token_for('gate')!r} 引用 gate 命令"
    )


def test_report_no_literal_sibling_invocation():
    """report.md 正文中不得字面出现兄弟命令（gate/impact/plan）的调用路径。"""
    path = _command_file("report")
    body = _read_body(path)
    _assert_no_literal_sibling_invocation(body, "report", "speckit.testing.report.md")
