---
description: "Speckit Testing 影响分析：解析 spec.md 变更与代码结构依赖，按规则语义风险分级，产出受影响规则清单、建议测试策略与功能测试案例集（TC，供前端 e2e 测试 AI 使用）"
---

# Speckit Testing Impact

本命令为 `after_implement` 钩子（`optional: false`，与
`speckit.testing.gate` 同事件，impact 在前产出风险、gate 在后消费）的变更
影响分析。Spec 发生变更（新增/修改/删除 `business_rules`）后立即触发，
解析变更范围、扫描代码结构依赖、按规则语义风险分级，产出 `ImpactReport`
供后续 `speckit.testing.gate` 读取风险等级与
受影响规则清单，并产出**功能测试案例集**（TC-xx，供前端 e2e 测试 AI
规划 e2e 测试，不进门槛）。

## 触发方式

- **手动**：用户在 AI Agent 中直接调用本命令。
- **自动**：`after_implement` 钩子触发（`optional: false`，与 gate 同事件，
  impact 在前执行）。AI Agent 读取 `.specify/extensions.yml` 中
  `hooks.after_implement` 段（列表形式），按顺序执行 impact -> gate。

## 输入

| 参考生成物 | 必需性 | 用途 |
|---|---|---|
| `git diff`（含 spec.md 与代码变更） | REQUIRED | 解析 spec.md 的 business_rules 变更（新增/修改/删除） |
| 源码目录树 + `@Spec` 注解分布 | REQUIRED（可降级：空仓库/非 Java 时仅做语义分级） | 依赖分析：识别受影响代码位置（类/方法）+ import/调用链 |
| `spec.md`（`business_rules` 段） | REQUIRED | 规则编号清单与语义（风险分级依据） |

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

### 步骤 3：按规则化评分风险分级（v0.6 9.7）

依据**命中方式**对每条受影响规则规则化评分（替代自由裁量，判定可复现、
可测试），取该规则集合中的最高等级作为整体 `risk_level`：

| 命中方式 | 评分 | 判定依据 |
|----------|------|----------|
| 直接命中 | `high` | 改动 Controller/Service 方法签名；改动文件即实现该规则（结合 `@Spec` 注解 `rule` 字段反向定位） |
| 间接命中 | `medium` | 调用链 / import 反推、同包引用导致的间接受影响 |
| 边缘 | `low` | 仅注释 / 样式 / 工具类 / 纯重构 |

**语义辅助锚定**（辅助判断"是否直接命中"，不构成独立评分轨道）：规则描述
含"金额/资金/转账/支付/扣款"、"权限/鉴权/授权"、"事务/原子/一致性"、
"数据完整性/幂等" -> 通常直接命中（`high`）；含"状态/流程/流转/编排"、
"业务规则" -> 通常间接命中（`medium`）；纯校验类、展示类规则 -> 按命中
方式评分。

**提升规则**（在命中评分基础上各升一级，`high` 封顶，不超 `high`）：

- 涉及 `*Mapper.java` / `*.sql` / Flyway 迁移 -> 升一级
- 涉及 `pom.xml` / `package.json` -> 升一级
- 涉及 `application*.yml` -> 升一级

**输出固定三档** `high` / `medium` / `low`，与 gate 步骤 5.5 对抗硬判直接
对接——`critical_path_required` 只对 `high` 风险规则生效（high 风险规则 0
对抗用例 -> FAIL），档位 MUST 由本步骤规则化评分得出，不得自由裁量。

### 步骤 4：产出受影响规则清单与建议测试策略

合并步骤 1-3 结果：

- **受影响规则清单**（`affected_rules`）：每条含规则编号、变更类型、
  风险等级、受影响代码位置
  （v0.6 9.7：每条 `risk` 档位由步骤 3 规则化评分得出——命中方式 + 提升
  规则，固定三档 `high`/`medium`/`low`；gate 步骤 5.5 对抗硬判只对 `high`
  风险规则生效，不得自由裁量）
- **建议测试策略**：
  - `high` 风险 -> 全量测试（契约测试 + 单测全覆盖 + 回归套件）
  - `medium` 风险 -> 增量测试（受影响规则的契约测试 + 单测 + 关联回归）
  - `low` 风险 -> 增量测试（仅受影响规则的单测）
- **契约测试条数建议**：受影响规则数 × 每规则契约数（正向 1 + 每错误码 1）
- **单测条数建议**：受影响规则数 × 3（正常 / 异常 / 边界）

### 步骤 5：生成功能测试案例集（TC，e2e 规划详细版）

基于步骤 1-4 结果（受影响规则 + 契约错误码 + 代码校验逻辑 + 风险分级），
生成**功能测试案例集**（TC-xx），写入 `ImpactReport` 产物的
"功能测试案例集（e2e 规划）"段，组织格式遵循 `e2e-case-template`
模板（`templates/e2e-case-template.md`）。

> **面向 e2e 测试 AI**：本案例集会独立转发给负责前端 e2e 测试的 AI
> （如 Playwright 脚本生成），**MUST 自包含**——每条用例仅凭自身内容即可
> 编写可执行的 e2e 脚本，不得依赖案例集外上下文（spec.md / 源码 / 本报告
> 其他段）。e2e 测试 AI 对业务细节了解有限，提示必须具体到可执行。

#### 5.1 用例来源与分类

- **来源**：识别受影响规则中的**用户可感知行为**（校验提示 / 错误提示 /
  成功反馈 / 交互流程）。纯后端内部行为（事务、幂等、数据一致性）若无
  可见 UI 效果，不生成 TC
- **分类**：
  - `功能测试 (正向)`：正常业务流主路径
  - `异常测试`：错误/校验场景，验证前端提示与 UI 状态
  - `交互测试`：弹窗 / 确认 / 多步操作的 UI 交互流
- **编号**：`TC-xx`，延续 test-plan.md 简版清单的编号；若 plan 未生成
  简版清单，则从 TC-01 起自行编号

#### 5.2 自包含要求（MUST，每条用例按 Given-When-Then 三段编写）

**Given**（前置条件 + 测试数据）：
- 所需账号状态 / 页面状态 / 数据准备（如"已登录、余额 50.00 元的账户"、
  "测试环境已存在转入账号"）
- 具体输入值用实际数值而非占位符（如"输入金额 0"而非"输入非法金额"）

**When**（操作步骤）：
- 按用户操作顺序，每步一个动作短语（登录 / 进入 / 输入 / 点击），用 `→`
  连接；涉及弹窗、确认等交互的操作 MUST 单独成步

**Then**（预期结果）：
- 具体可见 UI 行为——精确提示文案（含标点，如"请输入大于0的金额"）、元素
  状态（按钮置灰 / 弹窗出现 / 输入框报错）、数据变化（余额减少 1,000.00 元 /
  显示交易流水号）
- 文案以后端实际返回为准（与契约错误码 / 校验逻辑一致，可在代码中确认
  实际文案）

每条用例 MUST 标注**测试类型**（`功能测试 (正向)` / `异常测试` /
`交互测试`）与**关联规则**（对应 `business_rules` 编号，可多个，逗号分隔）。

**关联规则**字段即本案例集的 **`covered_rules`**（v0.6 9.9）：gate 步骤 1
用它求交受影响规则，得到本次回归的受影响 e2e 用例清单（前端 e2e 选择执行
`npx playwright test --grep <用例 ID>` 只跑命中用例）。**每条用例 MUST 写入
该字段**——缺失 covered_rules 的用例在选择执行中自动降级手工（不进入本次
回归，避免"没被选到 = 没测"的假安全）。

**禁止**含糊表述：如"验证转账功能正常"、"检查页面提示"（无具体文案）、
"输入错误账号"（未指明错误类型）。e2e 测试 AI 无法自行推断模糊内容。

#### 5.3 格式规范（Given-When-Then 结构化块，引用 e2e-case-template）

每条用例为一个 markdown 结构块（**不用表格**，e2e AI 更易解析），按
`e2e-case-template` 模板组织：

```markdown
### TC-01 正常转账全流程

- **类型**: 功能测试 (正向)
- **关联规则**: R6

**Given** 已登录且余额 ≥1,000.00 元的账户 A；测试环境存在转入账户 B
**When** 进入转账页面 → 输入转出账号 A、转入账号 B → 输入金额 1,000.00 →
       点击"确认转账" → 弹窗核对转出/转入/金额 → 点击"确认"
**Then** 页面提示"转账成功"并显示交易流水号；账户 A 余额减少 1,000.00 元

---

### TC-02 转账金额校验提示

- **类型**: 异常测试
- **关联规则**: R1

**Given** 已登录用户，位于转账页面
**When** 输入转出账号与转入账号 → 输入金额 0 → 点击"确认转账"
**Then** 金额输入框下方提示"请输入大于0的金额"；"确认转账"按钮置灰不可点击
```

要点：

- 每条例题包含：`### TC-xx` 标题、类型、关联规则、Given / When / Then 三段
- `**Given**` / `**When**` / `**Then**` 为加粗标记，e2e AI 可按标记解析
- 用例之间用 `---` 分隔；多条 Given 用分号分隔，多个 When 步骤用 `→` 连接，
  多条 Then 用分号分隔
- 用例较多时可按测试类型分组，组内加小标题（如 `#### 异常测试`）

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

### 功能测试案例集（e2e 规划，不进门槛）
（步骤 5 产出的 TC-xx 用例，按 e2e-case-template 模板组织：每条含类型 /
关联规则（即 covered_rules，供 gate 步骤 1 e2e 选择执行求交）/ Given /
When / Then 三段，自包含；格式见步骤 5.3）

### 产物路径
impact_report_path: specs/<feature>/docs/impact-report.md
```

## 契约不变量

- `affected_rules` 中每个规则编号必须存在于 `spec.md` 的
  `business_rules` 段（删除的规则不计入 `affected_rules`，仅计入
  `changed_rules` 中 `change_type: removed` 项）
- `risk_level` 必须为 `high` / `medium` / `low` 之一
- 每条 TC 的关联规则必须存在于 `business_rules`；TC 内容（前置 / 步骤 /
  预期）必须自包含，可独立转发给 e2e 测试 AI 使用
- 每条 TC MUST 携带 `covered_rules`（关联规则）字段，供 gate 步骤 1 e2e
  用例选择执行求交消费（v0.6 9.9）
- 功能测试案例集仅用于 e2e 规划，**不进门槛**（gate 不校验 TC）
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
- [ ] 功能测试案例集已生成（TC-xx，自包含：前置 / 步骤 / 预期 / 类型 /
      关联规则）
- [ ] `ImpactReport` 已写入产物路径
