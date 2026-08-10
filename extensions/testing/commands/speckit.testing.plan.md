---
description: "Speckit Testing 测试计划生成：读 ImpactReport 与 contracts/spec.md，按风险套验收阈值，生成契约测试与单测用例清单及排期建议"
---

# Speckit Testing Plan

本命令为手动命令（不绑钩子），在 `speckit.plan` 之后、`speckit.tasks`
之前运行。读取 `ImpactReport` 产物与 `contracts/` 接口契约定义，按风险
等级套用验收阈值，生成契约测试与单测用例清单（标注规则编号）及排期
建议，引用 `test-plan-template` 模板组织文档结构。

## 触发方式

- **手动**：用户在 AI Agent 中直接调用本命令。
- 不绑钩子（`before_plan` 已绑 `speckit.testing.impact`，本命令在 plan
  之后手动运行）。

## 输入

- `ImpactReport` 产物（取 `risk_level` 与 `affected_rules`）
- `spec.md`（`business_rules` + `api` 段）
- `contracts/` 接口契约定义（每个接口含正向请求与错误码清单）

## 处理逻辑

### 步骤 1：读取影响分析，套用验收阈值

读取 `ImpactReport.risk_level`（`high` / `medium` / `low`），按
`testing-config.yml` 的 `risk_overrides` 与 `gate` 默认值合并，确定本
测试计划的验收阈值：

| 风险 | 行覆盖率 | 契约测试通过率 | 单测通过率 | Spec 覆盖率 |
|------|----------|----------------|------------|-------------|
| high | >=90% | 100% | 100% | 100% |
| medium | >=80% | >=95% | 100% | 100% |
| low | >=70% | >=95% | 100% | 100% |

阈值记入 `TestPlan.acceptance_thresholds`，作为后续 `speckit.testing.gate`
判定的依据。

### 步骤 2：遍历 contracts/，生成契约测试用例

遍历 `contracts/` 下每个接口契约定义，为每个接口生成契约测试用例：

- **正向用例**：每个接口 1 条（`CT-<接口>-happy`）
- **反向用例**：每个错误码 1 条（`CT-<接口>-<错误码>`）
- 每条标注对应的规则编号（从接口契约的 `rules` 字段或 `business_rules`
  反查）
- 命名规则：`CT-<序号>`（如 `CT-01`、`CT-02`...）

契约不变量：每个 `Contract` 至少 1 条正向 + 每错误码 1 条反向契约测试。

### 步骤 3：遍历 business_rules，生成单测用例

遍历 `spec.md` 的 `business_rules` 段每条规则，生成单测用例：

- **正常路径**：`UT-<规则>-normal`
- **异常路径**：`UT-<规则>-abnormal`
- **边界路径**：`UT-<规则>-boundary`
- 命名规则：`UT-<序号>`（如 `UT-01`、`UT-02`...）
- 每条 `@DisplayName` 必须以 `R<n>-` 开头（如 `R1-转账金额为0应拒绝`）

契约不变量：每条 `SpecRule` 至少 1 条单测。

### 步骤 4：排期建议

按以下原则给出排期建议（`TestPlan.schedule`）：

- **契约测试先行**：契约测试在排期上先于单测（验证接口契约是后续
  实现的前置条件）
- **单测次之**：单测在契约测试通过后进行
- **高风险规则优先**：`high` 风险规则的用例在同类用例中优先排
- **依赖顺序**：被依赖的接口/规则的用例先于依赖方

排期格式：每条用例标注 `phase`（contract / unit）、`priority`
（high / medium / low）、`depends_on`（前置用例编号）。

## 输出（TestPlan）

引用 `test-plan-template` 模板组织文档结构：

```markdown
# Test Plan

## 验收阈值（按 ImpactReport.risk_level=high）
- line_coverage_min: 90
- contract_test_pass_rate_min: 100
- unit_test_pass_rate_min: 100
- spec_rule_coverage_min: 100

## 契约测试用例（CT-xx）
| 编号 | 接口 | 类型 | 错误码 | 规则 | 优先级 |
|------|------|------|--------|------|--------|
| CT-01 | POST /transfer | 正向 | - | R1,R6,R7 | high |
| CT-02 | POST /transfer | 反向 | INVALID_AMOUNT | R1 | high |
| CT-03 | POST /transfer | 反向 | SELF_TRANSFER | R7 | high |

## 单测用例（UT-xx）
| 编号 | 规则 | 路径 | 描述 | @DisplayName | 优先级 |
|------|------|------|------|--------------|--------|
| UT-01 | R1 | 正常 | 转账金额合法 | R1-转账金额合法应成功 | high |
| UT-02 | R1 | 异常 | 转账金额为0 | R1-转账金额为0应抛出INVALID_AMOUNT | high |
| UT-03 | R1 | 边界 | 转账金额为最小单位 | R1-转账金额为最小单位应成功 | high |

## 排期建议
| 阶段 | 用例 | 依赖 |
|------|------|------|
| contract | CT-01, CT-02, CT-03 | - |
| unit | UT-01, UT-02, UT-03 | CT-01 |

## 产物路径
test_plan_path: .specify/extensions/testing/test-plan.md
```

## 契约不变量

- 每个 `Contract` 至少 1 条正向 + 每错误码 1 条反向契约测试
- 每条 `SpecRule` 至少 1 条单测
- 验收阈值必须与 `ImpactReport.risk_level` 匹配：
  - `high` -> 行覆盖率 90% / 契约通过率 100% / 单测通过率 100%
  - `medium` -> 行覆盖率 80% / 契约通过率 95% / 单测通过率 100%
  - `low` -> 行覆盖率 70% / 契约通过率 95% / 单测通过率 100%
- `TestPlan` 产物路径必须可被后续 `speckit.tasks` 读取（默认写入
  `.specify/extensions/testing/test-plan.md`）

## 模板引用

本命令产出文档的组织结构遵循 `test-plan-template` 模板
（`templates/test-plan-template.md`），含：

- 验收阈值段
- 契约测试用例表
- 单测用例表
- 排期建议表

## Done When

- [ ] `ImpactReport.risk_level` 已读取，验收阈值已套用
- [ ] `contracts/` 每个接口已生成契约测试用例（正向 1 + 每错误码 1）
- [ ] `business_rules` 每条规则已生成单测用例（正常 / 异常 / 边界）
- [ ] 排期建议已产出（契约测试先行，单测次之）
- [ ] `TestPlan` 已按 `test-plan-template` 组织并写入产物路径
