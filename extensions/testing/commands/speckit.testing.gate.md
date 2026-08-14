---
description: "Speckit Testing 门禁：AI 调用 run_gate 脚本（mvn clean test + 技术栈校验 + @Spec 扫描 + DisplayName 一致性 + 按风险阈值判定），AI 仅读判定 JSON 输出阻断/通过指令"
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

- 用户项目业务代码（`.java` 源文件，含 `@Spec` 注解）
- 测试代码（单测 + 契约测试，单测带 `@DisplayName` 规则标注）
- `spec.md`（`business_rules` 规则编号清单）
- `ImpactReport` 产物（`specs/<feature>/docs/impact-report.md`，取
  `risk_level` 套阈值；after_implement 时由 `speckit.testing.impact` 在
  本命令前产出）
- `testing-config.yml`（阈值与风险覆盖配置）

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
> 参考下方"JaCoCo/Surefire 配置参考"）。唯一降级场景为项目非 Java（无
> `java`/`mvn` 可执行），见下方"降级：无 Java 环境"。

## 处理逻辑

> **AI 角色：仅读结果，不能改判**。以下全部步骤由 `run_gate` 脚本执行，
> AI 不执行 mvn test、不逐个调用扫描脚本、不比对阈值、不写 gate-result.md。
> AI 只负责：调用 run_gate（frontmatter `scripts:` 段声明的脚本）→ 读取
> stdout 判定 JSON → 按判定输出阻断/通过指令。

### 步骤 1：调用 run_gate 脚本

运行 frontmatter `scripts:` 段声明的 `run_gate` 脚本（按项目 `--script
sh|ps|py` 选择其一），脚本内部按以下 9 步执行（供 AI 理解脚本行为，AI
**不要**自行重复执行）：

| 步骤 | 动作 | 失败处理 |
|---|---|---|
| 0 | 检查 `specs/<feature>/docs/impact-report.md` 存在 | 不存在 -> FAIL（impact 未执行，请先运行 speckit.testing.impact） |
| 1 | `mvn clean test`（强制 clean，杜绝 target 残留污染） | 失败 -> FAIL；无 java/mvn -> 降级模式 |
| 2 | 调 `scan_test_stack` | `forbidden_findings` 非空 -> FAIL |
| 3 | 调 `parse_test_results` | jacoco.xml / surefire 缺失 -> FAIL（不降级） |
| 4 | 调 `scan_spec_annotations` | `unimplemented_rules` / `orphan_annotations` 非空 -> FAIL |
| 5 | 内联解析测试源码 `@DisplayName`，**双向**对齐（DisplayName->@Spec + @Spec->DisplayName） | 不对齐数 > 0 或有 `@Spec` 无测试的规则，且 `require_displayname_match` -> FAIL |
| 6 | 读 `impact-report.md` 的 `risk_level` + 读 `testing-config.yml` | 套风险档阈值 |
| 7 | 逐项比对覆盖率 / 通过率 / Spec 覆盖率与阈值 | 任一不达标 -> FAIL |
| 8 | **脚本直接写 `specs/<feature>/docs/gate-result.md`** + stdout 输出判定 JSON | AI 仅读，不能改判 |

### 步骤 2：读取判定 JSON 并输出指令

读取 `run_gate` stdout 输出的判定 JSON（含 PASS / FAIL、失败原因、修复
建议）：

- 若 **FAIL** -> 输出阻断指令（引用 gate-result.md 中的失败原因与修复建议）
- 若 **PASS** -> 输出通过指令 + 提示运行报告命令（令牌）

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

**判定 PASS/FAIL**：脚本逐项比对步骤 0-7 的实际值，任一检查未过 -> FAIL，
全部通过 -> PASS。

判定 FAIL 的条件（任一即 FAIL）：

- `unimplemented_rules` 非空（spec 规则未实现）
- `orphan_annotations` 非空（孤儿注解）
- 单测通过率 < 阈值
- 行覆盖率 / 分支覆盖率 < 阈值
- 契约测试通过率 < 阈值
- `require_displayname_match` 为 true 且 `displayname_mismatch_count` > 0
- `require_displayname_match` 为 true 且 `untested_spec_rules` 非空（有 `@Spec` 无对应测试）
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

### 单测明细
- 总数: N | 通过: N | 失败: N
- 行覆盖率: NN% (阈值 >=NN%) | 分支: NN% | 方法: NN% | 指令: NN% | 复杂度: NN%
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

## 降级：无 Java 环境

当 `run_gate` 脚本检测到当前环境无 `java` / `mvn` 可执行（或用户项目非
Java 项目）时，**脚本降级为仅做 `@Spec` 静态扫描**，跳过 `mvn clean test`
与 @DisplayName 解析（因无单测可读），仅执行 @Spec 注解扫描与 Spec 覆盖率
阈值判定（`spec_rule_coverage_min: 100`）。降级时脚本在 gate-result.md
中明确标注"降级模式（无 Java 环境）"。

降级时 AI 必须在输出中明确告知：

```text
## ⚠️ 降级模式（无 Java 环境）

未检测到 java/mvn，跳过单测与契约测试执行，仅做 @Spec 静态扫描。
覆盖率与通过率检查被跳过。仅校验：
- spec 规则覆盖率（unimplemented_rules / orphan_annotations）
- @Spec 注解格式与规则编号匹配

请在具备 Java 环境时重新运行门禁以获取完整校验。
```

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
