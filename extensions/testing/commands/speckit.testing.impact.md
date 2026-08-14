---
description: "Speckit Testing 影响分析：解析 spec.md 变更与代码结构依赖，按规则语义风险分级，产出受影响规则清单与建议测试策略"
---

# Speckit Testing Impact

本命令为 `after_implement` 钩子（`optional: false`，与
`speckit.testing.gate` 同事件，impact 在前产出风险、gate 在后消费）的变更
影响分析。Spec 发生变更（新增/修改/删除 `business_rules`）后立即触发，
解析变更范围、扫描代码结构依赖、按规则语义风险分级，产出 `ImpactReport`
供后续 `speckit.testing.gate` 读取风险等级与
受影响规则清单。

## 触发方式

- **手动**：用户在 AI Agent 中直接调用本命令。
- **自动**：`after_implement` 钩子触发（`optional: false`，与 gate 同事件，
  impact 在前执行）。AI Agent 读取 `.specify/extensions.yml` 中
  `hooks.after_implement` 段（列表形式），按顺序执行 impact -> gate。

## 输入

- **git diff + 源代码**：`git diff`（含 spec.md 与代码变更）+ 源码目录树
- 仓库代码结构（用于依赖分析）：
  - 源码目录树（包/类/方法清单）
  - 现有 `@Spec` 注解分布（若已接入）
  - 模块间引用关系（import / 调用链）

## 处理逻辑

### 步骤 1：解析 git diff 中的 spec.md 变更

从 git diff 中提取 spec.md 的变更（新增/修改/删除 business_rules），提取
`business_rules` 段的变更：

- **新增规则**：当前有、上一版本无的规则编号（如新增 `R8`）
- **修改规则**：规则编号不变但描述/约束变化的规则
- **删除规则**：上一版本有、当前无的规则编号

变更分类计入 `changed_rules`（含变更类型 `added` / `modified` / `removed`）。

### 步骤 2：扫描代码结构，做依赖分析

扫描仓库代码结构，识别受变更影响的代码位置：

- 遍历源码目录树，识别实现受影响规则的类与方法
- 若已接入 `@Spec` 注解，按注解 `rule` 字段反向定位代码位置
- 分析模块间引用关系（import / 调用链），识别间接受影响的类/方法
- 受影响代码位置（类/方法）计入 `affected_locations`

### 步骤 3：按规则语义风险分级

依据规则语义对每条受影响规则分级（取该规则集合中的最高等级作为整体
`risk_level`）：

| 风险等级 | 规则语义特征 | 示例 |
|----------|--------------|------|
| `high` | 涉及资金、权限、数据完整性 | 转账金额校验、鉴权、事务原子性 |
| `medium` | 业务流转、状态变更 | 订单状态机、流程编排 |
| `low` | 校验类、展示类 | 字段格式校验、UI 渲染 |

分级规则：

- 规则描述含"金额/资金/转账/支付/扣款"、"权限/鉴权/授权"、
  "事务/原子/一致性"、"数据完整性/幂等" -> `high`
- 规则描述含"状态/流程/流转/编排"、"业务规则" -> `medium`
- 其余校验类、辅助类规则 -> `low`
- 整体 `risk_level` = 受影响规则中最高等级

### 步骤 4：产出受影响规则清单与建议测试策略

合并步骤 1-3 结果：

- **受影响规则清单**（`affected_rules`）：每条含规则编号、变更类型、
  风险等级、受影响代码位置
- **建议测试策略**：
  - `high` 风险 -> 全量测试（契约测试 + 单测全覆盖 + 回归套件）
  - `medium` 风险 -> 增量测试（受影响规则的契约测试 + 单测 + 关联回归）
  - `low` 风险 -> 增量测试（仅受影响规则的单测）
- **契约测试条数建议**：受影响规则数 × 每规则契约数（正向 1 + 每错误码 1）
- **单测条数建议**：受影响规则数 × 3（正常 / 异常 / 边界）

## 输出（ImpactReport）

```markdown
## ImpactReport

### 影响范围（受影响代码位置清单）
- com.example.AccountService.transfer (R1, R6, R7)
- com.example.OrderService.updateStatus (R4)
- com.example.PaymentService.charge (R1)

### 风险等级
risk_level: high

### 受影响规则编号清单
affected_rules:
  - rule: R1
    change_type: modified
    risk: high
    locations: [com.example.AccountService.transfer:42]
  - rule: R7
    change_type: added
    risk: high
    locations: [com.example.AccountService.transfer:46]

### 建议测试策略
strategy: full
contract_test_count_estimate: 12
unit_test_count_estimate: 18
rationale: R1 涉及资金校验（high），触发全量测试策略

### 产物路径
impact_report_path: specs/<feature>/docs/impact-report.md
```

## 契约不变量

- `affected_rules` 中每个规则编号必须存在于 `spec.md` 的
  `business_rules` 段（删除的规则不计入 `affected_rules`，仅计入
  `changed_rules` 中 `change_type: removed` 项）
- `risk_level` 必须为 `high` / `medium` / `low` 之一
- `after_implement` 触发时，`ImpactReport` 产物路径必须可被后续
  `speckit.testing.gate` 读取（默认写入
  `specs/<feature>/docs/impact-report.md`）

## 后续动作

`ImpactReport` 产出后，下游命令会读取：

- `speckit.testing.gate` 读取 `risk_level` 套用门禁阈值，读取
  `affected_rules` 做风险定向校验（建议运行门禁命令：
  `__SPECKIT_COMMAND_TESTING_GATE__`，注：本命令不直接调用，
  由 after_implement 钩子按列表顺序在 impact 之后自动调用 gate）

注意：`speckit.testing.plan`（令牌 `__SPECKIT_COMMAND_TESTING_PLAN__`）
不再读取 ImpactReport 产物；上方 `__SPECKIT_COMMAND_TESTING_GATE__`
令牌由 spec-kit 注册时按当前 integration 的 `invoke_separator` 渲染为
实际调用形式，勿硬编码具体调用路径。

## 降级

当 git diff 为空或无 spec.md 变更时，将全文视为新增，全部
`business_rules` 规则计入 `changed_rules`（`change_type: added`），
其余流程不变。

当代码结构无法扫描（空仓库或非 Java 项目）时，`affected_locations` 为
空，仅基于规则语义做风险分级，`affected_rules` 仍按 spec 变更产出。

## Done When

- [ ] `spec.md` diff 已解析，`changed_rules` 已产出
- [ ] 代码结构依赖分析已完成（或降级说明已给出）
- [ ] 每条受影响规则已分级（`high` / `medium` / `low`）
- [ ] `affected_rules` 清单与建议测试策略已产出
- [ ] `ImpactReport` 已写入产物路径
