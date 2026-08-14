"""T008: @Spec 注解扫描脚本输出 JSON 契约测试。

用 subprocess 调用 ``scan_spec_annotations.py``，喂入 tmp 样本工程
（``.java`` 含 @Spec 注解 + ``spec.md`` 含 business_rules），断言输出 JSON
含 ``spec_rules`` / ``annotations`` / ``annotated_rules`` /
``unimplemented_rules`` / ``orphan_annotations`` / ``coverage_percent``
全部字段且值正确。

覆盖用例：
- (a) 全覆盖：R1..R7 全部有 @Spec，coverage 100%
- (b) 遗漏 R3：unimplemented_rules 含 R3，coverage 86%
- (c) 孤儿注解：代码含 R9 但 spec.md 无 R9 -> orphan_annotations 非空

另含三语言等价性测试（Python vs bash；pwsh 可用时也跑）。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import requires_bash

# 仓库根：tests/extensions/test_scan_spec_annotations.py -> parents[2] = spec-kit/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PY_SCRIPT = PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python" / "scan_spec_annotations.py"
SH_SCRIPT = PROJECT_ROOT / "extensions" / "testing" / "scripts" / "bash" / "scan-spec-annotations.sh"
PS_SCRIPT = PROJECT_ROOT / "extensions" / "testing" / "scripts" / "powershell" / "scan-spec-annotations.ps1"

HAS_PWSH = shutil.which("pwsh") is not None

# 规则 -> 实现方法名（样本工程用）
RULE_TO_METHOD = {
    "R1": "transfer",
    "R2": "checkBalance",
    "R3": "isFrozen",
    "R4": "withinLimit",
    "R5": "logAudit",
    "R6": "commit",
    "R7": "checkSelfTransfer",
}
RULE_TO_DESC = {
    "R1": "金额校验",
    "R2": "余额校验",
    "R3": "冻结校验",
    "R4": "额度上限",
    "R5": "审计日志",
    "R6": "原子操作",
    "R7": "自转账校验",
}
ALL_RULES = ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]

SPEC_MD = """\
# Transfer

## Business Rules

- R1: 转账金额必须大于0
- R2: 转账账户必须有足够余额
- R3: 不可向冻结账户转账
- R4: 单笔转账不超过10万
- R5: 转账需记录审计日志
- R6: 转账为原子操作
- R7: 不可自转账

## API

POST /api/v1/accounts/transfer
"""


# ── 样本工程辅助 ──────────────────────────────────────────────────────────


def _make_java_source(rules: list[str]) -> str:
    """生成样本 Java 源码，为给定规则列表各放一个 @Spec 方法级注解。"""
    lines = [
        "package com.example;",
        "",
        "import java.math.BigDecimal;",
        "import com.speckit.testing.Spec;",
        "",
        "@org.springframework.stereotype.Service",
        "public class AccountService {",
        "",
    ]
    for rule in rules:
        method = RULE_TO_METHOD[rule]
        desc = RULE_TO_DESC[rule]
        lines.append(
            f'    @Spec(capability = "transfer", rule = "{rule}", description = "{desc}")'
        )
        lines.append(f"    public void {method}() {{")
        lines.append("    }")
        lines.append("")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _spec_line_numbers(java_content: str) -> dict[str, int]:
    """从样本 Java 内容提取每个规则的 @Spec 行号（1-indexed）。"""
    expected: dict[str, int] = {}
    for i, line in enumerate(java_content.splitlines(), start=1):
        if "@Spec" in line:
            m = re.search(r'rule\s*=\s*"(R\d+)"', line)
            if m:
                expected[m.group(1)] = i
    return expected


def _expected_location(rule: str, java_content: str) -> str:
    method = RULE_TO_METHOD[rule]
    line = _spec_line_numbers(java_content)[rule]
    return f"com.example.AccountService.{method}:{line}"


@pytest.fixture
def sample_project(tmp_path: Path):
    """创建样本工程目录：spec.md + src/（待写入 .java）。"""
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(SPEC_MD, encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    return tmp_path, src_dir, spec_path


# ── 脚本执行辅助 ──────────────────────────────────────────────────────────


def _run_py(source_dir: Path, spec_path: Path) -> tuple[str, dict]:
    """调用 Python 扫描脚本，返回 (原始 stdout, 解析后 dict)。"""
    result = subprocess.run(
        [sys.executable, str(PY_SCRIPT),
         "--source", str(source_dir),
         "--spec", str(spec_path),
         "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"Python 扫描脚本退出码 {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result.stdout, json.loads(result.stdout)


def _run_sh(source_dir: Path, spec_path: Path) -> str:
    """调用 bash 扫描脚本，返回原始 stdout。"""
    result = subprocess.run(
        ["bash", str(SH_SCRIPT),
         "--source", str(source_dir),
         "--spec", str(spec_path),
         "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"bash 扫描脚本退出码 {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result.stdout


# ── 用例 (a): 全覆盖 ─────────────────────────────────────────────────────


def test_scan_full_coverage(sample_project):
    """R1..R7 全部有 @Spec 注解：coverage 100%，无 unimplemented/orphan。"""
    _, src_dir, spec_path = sample_project
    java_content = _make_java_source(ALL_RULES)
    (src_dir / "AccountService.java").write_text(java_content, encoding="utf-8")

    _, data = _run_py(src_dir, spec_path)

    # spec_rules：spec.md 中全部规则编号（保持出现顺序）
    assert data["spec_rules"] == ALL_RULES

    # annotations：每条 @Spec 含 rule/capability/description/location
    assert len(data["annotations"]) == 7
    for ann in data["annotations"]:
        assert ann["capability"] == "transfer"
        assert ann["rule"] in ALL_RULES
        assert ann["description"] == RULE_TO_DESC[ann["rule"]]
        assert ann["location"] == _expected_location(ann["rule"], java_content)

    # annotated_rules：规则编号 -> 位置清单（一对多）
    assert set(data["annotated_rules"].keys()) == set(ALL_RULES)
    for rule in ALL_RULES:
        assert data["annotated_rules"][rule] == [_expected_location(rule, java_content)]

    # unimplemented_rules：spec.md 有但代码无 @Spec（应空）
    assert data["unimplemented_rules"] == []
    # orphan_annotations：代码有 @Spec 但 spec.md 无对应规则（应空）
    assert data["orphan_annotations"] == []
    # coverage_percent：已注解规则数 / spec 规则总数 * 100
    assert data["coverage_percent"] == 100


# ── 用例 (b): 遗漏 R3 ────────────────────────────────────────────────────


def test_scan_missing_r3(sample_project):
    """遗漏 R3：unimplemented_rules == ["R3"]，coverage 86%。"""
    _, src_dir, spec_path = sample_project
    implemented = ["R1", "R2", "R4", "R5", "R6", "R7"]
    java_content = _make_java_source(implemented)
    (src_dir / "AccountService.java").write_text(java_content, encoding="utf-8")

    _, data = _run_py(src_dir, spec_path)

    assert data["spec_rules"] == ALL_RULES
    assert len(data["annotations"]) == 6
    assert set(data["annotated_rules"].keys()) == set(implemented)
    assert data["unimplemented_rules"] == ["R3"]
    assert data["orphan_annotations"] == []
    assert data["coverage_percent"] == round(6 / 7 * 100)  # 86


# ── 用例 (c): 孤儿注解 ───────────────────────────────────────────────────


def test_scan_orphan_annotation(sample_project):
    """代码含 R9 注解但 spec.md 无 R9：orphan_annotations 非空，R7 未实现。"""
    _, src_dir, spec_path = sample_project
    # 把 R7 注解的 rule 改成 spec.md 不存在的 R9
    orphan_java = _make_java_source(ALL_RULES).replace('rule = "R7"', 'rule = "R9"')
    (src_dir / "AccountService.java").write_text(orphan_java, encoding="utf-8")

    _, data = _run_py(src_dir, spec_path)

    assert data["spec_rules"] == ALL_RULES
    orphan_rules = [a["rule"] for a in data["orphan_annotations"]]
    assert "R9" in orphan_rules
    # R9 不在 spec_rules，所以 R7 未被注解
    assert "R7" in data["unimplemented_rules"]


# ── 用例 (d): @Repeatable @Spec 堆叠 ────────────────────────────────────


def test_scan_repeatable_spec(tmp_path: Path):
    """同一方法多个 @Spec 堆叠（@Repeatable）-> 各自独立注解行（Bug #6）。

    3 个 @Spec（R1/R2/R3）堆叠在同一个 transfer() 方法上：
    - 产出 3 条注解，全部指向 transfer()，每条 @Spec 用各自行号
    - coverage 100%（R1-R3 全实现），无 orphan / unimplemented
    """
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("""\
# Transfer

## Business Rules

- R1: 转账金额必须大于0
- R2: 转账账户必须有足够余额
- R3: 不可向冻结账户转账
""", encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    java_content = """\
package com.example;

import com.speckit.testing.Spec;

@org.springframework.stereotype.Service
public class AccountService {

    @Spec(capability = "transfer", rule = "R1", description = "金额校验")
    @Spec(capability = "transfer", rule = "R2", description = "余额校验")
    @Spec(capability = "transfer", rule = "R3", description = "冻结校验")
    public void transfer() {
    }
}
"""
    (src_dir / "AccountService.java").write_text(java_content, encoding="utf-8")

    _, data = _run_py(src_dir, spec_path)

    assert data["spec_rules"] == ["R1", "R2", "R3"]
    # 3 条注解全部指向 transfer()，且各自保留自己的 @Spec 行号
    assert len(data["annotations"]) == 3
    assert [a["rule"] for a in data["annotations"]] == ["R1", "R2", "R3"]
    assert [a["location"] for a in data["annotations"]] == [
        "com.example.AccountService.transfer:8",
        "com.example.AccountService.transfer:9",
        "com.example.AccountService.transfer:10",
    ]
    for ann in data["annotations"]:
        assert ann["capability"] == "transfer"
    assert data["unimplemented_rules"] == []
    assert data["orphan_annotations"] == []
    assert data["coverage_percent"] == 100


# ── 三语言等价性 ─────────────────────────────────────────────────────────


@requires_bash
@pytest.mark.skipif(not SH_SCRIPT.exists(), reason="bash 扫描脚本尚未实现")
def test_parity_python_vs_bash(sample_project):
    """Python 与 bash 扫描脚本输出字节级等价的 JSON。"""
    _, src_dir, spec_path = sample_project
    (src_dir / "AccountService.java").write_text(
        _make_java_source(ALL_RULES), encoding="utf-8"
    )

    py_stdout, _ = _run_py(src_dir, spec_path)
    sh_stdout = _run_sh(src_dir, spec_path)

    # 字节级等价：两份 stdout 完全相同
    assert py_stdout == sh_stdout, (
        "Python 与 bash 输出不一致:\n"
        f"--- py ---\n{py_stdout}\n--- sh ---\n{sh_stdout}"
    )


@pytest.mark.skipif(not HAS_PWSH, reason="pwsh 不可用")
@pytest.mark.skipif(not PS_SCRIPT.exists(), reason="ps1 扫描脚本尚未实现")
def test_parity_python_vs_powershell(sample_project):
    """Python 与 PowerShell 扫描脚本输出字节级等价的 JSON。"""
    _, src_dir, spec_path = sample_project
    (src_dir / "AccountService.java").write_text(
        _make_java_source(ALL_RULES), encoding="utf-8"
    )

    py_stdout, _ = _run_py(src_dir, spec_path)
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(PS_SCRIPT),
         "-Source", str(src_dir),
         "-Spec", str(spec_path),
         "-Json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"ps1 扫描脚本退出码 {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert py_stdout == result.stdout, (
        "Python 与 PowerShell 输出不一致:\n"
        f"--- py ---\n{py_stdout}\n--- ps ---\n{result.stdout}"
    )
