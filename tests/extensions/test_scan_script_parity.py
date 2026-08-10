"""T029: @Spec 注解扫描脚本三语言等价性补充测试。

本测试为 ``test_scan_spec_annotations.py`` 中基础等价性测试的**补充**，
覆盖更多场景的 Python vs bash（+ PowerShell）字节级等价性校验：

- (a) 单文件全覆盖（R1-R7 全注解）：验证基础场景三语言一致
- (b) 多文件（AccountService.java + ZService.java）：验证文件遍历排序一致
  （Python ``sorted(rglob)`` vs bash ``find | sort``）
- (c) 空目录边界（无 .java，spec.md 有规则 -> unimplemented_rules 全部）：
  验证无源文件时三语言输出一致

PowerShell 测试在 ``shutil.which("pwsh")`` 返回 None 时 skip
（与 ``test_scan_spec_annotations.py`` 一致）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import requires_bash

# 仓库根：tests/extensions/test_scan_script_parity.py -> parents[2] = spec-kit/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PY_SCRIPT = (
    PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python"
    / "scan_spec_annotations.py"
)
SH_SCRIPT = (
    PROJECT_ROOT / "extensions" / "testing" / "scripts" / "bash"
    / "scan-spec-annotations.sh"
)
PS_SCRIPT = (
    PROJECT_ROOT / "extensions" / "testing" / "scripts" / "powershell"
    / "scan-spec-annotations.ps1"
)

HAS_PWSH = shutil.which("pwsh") is not None

# spec.md 内容（含 R1-R7 business rules，三场景共用）
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

# 全部规则编号（保持 spec.md 出现顺序）
ALL_RULES = ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]


# ── 脚本执行辅助 ──────────────────────────────────────────────────────────


def _run_py(source_dir: Path, spec_path: Path) -> str:
    """调用 Python 扫描脚本，返回原始 stdout 字符串。"""
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
    return result.stdout


def _run_sh(source_dir: Path, spec_path: Path) -> str:
    """调用 bash 扫描脚本，返回原始 stdout 字符串。"""
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


def _run_ps(source_dir: Path, spec_path: Path) -> str:
    """调用 PowerShell 扫描脚本，返回原始 stdout 字符串。"""
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(PS_SCRIPT),
         "-Source", str(source_dir),
         "-Spec", str(spec_path),
         "-Json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"ps1 扫描脚本退出码 {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result.stdout


def _assert_parity(py_out: str, other_out: str, scenario: str, other_name: str) -> None:
    """断言 Python 与另一脚本输出字节级一致。"""
    assert py_out == other_out, (
        f"[{scenario}] Python 与 {other_name} 输出不一致:\n"
        f"--- py ---\n{py_out}\n--- {other_name} ---\n{other_out}"
    )


# ── Java 样本生成 ──────────────────────────────────────────────────────────


def _make_full_coverage_java() -> str:
    """生成单文件全覆盖 AccountService.java（R1-R7 全注解）。

    每条规则对应一个方法级 @Spec 注解，方法名与规则语义对应。
    """
    return """\
package com.example;

import com.speckit.testing.Spec;

@org.springframework.stereotype.Service
public class AccountService {

    @Spec(capability = "transfer", rule = "R1", description = "金额校验")
    public void transfer() {
    }

    @Spec(capability = "transfer", rule = "R2", description = "余额校验")
    public void checkBalance() {
    }

    @Spec(capability = "transfer", rule = "R3", description = "冻结校验")
    public void isFrozen() {
    }

    @Spec(capability = "transfer", rule = "R4", description = "额度上限")
    public void withinLimit() {
    }

    @Spec(capability = "transfer", rule = "R5", description = "审计日志")
    public void logAudit() {
    }

    @Spec(capability = "transfer", rule = "R6", description = "原子操作")
    public void commit() {
    }

    @Spec(capability = "transfer", rule = "R7", description = "自转账校验")
    public void checkSelfTransfer() {
    }
}
"""


def _make_account_service_java() -> str:
    """生成 AccountService.java（含 R1, R2, R6, R7 注解）。

    文件名以 A 开头，排序时位于 ZService 之前，用于验证
    Python ``sorted(rglob)`` 与 bash ``find | sort`` 排序一致。
    """
    return """\
package com.example;

import com.speckit.testing.Spec;

@org.springframework.stereotype.Service
public class AccountService {

    @Spec(capability = "transfer", rule = "R1", description = "金额校验")
    public void transfer() {
    }

    @Spec(capability = "transfer", rule = "R2", description = "余额校验")
    public void checkBalance() {
    }

    @Spec(capability = "transfer", rule = "R6", description = "原子操作")
    public void commit() {
    }

    @Spec(capability = "transfer", rule = "R7", description = "自转账校验")
    public void checkSelfTransfer() {
    }
}
"""


def _make_z_service_java() -> str:
    """生成 ZService.java（含 R3, R4, R5 注解）。

    文件名以 Z 开头，排序时位于 AccountService 之后，用于验证
    Python ``sorted(rglob)`` 与 bash ``find | sort`` 排序一致。
    """
    return """\
package com.example;

import com.speckit.testing.Spec;

@org.springframework.stereotype.Service
public class ZService {

    @Spec(capability = "transfer", rule = "R3", description = "冻结校验")
    public void isFrozen() {
    }

    @Spec(capability = "transfer", rule = "R4", description = "额度上限")
    public void withinLimit() {
    }

    @Spec(capability = "transfer", rule = "R5", description = "审计日志")
    public void logAudit() {
    }
}
"""


# ── fixture 工厂 ──────────────────────────────────────────────────────────


def _make_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """创建基础 fixture 目录：spec.md + 空的 src/ 目录。

    返回 (src_dir, spec_path)，调用方按场景写入 .java 文件。
    """
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(SPEC_MD, encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    return src_dir, spec_path


# ── 用例 (a): 单文件全覆盖 ────────────────────────────────────────────────


@requires_bash
@pytest.mark.skipif(not SH_SCRIPT.exists(), reason="bash 扫描脚本尚未实现")
def test_parity_single_file_full(tmp_path: Path):
    """单文件全覆盖（R1-R7 全注解）：Python 与 bash 输出字节级一致。

    场景：AccountService.java 含 R1-R7 全部 @Spec 注解，
    spec.md 含 R1-R7 全部 business_rules。
    预期：coverage 100%，无 unimplemented/orphan，三语言输出一致。
    """
    src_dir, spec_path = _make_fixture(tmp_path)
    (src_dir / "AccountService.java").write_text(
        _make_full_coverage_java(), encoding="utf-8"
    )

    py_out = _run_py(src_dir, spec_path)
    sh_out = _run_sh(src_dir, spec_path)
    _assert_parity(py_out, sh_out, "单文件全覆盖", "bash")

    # 同时验证输出内容正确（覆盖率 100%，无遗漏/孤儿）
    data = json.loads(py_out)
    assert data["coverage_percent"] == 100
    assert data["unimplemented_rules"] == []
    assert data["orphan_annotations"] == []
    assert len(data["annotations"]) == 7


@pytest.mark.skipif(not HAS_PWSH, reason="pwsh 不可用")
@pytest.mark.skipif(not PS_SCRIPT.exists(), reason="ps1 扫描脚本尚未实现")
def test_parity_single_file_full_ps(tmp_path: Path):
    """单文件全覆盖：Python 与 PowerShell 输出字节级一致。"""
    src_dir, spec_path = _make_fixture(tmp_path)
    (src_dir / "AccountService.java").write_text(
        _make_full_coverage_java(), encoding="utf-8"
    )

    py_out = _run_py(src_dir, spec_path)
    ps_out = _run_ps(src_dir, spec_path)
    _assert_parity(py_out, ps_out, "单文件全覆盖", "pwsh")


# ── 用例 (b): 多文件排序一致 ──────────────────────────────────────────────


@requires_bash
@pytest.mark.skipif(not SH_SCRIPT.exists(), reason="bash 扫描脚本尚未实现")
def test_parity_multi_file_sorted(tmp_path: Path):
    """多文件（AccountService.java + ZService.java）：验证排序一致。

    场景：两个 .java 文件分别含部分规则注解：
    - AccountService.java：R1, R2, R6, R7
    - ZService.java：R3, R4, R5

    Python 用 ``sorted(source_dir.rglob("*.java"))`` 遍历文件，
    bash 用 ``find "$SOURCE" -name '*.java' | LC_ALL=C sort`` 遍历。
    两者排序结果应一致（AccountService 在前，ZService 在后），
    输出 annotations 数组顺序一致，最终 stdout 字节级等价。
    """
    src_dir, spec_path = _make_fixture(tmp_path)
    (src_dir / "AccountService.java").write_text(
        _make_account_service_java(), encoding="utf-8"
    )
    (src_dir / "ZService.java").write_text(
        _make_z_service_java(), encoding="utf-8"
    )

    py_out = _run_py(src_dir, spec_path)
    sh_out = _run_sh(src_dir, spec_path)
    _assert_parity(py_out, sh_out, "多文件排序", "bash")

    # 验证排序：AccountService 的注解全部在 ZService 之前
    data = json.loads(py_out)
    locations = [ann["location"] for ann in data["annotations"]]
    account_locs = [loc for loc in locations if "AccountService" in loc]
    zservice_locs = [loc for loc in locations if "ZService" in loc]
    # locations 应为 account_locs + zservice_locs（AccountService 全在前）
    assert locations == account_locs + zservice_locs, (
        f"排序不一致：AccountService 注解应全部在 ZService 之前，"
        f"实际顺序: {locations}"
    )
    # R1-R7 全覆盖
    assert data["coverage_percent"] == 100
    assert len(data["annotations"]) == 7


@pytest.mark.skipif(not HAS_PWSH, reason="pwsh 不可用")
@pytest.mark.skipif(not PS_SCRIPT.exists(), reason="ps1 扫描脚本尚未实现")
def test_parity_multi_file_sorted_ps(tmp_path: Path):
    """多文件排序：Python 与 PowerShell 输出字节级一致。"""
    src_dir, spec_path = _make_fixture(tmp_path)
    (src_dir / "AccountService.java").write_text(
        _make_account_service_java(), encoding="utf-8"
    )
    (src_dir / "ZService.java").write_text(
        _make_z_service_java(), encoding="utf-8"
    )

    py_out = _run_py(src_dir, spec_path)
    ps_out = _run_ps(src_dir, spec_path)
    _assert_parity(py_out, ps_out, "多文件排序", "pwsh")


# ── 用例 (c): 空目录边界 ──────────────────────────────────────────────────


@requires_bash
@pytest.mark.skipif(not SH_SCRIPT.exists(), reason="bash 扫描脚本尚未实现")
def test_parity_empty_dir(tmp_path: Path):
    """空目录边界（无 .java，spec.md 有规则 -> unimplemented_rules 全部）。

    场景：src/ 目录存在但无任何 .java 文件，spec.md 含 R1-R7。
    预期：
    - annotations 为空
    - annotated_rules 为空 dict
    - unimplemented_rules == ["R1", "R2", ..., "R7"]（全部规则未实现）
    - orphan_annotations 为空
    - coverage_percent == 0
    - Python 与 bash 输出字节级一致
    """
    src_dir, spec_path = _make_fixture(tmp_path)
    # src_dir 已创建但为空，不写入任何 .java 文件

    py_out = _run_py(src_dir, spec_path)
    sh_out = _run_sh(src_dir, spec_path)
    _assert_parity(py_out, sh_out, "空目录边界", "bash")

    # 验证输出内容正确
    data = json.loads(py_out)
    assert data["annotations"] == []
    assert data["annotated_rules"] == {}
    assert data["unimplemented_rules"] == ALL_RULES
    assert data["orphan_annotations"] == []
    assert data["coverage_percent"] == 0


@pytest.mark.skipif(not HAS_PWSH, reason="pwsh 不可用")
@pytest.mark.skipif(not PS_SCRIPT.exists(), reason="ps1 扫描脚本尚未实现")
def test_parity_empty_dir_ps(tmp_path: Path):
    """空目录边界：Python 与 PowerShell 输出字节级一致。"""
    src_dir, spec_path = _make_fixture(tmp_path)
    # src_dir 已创建但为空

    py_out = _run_py(src_dir, spec_path)
    ps_out = _run_ps(src_dir, spec_path)
    _assert_parity(py_out, ps_out, "空目录边界", "pwsh")
