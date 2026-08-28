---
description: "Speckit Testing 测试计划生成：以 speckit.plan 产出的 spec.md/plan.md 等文档为输入，生成单测用例清单（B/C/E 四维度，注重质量），按风险或默认阈值给验收标准与排期建议"
---

# Speckit Testing Plan

本命令为手动命令（不绑钩子），在 `speckit.plan` 之后、`speckit.tasks` 之前
运行。**以 speckit.plan 已产出的 md 文档为输入**（spec.md / plan.md /
contracts/ / data-model.md），生成**单测用例清单**（标注规则编号）、验收阈值
与排期建议，引用 `test-plan-template` 模板组织文档结构。

> **ImpactReport 为可选输入**：用例清单的生成完全不依赖 ImpactReport——
> 它仅用于步骤 1 的阈值分档。若存在则按其 `risk_level` 套风险档阈值；
> 否则用 `testing-config.yml` 的 `gate` 默认阈值。

## 触发方式

- **手动**：用户在 AI Agent 中直接调用本命令。不绑钩子。

## 输入（已有 md 产物）

| 产物 | 必需性 | 用途 |
|---|---|---|
| `spec.md` | REQUIRED | `### Functional Requirements` 段（FR-001..FR-xxx），用例生成依据 |
| `plan.md` | REQUIRED | speckit.plan 产出的实现计划，含 contracts 路径与技术决策 |
| `contracts/` | REQUIRED | 接口契约定义（错误码清单），单测异常用例依据 |
| `data-model.md` | RECOMMENDED | 数据模型与字段约束，单测边界值与 fixture 依据 |
| `research.md` | OPTIONAL | 调研结论，影响测试策略 |
| `ImpactReport` | OPTIONAL | 存在则取 `risk_level` 套风险档阈值；缺失用默认档 |

> 任一 REQUIRED 产物缺失时，本命令**不得臆造**——向用户报缺什么、需先跑
> 哪个命令（如 plan.md 缺失 -> 先跑 `/speckit.plan`）。

## 处理逻辑

### 步骤 1：套用验收阈值

读取 `ImpactReport.risk_level`（若存在）；缺失则标记 `risk_level=default`。
按 `testing-config.yml` 的 `risk_overrides`（存在时）与 `gate` 默认值合并：

| 风险 | 行覆盖率 | 分支覆盖率 | 方法覆盖率 | 指令覆盖率 | 复杂度覆盖率 | 单测通过率 | Spec 覆盖率 |
|------|----------|------------|------------|------------|--------------|------------|-------------|
| high | >=90% | >=70% | >=90% | >=90% | >=80% | 100% | 100% |
| medium | >=80% | >=70% | >=80% | >=85% | >=70% | 100% | 100% |
| low | >=70% | >=70% | >=70% | >=80% | >=60% | 100% | 100% |
| default（无 ImpactReport） | >=80% | >=70% | >=80% | >=85% | >=70% | 100% | 100% |

阈值记入 `TestPlan.acceptance_thresholds`，作为后续 gate 判定的依据。

> **覆盖率推荐目标（团队最低质量线）**：方法覆盖率 50% / 语句覆盖率 30% /
> 核心模块语句+分支覆盖率 100%。与 gate 硬阈值不冲突——gate 阈值是门禁硬判，
> 本目标是日常开发最低质量线。

### 步骤 2：遍历 spec.md FR 段，生成单测用例（注重质量）

逐 FR-xxx 生成单测用例。**单测质量是本命令的核心产出**，提示词务必遵循
3.1-3.2 的要求。

#### 2.1 用例维度（BCDE 四原则，至少 3 条测试用例）

每条用例按 **BCDE 四字母**显式标注用例维度（部门规范，记入用例"场景"列）：

- **B = 边界（boundary）**：参考 `data-model.md` 字段约束：最小值 / 最大值 /
  空值 / 越界 / 临界等值
- **C = 正常（correct）**：合法输入，验证成功语义与副作用
- **D = 结合设计文档（design）**：结合 `plan.md` / `research.md` 设计决策的
  用例，如特定算法分支、并发/时序约束；设计文档不可用时跳过
- **E = 异常/错误（error）**：每个错误码一条，验证抛出与错误码

用例 ID 统一 **`UT-<序号>`**（按模板样例 UT-01、UT-02… 顺序分配），维度记入
"场景"列（边界/正常/设计/异常），规则编号记入"规则"列。

每条规则至少 3 条（**B/C/E 必含**，D 视设计文档可用性）。

#### 2.2 单测质量要求（MUST）

1. **规则标注（双通道，与 JUnit 版本无关）**：
   - JUnit5：`@DisplayName("FR-xxx-Rm-<具体场景描述>")`（顶层锚 + 子编号），
     描述须含期望结果，如 `FR-001-R1-转账金额为0应抛出INVALID_AMOUNT`
   - JUnit4：测试方法上标 `@Spec(rule="FR-xxx-Rm", description="<具体场景描述>")`
     （rule = 顶层锚 + 子编号，与 JUnit5 @DisplayName 完全对齐；@Spec 为
     spec-kit 自定义注解，与 JUnit 版本无关；描述须含期望结果）
2. **断言业务语义**：错误码匹配 / 状态变更 / 副作用验证（`verify` 调用）；
   **禁止仅用 `assertNotNull` / `assertTrue` 等弱断言**。每个测试方法至少
   一个业务语义断言。禁止 System.out/打印输出人肉验证。
3. **外部依赖 MUST Mock**：DB / RPC / MQ / 外部接口一律 Mockito
   （`@Mock` + `@InjectMocks`），单测不依赖真实基础设施，**不起容器、不用
   @Autowired**。Mock 隔离外部依赖（网络/服务/中间件/时间/随机），保证用例
   可重复（AIR-R）。
4. **given/when/then 三段式**：given 明确 fixture 与 mock 桩；when 调用被测
   方法；then 断言返回值 + `verify` 副作用（如违规场景不应触发
   `debit`/`credit`）。
5. **一个方法聚焦一个场景**：一个测试方法一个断言主旨，避免多场景堆叠导致
   失败定位困难；单测只测单类/单方法。
6. **异常路径用 `assertThrows`**：捕获业务异常并断言错误码
   （`assertEquals("INVALID_AMOUNT", thrown.getCode())`）。
7. **边界值依据 `data-model.md`**：字段约束驱动的边界（如金额 > 0 的边界：
   0 / 最小单位 / 最大值），不要凭空造边界。
8. **命名 `UT-<序号>`**，每条标注规则编号（顶层锚 FR-xxx），与代码侧
   `@Spec(rule="FR-xxx")` 顶层锚双向对齐。
9. **独立性（AIR-I）**：禁止 test A 调用 test B、禁止共享可变状态/依赖执行
   次序——每个用例独立可运行。
10. **命名规范**：测试类 = 被测类 + `Test`；测试方法 = `testXxx_状态`；包名
    与被测类一致。
11. **DB 测试**：不假设数据存在；程序插入/导入准备数据；自动回滚机制。

契约不变量：每条 `SpecRule` 至少 3 条单测（B / C / E 必含，D 视设计文档
可用性）。

### 步骤 3：排期建议（单测先行）

按以下原则给排期（`TestPlan.schedule`）：

- **高风险规则优先**：`high` 风险规则的用例在同类用例中优先排
- **依赖顺序**：被依赖的接口/规则的用例先于依赖方

排期格式：每条用例标注 `priority`（high / medium / low）、`depends_on`
（前置用例编号）。

## 输出（TestPlan）

引用 `test-plan-template` 模板组织文档结构：

```markdown
# Test Plan

## 验收阈值（risk_level=<risk_level 或 default>）
- line_coverage_min / branch_coverage_min / method_coverage_min /
  instruction_coverage_min / complexity_coverage_min
- unit_pass_rate_min / spec_rule_coverage_min

## 单测用例（UT-xx）
| 用例 ID | 规则 | 规则标注 | 场景 | 被测方法 |

## 排期建议（单测先行）
| 优先级 | 用例 ID | 依赖 |

## 产物路径
test_plan_path: specs/<feature>/docs/test-plan.md
```

## 契约不变量

- 每条 `SpecRule` 至少 3 条单测（B / C / E 必含，D 视设计文档可用性），
  满足 2.2 质量要求
- 单测规则标注格式 `FR-xxx-Rm-<描述>`（JUnit5 @DisplayName）或测试方法级
  `@Spec(rule="FR-xxx-Rm", description="<场景>")`（JUnit4），与代码侧
  `@Spec(rule="FR-xxx")` 按顶层锚双向对齐（代码侧 @Spec 永远只写顶层锚）
- 阈值：`ImpactReport` 存在则风险档，否则 default 档
- `TestPlan` 产物路径必须可被后续 `speckit.tasks` 读取（默认写入
  `specs/<feature>/docs/test-plan.md`）

## 模板引用

本命令产出文档的组织结构遵循 `test-plan-template` 模板
（`templates/test-plan-template.md`），含：验收阈值段、单测用例表、排期建议表。

## Done When

- [ ] `spec.md` / `plan.md` / `contracts/` 已读取（缺失即报错，不臆造）
- [ ] 阈值已套用（`ImpactReport` 存在则风险档，否则 default 档）
- [ ] spec.md FR 段每条规则已生成单测用例（B/C/E 必含，满足 2.2 全部质量要求）
- [ ] 排期建议已产出（**单测先行**）
- [ ] `TestPlan` 已按 `test-plan-template` 组织并写入产物路径