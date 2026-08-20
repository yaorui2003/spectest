# Speckit Testing 扩展

> Spec 驱动测试先行验证：`@Spec` 注解追溯 + 脚本化门禁（全逻辑下沉、AI 不改判）
> + 对抗测试 + 风险分级 + JaCoCo diff coverage + 前端测试支持（vitest 单测骨架
> + 确定性 e2e + 用例选择执行）。版本 1.4.0（v0.6 文档版 + v0.6.1 beta 简化）。
>
> beta 阶段说明：门禁脚本 **python-only**（`scripts/python/` 唯一实现，
> sh/ps 已弃用留档）；模块定位由 AI 辅助（`find pom.xml` 提示词），覆盖率
> 采用 diff coverage（只看 MR 变更行）。

## 目录

1. [工作原理：它是什么、为什么这样设计](#一工作原理)
2. [组成：扩展如何拼装](#二组成扩展如何拼装)
3. [全流程：端到端怎么跑](#三全流程端到端怎么跑)
4. [追溯机制：Spec ↔ 代码 ↔ 测试](#四追溯机制spec--代码--测试)
5. [门禁原理：run_gate 如何裁决](#五门禁原理run_gate-如何裁决)
6. [风险分级与前端测试](#六风险分级与前端测试)
7. [测试技术栈（必需前置）](#七测试技术栈必需前置)
8. [安装](#八安装)
9. [配置](#九配置)
10. [卸载 / 切回普通 spec-kit](#十卸载--切回普通-spec-kit)

---

## 一、工作原理

### 1.1 要解决的问题

spec-kit 核心只提供「需求 -> 方案 -> 任务 -> 实现」主链路，**不含测试治理**：
不强制写测试、无法证明"代码按 Spec 实现"、门禁靠 AI 自报（8/18 试点中 AI
声称 96% 覆盖率实际 62.9%）。

本扩展的目标是做到 **Spec 规则 ↔ 业务代码 ↔ 测试代码 一一对应**，且
"是否达标"由**确定性脚本裁决，不由 AI 自述**。

### 1.2 核心不变量（设计原则）

| 不变量 | 含义 | 落地 |
|---|---|---|
| **Spec 是唯一事实来源** | spec.md 的 `### Functional Requirements` 段 FR-001..FR-xxx 贯穿全链路 | impact（分级）/ plan（用例）/ gate（对齐）/ report（矩阵）都从 FR-001..FR-xxx 出发 |
| **测试先行** | 骨架 -> 单测（先 Red）-> 契约测试 -> 业务代码（Green） | tasks/implement 模板强制 |
| **@Spec 打通追溯链** | 业务代码标 `@Spec(rule="FR-001")`，测试标 `@DisplayName("FR-001-R1-...")`，契约测试标 CT-xx | 注解 + 命名规范 |
| **门禁脚本判定，AI 不改判** | run_gate 全逻辑下沉，AI 仅读 stdout JSON | 直击 P0「AI 伪造覆盖率」 |
| **脚本采集事实，AI 补语义** | 结构性检查（编译/覆盖/对齐）脚本 HARD 判定；语义检查（测试是否测对了业务）AI SOFT 验证 | T1/T2 双门禁（见 5.5） |
| **T2 达标 ≠ T1 达标** | 全绿 + 覆盖率达标只证明"能运行"，不证明"按业务实现" | AI 交叉验证第 5 维：每条规则至少 1 个直接单测 |

### 1.3 四层机制如何达成"一一对应"

```
注解打通链路 → 脚本采集事实 → 门禁硬校验 → 矩阵可视化
   @Spec         JSON 输出        PASS/FAIL 阻断     test-report.md
   @DisplayName  不依赖 AI 自报   任一方向断裂即 FAIL  缺口一目了然
```

---

## 二、组成：扩展如何拼装

spec-kit 的扩展机制分三层，本能力以**三层交付**叠加：

| 层 | 载体 | 职责 | 是否改核心行为 |
|---|---|---|---|
| **扩展 testing** | `extensions/testing/extension.yml` | 新增能力：4 命令 + 1 钩子 + 8 模板 + 5 脚本 + @Spec + 配置 | 否（只加新东西） |
| **预设 testing-tdd** | `presets/testing-tdd/preset.yml` | replace 宪法/spec/tasks 模板 + append implement 命令，强制 TDD 行为 | 是（必须配套装） |
| **bundle speckit-testing** | `examples/bundles/speckit-testing/bundle.yml` | 一键装扩展 + 预设 | — |

### 2.1 4 个命令（provides.commands）

命令是带 frontmatter 的 `.md` 指令文件，声明输入/处理逻辑/输出契约，由 AI 执行：

| 命令 | 触发 | 作用 | 产物 |
|---|---|---|---|
| `/speckit.testing.impact` | 手动 / **钩子自动**（在前） | 变更影响分析：git diff + 源码 @Spec 分布 -> 受影响规则清单 + **风险分级（规则化评分）** + 功能测试案例集（GWT） | `docs/impact-report.md` |
| `/speckit.testing.plan` | 手动（plan 后） | 测试计划：CT/UT 用例 + 验收阈值 + 前端测试项 TC + 单测先行排期 | `docs/test-plan.md` |
| `/speckit.testing.gate` | 手动 / **钩子自动**（在后） | 门禁：AI 调 `run_gate` 脚本，仅读 stdout JSON，不能改判 | `docs/gate-result.md`（脚本写） |
| `/speckit.testing.report` | 手动（gate PASS 后） | 汇总结果 + Spec 追溯矩阵；引用（不重生成）impact-report | `docs/test-report.md` |

### 2.2 强制钩子（hooks.after_implement）

`speckit.implement` 执行完**自动**触发，`impact` 在前、`gate` 在后（顺序是钩子链
不断裂的关键——gate 前置检查 impact-report.md 存在，缺失即 FAIL）：

```
implement ──► impact（先产出风险分级）──► gate（后消费风险套阈值）
```

### 2.3 8 个模板（provides.templates）

| 模板 | 用途 |
|---|---|
| `java-service` | 业务代码骨架，`@Spec` 注解占位 |
| `java-unit-test` | JUnit5 单测：`@DisplayName("FR-xxx-Rm-...")` + given/when/then |
| `contract-test` | 契约测试：WireMock stub + HTTP 客户端调用 + 断言响应码/体（每接口 1 正向 + 每错误码 1 反向） |
| `frontend-unit-test` | 前端单测（vitest + @vue/test-utils + happy-dom），describe 对齐规则编号（**可选实施**） |
| `frontend-e2e` | 确定性 e2e（Playwright，**可选实施**）：stub 外部不确定依赖（HTTP API 主路径，WS/第三方按项目实际扩展）+ 显式超时 + `covered_rules` 元数据注释 |
| `e2e-case-template` | 功能测试案例集（Given-When-Then + 关联规则），impact 生成、e2e 选择执行消费（**可选生成**） |
| `test-plan-template` | 测试计划文档结构（阈值 + 用例表 + 排期） |
| `spec-trace-matrix` | 追溯矩阵结构（FR-xxx -> @Spec -> 单测 -> CT） |

### 2.4 5 个脚本（provides.scripts，**python-only**）

beta 阶段只维护 `scripts/python/` 唯一实现（sh/ps 已标注 DEPRECATED 留档）。
脚本输出 JSON，AI 只读不改——这是「不依赖 AI 自报」的物理保证：

| 脚本 | 作用（输出 JSON） |
|---|---|
| `scan_spec_annotations` | 解析 `.java` 的 `@Spec` + spec.md 规则编号 -> spec_rules / annotated_rules / unimplemented_rules / orphan_annotations / coverage_percent；**UNSPEC_CODE 漂移告警**（业务类无 @Spec 且无测试引用，MEDIUM 不阻断，排除表控噪声） |
| `validate_spec_format` | spec.md 格式：Business Rules 段存在 + R 编号连续 |
| `parse_test_results` | surefire + JaCoCo 聚合：unit_tests / contract_tests / coverage；**逐行 `source_lines`**（供 diff coverage 消费） |
| `scan_test_stack` | 技术栈硬校验：禁 PowerMock / `@SpringBootTest` 起容器 |
| `run_gate` | 门禁编排（全逻辑），见第五章 |

### 2.5 @Spec 注解（annotations/）

```java
@Spec(capability = "transfer", rule = "FR-001", description = "金额校验")
public TransferResult transfer(...) { ... }
```

- `@Repeatable` 支持一个方法标注多条规则；`@Retention(SOURCE)`——**仅源码级标记**：
  门禁靠脚本静态正则扫描 `.java` 文本，无运行时反射消费方。
- `@Spec` 仅限 Java 业务代码；前端追溯用 `describe("FR-xxx-Rm-...")` 命名规范对齐。

### 2.6 配套预设 testing-tdd（改核心行为）

扩展只加新能力，**不改核心模板**。要强制 TDD 行为，需配装预设：

| 覆盖 | 策略 | 作用 |
|---|---|---|
| `constitution-template` | replace | Principle I Spec Traceability 置首 + II 中文文档/注释 + III 测试技术栈（含前端 vitest/e2e 可选+确定性句） |
| `spec-template` | replace | spec.md 使用上游原版模板（`### Functional Requirements` 段 FR-001 编号，spec-template 已由领导锁定不可改） |
| `tasks-template` | replace | 测试 REQUIRED + 骨架先行 + 单测先行 + 双标签 `[USx] [FR-xxx]` + Phase 2 checkpoint `mvn test-compile` + Red 判定三条件 + 前端任务区（可选） |
| `speckit.implement` | append | @Spec 强制 + 技术栈 + 单测先行 + **Red 判定三条件** + 第 4.5 阶段对抗测试 + 直接测试覆盖约定 + 插桩日志清理 + 禁改 test 适配 code 铁律 + 前端测试/e2e 可选约定与选择执行 |

**双标签设计**：`[USx]` 服务 spec-kit 核心任务编排，`[FR-xxx]` 服务 gate 的
@Spec/@DisplayName 双向对齐（顶层锚 FR-xxx，测试侧子编号 FR-xxx-Rm）——
两标签各司其职，缺一不可。

---

## 三、全流程：端到端怎么跑

### 3.1 依赖-产物流程图（全链路）

```
┌─ 治理 ─────────────────────────────────────────────────────────────┐
│ /speckit.constitution        ──► constitution.md（Principle I/II/III）│
├─ 需求 ─────────────────────────────────────────────────────────────┤
│ /speckit.specify             ──► spec.md（US + Functional Requirements FR-001..）│
├─ 方案 ─────────────────────────────────────────────────────────────┤
│ /speckit.plan                ──► plan.md + contracts/ + data-model   │
├─ 测试计划（手动）──────────────────────────────────────────────────┤
│ /speckit.testing.plan        ──► docs/test-plan.md（CT/UT+TC+阈值）   │
├─ 任务 ─────────────────────────────────────────────────────────────┤
│ /speckit.tasks               ──► tasks.md（骨架先行+单测先行+[USx][FR-xxx]）│
├─ 实现 ─────────────────────────────────────────────────────────────┤
│ /speckit.implement           ──► 骨架 → 单测(Red) → 契约 → 代码(Green) │
│   └─ 第 4.5 阶段对抗测试（run_gate --check-only 自检，可选）           │
├─ after_implement 钩子（自动，optional:false）────────────────────────┤
│  ① /speckit.testing.impact  ──► docs/impact-report.md               │
│     （受影响规则 + 风险分级 + 功能测试案例集 GWT）                     │
│  ② /speckit.testing.gate    ──► docs/gate-result.md（run_gate 脚本写）│
│     FAIL ─► 阻断提交，返回 implement 修复                            │
├─ 报告（手动）───────────────────────────────────────────────────────┤
│ /speckit.testing.report      ──► docs/test-report.md（追溯矩阵）      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 钩子链内部：impact -> gate

```
implement 完成
  ▼
impact：git diff + 源码扫描 -> 受影响规则 FR-xxx 清单
        ├─ 每条规则 risk_level：direct high / indirect medium / edge low
        │    （Mapper/SQL/yml/pom 变更自动升一级，high 封顶——规则化评分，
        │     替代 AI 自由裁量，让 gate 5.5 对抗硬判的"high"判定可复现）
        └─ 功能测试案例集：命中规则的 GWT 用例（带 covered_rules 字段）
  ▼
gate：AI 调 run_gate（全逻辑下沉，不能改判）
        前置检查 impact-report.md 存在（缺失即 FAIL）
        └─ 结果 JSON -> AI 输出 PASS/FAIL 指令
```

### 3.3 产物路径（统一在 `specs/<feature>/docs/`）

| 产物 | 路径 | 写入者 |
|---|---|---|
| 测试计划 | `specs/<feature>/docs/test-plan.md` | AI（testing.plan） |
| 影响报告 | `specs/<feature>/docs/impact-report.md` | AI（testing.impact） |
| 门禁结果 | `specs/<feature>/docs/gate-result.md` | **run_gate 脚本**（AI 不补写） |
| 测试报告 | `specs/<feature>/docs/test-report.md` | AI（testing.report） |

前端 e2e 规划产物为**可选**且不单独建文件：TC 简版并入 test-plan.md，详细版功能案例集并入
impact-report.md（「功能测试案例集（e2e 规划）」段）。默认不生成、不生成不 FAIL。

---

## 四、追溯机制：Spec ↔ 代码 ↔ 测试

### 4.1 追溯链全景

```
     spec.md（### Functional Requirements 段 FR-001..FR-xxx）← 唯一事实来源
        │
   ┌────┴─────┐
   ▼          ▼
 业务代码    测试代码
 @Spec       @DisplayName("FR-001-R1-...")
 rule=FR-001     │
   └─────┬─────┘
         ▼
  scan + 双向对齐校验（run_gate）
         ▼
  追溯矩阵（test-report.md）FR-001 -> @Spec 位置 -> 单测 -> CT-xx
         ▼
 （可选参考层）test-plan.md 业务规则细分段（FR-001-R1..，plan 可不跑，
         不承载权威——无 plan 时测试作者按 FR 自编号）
```

### 4.2 三条绑定路径

| 路径 | 机制 | 采集 |
|---|---|---|
| spec ↔ 代码 | 实现规则的 public 方法 MUST 标 `@Spec(rule="FR-001")` | scan_spec_annotations |
| spec ↔ 单测 | `@DisplayName("FR-001-R1-场景描述")`，描述须含期望结果 | run_gate 内联解析 |
| spec ↔ 契约测试 | plan 遍历 `contracts/` 生成 CT-xx，每接口 1 正向 + 每错误码 1 反向 | 追溯矩阵反查 |

### 4.3 双向一致性硬校验（run_gate，任一方向断裂即 FAIL）

| 方向 | 校验 | 断裂字段 | 判定 |
|---|---|---|---|
| spec -> 代码 | 每条规则 MUST 有 @Spec | `unimplemented_rules` 非空 | FAIL |
| 代码 -> spec | 每个 @Spec MUST 指向真实规则 | `orphan_annotations` 非空 | FAIL |
| DisplayName -> @Spec（正向） | 每条单测指向存在的规则 | `displayname_mismatch_count > 0` | FAIL |
| @Spec -> DisplayName（反向） | 每条已注解规则 MUST 至少 1 条测试 | `untested_spec_rules` 非空 | FAIL（堵「标了 @Spec 不写测试」缺口） |
| 规则覆盖率 | 已注解 / 总数 | < 100% | FAIL |

---

## 五、门禁原理：run_gate 如何裁决

### 5.1 为什么脚本判定

v0.3 的 gate 由 AI 编排脚本 + AI 比对阈值 + AI 写结果——试点证明 AI 会伪造
（声称 96% 实际 62.9%）。v0.4 起把**全部确定性逻辑下沉到 `run_gate` 脚本**，
AI 仅读 stdout JSON + 按判定输出指令，不能改判。

| 环节 | v0.3（AI 编排） | 现状（脚本编排） |
|---|---|---|
| mvn test | AI 跑 | run_gate 跑，强制 `mvn clean test`（杜绝 target 残留污染） |
| 脚本调用 / @DisplayName 解析 / 阈值比对 / 判定 | AI | run_gate 内部串行 |
| gate-result.md 写入 | AI 写 | 脚本写 |
| AI 角色 | 全权 | 仅读结果 |

> 诚实边界：run_gate 是"最大化脚本化"妥协——钩子由 AI 触发、结果由 AI 转述，
> 非硬强制；真实数据 + 降低伪造难度 + 可审计是当前可靠上限。

### 5.2 run_gate 步骤

```
0. 前置检查 impact-report.md 存在（缺失即 FAIL）
1. 模块定位（AI 辅助）：gate.md 强制先 find . -name pom.xml -maxdepth 3，
   把 --project 指向含 pom.xml 的模块目录；传错 -> 降级 + degraded_reason
   建议命令（脚本不自动探测——宁可降级不执行，不可错跑）
2. mvn clean test 全量执行（回归盲区兜底，永远跑）
3. scan_test_stack（技术栈硬校验：缺报告即 FAIL，不降级）
4. parse_test_results（surefire + JaCoCo，聚合覆盖率 + source_lines 行级）
5. scan_spec_annotations（@Spec 分布 + UNSPEC_CODE 漂移告警 MEDIUM）
6. 内联解析 @DisplayName -> 双向对齐校验
7. 5.5 关键路径对抗校验（critical_path_required 只对 high 风险规则硬判）
8. diff coverage 判定（见 5.3）
9. SOFT 段存在性检查（见 5.4）
10. 逐项比对阈值 -> PASS/FAIL（HARD）-> 写 gate-result.md + stdout JSON
```

`run_gate --check-only` 子模式：供 implement 第 4.5 阶段对抗测试自检，只跑不写。

### 5.3 覆盖率判定：JaCoCo diff coverage（v0.6.1 简化）

**原则：变更行管阈值，不管执行**——全量 `mvn clean test` 永远跑（回归兜底），
阈值只对 **git 变更行**强制（存量低覆盖行不在本次改动则不拖累）：

```
git diff --unified=0（--diff-base <branch> 时先 git merge-base 得 base）
   ▼ 变更行集合
与 JaCoCo 行级报告 source_lines 按 package/file 求交
   ▼
变更行覆盖率 >= 阈值（--diff-threshold，默认 config 80）？否则 FAIL
```

- 无 Java 变更 -> 跳过该维度；无 git 仓库 -> 回退全量聚合阈值（宁严勿松）；
  新增文件全行视作变更行；test 文件/未跟踪文件行不计入；多模块按模块匹配报告后聚合。
- 相比包级作用域方案：行级更精确，且天然无「作用域声明/越界检测/空作用域」问题。

### 5.4 AI 交叉验证（SOFT，不改判）

run_gate 只做结构 HARD 判定，语义正确性由 AI 补：gate 步骤 3 要求 AI 在
gate-result.md 追加 `## AI 交叉验证（SOFT，不影响判定）` 段，检查五维：
规则语义 / 断言质量 / 覆盖率真实性 / @Spec 放置 / **直接测试覆盖**（每条规则
至少 1 个直接单测，仅被编排间接覆盖要 WARN）。

- run_gate 只读正则检查该标题，缺失 -> WARN + `soft_missing: true`（**不 FAIL**——
  脚本不因 SOFT 缺失放行/阻断，AI 也不因 SOFT 存在而改判）；
- 写 gate-result.md 时**保留已有 AI 段**（追加非覆盖），防"补段后重跑"复现。

### 5.5 T1/T2 双门禁框架

| 目标 | 含义 | 判定工具 |
|---|---|---|
| **T2 运行正确性**（必要条件） | 代码没有运行错误 | 脚本 HARD：mvn clean test 全绿 + 覆盖率阈值 + diff coverage |
| **T1 业务一致性**（目的） | 测试能测出"是否按业务实现" | 混合：@Spec/@DisplayName 双向对齐（脚本 HARD）+ 对抗用例（脚本 HARD）+ AI 交叉验证（SOFT） |

gate FAIL 后先归因是 T2 缺口（补分支/补实现）还是 T1 缺口（补场景/补直接
测试/回 spec），再按**漂移决策矩阵**处置：

| 漂移类型 | 默认处置 |
|---|---|
| code 不满足 spec | 改 code，跑 test 验证 |
| test 漏场景 | 补测试（由 spec 派生逻辑驱动，**禁改 test 适配 code 铁律**） |
| spec 有歧义/错误 | 回 spec 澄清（AI 不得擅自改，交用户/PM） |
| code 多于 spec | 删 code 或补 spec 二选一，SOFT 段标注，人工决策 |

### 5.6 对抗测试与 Red 判定

- **对抗测试**（implement 第 4.5 阶段）：AI 主动"攻破自己代码"——第 1 轮
  反例/边界/异常/并发（high 风险规则），第 2 轮起目的性覆盖率补洞
  （辅助类/未覆盖分支），循环上限 `max_iterations`（默认 3）；high 风险规则
  public 方法 MUST 至少 1 条对抗用例（`critical_path_required` 门禁硬判）。
- **Red 判定三条件**（命令级硬规则，修 8/18「编译失败冒充红灯」P0）：
  ① `mvn test-compile` EXIT=0（骨架与测试签名一致）② `mvn test -Dtest=...`
  输出含断言失败特征 ③ 编译错误不是 Red——回补骨架再验①②。
  测试编译失败 -> 回补骨架，**不得进入 Green**。

---

## 六、风险分级与前端测试

### 6.1 impact 风险分级（规则化，高封顶）

| 命中方式 | 等级 | 说明 |
|---|---|---|
| 直接命中 | high | 改 Controller/Service 方法签名；改动文件即实现该规则 |
| 间接命中 | medium | 调用链 / import 反推、同包引用 |
| 边缘 | low | 注释 / 样式 / 工具类 / 纯重构 |

**提升规则**（各升一级，high 封顶）：`*Mapper.java` / `*.sql` / Flyway；
`pom.xml` / `package.json`；`application*.yml`。

### 6.2 e2e 用例选择执行（impact 驱动）

```
impact 受影响规则 ∩ 功能用例集 covered_rules ──► 命中用例
        ──► npx playwright test --grep <用例 ID>（只跑受影响用例）
```

不命中即不跑（避免全量慢跑）；covered_rules 与受影响规则均用顶层锚
FR-xxx 格式（子编号 FR-xxx-Rm 不进求交）；缺 covered_rules 的用例降级
手工。选择机制 **不替代**确定性 stub（stub 外部不确定依赖，禁真实调用）
——两者叠加。

前端约定：**前端测试与 e2e 为可选实施**（默认不做、不做不 FAIL，gate 不
校验）；如选择实施，改动 .vue/.js 应有对应组件测试（vitest）；e2e MUST
确定性（stub 外部不确定依赖——HTTP API / WS 推送 / 第三方接口按项目实际
拦截注入固定数据 + 显式超时双向断言）；真实链路 e2e 仅手工/定时慢跑，
**不进门禁**。

---

## 七、测试技术栈（必需前置）

| 组件 | 作用 | 必需性 |
|---|---|---|
| JUnit 4/5 | 测试框架 | REQUIRED |
| Mockito | Mock 依赖 | REQUIRED |
| Surefire | 测试执行 + surefire-reports | REQUIRED |
| JaCoCo | 覆盖率插桩（含行级 source_lines） | REQUIRED |

**禁用**：PowerMock（覆盖率失真）、`@SpringBootTest` 起容器（契约测试用
WireMock 桩）。缺 JaCoCo/surefire 报告 -> 门禁 FAIL（**不降级**）。
唯一降级：非 Java 项目（无 java/mvn）。

---

## 八、安装

三种方式，任选其一。

**方式 A（直装，发布版）**：

```bash
specify extension add testing \
  --from https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-1.1.2.zip
specify preset add testing-tdd \
  --from https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-tdd-1.1.2.zip
```

> `extension add --from` 对非 catalog 来源会弹 "Untrusted Source" 确认，按 `y` 继续。
> 当前仓库 `releases/` 已发布 1.1.2；更新版本发布后替换 URL 中的版本号即可。

**方式 A'（大陆网络备选，raw 直连被墙/丢包时）**：用 curl（自动重试）下载解压后
本地安装：

```bash
curl -fsS --retry 8 --retry-all-errors -o /tmp/ext-testing.zip \
  https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-1.1.2.zip
curl -fsS --retry 8 --retry-all-errors -o /tmp/ext-preset.zip \
  https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-tdd-1.1.2.zip
mkdir -p /tmp/ext-testing /tmp/ext-preset
python3 -c "import zipfile; zipfile.ZipFile('/tmp/ext-testing.zip').extractall('/tmp/ext-testing')"
python3 -c "import zipfile; zipfile.ZipFile('/tmp/ext-preset.zip').extractall('/tmp/ext-preset')"
specify extension add /tmp/ext-testing --dev
specify preset add testing-tdd --dev /tmp/ext-preset --priority 10
```

> GitHub Release 版 URL：`https://github.com/yaorui2003/spectest/releases/download/v1.1.2/testing-1.1.2.zip`。

**方式 B（开发调试，改源码直接生效）**：

```bash
specify extension add --dev <spec-kit>/extensions/testing
specify preset add --dev <spec-kit>/presets/testing-tdd --priority 10
```

**方式 C（bundle 一键装，需扩展与预设已可解析）**：

```bash
specify bundle install speckit-testing   # 一键装扩展 + 预设
```

> 调试期建议方式 B。预设会 replace 核心模板（宪法 / spec-template / tasks / implement）。

---

## 九、配置

配置位于 `.specify/extensions/testing/testing-config.yml`（安装时从模板复制，
项目可覆盖）：

| 段 | 关键项 | 默认 |
|---|---|---|
| `gate` | 行/分支/方法/指令/复杂度覆盖率、通过率 | 80/70/80/85/70、100% |
| `gate` | `ai_cross_validation` | true |
| `gate` | `diff_coverage_threshold` / `diff_base` | 80 / ""（工作区 vs HEAD） |
| `gate` | `spec_traceability`：规则覆盖 100% + `require_displayname_match` | true |
| `test_stack` | 禁 PowerMock / `@SpringBootTest` | true |
| `scan` | `unspec_exclude_patterns`（UNSPEC 告警额外排除） | [] |
| `risk_overrides` | high/medium/low 三档阈值（单调递减） | high 90% 起 / low 70% 起 |
| `adversarial` | `enabled` / `max_iterations` / `critical_path_required` | true / 3 / true |

## 十、卸载 / 切回普通 spec-kit

```bash
specify preset remove testing-tdd    # 移除预设，宪法/模板恢复 spec-kit 默认
specify extension remove testing     # 移除扩展，命令/钩子/配置全部卸载
```

> 临时停用可 `specify preset disable testing-tdd` / `specify extension disable testing`，
> 随时 `enable` 恢复。

## 许可证

MIT