# Speckit Testing 扩展

> Spec 驱动测试先行验证，含 `@Spec` 注解追溯、自动门禁（脚本化）与对抗测试。
> 版本 1.1.2（v0.4.x 维护：#5 禁改门禁脚本 + #6 bash/ps @Repeatable 修复 + #1 error_codes 噪声修复 + 审计 P1 反向 @Spec->DisplayName 检查 + P4 bash/ps @Spec parity 补全）。

## 概述

本扩展为 spec-kit 增加"Spec 驱动测试先行"能力，通过 4 个命令 + 2 个强制钩子
+ 5 个代码/文档模板 + 5 组三语言脚本（含 `run_gate` 门禁编排）+ `@Spec` 注解，
实现 **Spec-Code-Test 三角一致性**自动校验。

核心改造（v0.4）：**门禁全脚本化**——`run_gate` 把 gate 的全部确定性逻辑
（mvn clean test + 4 步校验 + 阈值比对 + PASS/FAIL 判定 + 写 gate-result.md）
下沉到脚本，AI 仅读 stdout 判定 JSON 不能改判，直击试点 P0「Agent 伪造覆盖率」。

核心理验：**Spec 是唯一事实来源，contracts 是测试与代码的共同输入，
测试先行，`@Spec` 注解打通追溯链路，门禁由脚本判定不由 AI 自报。**

---

## 一、与原 spec-kit 相比增加了什么

spec-kit 核心（`/speckit.*` 原生命令）只提供「需求 -> 方案 -> 任务 -> 实现」
的 Spec-Driven 主链路，**不含任何测试治理、追溯校验、自动门禁能力**。本项目以
**三层交付**在其上叠加闭环：

| 层 | 载体 | 职责 | 是否改核心行为 |
|---|---|---|---|
| **扩展 testing** | `extensions/testing/extension.yml` | 新增能力（命令/钩子/脚本/模板/注解/配置） | 否，只加新东西 |
| **预设 testing-tdd** | `presets/testing-tdd/preset.yml` | 改写核心模板与 implement 命令 | 是（replace/append 核心模板） |
| **bundle speckit-testing** | `examples/bundles/speckit-testing/bundle.yml` | 一键装扩展+预设 | — |

### 1.1 原 spec-kit 核心基线（对比基准）

| 核心命令 | 产物 | 说明 |
|---|---|---|
| `/speckit.constitution` | `constitution.md` | 治理准则（默认若干 Principle，Spec Traceability 原排在 Principle VI） |
| `/speckit.specify` | `spec.md` | 需求规格（User Stories + Requirements + API） |
| `/speckit.clarify` | — | 澄清不充分描述（specify 后、plan 前） |
| `/speckit.plan` | `plan.md` + `contracts/` + `data-model.md` + `research.md` | 技术方案 + 接口契约 + 数据模型 + 调研 |
| `/speckit.analyze` | — | 跨制品一致性与覆盖度分析（tasks 后、implement 前） |
| `/speckit.tasks` | `tasks.md` | 任务清单（核心模板中 **Tests 标 OPTIONAL**，存在矛盾） |
| `/speckit.implement` | 业务代码 | 执行任务构建功能（核心**不强制** @Spec、不强制测试先行） |

核心**没有**：测试命令、`after_implement` 钩子、`@Spec` 注解、测试模板、扫描脚本、
门禁、风险分级、覆盖率阈值、追溯矩阵、Business Rules 段、对抗测试。

### 1.2 testing 扩展（加新能力，不改核心）

扩展通过 `extension.yml` manifest 声明 `provides`，由 `specify extension add` 安装到
项目的 agent 命令目录。**核心 spec-kit 行为不变，只增量叠加**。

#### 1.2.1 4 个命令（provides.commands）

每个命令是一个带 frontmatter 的 `.md` 指令文件，声明触发方式、输入、处理逻辑、输出契约。

| 命令 | 作用 | 实现方式 |
|---|---|---|
| `/speckit.testing.impact` | 变更影响分析：解析 git diff 中 spec.md 变更 + 扫描代码依赖 + 按规则语义风险分级（high/medium/low）+ 产出受影响规则清单与测试策略 | 命令 `.md` 描述 AI 执行步骤（解析 diff / 扫描结构 / 语义分级 / 产出 ImpactReport）；`after_implement` 钩子 `optional:false` 强制自动 |
| `/speckit.testing.plan` | 测试计划：遍历 contracts/ + business_rules 生成 CT/UT 用例清单 + 单测质量要求 + 按风险套阈值 + 单测先行排期 | 命令 `.md` 描述生成逻辑，引用 `test-plan-template` 组织文档结构 |
| `/speckit.testing.gate` | 门禁：AI 调 `run_gate` 脚本执行全量校验，仅读 stdout 判定 JSON 输出阻断/通过指令 | frontmatter `scripts:` 段声明 run_gate 三语言入口；AI 不执行 mvn、不改判、不补写 |
| `/speckit.testing.report` | 测试报告：校验门禁已 PASS + 汇总结果 + 生成 Spec 追溯矩阵 + 引用（不重生成）ImpactReport | 命令 `.md` 描述汇总与矩阵生成，引用 `spec-trace-matrix` 模板 |

#### 1.2.2 2 个强制钩子（hooks.after_implement）

| 钩子 | 时机 | 绑定命令 | optional |
|---|---|---|---|
| `after_implement` | `speckit.implement` 执行后 | `impact` -> `gate`（列表形式，按序） | false（自动） |

实现方式：`extension.yml` 顶层 `hooks.after_implement` 为列表，AI Agent 读取
`.specify/extensions.yml` 的钩子段，在 implement 完成后按序执行
`impact`（先产出风险）-> `gate`（后消费风险套阈值）。**impact 在前、gate 在后**
的顺序是钩子链不断裂的关键——gate 前置检查 impact-report.md 存在，缺失即 FAIL。

#### 1.2.3 5 个模板（provides.templates）

| 模板 | 作用 | 实现方式 |
|---|---|---|
| `java-service-template` | Java Service 业务代码骨架，带 `@Spec` 注解占位符 | `.template.java` 文件，implement 时按约定参考（非机械复制） |
| `java-unit-test-template` | JUnit5 单测骨架，`@DisplayName("R<n>-...")` 规则标注 + given/when/then 三段式 | 同上 |
| `contract-test-template` | 契约测试骨架：WireMock stub + HTTP 客户端调用 + 断言响应码/体，每接口 1 正向 + 每错误码 1 反向，禁 `assertTrue(true)` | 同上 |
| `test-plan-template` | 测试计划文档结构（验收阈值 + CT/UT 用例表 + 排期表） | `.md` 文件，testing.plan 命令引用组织产物 |
| `spec-trace-matrix` | Spec 追溯矩阵结构（门禁状态 + 结果摘要 + R->@Spec->单测->CT 矩阵 + 影响引用） | `.md` 文件，testing.report 命令引用组织产物 |

#### 1.2.4 5 组三语言脚本（provides.scripts，sh/ps/py 字节级等价）

每个脚本组三套实现（`scripts/{bash,powershell,python}/`），由 `test_scan_script_parity.py`
强制 JSON 输出字节级一致。bash/ps 版用 `import run_gate` 复用 Python 核心保证等价。

| 脚本 | 作用 | 实现方式 |
|---|---|---|
| `scan-spec-annotations` | 解析 `.java` 提取 `@Spec` 注解 + 解析 spec.md business_rules，输出 JSON（spec_rules / annotated_rules / unimplemented_rules / orphan_annotations / coverage_percent） | 正则扫描源码 + 规则编号比对 |
| `validate-spec-format` | 校验 spec.md 格式：Business Rules 段存在 + R 编号连续 + Error Code Definitions 可选段 | 段落解析 + 编号连续性校验 |
| `parse-test-results` | 解析 surefire XML + JaCoCo XML，输出 unit_tests / contract_tests / coverage JSON | XML 解析聚合 |
| `scan-test-stack` | 技术栈硬校验：扫描 `src/test/` 检出 PowerMock / `@SpringBootTest` 禁用项 | 正则匹配禁用导入/注解 |
| `run-gate`（v0.4 核心） | 门禁编排：全逻辑下沉（mvn clean test + 4 步校验 + 阈值比对 + 写 gate-result.md），AI 仅读结果 | 9 步串行编排脚本；含 `--check-only` 子模式供对抗测试自检 |

脚本由命令 frontmatter `scripts:` 段声明，按项目 `--script sh|ps|py` 选择其一执行。

#### 1.2.5 @Spec 注解（annotations/）

| 文件 | 作用 | 实现方式 |
|---|---|---|
| `Spec.java` | `@Spec(capability, rule, description)` 注解定义 | `@Repeatable` + `@Retention(RUNTIME)`，运行时可反射读取 |
| `Specs.java` | `@Spec` 容器注解 | 支持 `@Repeatable` 多规则标注 |

> `@Spec` 仅限 Java 业务代码，扩展自身的 Python/Bash 代码不携带（扩展是提供方，非被扫描对象）。

#### 1.2.6 配置（provides.config）

`testing-config.template.yml`：门禁阈值（line/branch/method/instruction/complexity 覆盖率 + 通过率）
+ 风险分级覆盖（high/medium/low 三档单调递减）+ 技术栈禁用项 + v0.4 对抗测试段。
首次安装从模板复制到 `.specify/extensions/testing/testing-config.yml`，项目可覆盖。

### 1.3 testing-tdd 预设（replace/append 核心行为）

扩展只加新能力，**不改核心模板**。要让 constitution 预置追溯原则、spec 模板加规则段、
tasks 强制 TDD、implement 强制 @Spec，需配套安装 `testing-tdd` 预设。预设通过
`preset.yml` 的 `provides.templates` 声明 `strategy: replace|append` + `replaces` 字段，
由 `specify preset add` 安装时覆盖/追加核心模板。

| 覆盖目标 | 策略 | 原核心 | 改后 | 实现方式 |
|---|---|---|---|---|
| `constitution-template` | replace | Spec Traceability 在 Principle VI | **Principle I 置首**（Spec Traceability，NON-NEGOTIABLE）+ Principle II 中文文档与代码注释 + Principle III 测试技术栈 | replace 整个模板文件 |
| `spec-template` | replace | 无 Business Rules 段 | 加 `## Business Rules`（REQUIRED，R 编号连续）+ `### Error Code Definitions`（可选段） | replace 整个模板文件 |
| `tasks-template` | replace | **Tests OPTIONAL**（矛盾） | 测试 **REQUIRED** + 骨架先行（Phase 2 T010-T014 编译检查点）+ 单测先行 + 双标签 `[USx] [Rn]` | replace 整个模板文件 |
| `speckit.implement` 命令 | append | 不强制 @Spec | 追加：@Spec 强制 + 模板约定参考 + 技术栈 + 单测先行产出顺序 + 第 4.5 阶段对抗测试（`run_gate --check-only` 自检 + 关键路径必测 + 渐进式轮次） | append 到核心命令尾部 |

**双标签设计**：tasks-template 每个任务带 `[USx]`（spec-kit user-story 组织索引键，去掉破坏核心工作流）
+ `[Rn]`（testing 扩展规则追溯维度）。`[USx]` 服务核心任务编排，`[Rn]` 服务 gate 的
@Spec/@DisplayName 双向对齐——两标签各司其职，缺一不可。

### 1.4 speckit-testing bundle（一键装）

`bundle.yml` 声明 `provides.extensions`（testing）+ `provides.presets`（testing-tdd，priority 10），
`specify bundle install speckit-testing` 一键装齐扩展 + 预设，避免漏装预设导致核心行为未改。

---

## 二、Spec - 业务代码 - 测试代码一一对应（核心追溯机制）

本项目的最终目的是达到 **spec 规则 ↔ 业务代码 ↔ 测试代码** 的一一对应。
这不是靠人工保证，而是靠**注解打通链路 + 脚本采集事实 + 门禁硬校验 + 矩阵可视化**
四层机制实现。

### 2.1 追溯链全景

```
        spec.md  (Business Rules R1..Rn)  ← 唯一事实来源
           │
     ┌─────┴─────┐
     ▼           ▼
  业务代码     测试代码
  @Spec        @DisplayName
  rule=Rn      "Rn-描述"
     │           │
     └─────┬─────┘
           ▼
      scan + 双向对齐校验 (run_gate 步骤 4-5)
           │
           ▼
      追溯矩阵 (test-report.md)
      R1 -> @Spec 代码位置 -> 单测 -> 契约测试 CT
```

### 2.2 三条打通路径

#### 路径 A：spec 规则 ↔ 业务代码（@Spec 注解）

- **机制**：业务代码每个实现 Spec 规则的 public 方法 MUST 标注
  `@Spec(capability="<cap>", rule="Rn", description="<说明>")`，同一方法实现多规则用
  多条 `@Spec`（`@Repeatable`）。
- **为什么 RUNTIME**：运行时可反射读取，也支持静态源码扫描。
- **采集**：`scan_spec_annotations` 脚本正则解析全部 `.java` 提取 `@Spec` 的 rule 字段，
  同时解析 spec.md 的 business_rules 规则编号，输出三类比对结果：
  - `annotated_rules`：代码中 `@Spec` 标注的规则 -> 代码位置映射
  - `unimplemented_rules`：spec.md 有但代码无 `@Spec` 的规则（漏实现）
  - `orphan_annotations`：代码有 `@Spec` 但 spec.md 无对应规则（编号写错或 spec 已删）

#### 路径 B：spec 规则 ↔ 测试代码（@DisplayName 约定）

- **机制**：单测 MUST 在 `@DisplayName("R<n>-<具体场景描述>")` 中标注验证的规则编号，
  描述须含期望结果（如 `R1-转账金额为0应抛出INVALID_AMOUNT`，非泛泛"测试金额校验"）。
- **采集**：`run_gate` 步骤 5 内联解析单测源码的 `@DisplayName`，提取规则编号 `Rn`。
- **对齐对象**：与代码侧 `@Spec(rule="Rn")` 双向对齐（见 2.4）。

#### 路径 C：spec 规则 ↔ 契约测试（CT-xx + contracts/）

- **机制**：`testing.plan` 遍历 `contracts/` 每个接口契约（含 `rules` 字段或反查
  business_rules），生成契约测试用例 `CT-<序号>`，每接口 1 正向 + 每错误码 1 反向，
  每条标注对应规则编号。
- **对齐**：契约测试通过 CT 编号与规则编号反查，在追溯矩阵中呈现 Rn -> CT-xx。

### 2.3 事实采集：扫描脚本（不依赖 AI 自报）

校验不能基于 AI 自述（试点证明 AI 会伪造覆盖率）。本项目用**确定性脚本**采集事实：

| 采集项 | 脚本 | 输出 JSON 字段 |
|---|---|---|
| 代码侧 @Spec 分布 | scan_spec_annotations | annotated_rules / unimplemented_rules / orphan_annotations / coverage_percent |
| 单测 @DisplayName 规则编号 | run_gate 步骤 5 内联解析 | displayname 规则编号集合 / untested_spec_rules |
| 测试结果与覆盖率 | parse_test_results | unit_tests / contract_tests / coverage |
| 技术栈合规 | scan_test_stack | forbidden_findings |

脚本输出 JSON，AI 只读不改——这是「不依赖 AI 自报」的物理保证。

### 2.4 双向一致性硬校验（gate 步骤 4-5）

`run_gate` 对追溯链做**双向**对齐校验，任一方向断裂即 FAIL：

| 方向 | 校验内容 | 断裂检出字段 | 判定 |
|---|---|---|---|
| **spec -> 代码** | spec.md 每条规则 MUST 有 @Spec 对应 | `unimplemented_rules` 非空 | FAIL |
| **代码 -> spec** | 代码每个 @Spec MUST 指向 spec.md 真实规则 | `orphan_annotations` 非空 | FAIL |
| **DisplayName -> @Spec**（正向） | 每条单测 @DisplayName 指向真实存在的 @Spec 规则（`^R\d+-`） | `displayname_mismatch_count > 0` | FAIL（require_displayname_match=true 时） |
| **@Spec -> DisplayName**（反向，审计 P1） | 每条 @Spec 已注解规则 MUST 至少 1 条对应 @DisplayName 测试 | `untested_spec_rules` 非空 | FAIL（堵「标了 @Spec 不写测试也能过」缺口） |
| **Spec 规则覆盖率** | 已注解规则 / 规则总数 | `< 100%` | FAIL |

**反向校验（@Spec -> DisplayName）** 是审计 P1 补强：仅正向会让「标了 @Spec 占位但
不写测试」成为漏网——反向校验强制每条已注解规则至少有 1 条测试覆盖，真正实现一一对应。

### 2.5 追溯矩阵可视化（report）

gate PASS 后，`testing.report` 遍历 spec.md 全部 business_rules（R1..Rn），为每条
规则构建一行追溯记录，生成 `test-report.md`：

| 规则 | @Spec 代码位置 | 单测 @DisplayName | 契约测试 CT |
|---|---|---|---|
| R1 | AccountService.transfer:42 | R1-转账金额为0应抛出INVALID_AMOUNT | CT-02 |
| R2 | OrderService.updateStatus:18 | R2-订单状态流转合法 | CT-05 |
| ... | ... | ... | ... |

矩阵**必须覆盖 spec.md 全部规则**，无 @Spec 的规则也要列出（位置标注"未实现"），
让缺口一目了然。

### 2.6 实现方式总结

| 环节 | 机制 | 载体 |
|---|---|---|
| spec 规则编号化 | Business Rules 段 R1..Rn 连续 | testing-tdd 的 spec-template replace |
| 业务代码绑定规则 | @Spec 注解（RUNTIME + @Repeatable） | testing 扩展 annotations/ + implement append 强制 |
| 测试代码绑定规则 | @DisplayName("Rn-...") 约定 | testing-tdd 的 tasks-template + implement append + 单测模板 |
| 契约测试绑定规则 | CT-xx 编号 + contracts/ rules 字段 | testing.plan 命令 + 契约测试模板 |
| 事实采集 | 确定性脚本输出 JSON | testing 扩展 5 组脚本 |
| 一致性校验 | 双向对齐 + 阈值 + FAIL 阻断 | run_gate 步骤 4-7 |
| 可视化 | 追溯矩阵覆盖全部规则 | testing.report 命令 + spec-trace-matrix 模板 |
| 治理依据 | 宪法 Principle I 强制 @Spec | testing-tdd 的 constitution-template replace |

> **核心约束链**：宪法 Principle I（强制 @Spec）-> spec-template（规则编号化）
> -> tasks-template（双标签 [Rn] + 测试 REQUIRED）-> implement append（@Spec + @DisplayName）
> -> gate（双向校验 + FAIL 阻断）-> report（矩阵可视化）。每一环都有上游依据、下游消费。

---

## 三、全链路步骤：依赖数据源与生成产物

### 3.1 依赖-产物流程图

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 阶段 │ 命令                  │ 可信数据源(输入)                │ 生成产物(输出)            │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 治理 │ /speckit.constitution │ 用户输入                          │ constitution.md           │
│      │                       │                                   │ (Principle I/II/III)      │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 需求 │ /speckit.specify      │ constitution.md                   │ spec.md                   │
│      │                       │                                   │ (US + Business Rules R1..)│
├──────────────────────────────────────────────────────────────────────────────────┤
│ 澄清 │ /speckit.clarify      │ spec.md                           │ (补全 spec.md)            │
│ (可选)│                       │                                   │                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 方案 │ /speckit.plan         │ spec.md                           │ plan.md                   │
│      │                       │                                   │ contracts/                │
│      │                       │                                   │ data-model.md             │
│      │                       │                                   │ research.md               │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 测试 │ /speckit.testing.plan │ spec.md (REQUIRED)                │ test-plan.md              │
│ 计划 │ (扩展·手动)          │ plan.md (REQUIRED)                │ specs/<f>/docs/           │
│      │                       │ contracts/ (REQUIRED)             │ (验收阈值+CT/UT用例+排期) │
│      │                       │ data-model.md (RECOMMENDED)       │                           │
│      │                       │ research.md (OPTIONAL)            │                           │
│      │                       │ ImpactReport (OPTIONAL,套风险档) │                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 分析 │ /speckit.analyze      │ spec.md + plan.md + tasks.md      │ (一致性报告)              │
│ (可选)│ (tasks 后 implement 前)│                                   │                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 任务 │ /speckit.tasks        │ spec.md + plan.md + contracts/    │ tasks.md                  │
│      │                       │                                   │ (骨架先行+单测先行        │
│      │                       │                                   │  +双标签[USx][Rn])        │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 实现 │ /speckit.implement    │ tasks.md                          │ 业务代码(@Spec rule=Rn)   │
│      │ (implement append)   │ test-plan.md                      │ 单测(@DisplayName Rn-...) │
│      │                       │ 模板(java-service/unit/contract) │ 契约测试(CT-xx)           │
│      │   ┌─ 第4.5阶段 ─────┐│                                   │                           │
│      │   │ run_gate         ││ [对抗测试·可选]                   │ (覆盖率自检 JSON)        │
│      │   │ --check-only    ││                                   │                           │
│      │   └─────────────────┘│                                   │                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│      │ ↓↓↓ after_implement 钩子自动触发 (optional:false) ↓↓↓                         │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 影响 │ /speckit.testing.     │ git diff (spec.md + 代码变更)    │ impact-report.md          │
│ 分析 │ impact                │ spec.md (business_rules)          │ specs/<f>/docs/           │
│ (自动·在前)│                   │ 源码 + @Spec 分布                 │ (risk_level               │
│      │                       │                                   │  + affected_rules)        │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 门禁 │ /speckit.testing.gate │ 业务代码 + 测试代码               │ gate-result.md            │
│ (自动·在后)│ (AI 调 run_gate) │ spec.md (business_rules)          │ specs/<f>/docs/           │
│      │                       │ impact-report.md (取 risk_level) │ (脚本写,PASS/FAIL         │
│      │                       │ testing-config.yml (阈值)        │  +覆盖率+覆盖矩阵)        │
│      │                       │                                   │                           │
│      │   FAIL ──> 阻断提交，返回 implement 修复                                   │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 报告 │ /speckit.testing.     │ gate-result.md (校验已 PASS)     │ test-report.md            │
│ (手动)│ report                │ impact-report.md (引用不重生成)   │ specs/<f>/docs/           │
│      │                       │ spec.md (business_rules)          │ (Spec 追溯矩阵            │
│      │                       │ @Spec 扫描 JSON + TestPlan CT-xx │  R->@Spec->单测->CT)      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 产物路径总览（v0.4 统一）

核心 spec-kit 产物在 `specs/<feature>/`，扩展 4 个产物统一在 `specs/<feature>/docs/`
（废弃 v0.3 的 `.specify/extensions/testing/` 路径）：

| 产物 | 路径 | 产出命令 | 写入者 |
|---|---|---|---|
| 治理准则 | `specs/<feature>/constitution.md`（或根 `constitution.md`） | `/speckit.constitution` | AI |
| 需求规格 | `specs/<feature>/spec.md` | `/speckit.specify` | AI |
| 技术方案 | `specs/<feature>/plan.md` | `/speckit.plan` | AI |
| 接口契约 | `specs/<feature>/contracts/` | `/speckit.plan` | AI |
| 数据模型 | `specs/<feature>/data-model.md` | `/speckit.plan` | AI |
| 调研 | `specs/<feature>/research.md` | `/speckit.plan` | AI |
| 任务清单 | `specs/<feature>/tasks.md` | `/speckit.tasks` | AI |
| 测试计划 | `specs/<feature>/docs/test-plan.md` | `/speckit.testing.plan` | AI |
| 影响报告 | `specs/<feature>/docs/impact-report.md` | `/speckit.testing.impact` | AI |
| 门禁结果 | `specs/<feature>/docs/gate-result.md` | `/speckit.testing.gate` | **run_gate 脚本**（AI 不补写） |
| 测试报告 | `specs/<feature>/docs/test-report.md` | `/speckit.testing.report` | AI |

### 3.3 数据流关键约束

- **spec.md 是唯一事实来源**：business_rules 的 R1..Rn 贯穿 impact（分级）/ plan（生成用例）
  / gate（@Spec/@DisplayName 对齐）/ report（矩阵）全链路。
- **impact 在前、gate 在后**：gate 前置检查 impact-report.md 存在（堵钩子链断裂），
  gate 读 impact 的 risk_level 套阈值。
- **gate-result.md 只由脚本写**：AI 不得补写/改判（直击 P0 伪造覆盖率）。
- **report 引用而非重生成 ImpactReport**：避免重复执行影响分析。
- **ImpactReport 对 plan 是可选输入**：plan 可在 impact 产出前独立运行（缺失用 default 阈值档）。

---

## 命令

| 命令 | 触发方式 | 作用 |
|------|----------|------|
| `/speckit.testing.impact` | 手动 / `after_implement` 钩子（自动，impact 在前） | 变更影响分析 + 风险分级 + 受影响规则编号 |
| `/speckit.testing.plan` | 手动（plan 之后、tasks 之前） | 测试计划文档（用例清单 + 验收阈值） |
| `/speckit.testing.gate` | 手动 / `after_implement` 钩子（自动，gate 在后） | AI 调 `run_gate` 脚本（全逻辑下沉）+ 仅读结果判定 PASS/FAIL |
| `/speckit.testing.report` | 手动（gate 通过后） | 测试结果 + Spec 追溯矩阵 |

## 钩子

| 钩子 | 时机 | 绑定命令 | optional |
|------|------|----------|----------|
| `after_implement` | `speckit.implement` 执行后 | `speckit.testing.impact` -> `speckit.testing.gate`（列表形式，按序执行） | false（自动） |

## 全链路流程（简版）

```
spec.md 更新
  └─> speckit.plan（生成 contracts/ + plan.md + data-model.md）
      └─> testing.plan（测试计划，手动，依赖已有 md）
          └─> speckit.tasks（骨架先行 -> 单测任务 -> 契约测试任务 -> 业务代码）
              └─> speckit.implement
                  ├─ 1. 骨架（mvn compile 通过）
                  ├─ 2. 单测（JUnit5 + Mockito，@DisplayName 标规则，先 Red）
                  ├─ 3. 契约测试（WireMock + HTTP 客户端调用 + 断言响应，不起容器）
                  ├─ 4. 业务代码（@Spec 注解，TDD 让测试 Green）
                  └─ 5.【第 4.5 阶段·对抗测试 + 覆盖率达标，可选】
                      ├─ 调 run_gate --check-only 跑覆盖率自检
                      ├─ 第 1 轮：四类对抗（反例/边界/异常路径/并发竞态）
                      ├─ 第 2 轮起：目的性覆盖率补洞（辅助类/未覆盖分支）
                      ├─ 关键路径必测：high 风险规则方法 MUST 至少 1 条对抗用例
                      └─ 循环上限 max_iterations（默认 3），超限如实进 gate FAIL
                  └─[after_implement 自动]─> testing.impact（影响分析 + 风险分级）
                      └─> testing.gate（AI 调 run_gate 脚本：mvn clean test + 4 步校验
                          + 阈值比对 + 脚本写 gate-result.md，AI 仅读结果）
                          └─ PASS ─> testing.report（追溯矩阵，手动）
```

> 详尽的依赖-产物关系见上方「三、全链路步骤」流程图。

## @Spec 注解

业务代码用 `@Spec` 注解标注其实现的 Spec 规则：

```java
@Spec(capability = "transfer", rule = "R1", description = "金额校验")
public TransferResult transfer(...) { ... }
```

门禁通过扫描 `@Spec` 注解自动校验"Spec 规则 -> 代码实现"覆盖完整性，
单测侧通过 `@DisplayName("R1-...")` 实现双向对齐。详见「二、核心追溯机制」。

## 测试技术栈（必需前置）

本扩展门禁针对 Java 项目，以下技术栈为**必需前置条件**：

| 组件 | 作用 | 必需性 |
|------|------|--------|
| JUnit 4/5 | 测试框架 | REQUIRED |
| Mockito | Mock 依赖（@Mock / @InjectMocks） | REQUIRED |
| Surefire | 测试执行 + surefire-reports 生成 | REQUIRED |
| JaCoCo | 覆盖率插桩（line/branch/method/instruction/complexity） | REQUIRED |

**禁用**：PowerMock（覆盖率失真）、`@SpringBootTest` 起容器。

> 缺 JaCoCo/surefire 报告 -> 门禁 FAIL（不降级）。输出 pom.xml 配置参考。
> 唯一降级：非 Java 项目（无 java/mvn）-> @Spec 静态扫描。

## 门禁脚本化（run_gate，v0.4 核心）

v0.3 的 gate 由 AI 编排 4 个脚本 + AI 比对阈值 + AI 写 gate-result.md，试点证明
AI 会伪造（声称 96% 实际 62.9%）。v0.4 把 gate 的**全部确定性逻辑下沉到
`run_gate` 脚本**（三语言 sh/ps/py 字节级等价），AI 仅读结果不能改判：

| 维度 | v0.3（AI 编排） | v0.4（脚本编排） |
|---|---|---|
| mvn test | AI 跑 | run_gate 跑，强制 `mvn clean test`（杜绝 target 残留污染） |
| 4 脚本调用 | AI 逐个调 | run_gate 内部串行调 |
| @DisplayName 解析 | AI 解析 | run_gate 内联解析 |
| 阈值比对 / PASS/FAIL 判定 | AI | run_gate |
| gate-result.md 写入 | AI 写 | run_gate 脚本直接写 |
| AI 角色 | 全权 | 仅读 stdout JSON + 按判定输出指令 |

`run_gate` 9 步职责：0.检查 impact-report.md 存在 / 1.mvn clean test /
2.scan_test_stack / 3.parse_test_results / 4.scan_spec_annotations /
5.内联解析 @DisplayName（双向对齐）/ 6.读 risk_level+config / 7.逐项比对阈值 /
8.写 gate-result.md + stdout 输出判定 JSON。

`run_gate --check-only` 子模式：供 implement 第 4.5 阶段对抗测试调用，
只跑不写，输出覆盖率与阈值差距 JSON。

> 直击 P0：#1 Agent 伪造覆盖率（脚本判定）/ #2 target 残留污染（强制 clean）
> / #3 impact 未生成（前置检查 impact-report.md 存在）。
> 注：脚本化是"给 AI 真实数据 + 降低伪造难度 + 可审计"，非硬强制（AI 仍可不
> 调脚本而自行声称，真正强制需改执行模型）。

## 对抗测试（v0.4 新增）

在常规 TDD 用例（正常/异常/边界）之外，AI 主动生成的"试图攻破自己代码"的
补充用例集。目标：用真实测试数据把 JaCoCo 覆盖率推到套用阈值，而非堆砌通过用例。

| 轮次 | 目的 | 用例类型 |
|---|---|---|
| 第 1 轮 | 攻破自己代码 | 反例/边界/异常路径/并发竞态（仅 high 风险规则） |
| 第 2 轮 | 目的性覆盖率补洞 | 辅助类（DTO/枚举/异常处理器/Controller）+ 未覆盖分支 |
| 第 3 轮 | 兜底 | 继续补洞 + 可选重构 |

**关键路径必测**（独立 MUST，与 gate 阈值脱钩）：impact 标记 high 风险规则
（资金/权限/原子性/数据完整性）的 public 方法 MUST 至少 1 条对抗用例。

## 配套预设 testing-tdd

扩展只加新能力（命令/钩子/扫描），**不改 spec-kit 核心行为**。要让
`/speckit.constitution` 自动预置 Principle I（Spec Traceability，置首）、
`/speckit.tasks` 强制 TDD
（消灭核心 "Tests OPTIONAL"）、`/speckit.implement` 强制 @Spec + 引用模板，
需配套安装 `testing-tdd` 预设：

| 覆盖 | 策略 | 作用 |
|------|------|------|
| `constitution-template` | replace | 预置 Principle I（Spec Traceability 置首）+ Principle II（中文文档 + 代码重要部分中文注释）+ Principle III（测试技术栈） |
| `spec-template` | replace | 加 `## Business Rules`（REQUIRED）+ Error Code Definitions（可选） |
| `tasks-template` | replace | 测试 REQUIRED + 骨架先行 + 单测先行 + 双标签 `[US1] [R1]` |
| `speckit.implement` 命令 | append | 强制 @Spec 注解 + 约定参考 + 技术栈 + 单测先行 + 第 4.5 阶段对抗测试 |

详见 `presets/testing-tdd/`。

## 安装

三种方式，任选其一：

**方式 A（直装，推荐给终端用户，装在任何标准 spec-kit 上）**：

```bash
# 装扩展
specify extension add testing \
  --from https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-1.1.2.zip
# 装配套预设（预设会 replace 核心模板：宪法 / spec-template / tasks / implement）
specify preset add testing-tdd \
  --from https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-tdd-1.1.2.zip
```

> `extension add --from` 对非 catalog 来源会弹"Untrusted Source"确认，属正常安全提示，
> 按 `y` 继续即可。

**方式 A'（大陆网络备选，GitHub 直连被墙时）**：`--from` 用 python 下载且无重试，
大陆网络下可能超时。改用 curl（自动重试）下载 + `--dev` 本地安装：

```bash
# 下载并解压（--retry 应对间歇性连接失败）
curl -fsS --retry 8 --retry-all-errors -o /tmp/ext-testing.zip \
  https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-1.1.2.zip
curl -fsS --retry 8 --retry-all-errors -o /tmp/ext-preset.zip \
  https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-tdd-1.1.2.zip
mkdir -p /tmp/ext-testing /tmp/ext-preset
python3 -c "import zipfile; zipfile.ZipFile('/tmp/ext-testing.zip').extractall('/tmp/ext-testing')"
python3 -c "import zipfile; zipfile.ZipFile('/tmp/ext-preset.zip').extractall('/tmp/ext-preset')"

# 安装（注意 --dev 是 flag，路径作参数）
specify extension add /tmp/ext-testing --dev
specify preset add testing-tdd --dev /tmp/ext-preset --priority 10
```

> 也可在 `/etc/hosts` 固定 `185.199.111.133 raw.githubusercontent.com` 提升 raw 直连
> 稳定性（需 sudo，一次性）。GitHub Release 版 URL：
> `https://github.com/yaorui2003/spectest/releases/download/v1.1.2/testing-1.1.2.zip`。

**方式 B（dev 直装，调试期快速迭代）**：

```bash
# 装扩展
specify extension add --dev <spec-kit>/extensions/testing
# 装配套预设
specify preset add --dev <spec-kit>/presets/testing-tdd --priority 10
```

**方式 C（bundle 一键装，发布期，需扩展与预设已可解析）**：

```bash
specify bundle install speckit-testing   # 一键装扩展 + 预设
```

> 调试期建议方式 B（改源码直接生效，无需重装）。

## 卸载 / 切回普通 spec-kit

在任意标准 spec-kit 项目上，装上的东西可干净移除、恢复原样：

```bash
specify preset remove testing-tdd    # 移除预设，宪法/模板恢复 spec-kit 默认
specify extension remove testing     # 移除扩展，命令/钩子/配置全部卸载
```

> 只想临时停用（保留安装）可用 `specify preset disable testing-tdd` /
> `specify extension disable testing`，随时 `enable` 恢复。
> `extension remove` 同样有确认提示，按 `y` 继续。

## 配置

门禁阈值与风险分级配置于
`.specify/extensions/testing/testing-config.yml`（首次安装时从模板复制）。

| 风险 | 行覆盖率 | 方法覆盖率 | 指令覆盖率 | 复杂度覆盖率 | 单测通过率 | 契约通过率 |
|------|----------|------------|------------|--------------|------------|------------|
| high | >=90% | >=90% | >=90% | >=80% | 100% | 100% |
| medium | >=80% | >=80% | >=85% | >=70% | 100% | >=95% |
| low | >=70% | >=70% | >=80% | >=60% | 100% | >=95% |

v0.4 新增 `adversarial` 段：

```yaml
adversarial:
  enabled: true              # 是否启用对抗测试阶段（默认 true）
  max_iterations: 3          # 循环上限（默认 3）
  critical_path_required: true # high 风险规则方法 MUST 至少 1 条对抗用例
```

## 产物路径（v0.4 统一）

4 个产物统一存放于 `specs/<feature>/docs/*.md`（废弃 v0.3 的
`.specify/extensions/testing/` 路径）：

| 产物 | 路径 |
|---|---|
| 测试计划 | `specs/<feature>/docs/test-plan.md` |
| 影响报告 | `specs/<feature>/docs/impact-report.md` |
| 门禁结果 | `specs/<feature>/docs/gate-result.md`（run_gate 脚本写） |
| 测试报告 | `specs/<feature>/docs/test-report.md` |

## 宪法依据

本扩展的治理基础是项目宪法 Principle I（Spec Traceability，置首）：
所有业务代码 MUST 用 `@Spec` 注解标注其实现的 Spec 规则。
Principle II（中文文档 + 代码重要部分中文注释）要求高风险规则方法加中文注释
说明业务语义，支撑后续审计与对抗测试定位。
Principle III（测试技术栈）由门禁 scan_test_stack 强制。

## 许可证

MIT
