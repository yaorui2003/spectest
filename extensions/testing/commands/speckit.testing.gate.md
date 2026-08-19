---
description: "Speckit Testing 门禁：AI 调用 run_gate 脚本（mvn clean test + 技术栈校验 + @Spec 扫描 + DisplayName 一致性 + 关键路径对抗用例硬判 + 按风险阈值判定），AI 仅读判定 JSON 输出阻断/通过指令 + AI 语义交叉验证（SOFT，不改判）"
scripts:
  sh: ../../scripts/bash/run-gate.sh
  ps: ../../scripts/powershell/run-gate.ps1
  py: ../../scripts/python/run_gate.py
---

# Speckit Testing Gate

本命令为 `after_implement` 钩子（`optional: false`，强制自动执行）的门禁。
代码实现完成后立即触发。**v0.4 起门禁的全部确定性逻辑已下沉到 `run_gate`
编排脚本**（三语言 sh/ps/py 字节级等价）：脚本执行 `mvn clean test` + 调用
4 个扫描脚本（scan_test_stack / parse_test_results / scan_spec_annotations）+
内联解析 @DisplayName + 按 `ImpactReport.risk_level` 套用
`testing-config.yml` 阈值 + 判定 PASS/FAIL + 直接写 gate-result.md。
**AI 仅读取脚本 stdout 输出的判定 JSON，按脚本判定输出阻断/通过指令——
不能改判、不能补写 gate-result.md、不能跳过步骤。**

> 本命令不再由 AI 编排脚本 / 比对阈值 / 写产物（v0.3 方式已被试点证明可被
> AI 伪造覆盖率），全部改由 run_gate 脚本执行。AI 的角色是调用脚本 + 读
> 结果 + 输出指令。

## 触发方式

- **手动**：用户在 AI Agent 中直接调用本命令。
- **自动**：`after_implement` 钩子触发（`optional: false`）。AI Agent 读取
  `.specify/extensions.yml` 中 `hooks.after_implement` 段，输出
  `EXECUTE_COMMAND: speckit.testing.gate` 并实际调用本命令，等待结果后再
  继续 `speckit.implement` 的收尾。

## 输入

| 参考生成物 | 必需性 | 用途 |
|---|---|---|
| 用户项目业务代码（`.java` 源文件，含 `@Spec` 注解） | REQUIRED | 扫描 @Spec 注解 + 规则覆盖校验 |
| 测试代码（单测 + 契约测试，单测带 `@DisplayName` 规则标注） | REQUIRED | `mvn clean test` 执行 + @DisplayName 双向对齐 |
| `spec.md`（`business_rules` 规则编号清单） | REQUIRED | 规则编号比对（unimplemented_rules / orphan_annotations） |
| `ImpactReport` 产物（`specs/<feature>/docs/impact-report.md`） | REQUIRED（前置检查，缺失即 FAIL） | 取 `risk_level` 套阈值；after_implement 时由 `speckit.testing.impact` 在本命令前产出 |
| `testing-config.yml`（阈值与风险覆盖配置） | REQUIRED（缺失时降级：run_gate 使用与模板默认一致的内置阈值，并在 gate-result.md 标注"配置缺失，按默认阈值判定"） | 阈值与风险覆盖配置 |

## 技术栈前置要求（REQUIRED）

本门禁针对 Java 项目，以下技术栈为**必需前置条件**（默认用户已配置），由
`run_gate` 脚本执行 `scan_test_stack` 硬校验：

| 组件 | 作用 | 必需性 |
|---|---|---|
| JUnit 4/5 | 测试框架 | REQUIRED |
| Mockito | Mock 依赖（`@Mock` / `@InjectMocks`） | REQUIRED |
| Surefire（`mvn test`） | 测试执行 + surefire-reports 生成 | REQUIRED |
| JaCoCo | 覆盖率插桩（line/branch/method/instruction/complexity） | REQUIRED |

**禁用**（脚本 `scan_test_stack` 检出即 FAIL）：

- **PowerMock** -- 覆盖率失真，门禁判定为 FAIL
- **`@SpringBootTest` 起容器** -- 契约测试基于 WireMock contract mock、
  单测基于 Mockito，均不起容器；起容器的测试不属于本门禁范围且拖慢执行

> **不降级原则**：`mvn clean test` 执行后若 `target/surefire-reports/` 或
> `target/site/jacoco/jacoco.xml` 缺失，判定 **FAIL**（通过率/覆盖率指标
> 不可用 = 未达标），由脚本输出修复建议（添加 Surefire/JaCoCo 插件配置，
> 参考下方"JaCoCo/Surefire 配置参考"）。唯一降级场景（beta 简化，与脚本
> 对齐）= **无 `java`/`mvn` 可执行**，**或** `--project` 指向目录无
> `pom.xml`（AI 定位错误），见下方"降级模式"。

## T1/T2 双门禁框架（v0.6 8.0，认知框架，不改脚本判定逻辑）

本门禁显式区分两层目标（承 SCT 1.2/6.5），**不可合并**：

| 目标 | 含义 | 典型缺口 | 判定工具 |
|---|---|---|---|
| **T2 运行正确性**（必要条件） | 代码没有运行错误（NPE/越界/死锁） | 覆盖率数字好看但分支未测 | 脚本 HARD：mvn clean test 全绿 + 覆盖率阈值 |
| **T1 业务一致性**（目的） | 测试能测出"代码是否按业务实现" | test 全过但漏 spec 场景 / 测了没意义的代码 | 脚本（结构性）+ AI（语义性）混合：@Spec/@DisplayName 对齐 + 对抗用例 + AI 交叉验证 |

**关键不变量：T2 达标 ≠ T1 达标**（8/18 反例：52 绿 + 覆盖率达标但核心
生成链零直接测试）。run_gate 检查项按两层归类（纯表述，不改脚本判定逻辑）：

| 检查项 | 层 | 判定者 |
|---|---|---|
| mvn clean test 全绿 | T2 | 脚本（HARD） |
| 覆盖率阈值（line/branch/method/instruction/complexity） | T2 | 脚本（HARD） |
| @Spec/@DisplayName 编号对齐 + orphan 检测 | T1 结构性 | 脚本（HARD） |
| 步骤 5.5 对抗用例硬判（high 风险规则） | T1 行为性 | 脚本（HARD） |
| 步骤 3 AI 交叉验证五维（含第 5 维直接测试覆盖） | T1 语义性 | AI（SOFT，不改判） |
| 漂移处置决策矩阵（见步骤 3） | T1 归因 | AI（SOFT）+ 人工决策 |

> **推论（衔接 8.0）**：gate FAIL 时先区分是 T2 缺口（补分支/补实现）还是
> T1 缺口（补场景/补直接测试/回 spec）——归因决定处置路径，再按步骤 3
> "漂移处置框架"的决策矩阵处置。

## 处理逻辑

> **AI 角色：仅读结果，不能改判**。以下全部步骤由 `run_gate` 脚本执行，
> AI 不执行 mvn test、不逐个调用扫描脚本、不比对阈值、不写 gate-result.md。
> AI 只负责：调用 run_gate（frontmatter `scripts:` 段声明的脚本）→ 读取
> stdout 判定 JSON → 按判定输出阻断/通过指令。

### 步骤 1：调用 run_gate 脚本

运行 frontmatter `scripts:` 段声明的 `run_gate` 脚本（按项目 `--script
sh|ps|py` 选择其一），脚本内部按以下 10 步执行（供 AI 理解脚本行为，AI
**不要**自行重复执行）：

**前置检查（MUST，beta 简化）**：

- **多模块项目 MUST 先 `find . -name pom.xml -maxdepth 3`**（或已知工程
  结构）将 `--project` 指向**含 pom.xml 的模块目录**（如 `backend/`），再
  运行 run_gate；**run_gate 不做模块自动探测**（POM 定位由 AI 负责），
  `--project` 传错（目录无 pom.xml）即降级并提示。
- **diff coverage（替换 v0.6 9.4 作用域，beta 简化）**：
  `--diff-threshold <pct>`（默认 80，`config gate.diff_coverage_threshold`
  可写）阈值只对 **git diff 变更行**强制——"只看 MR 变更行覆盖率"；
  `--diff-base <branch>` 用于 MR 场景（merge-base 对比），默认工作区 vs
  HEAD。**全量 `mvn clean test` 永远跑**（回归盲区兜底），diff coverage
  只做阈值判定不限制执行；无 git 仓库时回退全量聚合阈值判定；无 Java
  变更时该维度跳过（不 FAIL）。
- **受影响 e2e 用例清单（可选，v0.6 9.9）**：impact 命中规则与功能测试
  案例集的 `covered_rules` 字段**求交**，得到本次回归受影响的 e2e 用例 ID
  清单；前端 e2e 选择执行 `npx playwright test --grep <用例 ID>` 只跑命中
  用例（不命中即不跑，避免全量慢跑；缺 covered_rules 的用例降级手工）。
  清单随步骤 3 SOFT 段追加到 gate-result.md 的 e2e 段（不改写 HARD 段）。

最终参数清单（beta 简化）：

```bash
run_gate --source <java_dir> --test-source <test_dir> --spec <spec.md> \
  --project <模块目录> --feature-dir <specs/<feature>> --config <testing-config.yml> \
  [--check-only] [--diff-threshold <pct>] [--diff-base <branch>] --json
```

| 步骤 | 动作 | 失败处理 |
|---|---|---|
| 0 | 检查 `specs/<feature>/docs/impact-report.md` 存在 | 不存在 -> FAIL（impact 未执行，请先运行 speckit.testing.impact） |
| 1 | `mvn clean test`（在 `--project` 指定模块目录执行，强制 clean，杜绝 target 残留污染） | 失败 -> FAIL；无 java/mvn 或 `--project` 目录无 pom.xml -> 降级模式 |
| 2 | 调 `scan_test_stack` | `forbidden_findings` 非空 -> FAIL |
| 3 | 调 `parse_test_results` | jacoco.xml / surefire 缺失 -> FAIL（不降级） |
| 4 | 调 `scan_spec_annotations` | `unimplemented_rules` / `orphan_annotations` 非空 -> FAIL |
| 5 | 内联解析测试源码 `@DisplayName`，**双向**对齐（DisplayName->@Spec + @Spec->DisplayName） | 不对齐数 > 0 或有 `@Spec` 无测试的规则，且 `require_displayname_match` -> FAIL |
| 5.5 | 关键路径对抗校验（v0.5，configurable）：读 impact-report 逐规则 risk + 检测 `@DisplayName("Rn-对抗-...")` 对抗用例 | `critical_path_required=true` 且 high 风险规则 0 对抗用例 -> FAIL；`false` 跳过（降级） |
| 6 | 读 `impact-report.md` 的 `risk_level` + 读 `testing-config.yml` | 套风险档阈值 |
| 7 | 逐项比对覆盖率（全量聚合 + diff coverage 变更行，若适用）/ 通过率 / Spec 覆盖率与阈值 | 任一不达标 -> FAIL |
| 8 | **脚本直接写 `specs/<feature>/docs/gate-result.md`** + stdout 输出判定 JSON；写前只读正则检查 SOFT 标题存在性，缺则 WARN + `soft_missing: true`（不 FAIL） | AI 仅读，不能改判 |

### 步骤 2：读取判定 JSON 并输出指令

读取 `run_gate` stdout 输出的判定 JSON（含 PASS / FAIL、失败原因、修复
建议）：

- 若 **FAIL** -> 输出阻断指令（引用 gate-result.md 中的失败原因与修复建议）
- 若 **PASS** -> 输出通过指令 + 提示运行报告命令（令牌）
- 若 JSON 含 `soft_missing: true`（v0.6，脚本只读检查 SOFT 标题缺失，
  不 FAIL）-> 提示 AI 补步骤 3 交叉验证段（`## AI 交叉验证（SOFT，不影响
  判定）` 段）到 gate-result.md 后重跑门禁——**仅补段，不重跑 mvn**（脚本
  只读正则检查标题存在性，补段后重跑即消 WARN，不改判 PASS/FAIL）

**硬约束（MUST）**：

- AI **不能改判**：即使认为脚本判定有误，也必须按脚本判定输出阻断 / 通过指令
- AI **不能补写** `gate-result.md`：产物只能由 run_gate 脚本写入
- AI **不能跳过步骤**：必须调用 run_gate 脚本获取真实数据，不得自行声称通过
- AI **不得修改** `scripts/` 下脚本：不得编辑、打补丁、加豁免或以任何方式改动
  `extensions/testing/scripts/` 内的扫描脚本（scan_test_stack /
  scan_spec_annotations / parse_test_results / validate_spec_format）与
  `run_gate`。**改脚本让门禁通过 = 绕过门禁**，属严重违规。脚本若判定有真实
  bug，须回 spec-kit 源修复并重装扩展，绝不在用户项目内就地打补丁（v0.4 试点
  已出现 AI 给 `scan_test_stack` 加 `@SpringBootTest` 豁免以让违规测试过门禁的
  反例--该豁免与"禁用 `@SpringBootTest` 起容器"规范冲突，已被判定为错误修复）。

### 步骤 3：AI 语义交叉验证（SOFT，不改判；v0.5 新增，v0.6 加第 5 维与漂移处置框架）

当 `testing-config.yml` 的 `gate.ai_cross_validation: true`（默认）时，在步骤 2
之后执行。

读取 run_gate 判定 JSON + gate-result.md + 测试源码（`src/test/`）+ 业务代码
（`src/main/`）+ spec.md，做五维语义检查（v0.6 在 v0.5 四维基础上新增第 5 维
直接测试覆盖，8.4）：

| 维度 | 脚本判了什么 | AI 补判什么 |
|---|---|---|
| 规则-测试语义对齐 | @Spec/@DisplayName 编号匹配 | 测试方法体是否真正验证规则业务语义 |
| 断言质量 | 断言存在 | 断言是否有业务语义（非 assertTrue(true)） |
| 覆盖率真实性 | JaCoCo % | 覆盖是否来自有意义测试 |
| @Spec 放置 | rule 编号在 spec.md | @Spec 是否标在真正实现该规则的方法上 |
| 直接测试覆盖（v0.6） | 无（脚本不检查直接性） | 每条规则是否至少一个直接单测；若规则仅被编排/集成测试间接覆盖 -> WARN 建议补直接单测（8/18 反例：GeneratorAgent/PlannerAgent 零直接测试零 @Spec） |

每维输出 `[PASS/WARN/CRITICAL]` + 说明。CRITICAL = 建议人工复核（不自动阻断）。

**硬约束（MUST）**：

- **不能改判**：HARD FAIL 仍阻断，HARD PASS 不因 AI 发现问题而改 FAIL
- **不能删除/修改** gate-result.md 中脚本写入的 HARD 段
- **仅追加** "## AI 交叉验证（SOFT，不影响判定）" 段到 gate-result.md
- 降级模式（无测试源码）跳过交叉验证
- check-only 模式跳过交叉验证（不写产物）

输出格式（追加到 gate-result.md 末尾，不改写 HARD 段）：

```markdown
## AI 交叉验证（SOFT，不影响判定）

### 规则-测试语义对齐
- R1: PASS - testTransferAmountValidation 测试了金额边界（0/负数/超限）
- R2: WARN - testCheckBalance 仅测正常余额，未测不足余额分支

### 断言质量
- PASS - 未发现 assertTrue(true) 空断言

### 覆盖率真实性
- PASS - 100% 覆盖来自有意义测试

### @Spec 放置
- PASS - 各 @Spec 标注在实现该规则的方法上

### 直接测试覆盖
- PASS - 每条规则均有直接单测（R1 -> AccountServiceTest.testTransfer...）
- WARN - R5 仅被编排测试 OrchestratorImplTest 间接覆盖，建议补 PlannerAgent 直接单测

### 交叉验证结论
- 2 项 WARN（R2 测试覆盖不全 + R5 缺直接单测），建议补测不足余额分支与直接单测
- 0 项 CRITICAL
```

#### 漂移处置框架（v0.6 9.8，gate FAIL 后的归因与处置）

gate FAIL 后**先归因 T1/T2**（见"T1/T2 双门禁框架"推论），再按下述框架
处置。本框架在步骤 3 SOFT 段给出**建议归因**，**不自动改判**——HARD FAIL
仍阻断，处置完成由用户/主流程决定重跑时机。

**铁律（MUST）**：永远不允许直接改 test 适配 code（与 v0.4 防伪造同源，
显式化）。发现测试与代码不一致时先归因，**不得为了让测试变绿而改断言/改
用例去迁就代码**。

**归因三问**：

1. **差异在哪个文件/行/字段**（定位）：精确到文件、行号、字段/方法，
   禁止"测试和代码对不上"式模糊归因
2. **谁主张谁复核**（权责）：提出差异者给出证据（源码 / 测试 / spec.md
   原文），复核者独立确认，不搞"自己提自己核"
3. **改 spec/code/test 哪个，为什么**（归因）：给出改动方向与理由；且
   **改 test 必须由 spec 派生逻辑驱动**（补 spec 规定的场景，而非适配 code）

**决策矩阵**（AI 在 SOFT 段给出建议归因，人工决策）：

| 漂移类型 | 默认处置 | 复核 |
|---|---|---|
| code 不满足 spec（缺实现） | 改 code | 跑 test 验证 |
| test 漏场景（T1 缺口） | 补测试（由 spec 派生逻辑驱动，非适配 code） | 重跑 gate |
| spec 有歧义/错误 | 回 spec 澄清（AI 不得擅自改 spec，交用户/PM） | 重跑 codegen |
| code 多于 spec | 删 code 或补 spec 二选一，SOFT 段标注 | 人工决策 |

### run_gate 内部逻辑说明

以下为 `run_gate` 脚本内部执行的校验逻辑（供 AI 理解脚本行为，非 AI
操作；这些是脚本的确定性步骤，AI 不得自行"代跑"）：

**单测与契约测试（mvn clean test）**：脚本在项目根目录执行 `mvn clean test`
（强制 clean 杜绝 `target/` 残留旧 jacoco 污染），收集：

- **单测明细**：总数 / 通过 / 失败 / 行覆盖率 / 分支覆盖率 / 通过率
  （覆盖率取自 JaCoCo 报告 `target/site/jacoco/jacoco.xml`）
- **契约测试明细**：总数 / 通过 / 失败 / 通过率（契约测试以 `CT-` 前缀命名
  或位于 `src/test/java/.../contracts/` 包下识别）

**报告缺失即 FAIL**：`mvn clean test` 执行后若 `target/surefire-reports/`
缺失 -> 通过率指标不可用 -> FAIL；若 `target/site/jacoco/jacoco.xml` 缺失
-> 覆盖率指标不可用 -> FAIL。输出修复建议（见"JaCoCo/Surefire 配置
参考"段），不降级跳过。

**技术栈硬校验（scan_test_stack）**：脚本调用
`scripts/{bash,powershell,python}/scan-test-stack.{sh,ps1,py}`，扫描
`src/test/` 下全部 `.java` 测试文件，检出禁用技术：

- `org.powermock.*` 导入 -> type: powermock
- `@SpringBootTest` 注解 -> type: springboottest

若 `forbidden_findings` 非空 -> **直接 FAIL**，输出违规清单（文件、行号、
违规内容），提示移除 PowerMock 依赖或将 `@SpringBootTest` 改为 Mockito +
WireMock 契约测试。

**@Spec 注解扫描（scan_spec_annotations）**：脚本调用
`scripts/{bash,powershell,python}/scan-spec-annotations.{sh,ps1,py}`，解析
用户项目全部 `.java` 源文件，正则提取 `@Spec(capability="...", rule="Rn",
...)` 注解，同时解析 `spec.md` 的 `business_rules` 规则编号，输出 JSON：

```json
{
  "spec_rules": ["R1", "R2", ..., "R7"],
  "annotations": [
    {"rule": "R1", "capability": "transfer", "description": "...",
     "location": "com.example.AccountService.transfer:42"}
  ],
  "annotated_rules": {"R1": ["com.example.AccountService.transfer:42"]},
  "unimplemented_rules": ["R2", "R3"],
  "orphan_annotations": [{"rule": "R9", "location": "..."}],
  "coverage_percent": 71
}
```

重点关注以下两个字段（任一非空即 FAIL）：

- `unimplemented_rules`：`spec.md` 有但代码无 `@Spec` 注解的规则（漏实现）
- `orphan_annotations`：代码有 `@Spec` 但 `spec.md` 无对应规则的注解
  （规则编号写错或 spec 已删该规则）

**@DisplayName 一致性校验（双向）**：脚本遍历单测方法，解析
`@DisplayName("Rn-描述")` 中的规则编号 `Rn`，做双向对齐：

- **正向（DisplayName->@Spec）**：每条单测 `@DisplayName` 必须指向真实存在的
  `@Spec` 规则（格式 `R<n>-<描述>`，正则 `^R\d+-`）；指向不存在 `@Spec` 的计入
  `displayname_mismatch_count`
- **反向（@Spec->DisplayName）**：每条 `@Spec` 已注解规则 MUST 至少有 1 条
  对应 `@DisplayName("Rn-...")` 测试；有 `@Spec` 但无测试的规则计入
  `untested_spec_rules`（堵审计 F1：标了 `@Spec` 不写测试也能过的缺口）

若 `testing-config.yml` 中
`gate.spec_traceability.require_displayname_match: true`（默认），则
`mismatch_count > 0` 或 `untested_spec_rules` 非空时 FAIL。

**按风险等级套用阈值**：脚本读取 `ImpactReport.risk_level`（`high` /
`medium` / `low`），按 `testing-config.yml` 的 `risk_overrides` 与 `gate`
默认值合并后套用（覆盖值优先）：

| 风险 | 行覆盖率 | 分支覆盖率 | 方法覆盖率 | 指令覆盖率 | 复杂度覆盖率 | 单测通过率 | 契约通过率 | Spec 覆盖率 |
|------|----------|------------|------------|------------|--------------|------------|------------|-------------|
| high | >=90% | >=70% | >=90% | >=90% | >=80% | 100% | 100% | 100% |
| medium | >=80% | >=70% | >=80% | >=85% | >=70% | 100% | >=95% | 100% |
| low | >=70% | >=70% | >=70% | >=80% | >=60% | 100% | >=95% | 100% |

**判定 PASS/FAIL**：脚本逐项比对步骤 0-8（含 5.5 关键路径对抗校验）的实际
值，任一检查未过 -> FAIL，全部通过 -> PASS。

判定 FAIL 的条件（任一即 FAIL）：

- `unimplemented_rules` 非空（spec 规则未实现）
- `orphan_annotations` 非空（孤儿注解）
- 单测通过率 < 阈值
- 行覆盖率 / 分支覆盖率 < 阈值
- 契约测试通过率 < 阈值
- `require_displayname_match` 为 true 且 `displayname_mismatch_count` > 0
- `require_displayname_match` 为 true 且 `untested_spec_rules` 非空（有 `@Spec` 无对应测试）
- `critical_path_required=true` 且 high 风险规则无对抗用例（`@DisplayName("Rn-对抗-...")`）
- Spec 规则覆盖率 < 100%

### JaCoCo/Surefire 配置参考

> 本扩展不自动修改用户 `pom.xml`。若门禁因报告缺失 FAIL，按以下参考在
> 项目 `pom.xml` 的 `<plugins>` 段添加配置后重跑门禁。

Surefire（通常 Spring Boot archetype 已含，缺则补）：

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-surefire-plugin</artifactId>
    <version>3.2.5</version>
</plugin>
```

JaCoCo（prepare-agent + report）：

```xml
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>0.8.11</version>
    <executions>
        <execution>
            <id>prepare-agent</id>
            <goals><goal>prepare-agent</goal></goals>
        </execution>
        <execution>
            <id>report</id>
            <phase>test</phase>
            <goals><goal>report</goal></goals>
        </execution>
    </executions>
</plugin>
```

## 输出（GateResult）

由 `run_gate` 脚本直接写入 `specs/<feature>/docs/gate-result.md`（AI **不
补写**）。格式如下（v0.4 5.4）：

```markdown
## Gate Result: PASS | FAIL

### 执行环境
- mvn clean test: SUCCESS | FAIL
- target 清理: 已清理（杜绝残留污染）
- 模块定位: backend/（--project 指定）| 未找到（degraded_reason: ...）

### 单测明细
- 总数: N | 通过: N | 失败: N
- 行覆盖率: NN% (阈值 >=NN%) | 分支: NN% | 方法: NN% | 指令: NN% | 复杂度: NN%
- 变更行覆盖率 (diff): NN% (阈值 >=NN%) | diff-base: HEAD | 未应用（无 git / 无 Java 变更）
- 通过率: NN% (阈值 100%)

### 契约测试明细
- 总数: N | 通过: N | 失败: N | 通过率: NN%

### Spec 规则覆盖矩阵
- 规则总数: N | 已注解数: N | 未实现规则: [] | 孤儿注解: []
- DisplayName 对齐数: N / N

### 判定依据
- risk_level: high | medium | low | default
- 套用阈值来源: testing-config.yml risk_overrides.<risk>

### 失败原因与修复建议（仅 FAIL 时）
- [FAIL] line_coverage 65% < 90% (high) -> 补 XxxService.transfer 的边界用例
```

## 契约不变量

- FAIL 时 `fail_reasons` 必须非空且含可执行修复建议（指明文件/方法/规则）
- `spec_coverage.unimplemented_rules` > 0 时必须 FAIL
- `spec_coverage.orphan_annotations` > 0 时必须 FAIL
- `after_implement` 触发时，FAIL 必须阻断提交（见下方阻断指令）
- **gate-result.md 由 run_gate 脚本写入，AI 不得补写 / 改判**

## FAIL 阻断提交指令

当判定为 FAIL 时，**必须输出以下阻断指令**并终止 `speckit.implement` 流程：

```text
## ⛔ GATE FAILED - 阻断提交

门禁未通过，禁止执行 git commit / git push。请按上述失败原因与修复建议
修正后重新运行门禁：

EXECUTE_COMMAND: speckit.testing.gate

修正完成并重新通过门禁前，不得继续后续流程。
```

## 降级模式（无 java/mvn，或 --project 目录无 pom.xml）

**降级判定（beta 简化，与脚本对齐）**：`degraded = 无 java/mvn 可执行
**或** `--project` 指向目录无 `pom.xml`（AI 定位错误）`。run_gate **不做
模块自动探测**——多模块 Java 项目 MUST 先用 `find . -name pom.xml
-maxdepth 3`（或已知工程结构）把 `--project` 指向含 pom.xml 的模块目录
（如 `backend/`），传错（无 pom）即降级。

脚本降级时输出 `degraded_reason`（如 `pom.xml not found at <path>` 或
`no java/mvn on PATH`），gate-result.md"执行环境"段标注
`模块定位: 未找到（degraded_reason: ...）`；stdout JSON 同时含
`suggestion` 字段（降级时给具体建议命令，如
`run_gate --project backend --spec specs/... --gate-result ...`）。

降级时脚本**仅做 `@Spec` 静态扫描**，跳过 `mvn clean test` 与 @DisplayName
解析（因无单测可读），仅执行 @Spec 注解扫描与 Spec 覆盖率阈值判定
（`spec_rule_coverage_min: 100`）。降级时脚本在 gate-result.md 中明确标注
"降级模式"。

降级时 AI 必须在输出中明确告知：

```text
## ⚠️ 降级模式（无 java/mvn 或 --project 无 pom.xml）

未检测到 java/mvn，或 --project 指向目录无 pom.xml（degraded_reason: ...），
跳过单测与契约测试执行，仅做 @Spec 静态扫描。覆盖率与通过率检查被跳过。
仅校验：
- spec 规则覆盖率（unimplemented_rules / orphan_annotations）
- @Spec 注解格式与规则编号匹配

请在具备 Java 环境或正确指定 --project 模块目录时重新运行门禁以获取完整校验。
```

## 对抗门禁降级模式（v0.5）

`testing-config.yml` 的 `adversarial` 段两级开关控制对抗用例门禁：

| `adversarial.enabled` | `adversarial.critical_path_required` | 行为 |
|---|---|---|
| true（默认） | true（默认） | implement 4.5 做 + **gate 硬判**：high 风险规则 0 对抗用例 -> FAIL（full） |
| true | false | implement 4.5 做 + gate 不硬判（advisory，仅统计不阻断） |
| false | false | implement 4.5 不做 + gate 不校验（off，最宽降级） |

> `enabled` 控制 AI 行为（implement 4.5 阶段），`critical_path_required` 控制 gate 脚本是否硬判。降级模式（无 java/mvn 或 `--project` 无 pom.xml）自动跳过对抗校验。

## PASS 后续动作

当判定为 PASS 时，提示用户可运行测试报告命令生成追溯矩阵：

```text
## ✅ GATE PASSED

门禁通过，可继续提交流程。建议运行测试报告命令生成 Spec 追溯矩阵：

EXECUTE_COMMAND: __SPECKIT_COMMAND_TESTING_REPORT__
```

注意：上方令牌 `__SPECKIT_COMMAND_TESTING_REPORT__` 由 spec-kit 注册时
按当前 integration 的 `invoke_separator` 渲染为实际调用形式
（点分 agent、连字符 agent、skills agent 各自的渲染结果），勿硬编码具体
调用路径——令牌本身已涵盖跨 agent 兼容。

## Done When

- [ ] 已调用 `run_gate` 脚本（frontmatter `scripts:` 段声明，按 `--script` 选择）
- [ ] 已读取 run_gate stdout 判定 JSON（PASS 或 FAIL）
- [ ] FAIL 时已输出阻断指令（引用 gate-result.md 失败原因与修复建议）
- [ ] PASS 时已输出通过指令 + report 命令提示（令牌）
- [ ] 未改判、未补写 gate-result.md、未跳过任何步骤
- [ ] 未修改 `scripts/` 下任何脚本（scan_test_stack / scan_spec_annotations / parse_test_results / validate_spec_format / run_gate）
