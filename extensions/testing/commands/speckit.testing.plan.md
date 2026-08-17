---
description: "Speckit Testing 测试计划生成：以 speckit.plan 已产出的 spec.md/plan.md/contracts 等文档为输入，生成契约测试、单测用例与前端测试项（TC，e2e 规划）清单，注重单测质量，按风险或默认阈值给验收标准与排期建议"
---

# Speckit Testing Plan

本命令为手动命令（不绑钩子），在 `speckit.plan` 之后、`speckit.tasks`
之前运行。**以 speckit.plan 已产出的 md 文档为输入**（spec.md / plan.md /
contracts/ / data-model.md / research.md），生成契约测试、单测用例清单
（标注规则编号）与前端测试项（TC，e2e 规划简版）、验收阈值与排期建议，
引用 `test-plan-template` 模板组织文档结构。

> **ImpactReport 为可选输入**：用例清单的生成完全不依赖 ImpactReport--
> 它仅用于步骤 1 的阈值分档。若 ImpactReport 存在（如 after_implement
> 阶段补跑本命令时）则按其 `risk_level` 套风险档阈值；否则用
> `testing-config.yml` 的 `gate` 默认阈值。这样 plan 可在 impact 产出前
> 独立运行。

## 触发方式

- **手动**：用户在 AI Agent 中直接调用本命令。
- 不绑钩子。

## 输入（已有 md 产物）

| 产物 | 必需性 | 用途 |
|---|---|---|
| `spec.md` | REQUIRED | `business_rules`（R1..Rn）+ `api` 段，用例生成依据 |
| `plan.md` | REQUIRED | speckit.plan 产出的实现计划，含 contracts 路径与技术决策 |
| `contracts/` | REQUIRED | 接口契约定义（每接口含正向请求与错误码清单），契约测试依据 |
| `data-model.md` | RECOMMENDED | 数据模型与字段约束，单测边界值与 fixture 依据（缺失时降级：边界值按 `contracts/` 字段约束或 `spec.md` 规则语义推导，并在 TestPlan 中注明"data-model.md 缺失，边界值为推导值"） |
| `research.md` | OPTIONAL | 调研结论，影响测试策略（缺失时不影响用例生成，策略按默认 TDD 流程走） |
| `ImpactReport` | OPTIONAL | 存在则取 `risk_level` 套风险档阈值；缺失用默认档 |

> 任一 REQUIRED 产物缺失时，本命令**不得臆造**--向用户报缺什么、
> 需先跑哪个命令（如 plan.md 缺失 -> 先跑 `/speckit.plan`）。

## 处理逻辑

### 步骤 1：套用验收阈值

读取 `ImpactReport.risk_level`（若存在）；缺失则标记 `risk_level=default`。
按 `testing-config.yml` 的 `risk_overrides`（存在时）与 `gate` 默认值
合并确定阈值：

| 风险 | 行覆盖率 | 分支覆盖率 | 方法覆盖率 | 指令覆盖率 | 复杂度覆盖率 | 单测通过率 | 契约通过率 | Spec 覆盖率 |
|------|----------|------------|------------|------------|--------------|------------|------------|-------------|
| high | >=90% | >=70% | >=90% | >=90% | >=80% | 100% | 100% | 100% |
| medium | >=80% | >=70% | >=80% | >=85% | >=70% | 100% | >=95% | 100% |
| low | >=70% | >=70% | >=70% | >=80% | >=60% | 100% | >=95% | 100% |
| default（无 ImpactReport） | >=80% | >=70% | >=80% | >=85% | >=70% | 100% | >=95% | 100% |

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

### 步骤 2.5：生成前端测试项（TC，e2e 规划简版）

遍历 `spec.md` 的 `business_rules`，识别**用户可感知行为**（校验提示 / 错误
提示 / 成功反馈 / 交互流程）的规则，为每条生成一条前端测试项（`TC-<序号>`，
如 TC-01、TC-02...，编号与 CT/UT 独立）：

- **分类标签**：
  - `[正向]`：正常业务流（happy path），如"正常转账全流程"
  - `[异常]`：错误/校验场景的前端提示，如"转账金额校验提示"、"余额不足提示"
  - `[交互]`：UI 交互流，如"转账确认弹窗交互"、"多步操作"
- **覆盖规则**：标注对应 `business_rules` 编号（可多个，逗号分隔），保证
  与后端规则可追溯
- **详略**：本清单为**规划级简版**（编号 + 场景 + 标签 + 覆盖规则），**不写
  测试步骤/预期结果**；详细测试步骤与预期由实现后的 `speckit.testing.impact`
  生成功能测试案例集（写入 `impact-report.md`，供前端 e2e 测试 AI 使用），
  此处不重复展开

> **e2e 定位**：前端测试项用于 e2e 测试**规划**，**不进门槛**——gate 只校验
> 后端单测/契约测试，不要求生成或执行 e2e 测试代码。纯后端内部行为（事务、
> 幂等、数据一致性）若无可见 UI 效果，不生成 TC。

### 步骤 3：遍历 business_rules，生成单测用例（注重质量）

遍历 `spec.md` 的 `business_rules` 段每条规则，按以下**质量要求**生成
单测用例。单测质量是本命令的核心产出，提示词务必遵循。

#### 3.1 用例维度（每条规则至少 3 条）

- **正常路径**：`UT-<规则>-normal`（合法输入，验证成功语义与副作用）
- **异常路径**：`UT-<规则>-abnormal`（每个错误码一条，验证抛出与错误码）
- **边界路径**：`UT-<规则>-boundary`（参考 `data-model.md` 字段约束：
  最小值 / 最大值 / 空值 / 越界 / 临界等值）

#### 3.2 单测质量要求（MUST）

1. **`@DisplayName` 格式**：`R<n>-<具体场景描述>`，描述须含期望结果，
   如 `R1-转账金额为0应抛出INVALID_AMOUNT`（非泛泛"测试金额校验"）。
2. **断言业务语义**：错误码匹配 / 状态变更 / 副作用验证（`verify` 调用）；
   **禁止仅用 `assertNotNull` / `assertTrue` 等弱断言**。每个测试方法至少
   一个业务语义断言。
3. **外部依赖 MUST Mock**：DB / RPC / MQ / 外部接口一律 Mockito
   （`@Mock` + `@InjectMocks`），单测不依赖真实基础设施，不起容器。
4. **given/when/then 三段式**：given 明确 fixture 与 mock 桩；when 调用
   被测方法；then 断言返回值 + `verify` 副作用（如违规场景不应触发
   `debit`/`credit`）。
5. **一个方法聚焦一个场景**：一个测试方法一个断言主旨，避免多场景堆叠
   导致失败定位困难。
6. **异常路径用 `assertThrows`**：捕获业务异常并断言错误码
   （`assertEquals("INVALID_AMOUNT", thrown.getCode())`）。
7. **边界值依据 `data-model.md`**：字段约束驱动的边界（如金额 > 0 的
   边界：0 / 最小单位 / 最大值），不要凭空造边界。**降级**：`data-model.md`
   缺失时，边界值按 `contracts/` 字段约束或 `spec.md` 规则语义推导（仍不得
   臆造），并在 TestPlan 边界路径用例旁注明来源为推导值。
8. **命名 `UT-<序号>`**，每条标注规则编号，与代码侧 `@Spec(rule="Rn")`
   双向对齐。

契约不变量：每条 `SpecRule` 至少 3 条单测（正常 / 异常 / 边界）。

### 步骤 4：排期建议（单测先行）

按以下原则给排期（`TestPlan.schedule`）：

- **单测先行**：单测在排期上先于契约测试（骨架先行已保证单测可编译运行）
- **契约测试次之**：契约测试在单测通过后进行
- **高风险规则优先**：`high` 风险规则的用例在同类用例中优先排
- **依赖顺序**：被依赖的接口/规则的用例先于依赖方

排期格式：每条用例标注 `phase`（unit / contract）、`priority`
（high / medium / low）、`depends_on`（前置用例编号）。

## 输出（TestPlan）

引用 `test-plan-template` 模板组织文档结构：

```markdown
# Test Plan

## 验收阈值（risk_level=<risk_level 或 default>）
- line_coverage_min / branch_coverage_min / method_coverage_min /
  instruction_coverage_min / complexity_coverage_min
- unit_pass_rate_min / contract_pass_rate_min / spec_rule_coverage_min

## 契约测试用例（CT-xx）
| 编号 | 接口 | 类型 | 错误码 | 规则 | 优先级 |

## 单测用例（UT-xx）
| 编号 | 规则 | 路径 | @DisplayName | 被测方法 | 优先级 |

## 前端测试项（TC-xx，e2e 规划简版）
| 编号 | 场景 | 测试类型 | 覆盖规则 |
| TC-01 | 正常转账全流程 | [正向] | R6 |
| TC-02 | 转账金额校验提示 | [异常] | R1 |
| TC-03 | 冻结账户转账提示 | [异常] | R3 |
| TC-04 | 余额不足提示 | [异常] | R4 |
| TC-05 | 转账成功结果展示 | [正向] | R6 |
| TC-06 | 转账确认弹窗交互 | [交互] | R6 |

## 排期建议（单测先行）
| 阶段 | 用例 | 依赖 |

## 产物路径
test_plan_path: specs/<feature>/docs/test-plan.md
```

## 契约不变量

- 每个 `Contract` 至少 1 条正向 + 每错误码 1 条反向契约测试
- 每条 `SpecRule` 至少 3 条单测（正常 / 异常 / 边界），满足 3.2 质量要求
- 单测 `@DisplayName` 格式 `R<n>-<描述>`，与 `@Spec(rule="Rn")` 双向对齐
- 每条 TC 的覆盖规则必须存在于 `business_rules`
- 前端测试项为规划级简版（不含步骤/预期），**不进门槛**；详细内容由
  `speckit.testing.impact` 生成，此处不重复展开
- 阈值：`ImpactReport` 存在则风险档，否则 default 档
- `TestPlan` 产物路径必须可被后续 `speckit.tasks` 读取（默认写入
  `specs/<feature>/docs/test-plan.md`）

## 模板引用

本命令产出文档的组织结构遵循 `test-plan-template` 模板
（`templates/test-plan-template.md`），含：

- 验收阈值段
- 契约测试用例表
- 单测用例表
- 前端测试项表（TC，e2e 规划）
- 排期建议表（单测先行）

## Done When

- [ ] `spec.md` / `plan.md` / `contracts/` 已读取（缺失即报错，不臆造）
- [ ] 阈值已套用（`ImpactReport` 存在则风险档，否则 default 档）
- [ ] `contracts/` 每个接口已生成契约测试用例（正向 1 + 每错误码 1）
- [ ] `business_rules` 每条规则已生成单测用例（正常 / 异常 / 边界，
      满足 3.2 全部质量要求）
- [ ] 已生成前端测试项（TC-xx，标注分类标签与覆盖规则）
- [ ] 排期建议已产出（**单测先行**，契约测试次之）
- [ ] `TestPlan` 已按 `test-plan-template` 组织并写入产物路径
