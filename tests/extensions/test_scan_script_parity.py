"""T029: @Spec 注解扫描脚本 Python 实现契约测试。

**beta 阶段只维护 Python 实现**：sh/ps 脚本已弃用（保留文件但不再维护、
不再测试），三语言字节级 parity 已无意义。本文件只测 Python 实现的核心
契约（scan 输出键、unspec_codes 语义、Javadoc 幻影 fixture、@Repeatable、
parse_test_results / run_gate 输出字段等）。

覆盖场景（均为纯 Python 断言）：

- (a) 单文件全覆盖（R1-R7 全注解）：验证基础场景输出正确
- (b) 多文件（AccountService.java + ZService.java）：验证文件遍历排序一致
  （Python ``sorted(rglob)``）
- (c) 空目录边界（无 .java，spec.md 有规则 -> unimplemented_rules 全部）
- (d) @Repeatable @Spec 堆叠（Bug #6）
- (e) 类级 @Spec / 同一行 @Spec+方法签名（F7）
- (f) Javadoc 幻影（注释跳过状态机，修发现 A）
- (g) 多分隔符标题（business_rules 量词补 +，修 F4）
- (h) UNSPEC_CODE 漂移检测（9.6，T1 结构性 MEDIUM）
- (i) validate_spec_format / parse_test_results / scan_test_stack / run_gate
  Python 实现契约
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# 仓库根：tests/extensions/test_scan_script_parity.py -> parents[2] = spec-kit/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PY_SCRIPT = (
    PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python"
    / "scan_spec_annotations.py"
)

# spec.md 内容（含 R1-R7 business rules，多场景共用）
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


def _run_py(
    source_dir: Path,
    spec_path: Path,
    test_source: Path | None = None,
    exclude_patterns: str = "",
) -> str:
    """调用 Python 扫描脚本，返回原始 stdout 字符串。

    ``test_source`` / ``exclude_patterns`` 为 v0.6（9.6）UNSPEC_CODE 漂移
    检测的可选参数：测试引用判定 + 追加排除模式，缺省时与旧调用等价。
    """
    cmd = [sys.executable, str(PY_SCRIPT),
           "--source", str(source_dir),
           "--spec", str(spec_path)]
    if test_source is not None:
        cmd += ["--test-source", str(test_source)]
    if exclude_patterns:
        cmd += ["--exclude-patterns", exclude_patterns]
    cmd += ["--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, (
        f"Python 扫描脚本退出码 {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result.stdout


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
    Python ``sorted(rglob)`` 排序一致。
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
    Python ``sorted(rglob)`` 排序一致。
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


def _make_repeatable_java() -> str:
    """生成 @Repeatable @Spec 堆叠的 AccountService.java（试点场景）。

    R1-R7 全部堆叠在同一个 transfer() 方法上（逐行连续），用于验证
    Python 不丢弃中间的 @Spec（Bug #6：p_rule/p_cap 单标量被后一条
    覆盖，此前 bash 只产出最后一条）。
    """
    return """\
package com.example;

import com.speckit.testing.Spec;

@org.springframework.stereotype.Service
public class AccountService {

    @Spec(capability = "transfer", rule = "R1", description = "金额校验")
    @Spec(capability = "transfer", rule = "R2", description = "余额校验")
    @Spec(capability = "transfer", rule = "R3", description = "冻结校验")
    @Spec(capability = "transfer", rule = "R4", description = "额度上限")
    @Spec(capability = "transfer", rule = "R5", description = "审计日志")
    @Spec(capability = "transfer", rule = "R6", description = "原子操作")
    @Spec(capability = "transfer", rule = "R7", description = "自转账校验")
    public void transfer() {
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


def test_scan_single_file_full(tmp_path: Path):
    """单文件全覆盖（R1-R7 全注解）：Python 输出内容正确。

    场景：AccountService.java 含 R1-R7 全部 @Spec 注解，
    spec.md 含 R1-R7 全部 business_rules。
    预期：coverage 100%，无 unimplemented/orphan，无 UNSPEC_CODE 漂移。
    """
    src_dir, spec_path = _make_fixture(tmp_path)
    (src_dir / "AccountService.java").write_text(
        _make_full_coverage_java(), encoding="utf-8"
    )

    py_out = _run_py(src_dir, spec_path)
    data = json.loads(py_out)
    assert data["coverage_percent"] == 100
    assert data["unimplemented_rules"] == []
    assert data["orphan_annotations"] == []
    assert len(data["annotations"]) == 7
    # 9.6：全类已 @Spec 标注 -> 无 UNSPEC_CODE 漂移
    assert data["unspec_codes"] == []


# ── 用例 (b): 多文件排序一致 ──────────────────────────────────────────────


def test_scan_multi_file_sorted(tmp_path: Path):
    """多文件（AccountService.java + ZService.java）：验证排序一致。

    场景：两个 .java 文件分别含部分规则注解：
    - AccountService.java：R1, R2, R6, R7
    - ZService.java：R3, R4, R5

    Python 用 ``sorted(source_dir.rglob("*.java"))`` 遍历文件，
    AccountService 在前，ZService 在后，annotations 数组顺序一致。
    """
    src_dir, spec_path = _make_fixture(tmp_path)
    (src_dir / "AccountService.java").write_text(
        _make_account_service_java(), encoding="utf-8"
    )
    (src_dir / "ZService.java").write_text(
        _make_z_service_java(), encoding="utf-8"
    )

    py_out = _run_py(src_dir, spec_path)
    data = json.loads(py_out)
    # 验证排序：AccountService 的注解全部在 ZService 之前
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


# ── 用例 (c): 空目录边界 ──────────────────────────────────────────────────


def test_scan_empty_dir(tmp_path: Path):
    """空目录边界（无 .java，spec.md 有规则 -> unimplemented_rules 全部）。

    场景：src/ 目录存在但无任何 .java 文件，spec.md 含 R1-R7。
    预期：
    - annotations 为空
    - annotated_rules 为空 dict
    - unimplemented_rules == ["R1", "R2", ..., "R7"]（全部规则未实现）
    - orphan_annotations 为空
    - coverage_percent == 0
    """
    src_dir, spec_path = _make_fixture(tmp_path)
    # src_dir 已创建但为空，不写入任何 .java 文件

    py_out = _run_py(src_dir, spec_path)
    data = json.loads(py_out)
    assert data["annotations"] == []
    assert data["annotated_rules"] == {}
    assert data["unimplemented_rules"] == ALL_RULES
    assert data["orphan_annotations"] == []
    assert data["coverage_percent"] == 0
    # 9.6：无任何类 -> 无 UNSPEC_CODE 漂移
    assert data["unspec_codes"] == []


# ── 用例 (d): @Repeatable @Spec 堆叠 ─────────────────────────────────────


def test_scan_repeatable_spec(tmp_path: Path):
    """@Repeatable @Spec 堆叠：Python 逐条保留（Bug #6）。

    场景：R1-R7 全部堆叠在同一个 transfer() 方法上（试点场景）。
    修复前 bash 用单标量 p_rule/p_cap 存 pending，只保留最后一条 @Spec
    （1 条注解 / coverage 29%）；Python 应逐条保留（7 条 / coverage 100%）。
    """
    src_dir, spec_path = _make_fixture(tmp_path)
    (src_dir / "AccountService.java").write_text(
        _make_repeatable_java(), encoding="utf-8"
    )

    py_out = _run_py(src_dir, spec_path)
    data = json.loads(py_out)
    # 内容校验：7 条注解全部指向 transfer()，coverage 100%，无遗漏/孤儿
    assert len(data["annotations"]) == 7
    for ann in data["annotations"]:
        assert ann["location"].startswith("com.example.AccountService.transfer:")
    assert data["coverage_percent"] == 100
    assert data["unimplemented_rules"] == []
    assert data["orphan_annotations"] == []


# ── 用例 (e): 类级 @Spec（无方法签名行跟随，类名兜底） ─────────────────────


def _make_class_level_java() -> str:
    """生成类级 @Spec 的 OrderService.java（F7 修复点 1）。

    @Spec 直接标在类声明行上，类内方法均为包私有（无 public/protected/
    private 访问修饰符）——不匹配方法签名模式，pending 直到文件末尾仍残留，
    Python 用类名兜底（``None -> class_name``）：
    location = com.example.OrderService.OrderService:<@Spec 行号>。
    """
    return """\
package com.example;

import com.speckit.testing.Spec;

@Spec(capability = "transfer", rule = "R1", description = "类级规则")
public class OrderService {

    void createOrder() {
    }

    void cancel() {
    }
}
"""


def _make_same_line_java() -> str:
    """生成同一行 @Spec + 方法签名的 CancelService.java（F7 修复点 2）。

    @Spec 与 ``public void cancel()`` 在同一行——应在该行立即解析出方法名
    cancel。location = com.example.CancelService.cancel:<@Spec 行号>。
    """
    return """\
package com.example;

import com.speckit.testing.Spec;

public class CancelService {

    @Spec(capability = "transfer", rule = "R2", description = "取消防单") public void cancel() {
    }
}
"""


def test_scan_class_level_spec(tmp_path: Path):
    """类级 @Spec（无方法签名行跟随）：Python 类名兜底（F7）。

    场景：@Spec 标在类声明行，类内只有包私有方法（不匹配方法签名模式），
    pending 直到文件末尾残留。Python 用类名兜底（OrderService.OrderService）
    1 条 / 14%。
    """
    src_dir, spec_path = _make_fixture(tmp_path)
    (src_dir / "OrderService.java").write_text(
        _make_class_level_java(), encoding="utf-8"
    )

    py_out = _run_py(src_dir, spec_path)
    data = json.loads(py_out)
    # 内容校验：类名兜底 1 条注解，coverage 14%，R2-R7 未实现
    assert len(data["annotations"]) == 1
    assert data["annotations"][0]["location"] == "com.example.OrderService.OrderService:5"
    assert data["coverage_percent"] == round(1 / 7 * 100)  # 14
    assert data["unimplemented_rules"] == ["R2", "R3", "R4", "R5", "R6", "R7"]
    assert data["orphan_annotations"] == []


def test_scan_same_line_spec(tmp_path: Path):
    """同一行 @Spec + 方法签名：Python 立即解析方法名（F7）。

    场景：@Spec(...) public void cancel() 同一行。Python 本行立即解析
    方法名 cancel（1 条 / 14%）。
    """
    src_dir, spec_path = _make_fixture(tmp_path)
    (src_dir / "CancelService.java").write_text(
        _make_same_line_java(), encoding="utf-8"
    )

    py_out = _run_py(src_dir, spec_path)
    data = json.loads(py_out)
    # 内容校验：cancel 1 条注解，coverage 14%，R1/R3-R7 未实现
    assert len(data["annotations"]) == 1
    assert data["annotations"][0]["location"] == "com.example.CancelService.cancel:7"
    assert data["coverage_percent"] == round(1 / 7 * 100)  # 14
    assert data["unimplemented_rules"] == ["R1", "R3", "R4", "R5", "R6", "R7"]
    assert data["orphan_annotations"] == []


# ── 用例 (f): Javadoc 幻影（注释跳过状态机，修发现 A） ──────────────────────


def _make_javadoc_phantom_java() -> str:
    """生成含注释幻影 @Spec 的 PhantomService.java（发现 A 修复验证）。

    块注释（Javadoc）内含 ``@Spec(rule="R99")``、行注释内含
    ``@Spec(rule="R88")`` —— 注释状态机须将其跳过（不算幻影注解）；
    仅保留真实方法级 ``@Spec(rule="R1")``。
    """
    return """\
package com.example;
import com.speckit.testing.Spec;

/**
 * 示例注解（Javadoc，必须被注释跳过）：
 * @Spec(capability = "transfer", rule = "R99", description = "幻影")
 */
@org.springframework.stereotype.Service
public class PhantomService {

    @Spec(capability = "transfer", rule = "R1", description = "真实规则")
    public void transfer() {
    }

    // @Spec(capability = "transfer", rule = "R88", description = "行注释幻影")
    public void helper() {
    }
}
"""


def test_scan_javadoc_phantom(tmp_path: Path):
    """Javadoc 幻影：注释内 @Spec 被跳过（发现 A）。

    场景：Javadoc 块注释含 R99 幻影、行注释含 R88 幻影，仅 R1 为真实注解。
    修复前把 R99/R88 误扫为幻影注解（orphan_annotations 污染）；
    修复后仅 1 条注解 / coverage 14%，orphan 为空。
    """
    src_dir, spec_path = _make_fixture(tmp_path)
    (src_dir / "PhantomService.java").write_text(
        _make_javadoc_phantom_java(), encoding="utf-8"
    )

    py_out = _run_py(src_dir, spec_path)
    data = json.loads(py_out)
    # 内容断言：仅 R1 真实注解，R99/R88 不出现，coverage 14%（1/7）
    assert len(data["annotations"]) == 1
    assert data["annotations"][0]["rule"] == "R1"
    assert data["annotations"][0]["location"] == "com.example.PhantomService.transfer:11"
    assert "R99" not in json.dumps(data)
    assert "R88" not in json.dumps(data)
    assert data["coverage_percent"] == round(1 / 7 * 100)  # 14
    assert data["unimplemented_rules"] == ["R2", "R3", "R4", "R5", "R6", "R7"]
    assert data["orphan_annotations"] == []


# ── 用例 (g): 多分隔符标题（business_rules 量词补 +，修 F4） ────────────────


# spec.md 用 `## Business  Rules`（两个空格分隔）标题 + R1-R3 三条规则
SPEC_MD_MULTI_SPACE = """\
# Transfer

## Business  Rules

- R1: 转账金额必须大于0
- R2: 转账账户必须有足够余额
- R3: 不可向冻结账户转账

## API

POST /api/v1/accounts/transfer
"""


def _make_multi_space_java() -> str:
    """生成 R1-R3 三注解的 MultiSpaceService.java（多分隔符标题场景）。"""
    return """\
package com.example;

import com.speckit.testing.Spec;

public class MultiSpaceService {

    @Spec(capability = "transfer", rule = "R1", description = "金额校验")
    public void transfer() {
    }

    @Spec(capability = "transfer", rule = "R2", description = "余额校验")
    public void checkBalance() {
    }

    @Spec(capability = "transfer", rule = "R3", description = "冻结校验")
    public void isFrozen() {
    }
}
"""


def _make_multi_space_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """创建多分隔符标题 fixture：spec.md 用双空格标题 + R1-R3 源码。"""
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(SPEC_MD_MULTI_SPACE, encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "MultiSpaceService.java").write_text(
        _make_multi_space_java(), encoding="utf-8"
    )
    return src_dir, spec_path


def test_scan_multi_space_header(tmp_path: Path):
    """多分隔符标题（## Business  Rules 双空格）：Python 正确识别（F4）。

    场景：business_rules 章节标题用两个空格分隔 —— Python 用
    ``[\\s_-]+`` 匹配，正确识别 R1-R3 -> coverage 100%。
    """
    src_dir, spec_path = _make_multi_space_fixture(tmp_path)

    py_out = _run_py(src_dir, spec_path)
    data = json.loads(py_out)
    # 内容断言：R1-R3 全识别，coverage 100%
    assert data["spec_rules"] == ["R1", "R2", "R3"]
    assert data["coverage_percent"] == 100
    assert data["unimplemented_rules"] == []
    assert data["orphan_annotations"] == []


# ── 用例 (h): UNSPEC_CODE 漂移检测（9.6，T1 结构性 MEDIUM） ───────────────


def _make_unspec_business_java() -> str:
    """生成无 @Spec 的业务类 PaymentService.java（应进入 unspec_codes 告警）。"""
    return """\
package com.example;

public class PaymentService {

    public void pay() {
    }
}
"""


def _make_unspec_spec_java() -> str:
    """生成含 @Spec 的 TransferService.java（已标注 -> 不告警）。"""
    return """\
package com.example;

import com.speckit.testing.Spec;

public class TransferService {

    @Spec(capability = "transfer", rule = "R1", description = "金额校验")
    public void transfer() {
    }
}
"""


def _make_unspec_mapper_java() -> str:
    """生成 *Mapper 后缀类 OrderMapper.java（内置类名后缀排除 -> 不告警）。"""
    return """\
package com.example;

public class OrderMapper {
}
"""


def _make_unspec_dto_java() -> str:
    """生成 dto 包段类 OrderDto.java（内置包段排除 -> 不告警）。"""
    return """\
package com.example.dto;

public class OrderDto {
}
"""


def _make_unspec_entity_java() -> str:
    """生成 entity 包段类 User.java（内置包段排除 -> 不告警）。"""
    return """\
package com.example.entity;

public class User {
}
"""


def _make_unspec_refund_java() -> str:
    """生成无 @Spec 的 RefundService.java（被测试引用 -> 传 --test-source 不告警）。"""
    return """\
package com.example;

public class RefundService {

    public void refund() {
    }
}
"""


def _make_unspec_legacy_java() -> str:
    """生成 legacy 包段业务类 FeeService.java（--exclude-patterns 追加排除 -> 不告警）。"""
    return """\
package com.example.legacy;

public class FeeService {

    public void charge() {
    }
}
"""


def _make_unspec_refund_test_java() -> str:
    """生成引用 RefundService 的 RefundServiceTest.java（测试引用判定）。"""
    return """\
package com.example;

import org.junit.jupiter.api.Test;

class RefundServiceTest {

    @Test
    void shouldRefund() {
        RefundService service = new RefundService();
        service.refund();
    }
}
"""


def _make_unspec_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """创建 UNSPEC_CODE 漂移 fixture：业务类/DTO/实体/Mapper/@Spec 类混合目录。

    返回 (src_dir, spec_path)。判定预期（9.6 三类）：
    - PaymentService（业务类，无 @Spec 无测试引用）-> unspec_codes 告警
    - dto/entity 包段类（OrderDto/User）+ *Mapper 后缀类（OrderMapper）
      -> 内置排除表不告警
    - TransferService（@Spec 标注）-> 不告警
    """
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(SPEC_MD, encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "PaymentService.java").write_text(
        _make_unspec_business_java(), encoding="utf-8"
    )
    (src_dir / "TransferService.java").write_text(
        _make_unspec_spec_java(), encoding="utf-8"
    )
    (src_dir / "OrderMapper.java").write_text(
        _make_unspec_mapper_java(), encoding="utf-8"
    )
    dto_dir = src_dir / "dto"
    dto_dir.mkdir()
    (dto_dir / "OrderDto.java").write_text(_make_unspec_dto_java(), encoding="utf-8")
    entity_dir = src_dir / "entity"
    entity_dir.mkdir()
    (entity_dir / "User.java").write_text(_make_unspec_entity_java(), encoding="utf-8")
    return src_dir, spec_path


def _make_unspec_exclude_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """创建 UNSPEC_CODE 排除/测试引用 fixture。

    返回 (src_dir, test_src_dir, spec_path)。判定预期（9.6 可选加分）：
    - RefundService（业务类，无 @Spec）-> 被 RefundServiceTest 引用，
      传 --test-source 后不告警
    - legacy/FeeService（业务类，无 @Spec）-> 传 --exclude-patterns "legacy"
      追加排除后不告警
    """
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(SPEC_MD, encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "RefundService.java").write_text(
        _make_unspec_refund_java(), encoding="utf-8"
    )
    legacy_dir = src_dir / "legacy"
    legacy_dir.mkdir()
    (legacy_dir / "FeeService.java").write_text(
        _make_unspec_legacy_java(), encoding="utf-8"
    )
    test_dir = tmp_path / "test-src"
    test_dir.mkdir()
    (test_dir / "RefundServiceTest.java").write_text(
        _make_unspec_refund_test_java(), encoding="utf-8"
    )
    return src_dir, test_dir, spec_path


def test_scan_unspec_codes(tmp_path: Path):
    """UNSPEC_CODE 漂移：三类判定正确（9.6）。

    场景：业务类无 @Spec 且无测试引用（PaymentService）-> 告警完整类名
    com.example.PaymentService；DTO 类（dto 包段 OrderDto / entity 包段
    User / *Mapper 后缀 OrderMapper）-> 内置排除表不告警；@Spec 类
    （TransferService）-> 不告警。
    """
    src_dir, spec_path = _make_unspec_fixture(tmp_path)

    py_out = _run_py(src_dir, spec_path)
    data = json.loads(py_out)
    # 内容断言：仅 PaymentService 告警（完整类名），其余类全部排除
    assert data["unspec_codes"] == ["com.example.PaymentService"]
    warned = {code.rsplit(".", 1)[-1] for code in data["unspec_codes"]}
    assert warned == {"PaymentService"}
    for cls in ("TransferService", "OrderMapper", "OrderDto", "User"):
        assert cls not in warned, f"{cls} 不应出现在 unspec_codes: {data['unspec_codes']}"


def test_scan_unspec_exclusions(tmp_path: Path):
    """UNSPEC_CODE 排除：--test-source 引用 + --exclude-patterns 追加生效（9.6）。

    场景：RefundService 被 RefundServiceTest 引用（传 --test-source 不告警）；
    legacy/FeeService 命中 --exclude-patterns "legacy"（追加排除不告警）。
    预期无漂移（unspec_codes == []）。
    """
    src_dir, test_dir, spec_path = _make_unspec_exclude_fixture(tmp_path)

    py_out = _run_py(src_dir, spec_path, test_source=test_dir, exclude_patterns="legacy")
    data = json.loads(py_out)
    assert data["unspec_codes"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# 其他 Python 脚本契约：validate_spec_format / parse_test_results / scan_test_stack
# / run_gate（beta 阶段只维护 Python 实现，直接断言 Python 输出）
# ═══════════════════════════════════════════════════════════════════════════════

# ── 路径常量 ──────────────────────────────────────────────────────────────────

_VSF_PY = PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python" / "validate_spec_format.py"
_PTR_PY = PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python" / "parse_test_results.py"
_STS_PY = PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python" / "scan_test_stack.py"
_RG_PY = PROJECT_ROOT / "extensions" / "testing" / "scripts" / "python" / "run_gate.py"


# ── validate_spec_format 契约 ─────────────────────────────────────────────

_VSF_SPEC = """\
# Transfer

## Business Rules

- R1: 转账金额必须大于0
- R2: 转账账户必须有足够余额
- R3: 不可向冻结账户转账

### Error Code Definitions

| Error Code | HTTP Status | Description |
|------------|------------|-------------|
| INVALID_AMOUNT | 400 | 金额非法 |
| ACCOUNT_NOT_FOUND | 404 | 账号不存在 |
"""

# 噪音场景：HTML 注释行 + HTTP Status 列 + Related Rule 列（R1..R7）
# + 描述含全大写单词 -> error_codes_found 只含真正的错误码（Bug #1）。
_VSF_SPEC_NOISY = """\
# Transfer

## Business Rules

- R1: 转账金额必须大于0
- R2: 转账账户必须有足够余额
- R3: 不可向冻结账户转账

### Error Code Definitions

<!-- OPTIONAL API errors -->

| Error Code | HTTP Status | Description | Related Rule |
|------------|------------|-------------|--------------|
| INVALID_AMOUNT | 400 | 金额非法 HTTP | R1, R2, R3 |
| ACCOUNT_NOT_FOUND | 404 | 账号不存在 API | R4, R5, R6, R7 |
"""


def _vsf_run_py(spec_path: Path) -> str:
    r = subprocess.run(
        [sys.executable, str(_VSF_PY), "--spec", str(spec_path), "--json"],
        capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"py 退出码 {r.returncode}\n{r.stderr}"
    return r.stdout


def test_validate_spec_format_py(tmp_path: Path):
    """validate_spec_format: Python 输出契约（valid + error_codes_found）。"""
    spec = tmp_path / "spec.md"
    spec.write_text(_VSF_SPEC, encoding="utf-8")
    data = json.loads(_vsf_run_py(spec))
    assert data["valid"] is True
    assert data["error_codes_found"] == ["INVALID_AMOUNT", "ACCOUNT_NOT_FOUND"]


def test_validate_spec_format_noise_py(tmp_path: Path):
    """validate_spec_format 噪音场景：内容干净（Bug #1）。

    ECD 段含 HTML 注释行（OPTIONAL/API）、HTTP Status 列、Related Rule 列
    （R1..R7）、描述含全大写单词 -> error_codes_found 必须恰好等于
    ["INVALID_AMOUNT", "ACCOUNT_NOT_FOUND"]，valid 仍 true。
    """
    spec = tmp_path / "spec.md"
    spec.write_text(_VSF_SPEC_NOISY, encoding="utf-8")
    data = json.loads(_vsf_run_py(spec))
    assert data["error_codes_found"] == ["INVALID_AMOUNT", "ACCOUNT_NOT_FOUND"]
    assert data["valid"] is True


# ── parse_test_results 契约 ───────────────────────────────────────────────

_PTR_SUREFIRE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.AccountServiceTest" tests="3" failures="0" errors="0">
  <testcase name="shouldRejectZeroAmount" classname="com.example.AccountServiceTest" time="0.001"/>
  <testcase name="shouldPassValidTransfer" classname="com.example.AccountServiceTest" time="0.002"/>
  <testcase name="shouldRejectSelfTransfer" classname="com.example.AccountServiceTest" time="0.001"/>
</testsuite>
"""

_PTR_CONTRACT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.TransferContractTest" tests="2" failures="1" errors="0">
  <testcase name="shouldReturnSuccessOnValidRequest" classname="com.example.TransferContractTest" time="0.005"/>
  <testcase name="shouldReturn400OnInvalidAmount" classname="com.example.TransferContractTest" time="0.003">
    <failure message="expected 400 but was 200"/>
  </testcase>
</testsuite>
"""

_PTR_JACOCO_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<report>
  <counter type="LINE" missed="5" covered="50"/>
  <counter type="BRANCH" missed="3" covered="15"/>
  <counter type="METHOD" missed="2" covered="20"/>
  <counter type="INSTRUCTION" missed="10" covered="90"/>
  <counter type="COMPLEXITY" missed="3" covered="10"/>
</report>
"""


def _ptr_make_fixture(tmp_path: Path) -> tuple[Path, Path]:
    sf_dir = tmp_path / "surefire-reports"
    sf_dir.mkdir()
    (sf_dir / "TEST-AccountServiceTest.xml").write_text(_PTR_SUREFIRE_XML, encoding="utf-8")
    (sf_dir / "TEST-TransferContractTest.xml").write_text(_PTR_CONTRACT_XML, encoding="utf-8")
    jacoco = tmp_path / "jacoco.xml"
    jacoco.write_text(_PTR_JACOCO_XML, encoding="utf-8")
    return sf_dir, jacoco


def _ptr_run_py(sf_dir: Path, jacoco: Path) -> str:
    r = subprocess.run(
        [sys.executable, str(_PTR_PY), "--surefire", str(sf_dir),
         "--jacoco", str(jacoco), "--json"],
        capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"py 退出码 {r.returncode}\n{r.stderr}"
    return r.stdout


def test_parse_test_results_py(tmp_path: Path):
    """parse_test_results: Python 输出契约（unit/contract/coverage/source_lines）。

    v0.6 起 parse_test_results 输出 ``source_lines``（行级覆盖率，供 diff
    coverage 判定），不再输出 ``classes`` 键。
    """
    sf_dir, jacoco = _ptr_make_fixture(tmp_path)
    data = json.loads(_ptr_run_py(sf_dir, jacoco))
    # 单测/契约测试明细
    assert data["unit_tests"]["total"] == 3
    assert data["unit_tests"]["passed"] == 3
    assert data["contract_tests"]["total"] == 2
    assert data["contract_tests"]["failed"] == 1
    # 覆盖率聚合（键为 line_coverage 等，非 line_percent）
    assert data["coverage"]["line_coverage"] == round(50 / (5 + 50) * 100)
    # v0.6：source_lines 键存在（行级覆盖率），classes 键已删除
    assert "source_lines" in data
    assert "classes" not in data


# ── scan_test_stack 契约 ───────────────────────────────────────────────────

_STS_POWERMOCK_JAVA = """\
package com.example;

import org.powermock.api.mockito.PowerMockito;

class PowerMockTest { }
"""

_STS_SPRINGBOOT_JAVA = """\
package com.example;

import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
class IntegrationTest { }
"""

_STS_CLEAN_JAVA = """\
package com.example;

import org.junit.jupiter.api.Test;

class CleanTest { }
"""


def _sts_make_fixture(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "ATest.java").write_text(_STS_POWERMOCK_JAVA, encoding="utf-8")
    (src / "BTest.java").write_text(_STS_CLEAN_JAVA, encoding="utf-8")
    (src / "ZTest.java").write_text(_STS_SPRINGBOOT_JAVA, encoding="utf-8")
    return src


def _sts_run_py(source_dir: Path) -> str:
    r = subprocess.run(
        [sys.executable, str(_STS_PY), "--source", str(source_dir), "--json"],
        capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"py 退出码 {r.returncode}\n{r.stderr}"
    return r.stdout


def test_scan_test_stack_py(tmp_path: Path):
    """scan_test_stack: Python 输出契约（检出 PowerMock + @SpringBootTest）。"""
    src = _sts_make_fixture(tmp_path)
    data = json.loads(_sts_run_py(src))
    findings = data["forbidden_findings"]
    types = {f["type"] for f in findings}
    assert "powermock" in types
    assert "springboottest" in types
    # 干净测试类不误报
    assert all("CleanTest" not in f.get("file", "") for f in findings)


# ── run_gate 契约（降级模式，fixture 无 pom.xml） ─────────────────────────

_RG_SPEC_MD = """\
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

_RG_IMPACT_REPORT_MD = """\
## ImpactReport

### 影响范围
- com.example.AccountService.transfer (R1, R6, R7)

### 风险等级
risk_level: medium

### 受影响规则编号清单
affected_rules:
  - rule: R1
    change_type: modified
    risk: medium

### 建议测试策略
strategy: full
"""

_RG_CONFIG_YML = """\
gate:
  unit_test:
    line_coverage_min: 80
    branch_coverage_min: 70
    method_coverage_min: 80
    instruction_coverage_min: 85
    complexity_coverage_min: 70
    pass_rate_min: 100
  contract_test:
    pass_rate_min: 95
  spec_traceability:
    spec_rule_coverage_min: 100
    require_displayname_match: true

risk_overrides:
  high:
    unit_test:
      line_coverage_min: 90
      method_coverage_min: 90
      instruction_coverage_min: 90
      complexity_coverage_min: 80
      pass_rate_min: 100
    contract_test:
      pass_rate_min: 100
  medium:
    unit_test:
      line_coverage_min: 80
      method_coverage_min: 80
      instruction_coverage_min: 85
      complexity_coverage_min: 70
  low:
    unit_test:
      line_coverage_min: 70
      method_coverage_min: 70
      instruction_coverage_min: 80
      complexity_coverage_min: 60
"""

_RG_TEST_JAVA = """\
package com.example;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;

class AccountServiceTest {

    @Test
    @DisplayName("R1-金额校验")
    void testR1() {
    }

    @Test
    @DisplayName("R2-余额校验")
    void testR2() {
    }

    @Test
    @DisplayName("R3-冻结校验")
    void testR3() {
    }

    @Test
    @DisplayName("R4-额度上限")
    void testR4() {
    }

    @Test
    @DisplayName("R5-审计日志")
    void testR5() {
    }

    @Test
    @DisplayName("R6-原子操作")
    void testR6() {
    }

    @Test
    @DisplayName("R7-自转账校验")
    void testR7() {
    }
}
"""


def _rg_make_fixture(tmp_path: Path) -> dict:
    """创建降级模式 fixture（无 pom.xml）。

    beta 简化降级语义：无 java/mvn 或 ``--project`` 目录无 pom.xml 即降级。
    """
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(_RG_SPEC_MD, encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "AccountService.java").write_text(
        _make_full_coverage_java(), encoding="utf-8"
    )

    test_dir = tmp_path / "test-src"
    test_dir.mkdir()
    (test_dir / "AccountServiceTest.java").write_text(_RG_TEST_JAVA, encoding="utf-8")

    feature_dir = tmp_path / "specs" / "001-bank-transfer"
    docs_dir = feature_dir / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "impact-report.md").write_text(_RG_IMPACT_REPORT_MD, encoding="utf-8")

    config_path = tmp_path / "testing-config.yml"
    config_path.write_text(_RG_CONFIG_YML, encoding="utf-8")

    return {
        "tmp_path": tmp_path,
        "src": src_dir,
        "test_src": test_dir,
        "spec": spec_path,
        "feature_dir": feature_dir,
        "docs_dir": docs_dir,
        "config": config_path,
    }


def _rg_run_py(fx: dict) -> str:
    r = subprocess.run(
        [sys.executable, str(_RG_PY),
         "--source", str(fx["src"]),
         "--test-source", str(fx["test_src"]),
         "--spec", str(fx["spec"]),
         "--project", str(fx["tmp_path"]),
         "--feature-dir", str(fx["feature_dir"]),
         "--config", str(fx["config"]),
         "--json"],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"py 退出码 {r.returncode}\nstdout: {r.stdout}\nstderr: {r.stderr}"
    return r.stdout


def test_run_gate_degraded_py(tmp_path: Path):
    """run_gate（降级模式）：Python 输出契约 + gate-result.md。

    beta 简化降级语义：fixture 无 pom.xml -> degraded。输出含
    degraded_reason / diff_coverage / diff_threshold 等新字段，
    不再含 scope_* / suggestion / located_module。
    """
    fx = _rg_make_fixture(tmp_path)
    data = json.loads(_rg_run_py(fx))

    # 降级模式 PASS + 全部契约字段
    assert data["status"] == "PASS"
    assert data["mode"] == "degraded"
    assert data["mvn_clean_test"] == "SKIPPED"
    assert data["risk_level"] == "medium"
    assert data["spec_coverage"]["coverage_percent"] == 100
    assert data["fail_reasons"] == []

    # beta 简化降级语义：无 pom.xml -> degraded_reason 非空
    assert data["degraded_reason"], "降级模式必须给出 degraded_reason"
    assert "pom.xml" in data["degraded_reason"]

    # v0.6 新字段：diff coverage 语义（降级时 N/A）
    assert "diff_coverage" in data
    assert "diff_threshold" in data
    assert data["diff_coverage"]["mode"] == "N/A"

    # 已删除字段：scope_* / suggestion / located_module 不再输出
    assert "suggestion" not in data
    assert "located_module" not in data
    assert not any(k.startswith("scope_") for k in data)

    # gate-result.md 由脚本写出（beta 简化降级文案）
    md = (fx["docs_dir"] / "gate-result.md").read_text(encoding="utf-8")
    assert "## Gate Result: PASS" in md
    assert "降级模式（无 java/mvn 或 --project 目录无 pom.xml）" in md
