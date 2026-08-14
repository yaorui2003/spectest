---
description: "Speckit Testing 测试报告：校验门禁已执行，汇总测试结果，生成 Spec 追溯矩阵并引用 ImpactReport 产物（不重生成）"
---

# Speckit Testing Report

本命令为手动命令（不绑钩子），在 `speckit.testing.gate` 通过后运行。
校验门禁已执行，汇总测试结果（覆盖率与通过率），生成 Spec 追溯矩阵
（R1..Rn -> @Spec 代码位置 -> 单测 @DisplayName -> 契约测试 CT 编号），
引用（不重生成）`ImpactReport` 产物，最终引用 `spec-trace-matrix`
模板组织文档结构。

## 触发方式

- **手动**：用户在 AI Agent 中直接调用本命令。
- 不绑钩子（`after_implement` 已绑 `speckit.testing.impact` + `speckit.testing.gate`
  两条命令，本命令在 gate 通过后手动运行）。

## 输入

- `GateResult` 产物（含 PASS/FAIL 判定、单测明细、契约测试明细、Spec
  规则覆盖矩阵）
- `ImpactReport` 产物（引用，不重复生成）
- `spec.md`（`business_rules` 规则编号清单）
- 扫描脚本产出的覆盖矩阵（`@Spec` 注解分布 JSON）

## 处理逻辑

### 步骤 1：校验门禁已执行

读取 `GateResult` 产物路径（默认
`specs/<feature>/docs/gate-result.md`）：

- 若产物不存在 -> **拒绝生成报告**，输出提示：

  ```text
  ## ⛔ 门禁未执行

  未检测到 GateResult 产物。请先运行门禁命令（speckit.testing.gate），
  门禁通过后再运行本报告命令。

  提示：可运行门禁命令（令牌 __SPECKIT_COMMAND_TESTING_GATE__）。
  ```

- 若产物存在但判定为 FAIL -> **拒绝生成报告**，输出提示要求先修复并
  重新通过门禁。
- 若产物存在且判定为 PASS -> 继续步骤 2。

注意：上方令牌 `__SPECKIT_COMMAND_TESTING_GATE__` 由 spec-kit 注册时
按当前 integration 的 `invoke_separator` 渲染为实际调用形式，勿硬编码
具体调用路径。

### 步骤 2：汇总测试执行结果

从 `GateResult` 读取并汇总：

- **覆盖率**：
  - 行覆盖率（与阈值比对，标注 PASS/FAIL）
  - 分支覆盖率（与阈值比对）
- **通过率**：
  - 单测通过率（总数 / 通过 / 失败）
  - 契约测试通过率（总数 / 通过 / 失败）
- **Spec 规则覆盖**：
  - 规则总数 / 已注解数 / 未实现规则数 / 孤儿注解数
  - DisplayName 对齐数

汇总结果记入 `TestResultSummary`。

### 步骤 3：生成 Spec 追溯矩阵

遍历 `spec.md` 全部 `business_rules` 规则编号（R1..Rn），为每条规则
构建一行追溯记录：

| 字段 | 来源 |
|------|------|
| 规则编号 | spec.md business_rules |
| @Spec 代码位置 | 扫描脚本 JSON 的 `annotated_rules` |
| 单测 @DisplayName | 解析单测方法 @DisplayName 中的规则编号 |
| 契约测试 CT 编号 | 测试计划 TestPlan 的 CT-xx（按规则编号反查） |

追溯矩阵记入 `TraceabilityMatrix`，每行一条 SpecRule，必须覆盖
spec.md 全部 business_rules 规则（无 @Spec 的规则对应位置标注
"未实现"）。

### 步骤 4：引用 ImpactReport 产物（不重生成）

读取 `ImpactReport` 产物路径（默认
`specs/<feature>/docs/impact-report.md`），在报告中以引用形式
（链接/路径）呈现其 `risk_level` 与 `affected_rules` 摘要，**不重复
执行影响分析**。报告中明确标注：

```text
## 影响分析（引用）

本节引用 ImpactReport 产物，不重复生成：
- 产物路径: specs/<feature>/docs/impact-report.md
- 风险等级: high
- 受影响规则数: N
（详见产物原文）
```

## 输出（TraceabilityMatrix + 测试结果汇总）

引用 `spec-trace-matrix` 模板组织文档结构：

```markdown
# Test Report

## 门禁状态
gate_status: PASS
gate_run_at: 2026-08-10T...

## 测试结果摘要
- 行覆盖率: 92% (阈值 >=90%, PASS)
- 分支覆盖率: 78% (阈值 >=70%, PASS)
- 单测通过率: 100% (N/N, 阈值 100%, PASS)
- 契约测试通过率: 100% (N/N, 阈值 100%, PASS)
- Spec 规则覆盖率: 100% (7/7, 阈值 100%, PASS)

## Spec 追溯矩阵（TraceabilityMatrix）
| 规则 | @Spec 代码位置 | 单测 @DisplayName | 契约测试 CT |
|------|----------------|-------------------|-------------|
| R1 | AccountService.transfer:42 | R1-转账金额为0应抛出INVALID_AMOUNT | CT-02 |
| R2 | OrderService.updateStatus:18 | R2-订单状态流转合法 | CT-05 |
| ... | ... | ... | ... |
| R7 | AccountService.transfer:46 | R7-自转账应抛出SELF_TRANSFER_NOT_ALLOWED | CT-03 |

## 影响分析（引用）
- 产物路径: specs/<feature>/docs/impact-report.md
- 风险等级: high
- 受影响规则数: 5
（详见产物原文，本报告不重复生成）

## 产物路径
report_path: specs/<feature>/docs/test-report.md
```

## 契约不变量

- **门禁未执行时拒绝生成报告**：`GateResult` 产物不存在或 FAIL 时
  必须拒绝并提示先运行门禁
- **追溯矩阵必须覆盖 spec.md 全部 business_rules 规则**：每条规则一行，
  无 @Spec 的规则也要列出（位置标注"未实现"）
- **必须引用而非重生成 ImpactReport**：仅以路径/链接引用产物，不重新
  执行影响分析逻辑

## 模板引用

本命令产出文档的组织结构遵循 `spec-trace-matrix` 模板
（`templates/spec-trace-matrix.md`），含：

- 门禁状态段
- 测试结果摘要段
- Spec 追溯矩阵表
- 影响分析引用段

## Done When

- [ ] 门禁已执行校验通过（`GateResult` 存在且 PASS）
- [ ] 测试结果已汇总（覆盖率 + 通过率）
- [ ] Spec 追溯矩阵已生成（覆盖全部 business_rules 规则）
- [ ] `ImpactReport` 产物已引用（路径呈现，未重生成）
- [ ] 报告已按 `spec-trace-matrix` 模板组织并写入产物路径
