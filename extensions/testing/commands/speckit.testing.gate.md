---
description: "Speckit Testing 门禁（after_implement 钩子）：AI 调用 run_gate 脚本执行 mvn clean test + 技术栈校验 + @Spec 扫描 + DisplayName 一致性 + 关键路径对抗用例 + diff coverage 判定，仅读判定 JSON 输出阻断/通过指令 + AI 语义交叉验证（SOFT，不改判）"
scripts:
  py: ../../scripts/python/run_gate.py
  # DEPRECATED (beta 阶段)：sh/ps 版已弃用，仅保留供参考，不再维护。
  # sh: ../../scripts/bash/run-gate.sh
  # ps: ../../scripts/powershell/run-gate.ps1
---

# Speckit Testing Gate

`after_implement` 钩子（`optional: false`，强制）。**门禁全部确定性逻辑已下沉
`run_gate` 脚本**（python 唯一实现，sh/ps 弃用）：`mvn clean test` + 技术栈校验
+ @Spec 扫描 + @DisplayName 一致性 + 关键路径对抗硬判 + 按风险套阈值 + 写
`specs/<feature>/docs/gate-result.md` + stdout 输出判定 JSON。

**AI 角色：仅读判定 JSON，输出阻断/通过指令**——不能改判、不能补写
gate-result.md、不能跳过步骤（v0.3 手动编排可被 AI 伪造覆盖率，试点失败后
v0.4 起全脚本化）。脚本内部实现细节不在此展开，需要理解时读 `run_gate.py`
docstring 与 `tests/extensions/test_run_gate.py`。

## 触发方式

- 手动：用户在 AI Agent 中直接调用本命令。
- 自动：`after_implement` 钩子触发（`optional: false`），以
  `EXECUTE_COMMAND: speckit.testing.gate` 调用，等待结果后再继续
  `speckit.implement` 收尾。

## 前置输入（REQUIRED）

- `specs/<feature>/docs/impact-report.md`：**前置检查，缺失即 FAIL**（先运行
  `speckit.testing.impact`）；取其 `risk_level` 套阈值
- 业务代码（`.java`，含 @Spec 注解）、测试代码（单测 + 契约测试）、`spec.md`
- `testing-config.yml`：缺失时按与模板一致的内置默认阈值判定，并在
  gate-result.md 标注"配置缺失，按默认阈值判定"

## 技术栈（REQUIRED，scan_test_stack 硬校验）

JUnit4/5 + Mockito + Surefire（`mvn test`）+ JaCoCo；**禁用** PowerMock 与
`@SpringBootTest` 起容器（检出即 FAIL）。报告缺失（surefire-reports /
jacoco.xml）即 FAIL（不降级）——修复建议由脚本 JSON 输出，AI 直接转达即可。

## T1/T2 双门禁框架（认知框架，不改判）

| 目标 | 含义 | 判定 |
|---|---|---|
| **T2 运行正确性**（必要条件） | 代码没有运行错误 | 脚本 HARD：mvn clean test 全绿 + diff/覆盖率阈值 |
| **T1 业务一致性**（目的） | 测试能测出"代码是否按业务实现" | 脚本（结构性）+ AI（语义性，SOFT）：@Spec/@DisplayName 对齐 + 对抗用例 + 交叉验证 + 漂移归因 |

**不变量：T2 达标 ≠ T1 达标**（8/18 反例：52 绿 + 覆盖率达标但核心链路零
直接测试）。gate FAIL 时先归因是 T2 缺口（补实现/分支）还是 T1 缺口（补
场景/直接测试/回 spec），归因决定处置路径（见步骤 3 漂移处置框架）。

## 处理逻辑

> AI 不执行 mvn test、不逐个调用扫描脚本、不比对阈值、不写产物；只负责
> 调用 run_gate（frontmatter `scripts:` 段声明）→ 读 stdout 判定 JSON →
> 输出指令。

### 步骤 1：调用 run_gate 脚本

**前置检查（MUST，beta 简化）**：

- **多模块项目 MUST 先 `find . -name pom.xml`**（或已知工程结构）把
  `--project` 指向**含 pom.xml 的模块目录**（如 `backend/`）；**run_gate 不做模块自动探测**（POM 定位由 AI 负责），`--project` 传错（目录无 pom.xml，
  定位错误）即降级（见"降级模式"）。
- **diff coverage**：`--diff-threshold <pct>`（**默认 80**，config
  `gate.diff_coverage_threshold` 可写），阈值只对 **git diff 变更行**强制；
  `--diff-base <branch>` 用于 MR 场景（**merge-base** 对比），默认**工作区 vs
  HEAD**。**全量 mvn clean test 永远跑**（回归兜底），diff coverage 只做
  阈值判定不限制执行；无 git 时**回退全量**聚合阈值判定；**无 Java 变更**时
  该维度**跳过**（不 FAIL）。
- **受影响 e2e 用例（可选）**：impact 命中规则 × 用例 `covered_rules` **求交**
  → `npx playwright test --grep <用例 ID>` 只跑受影响用例（缺 covered_rules
  降级手工），清单随 SOFT 段追加。

```bash
run_gate --source <java_dir> --test-source <test_dir> --spec <spec.md> \
  --project <模块目录> --feature-dir <specs/<feature>> --config <testing-config.yml> \
  [--check-only] [--diff-threshold <pct>] [--diff-base <branch>] --json
```

脚本内部步骤（供理解脚本行为，AI **不要**代跑）：

| 步骤 | 动作 | 失败处理 |
|---|---|---|
| 0 | `specs/<feature>/docs/impact-report.md` 存在 | 缺失 -> FAIL（先跑 impact） |
| 1 | `mvn clean test`（`--project` 目录，强制 clean 防 target 残留污染） | 失败 -> FAIL；无 java/mvn 或目录无 pom.xml -> 降级 |
| 2 | `scan_test_stack`（禁 PowerMock / @SpringBootTest） | 检出 -> FAIL |
| 3 | `parse_test_results`（聚合 coverage + 行级 source_lines） | 报告缺失 -> FAIL（不降级） |
| 4 | `scan_spec_annotations` | `unimplemented_rules` / `orphan_annotations` 非空 -> FAIL |
| 5 | @DisplayName 双向对齐（DisplayName<->@Spec）+ **5.5 关键路径对抗校验** | 不对齐（require_displayname_match）或 `critical_path_required=true` 且 high 风险规则 0 个 `Rn-对抗-...` 用例 -> FAIL |
| 6 | 按 `risk_level` 套阈值：high/medium/low 行覆盖 **90/80/70**% 等档（config `risk_overrides` 可覆盖） | 档内指标不达标 -> FAIL |
| 7 | diff coverage 判定（变更行覆盖率；无 git 回退全量聚合阈值） | 不达标 -> FAIL |
| 8 | 写 `specs/<feature>/docs/gate-result.md` + stdout 判定 JSON；只读检查 SOFT 标题缺失 -> WARN + `soft_missing: true`（不 FAIL） | AI 仅读，不能改判 |

### 步骤 2：读判定 JSON 并输出指令

- **FAIL** -> 输出阻断指令（引用 gate-result.md 中的失败原因与修复建议）
- **PASS** -> 输出通过指令 + 提示运行报告命令（令牌）
- **`soft_missing: true`** -> 提示 AI 补交叉验证段后重跑——**仅补段，不重跑
  mvn**（补段后 WARN 消失，不改判 PASS/FAIL）

**硬约束（MUST）**：

- **不能改判**：即使认为脚本判定有误，也必须按脚本判定输出阻断/通过指令
- **不能补写** gate-result.md：产物只能由 run_gate 脚本写入
- **不能跳过步骤**：必须真实调用 run_gate 获取数据，不得自行声称通过
- **不得修改 `scripts/` 下任何脚本**（scan_test_stack / scan_spec_annotations
  / parse_test_results / validate_spec_format / run_gate）：改脚本让门禁通过 =
  绕过门禁，属严重违规；脚本有真实 bug 须回 spec-kit 修复并重装扩展，绝不在
  用户项目内就地打补丁（v0.4 试点出现过给 scan_test_stack 加
  @SpringBootTest 豁免的失败反例）

### 步骤 3：AI 语义交叉验证（SOFT，不改判；`gate.ai_cross_validation=true` 时）

读判定 JSON + gate-result.md + 测试/业务源码 + spec.md，五维检查，每维输出
`[PASS/WARN/CRITICAL]` + 说明（CRITICAL = 建议人工复核，不自动阻断）：

| 维度 | AI 补判 |
|---|---|
| 规则-测试语义对齐 | 测试方法体是否真正验证规则业务语义 |
| 断言质量 | 断言有业务语义（非 assertTrue(true)） |
| 覆盖率真实性 | 覆盖是否来自有意义测试 |
| @Spec 放置 | @Spec 是否标在真正实现该规则的方法上 |
| 直接测试覆盖（v0.6） | 每条规则至少一个**直接单测**；仅被间接覆盖 -> **WARN** 建议补（8/18 反例） |

**硬约束（MUST）**：不能改判（HARD FAIL 仍阻断，HARD PASS 不因 AI 发现
问题改 FAIL）；不能删除/修改脚本写入的 HARD 段；**仅追加**
`## AI 交叉验证（SOFT，不影响判定）` 段到 gate-result.md 末尾；降级模式与
check-only 跳过交叉验证。

输出示例（追加到 gate-result.md 末尾）：

```markdown
## AI 交叉验证（SOFT，不影响判定）
- 规则-测试语义对齐: FR-001 PASS / FR-002 WARN（仅测正常余额，未测不足余额分支）
- 直接测试覆盖: FR-005 WARN - 仅被 OrchestratorImplTest 间接覆盖，建议补直接单测
- 交叉验证结论: 2 项 WARN / 0 项 CRITICAL
```

#### 漂移处置框架（gate FAIL 后的归因与处置；SOFT 段给建议归因，**不自动改判**）

**铁律（MUST）**：永远不允许直接**改 test 适配 code**——发现测试与代码
不一致先归因，不得为了让测试变绿而改断言/用例去迁就代码。

**归因三问**：

1. **差异在哪个文件**/行/字段（精确到文件行号，禁"测试和代码对不上"式模糊）
2. **谁主张谁复核**（提出者给证据：源码/测试/spec.md 原文；复核者独立确认）
3. **改 spec/code/test** 哪个、为什么（**由 spec 派生逻辑驱动**，补 spec 规定的
   场景，而非适配 code）

**决策矩阵**（AI 给建议归因，人工决策）：

| 漂移类型 | 默认处置 | 复核 |
|---|---|---|
| code 不满足 spec（缺实现） | 改 code | 跑 test 验证 |
| test 漏场景（T1 缺口） | 补测试（由 spec 派生逻辑驱动，非适配 code） | 重跑 gate |
| spec 有歧义/错误 | 回 spec 澄清（AI 不得擅自改 spec，交用户/PM） | 重跑 codegen |
| code 多于 spec | 删 code 或补 spec 二选一，SOFT 段标注 | 人工决策 |

## 输出指令模板

**FAIL（必须阻断并终止 implement）**：

```text
## ⛔ GATE FAILED - 阻断提交

门禁未通过，禁止执行 git commit / git push。请按失败原因与修复建议修正后重跑：

EXECUTE_COMMAND: speckit.testing.gate

修正完成并通过门禁前，不得继续后续流程。
```

**PASS**：

```text
## ✅ GATE PASSED

门禁通过，可继续提交流程。建议运行测试报告命令生成 Spec 追溯矩阵：

EXECUTE_COMMAND: __SPECKIT_COMMAND_TESTING_REPORT__
```

（令牌由 spec-kit 按 integration 的 invoke_separator 渲染，勿硬编码调用路径）

## 降级模式（无 java/mvn，或 --project 目录无 pom.xml）

降级判定 = **无 java/mvn** 可执行 **或** `--project` 指向目录**无 pom.xml**
（AI 定位错误）。脚本输出 `degraded_reason`（含修复提示），gate-result.md
"执行环境"段标注降级原因；**仅做 @Spec 静态扫描**（跳过 mvn test 与
@DisplayName 解析），按 `spec_rule_coverage_min: 100` 判定。AI 必须明确告知：

```text
## ⚠️ 降级模式（无 java/mvn 或 --project 无 pom.xml）

degraded_reason: ... 仅做 @Spec 静态扫描（unimplemented_rules /
orphan_annotations 与规则编号匹配），覆盖率与通过率检查跳过。
请具备 Java 环境或把 --project 指向含 pom.xml 的模块目录后重跑。
```

## 对抗门禁降级模式（v0.5，config `adversarial` 段）

| `adversarial.enabled` | `critical_path_required` | 行为 |
|---|---|---|
| true（默认） | true（默认） | implement 4.5 做 + gate 硬判（high 风险规则 0 对抗用例 -> FAIL） |
| true | false | implement 4.5 做 + gate 不硬判（advisory，仅统计不阻断） |
| false | false | implement 4.5 不做 + gate 不校验（off，最宽降级） |

（降级模式自动跳过对抗校验）

## Done When

- [ ] 已调用 run_gate 脚本并读取 stdout 判定 JSON（PASS 或 FAIL）
- [ ] FAIL 已输出阻断指令（引用失败原因与修复建议）；PASS 已输出通过指令
      + report 命令令牌（`__SPECKIT_COMMAND_TESTING_REPORT__`）
- [ ] 未改判、未补写 gate-result.md、未跳过任何步骤、未修改 scripts/ 下脚本
- [ ] SOFT 交叉验证段仅追加、格式正确（含 soft_missing 补段则已重跑）