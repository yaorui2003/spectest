# Speckit Testing 扩展

> Spec 驱动测试先行：`@Spec` 注解追溯 + 脚本化门禁（AI 不改判）+ 对抗测试 + 风险分级
> + JaCoCo diff coverage。版本 1.5.0（仅保留单元测试要求，删除契约测试与前端测试支持；
> JUnit4/5 双通道规则标注；禁 @Autowired）。
>
> beta 说明：脚本 **python-only**（`scripts/python/` 唯一实现，sh/ps 已弃用留档）；
> 模块定位由 AI 辅助（`find pom.xml`）；覆盖率只看 **git diff 变更行**（diff coverage）。

## 目录

1. [一张图：全流程与产物](#一一张图全流程与产物)
2. [核心机制（追溯 / 门禁 / 风险分级）](#二核心机制追溯--门禁--风险分级)
3. [组成：三层交付](#三组成三层交付)
4. [测试技术栈（必需前置）](#四测试技术栈必需前置)
5. [快速上手（安装 / 配置 / 卸载）](#五快速上手安装--配置--卸载)

---

## 一、一张图：全流程与产物

```
◆ = spec-kit 原有生命周期      ◇ = 新增（扩展 testing 插入）
★ = 增强（预设 testing-tdd 改造）      ··► FAIL 回流修复

 ① 治理 · 需求       ② 方案 · 测试计划      ③ 任务 · 实现
╭──────────────────────────────────────────────╮
│ /speckit.constitution           ◆ 原有       │
│ 产出 constitution.md（Principle I/II/III）    │
╰──────────────────────────────────────────────╯
                      │
                      ▼
╭──────────────────────────────────────────────╮
│ /speckit.specify                 ◆ 原有       │
│ 产出 spec.md（FR-001..FR-xxx 唯一事实来源）    │
╰──────────────────────────────────────────────╯
                      │
                      ▼
╭──────────────────────────────────────────────╮
│ /speckit.plan                    ◆ 原有       │
│ 产出 plan.md + contracts/ + data-model        │
╰──────────────────────────────────────────────╯
                      │
                      ▼
╭──────────────────────────────────────────────╮
│ /speckit.testing.plan            ◇ 新增       │
│ 插入测试计划：docs/test-plan.md               │
│ （UT 用例 + 阈值 + 单测先行排期）              │
╰──────────────────────────────────────────────╯
                      │
                      ▼
╭──────────────────────────────────────────────╮
│ /speckit.tasks                    ★ 增强      │
│ 改造：任务强制 骨架先行 + 单测先行            │
│ 双标签 [USx][FR-xxx]                         │
╰──────────────────────────────────────────────╯
                      │
                      ▼
╭──────────────────────────────────────────────╮
│ /speckit.implement               ★ 增强      │
│ 改造：单测先行 TDD（Red 三条件硬校验）        │
│ 骨架 → 单测Red → 代码Green                   │
│ 业务方法 MUST 标 @Spec · 对抗测试             │
╰──────────────────────────────────────────────╯
                      │
                      ▼   ← after_implement 钩子自动触发
╭──────────────────────────────────────────────╮
│ ① /speckit.testing.impact       ◇ 新增       │
│ 产出 docs/impact-report.md                  │
│ （受影响规则 + 风险分级 + 测试策略）           │
╰──────────────────────────────────────────────╯
                      │
                      ▼   ← gate 前置检查 impact-report.md
╭──────────────────────────────────────────────╮
│ ② /speckit.testing.gate         ◇ 新增       │
│ run_gate 脚本判定（AI 只读，不能改判）        │
│ 双向对齐 + diff coverage + 对抗硬判          │
╰──────────────────────────────────────────────╯
                      │ PASS
                      ▼
╭──────────────────────────────────────────────╮
│ /speckit.testing.report           ◇ 新增      │
│ 手动：docs/test-report.md                   │
│ （汇总 + 追溯矩阵 FR-xxx → @Spec → 单测）     │
╰──────────────────────────────────────────────╯

  ··► FAIL ➜ 回流 ⑥ implement（漂移决策矩阵归因：改 code / 补 test / 回 spec）
```

（注：图中节点即全流程图；产物统一落在 `specs/<feature>/docs/`，gate-result.md 由 run_gate 脚本写入、AI 不补写。）

### 步骤详解：每一步具体干什么

| # | 步骤 | 触发 | 具体干什么 | 产物 |
|---|---|---|---|---|
| 1 | 治理 | `/speckit.constitution` | 建立宪法：Principle I Spec 可追溯置首 + II 中文文档/注释 + III 测试技术栈（NON-NEGOTIABLE） | constitution.md |
| 2 | 需求 | `/speckit.specify` | 产出需求与业务规则 `FR-001..FR-xxx`——全链路唯一事实来源，impact/plan/gate/report 都从它出发 | spec.md |
| 3 | 方案 | `/speckit.plan` | 技术选型与架构；定义接口契约（`contracts/`）与数据模型 | plan.md + contracts/ |
| 4 | 测试计划 | `/speckit.testing.plan`（手动） | 依 spec/plan/contracts 生成：单测用例（B/C/E 四维度）+ 验收阈值 + 单测先行排期 | docs/test-plan.md |
| 5 | 拆分任务 | `/speckit.tasks` | 任务清单：骨架先行 + 单测先行 + 测试 REQUIRED；双标签 `[USx]`（编排）`[FR-xxx]`（追溯） | tasks.md |
| 6 | 实现 | `/speckit.implement` | 骨架 → 单测（先证红，Red 三条件硬校验）→ 业务代码转绿；业务方法 MUST 标 `@Spec(rule=...)`；第 4.5 阶段对抗测试主动攻破自己代码 | 代码 + @Spec |
| 7 | 影响分析 | after_implement 钩子①（自动） | git diff + 源码扫描 → 受影响规则清单 + **风险分级**（直接 high / 间接 medium / 边缘 low，Mapper/SQL/yml/pom 变更升一级，high 封顶） | docs/impact-report.md |
| 8 | 门禁 | after_implement 钩子②（自动） | AI 调 `run_gate`（全逻辑下沉）仅读 stdout JSON 不能改判：前置检查 → mvn clean test → 技术栈/结果/注解扫描 → 测试规则双向对齐（双通道）→ diff coverage → HARD PASS/FAIL；AI 补 SOFT 交叉验证（不改判） | docs/gate-result.md（脚本写） |
| 9 | 修复回流 | gate FAIL | 按**漂移决策矩阵**归因：code 不符→改 code；test 漏场景→补测试（**禁改 test 适配 code**）；spec 歧义→回 spec 澄清；code 多于 spec→删 code 或补 spec | — |
| 10 | 测试报告 | `/speckit.testing.report`（手动） | 汇总门禁结果 + Spec 追溯矩阵（FR-xxx → @Spec → 单测）；引用不重生成 impact | docs/test-report.md |

**产物路径统一**：4 个测试产物都在 `specs/<feature>/docs/`（test-plan / impact-report / gate-result / test-report），gate-result 由 **run_gate 脚本写**，AI 不补写。

---

## 二、核心机制（追溯 / 门禁 / 风险分级）

### 1. 追溯：Spec ↔ 代码 ↔ 测试 一一对应

```
              spec.md（FR-001..FR-xxx）← 唯一事实来源
        │  MUST 标 @Spec(rule=FR-001)      │  规则标注（双通道）
        ▼                                  ▼
   业务代码  ◄── 反向：每规则 ≥1 条测试 ────►  测试代码（单测）
        │                                  │
        └──────────────┬───────────────────┘
                       ▼
     run_gate 采集 + 双向对齐校验（任一方向断裂即 FAIL）
                       ▼
              test-report.md 追溯矩阵
```

**规则标注双通道**（与 JUnit 版本无关）：

- **JUnit5**：`@DisplayName("FR-001-R1-<场景>")`（顶层锚 + 子编号）
- **JUnit4**：测试方法上标 `@Spec(rule="FR-001-R1", description="<场景>")`
  （rule = 顶层锚 + 子编号，与 JUnit5 对齐；@Spec 为 spec-kit 自定义注解，
  SOURCE 保留，门禁静态正则扫描，不依赖 JUnit 机制，JUnit4 项目同样可用）

| 校验方向 | 断裂表现 | 判定 |
|---|---|---|
| spec → 代码 | 规则无 @Spec | `unimplemented_rules` 非空 → FAIL |
| 代码 → spec | @Spec 指向不存在的规则 | `orphan_annotations` 非空 → FAIL |
| 测试 → 规则 | 规则标注指向不存在规则 | `displayname_mismatch_count > 0` → FAIL |
| 规则 → 测试 | 已注解规则无测试 | `untested_spec_rules` 非空 → FAIL |

`@Spec` 为 `@Repeatable` + `@Retention(SOURCE)`，仅源码级标记，门禁靠脚本静态正则扫描，无运行时反射。

### 2. 门禁：run_gate 如何裁决（脚本判定，AI 不改判）

> 为什么：v0.3 试点中 AI 自报 96% 覆盖率、实际 62.9%。v0.4 起全部确定性逻辑下沉到脚本，
> **AI 仅读 stdout JSON 输出指令，不能改判**——这是「不依赖 AI 自报」的物理保证。

`run_gate` 执行顺序（`--check-only` 供实现阶段自检，只跑不写）：

```
0. 前置检查 impact-report.md 存在（缺失即 FAIL）
1. 模块定位（AI 辅助）：先 find pom.xml，--project 指向含 pom 的模块；传错 → 降级+degraded_reason
2. mvn clean test 全量执行（回归兜底，永远跑）
3. scan_test_stack 技术栈硬校验（禁 PowerMock / @SpringBootTest / @Autowired；缺报告即 FAIL，不降级）
4. parse_test_results：surefire + JaCoCo 聚合 + source_lines 行级数据
5. scan_spec_annotations：@Spec 分布 + UNSPEC_CODE 漂移告警（MEDIUM 不阻断）
6. 内联解析测试规则标注（双通道）→ 双向对齐校验（见上表）
7. 对抗用例硬判（critical_path_required：high 风险规则 MUST 有对抗用例）
8. diff coverage 判定：变更行覆盖率 ≥ 阈值（默认 80，--diff-base 时先 merge-base）
9. SOFT 段存在性检查（见下）
10. 逐项比对 → PASS/FAIL → 写 gate-result.md + stdout JSON
```

- **T1/T2 双门禁**：T2 运行正确性（脚本 HARD：全绿 + 覆盖率 + diff coverage）≠ T1 业务一致性（@Spec 双向对齐硬判 + 对抗用例 + AI 交叉验证 SOFT）。全绿只能证明"能运行"，不证明"按业务实现"。
- **SOFT 交叉验证**：AI 在 gate-result.md 追加 `## AI 交叉验证（SOFT，不影响判定）` 段，检查规则语义/断言质量/覆盖率真实性/@Spec 放置/直接测试覆盖五维；run_gate 只读检查该标题，缺则 WARN + `soft_missing`（不 FAIL）；写文件时保留已有 AI 段（追加非覆盖）。
- **diff coverage**：全量 `mvn clean test` 永远跑，阈值只对 **git 变更行**强制；无 Java 变更跳过，无 git 回退全量阈值；test 文件/未跟踪行不计入。
- **Red 判定三条件**（修「编译失败冒充红灯」P0）：① `mvn test-compile` EXIT=0 ② `mvn test` 输出断言失败特征 ③ 编译错误不是 Red——回补骨架再验①②，不得进入 Green。

### 3. 风险分级 + 对抗测试

- **风险分级**（impact 规则化评分，替代 AI 自由裁量）：直接命中 high（改实现该规则的文件）/ 间接 medium（调用链/同包引用）/ 边缘 low（注释/工具类/纯重构）；`*Mapper.java`、`*.sql`、`pom.xml`、`application*.yml` 变更升一级（high 封顶）——让 gate 的 high 硬判可复现。
- **对抗测试**：implement 第 4.5 阶段，AI 主动攻破自己：第 1 轮反例/边界/异常/并发（high 规则），第 2 轮起目的性补洞，循环上限 `max_iterations`（默认 3）。

---

## 三、组成：三层交付

| 层 | 载体 | 职责 | 改核心行为 |
|---|---|---|---|
| 扩展 testing | `extensions/testing/` | 新增能力：4 命令 + 1 钩子 + 4 模板 + 5 脚本 + @Spec 注解 + 配置 | 否 |
| 预设 testing-tdd | `presets/testing-tdd/` | replace 宪法/spec/tasks 模板 + append implement，强制 TDD | 是（必须配套） |
| bundle speckit-testing | `examples/bundles/speckit-testing/` | 一键装扩展 + 预设 | — |

- **4 命令**：impact（影响分析）/ plan（测试计划）/ gate（门禁）/ report（测试报告），见第一章步骤。
- **钩子**：`hooks.after_implement` 自动触发，impact 在前、gate 在后（gate 前置检查 impact-report.md，缺失即 FAIL）。
- **5 脚本**（python-only，输出 JSON，AI 只读不改）：`scan_spec_annotations`（@Spec 扫描+UNSPEC 告警）/ `validate_spec_format`（R 编号连续）/ `parse_test_results`（surefire+JaCoCo+行级 source_lines）/ `scan_test_stack`（禁 PowerMock/@SpringBootTest/@Autowired）/ `run_gate`（门禁编排）。
- **4 模板**：java-service（@Spec 注解占位）/ java-unit-test（JUnit4/5 双通道规则标注 + given-when-then）/ test-plan-template（UT 用例 + 阈值）/ spec-trace-matrix（追溯矩阵）。
- **预设覆盖**：constitution（Principle I/II/III）、spec-template（Functional Requirements 段）、tasks-template（单测先行+双标签+checkpoint `mvn test-compile`）、implement（@Spec 强制+Red 三条件+对抗测试+禁改 test 适配 code）。

---

## 四、测试技术栈（必需前置）

| 组件 | 作用 | 必需性 |
|---|---|---|
| JUnit 4/5 + Mockito | 测试框架 / Mock 依赖（@Mock / @InjectMocks） | REQUIRED |
| Surefire | 测试执行 + surefire-reports | REQUIRED |
| JaCoCo | 覆盖率插桩（含行级 source_lines） | REQUIRED |

**禁用**：PowerMock（覆盖率失真）、`@SpringBootTest` 起容器、`@Autowired`
（测试须显式 Mock/构造注入，不起 Spring 容器）。缺 JaCoCo/surefire 报告 →
门禁 FAIL（**不降级**）。唯一降级：非 Java 项目（无 java/mvn）。

---

## 五、快速上手（安装 / 配置 / 卸载）

### 安装（任选一种）

```bash
# A. 直装（发布版，当前 1.5.0；更新版本替换 URL 中版本号）
specify extension add testing --from https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-1.5.0.zip
specify preset add testing-tdd --from https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-tdd-1.5.0.zip

# A'. 大陆备选（raw 被墙/丢包时）：curl 自动重试下载解压后本地 --dev 安装
#    （详见原 README 或 release 脚本；GitHub Release 版 URL 为 .../releases/download/v1.5.0/xxx.zip）

# B. 开发调试（改源码直接生效）
specify extension add --dev <spec-kit>/extensions/testing
specify preset add --dev <spec-kit>/presets/testing-tdd --priority 10

# C. bundle 一键装
specify bundle install speckit-testing
```

> 调试期建议 B。预设会 replace 核心模板（宪法/spec/tasks/implement）。`--from` 非 catalog 来源会弹
> "Untrusted Source" 确认，按 `y`。

### 配置

`.specify/extensions/testing/testing-config.yml`（安装时从模板复制，项目可覆盖）：

| 段 | 关键项 | 默认 |
|---|---|---|
| `gate` | 行/分支/方法/指令覆盖率、通过率 | 80/70/80/85、100% |
| `gate` | `ai_cross_validation` / `diff_coverage_threshold` / `diff_base` | true / 80 / "" |
| `gate` | `spec_traceability`：规则覆盖 100% + `require_displayname_match` | true |
| `test_stack` | 禁 PowerMock / `@SpringBootTest` / `@Autowired` | true |
| `scan` | `unspec_exclude_patterns`（UNSPEC 告警额外排除，内置 dto/vo/entity/mapper 等表） | [] |
| `risk_overrides` | high/medium/low 阈值 | 90% 起 / 70% 起 |
| `adversarial` | `enabled` / `max_iterations` / `critical_path_required` | true / 3 / true |

### 卸载 / 切回普通 spec-kit

```bash
specify preset remove testing-tdd    # 宪法/模板恢复 spec-kit 默认
specify extension remove testing     # 命令/钩子/配置全部卸载
```

> 临时停用：`specify preset disable testing-tdd` / `specify extension disable testing`，`enable` 随时恢复。

## 许可证

MIT