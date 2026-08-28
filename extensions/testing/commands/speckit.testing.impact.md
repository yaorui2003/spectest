---
description: "Speckit Testing 影响分析：解析 spec.md 变更与代码结构依赖，按规则语义风险分级，产出受影响规则清单与建议测试策略"
---

# Speckit Testing Impact

`after_implement` 钩子（`optional: false`，与 `speckit.testing.gate` 同事件，
impact 在前产出风险、gate 在后消费）。Spec 发生变更后立即触发，解析变更范围、
扫描代码结构依赖、按规则语义风险分级，产出 `ImpactReport`（写入
`specs/<feature>/docs/impact-report.md`）供 gate 读取风险等级与受影响规则清单。

## 触发方式

- **手动**：用户在 AI Agent 中直接调用本命令。
- **自动**：`after_implement` 钩子触发（读取 `.specify/extensions.yml` 中
  `hooks.after_implement` 段，按顺序执行 impact -> gate）。

## 输入

| 参考生成物 | 必需性 | 用途 |
|---|---|---|
| `git diff`（含 spec.md 与代码变更） | REQUIRED | 解析规则变更（新增/修改/删除）+ 代码侧 @Spec 差分 |
| 源码目录树 + `@Spec` 注解分布 | REQUIRED（空仓库/非 Java 时可降级） | 依赖分析：识别受影响代码位置 + import/调用链 |
| `spec.md`（`### Functional Requirements` 段，Business Rules 段兼容回落） | REQUIRED | 规则编号清单与语义（风险分级依据） |

## 处理逻辑

### 步骤 1：规则变更提取

**规则权威源** = spec.md `### Functional Requirements` 段（`FR-001`）优先；
`## Business Rules` 段（`R\d+`）仅在 FR 段缺失时兼容回落；两者皆无 ->
`changed_rules` 为空 + `risk_level` 降级说明。

**变更分类**（编号匹配顶层锚 `FR-\d+`，保留前导零）：

- `added`：当前有、上一版本无的编号
- `modified`：编号不变但描述/约束变化的规则
- `removed`：上一版本有、当前无的编号（计入 `changed_rules`，不计入 `affected_rules`）

**代码侧 @Spec 差分信号（补充）**：对 git diff 的 Java 源码变化，抽取新增/删除/
修改的 `@Spec(rule=...)` 集合（顶层锚），与权威源 diff 结果**合并去重**（同一
FR 双侧命中取更高变更类型：`removed` > `modified` > `added`）。

> 子场景编号（FR-001-R1）不进入 affected_rules——受影响规则只到顶层锚粒度。

### 步骤 2：扫描代码结构，做依赖分析

- 遍历源码目录树，识别实现受影响规则的类与方法（按 @Spec 注解 `rule` 字段
  反向定位）
- 分析模块间引用关系（import / 调用链），识别间接受影响类/方法
- 受影响代码位置计入 `affected_locations`

### 步骤 3：按规则化评分风险分级

依据**命中方式**对每条受影响规则评分（替代自由裁量，判定可复现、可测试），
取规则集合中的最高等级作为整体 `risk_level`：

| 命中方式 | 评分 | 判定依据 |
|----------|------|----------|
| 直接命中 | `high` | 改动 Controller/Service 方法签名；改动文件即实现该规则（结合 @Spec 注解反向定位） |
| 间接命中 | `medium` | 调用链 / import 反推、同包引用导致的间接受影响 |
| 边缘 | `low` | 仅注释 / 样式 / 工具类 / 纯重构 |

**语义辅助锚定**：规则描述含"金额/资金/转账/支付/扣款"、"权限/鉴权/授权"、
"事务/原子/一致性"、"数据完整性/幂等" -> 通常直接命中；含"状态/流程/流转/
编排"、纯校验/展示类 -> 按命中方式评分。

**提升规则**（各升一级，`high` 封顶）：涉及 `*Mapper.java` / `*.sql` / Flyway
迁移、`pom.xml` / `package.json`、`application*.yml` -> 升一级。

**输出固定三档** `high` / `medium` / `low`，与 gate 对抗硬判直接对接
（`critical_path_required` 只对 `high` 风险规则生效），档位 MUST 由本步骤
规则化评分得出，不得自由裁量。

### 步骤 4：产出受影响规则清单与建议测试策略

- **受影响规则清单**（`affected_rules`）：每条含规则编号（顶层锚 FR-xxx）、
  变更类型、风险等级、受影响代码位置
- **建议测试策略**：
  - `high` 风险 -> 全量测试（受影响规则单测全覆盖 + 回归套件）
  - `medium` 风险 -> 增量测试（受影响规则单测 + 关联回归）
  - `low` 风险 -> 增量测试（仅受影响规则的单测）
- **单测条数建议**：受影响规则数 × 3（正常 / 异常 / 边界）

## 输出（ImpactReport）

```markdown
## ImpactReport

### 影响范围（受影响代码位置清单）
- com.example.AccountService.transfer (FR-001, FR-006, FR-007)

### 风险等级
risk_level: high

### 受影响规则编号清单
affected_rules:
  - rule: FR-001
    change_type: modified
    risk: high
    locations: [com.example.AccountService.transfer:42]

### 建议测试策略
strategy: full
unit_test_count_estimate: 18
rationale: FR-001 涉及资金校验（high），触发全量测试策略

### 产物路径
impact_report_path: specs/<feature>/docs/impact-report.md
```

> 注意：`affected_rules` 段格式（`- rule: <FR-xxx>` + 跟随 `risk: high|medium|low`）
> 被 run_gate 内联解析（`_parse_affected_rules`），MUST 保持，不得改格式。

## 契约不变量

- `affected_rules` 中每个规则编号必须存在于 spec.md 的 FR 段（或 Business
  Rules 段兼容回落；删除的规则不计入 `affected_rules`）
- `risk_level` 必须为 `high` / `medium` / `low` 之一
- `after_implement` 触发时，`ImpactReport` 产物路径必须可被后续
  `speckit.testing.gate` 读取（默认写入 `specs/<feature>/docs/impact-report.md`）

## 后续动作

`ImpactReport` 产出后，由 after_implement 钩子按列表顺序自动调用门禁
（`__SPECKIT_COMMAND_TESTING_GATE__`，令牌由 spec-kit 注册时渲染，勿硬编码）。

注意：`speckit.testing.plan`（令牌 `__SPECKIT_COMMAND_TESTING_PLAN__`）不读取
ImpactReport 产物——测试计划可独立于影响分析运行。

## 降级

- git diff 为空或无 spec.md 变更：全文视为新增，全部 FR 段规则计入
  `changed_rules`（`change_type: added`），其余流程不变
- 代码结构无法扫描（空仓库或非 Java 项目）：`affected_locations` 为空，
  仅基于规则语义做风险分级

## Done When

- [ ] `spec.md` diff 已解析，`changed_rules` 已产出
- [ ] 代码结构依赖分析已完成（或降级说明已给出）
- [ ] 每条受影响规则已分级（`high` / `medium` / `low`，规则化评分）
- [ ] `affected_rules` 清单（顶层锚 FR-xxx 格式）与建议测试策略已产出
- [ ] `ImpactReport` 已写入产物路径