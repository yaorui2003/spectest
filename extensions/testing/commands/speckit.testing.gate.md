---
description: "Speckit Testing 门禁：执行单测/契约测试 + @Spec 注解扫描 + DisplayName 一致性校验，按风险阈值判定 PASS/FAIL 并阻断提交"
scripts:
  sh: ../../scripts/bash/scan-spec-annotations.sh
  ps: ../../scripts/powershell/scan-spec-annotations.ps1
  py: ../../scripts/python/scan_spec_annotations.py
---

# Speckit Testing Gate

本命令为 `after_implement` 钩子（`optional: false`，强制自动执行）的门禁。
代码实现完成后立即触发，校验 Spec 规则与代码实现的追溯一致性，并按
`ImpactReport.risk_level` 套用 `testing-config.yml` 阈值判定 PASS/FAIL。
任一检查未通过则 FAIL 并阻断提交。

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
- `ImpactReport` 产物（取 `risk_level` 套阈值；after_implement 时由
  `speckit.testing.impact` 在本命令前产出）
- `testing-config.yml`（阈值与风险覆盖配置）

## 技术栈前置要求（REQUIRED）

本门禁针对 Java 项目，以下技术栈为**必需前置条件**（默认用户已配置）：

| 组件 | 作用 | 必需性 |
|---|---|---|
| JUnit 4/5 | 测试框架 | REQUIRED |
| Mockito | Mock 依赖（`@Mock` / `@InjectMocks`） | REQUIRED |
| Surefire（`mvn test`） | 测试执行 + surefire-reports 生成 | REQUIRED |
| JaCoCo | 覆盖率插桩（line/branch/method/instruction/complexity） | REQUIRED |

**禁用**：

- **PowerMock** -- 覆盖率失真，门禁判定为 FAIL（由技术栈扫描脚本检出）
- **`@SpringBootTest` 起容器** -- 契约测试基于 WireMock contract mock、
  单测基于 Mockito，均不起容器；起容器的测试不属于本门禁范围且拖慢执行

> **不降级原则**：`mvn test` 执行后若 `target/surefire-reports/` 或
> `target/site/jacoco/jacoco.xml` 缺失，判定 **FAIL**（通过率/覆盖率指标
> 不可用 = 未达标），输出修复建议（添加 Surefire/JaCoCo 插件配置，参考
> 下方"JaCoCo/Surefire 配置参考"）。唯一降级场景为项目非 Java（无
> `java`/`mvn` 可执行），见下方"降级：无 Java 环境"。

## 处理逻辑

> **Spec 格式预检（建议）**：可调用
> `scripts/{bash,powershell,python}/validate-spec-format.{sh,ps1,py}`
> 校验 spec.md 的 Business Rules 段格式（规则编号连续性）。此为建议项，
> 不阻断门禁（warning 级别）。

### 步骤 1：执行单测与契约测试（mvn test）

在用户项目根目录执行 `mvn test`，收集：

- **单测明细**：总数 / 通过 / 失败 / 行覆盖率 / 分支覆盖率 / 通过率
  （覆盖率取自 JaCoCo 报告 `target/site/jacoco/jacoco.xml`）
- **契约测试明细**：总数 / 通过 / 失败 / 通过率（契约测试以 `CT-` 前缀命名
  或位于 `src/test/java/.../contracts/` 包下识别）

**报告缺失即 FAIL**：`mvn test` 执行后若 `target/surefire-reports/`
缺失 -> 通过率指标不可用 -> FAIL；若 `target/site/jacoco/jacoco.xml`
缺失 -> 覆盖率指标不可用 -> FAIL。输出修复建议（添加 Surefire/JaCoCo
插件配置，见"JaCoCo/Surefire 配置参考"段）。不降级跳过。

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

### 步骤 1.5：技术栈硬校验（scan_test_stack）

调用 `scripts/{bash,powershell,python}/scan-test-stack.{sh,ps1,py}`（按项目
`--script sh|ps|py` 选择对应语言版本），扫描 `src/test/` 目录下全部 `.java`
测试文件，检出禁用技术：

- `org.powermock.*` 导入 -> type: powermock
- `@SpringBootTest` 注解 -> type: springboottest

若 `forbidden_findings` 非空 -> **直接 FAIL**，输出违规清单（文件、行号、
违规内容），提示移除 PowerMock 依赖或将 `@SpringBootTest` 改为 Mockito +
WireMock 契约测试。

### 步骤 2：调用 @Spec 注解扫描脚本

运行 frontmatter `scripts:` 段声明的扫描脚本（按项目 `--script sh|ps|py`
选择其一），脚本解析用户项目全部 `.java` 源文件，正则提取
`@Spec(capability="...", rule="Rn", ...)` 注解，同时解析 `spec.md` 的
`business_rules` 规则编号，输出如下 JSON：

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

读取该 JSON，重点关注以下两个字段（任一非空即 FAIL）：

- `unimplemented_rules`：`spec.md` 有但代码无 `@Spec` 注解的规则（漏实现）
- `orphan_annotations`：代码有 `@Spec` 但 `spec.md` 无对应规则的注解
  （规则编号写错或 spec 已删该规则）

> 此外，步骤 1 的 `mvn test` 结果（surefire-reports + jacoco.xml）由
> `scripts/{bash,powershell,python}/parse-test-results.{sh,ps1,py}` 脚本
> 解析为结构化 JSON（unit_tests/contract_tests/coverage 三段），供后续
> 阈值判定使用。

### 步骤 3：解析单测 @DisplayName，校验一致性

遍历单测方法，解析 `@DisplayName("Rn-描述")` 中的规则编号 `Rn`，校验：

- 每条单测 `@DisplayName` 必须标注规则编号（格式 `R<n>-<描述>`，
  正则 `^R\d+-`）
- 每条 `@Spec` 注解应有对应 `@DisplayName` 单测（双向对齐）
- 不对齐的项计入 `displayname_mismatch_count`

若 `testing-config.yml` 中
`gate.spec_traceability.require_displayname_match: true`（默认），
则不对齐数 > 0 时 FAIL。

### 步骤 4：按风险等级套用阈值

读取 `ImpactReport.risk_level`（`high` / `medium` / `low`），按
`testing-config.yml` 的 `risk_overrides` 与 `gate` 默认值合并后套用：

| 风险 | 行覆盖率 | 分支覆盖率 | 方法覆盖率 | 指令覆盖率 | 复杂度覆盖率 | 单测通过率 | 契约通过率 | Spec 覆盖率 |
|------|----------|------------|------------|------------|--------------|------------|------------|-------------|
| high | >=90% | >=70% | >=90% | >=90% | >=80% | 100% | 100% | 100% |
| medium | >=80% | >=70% | >=80% | >=85% | >=70% | 100% | >=95% | 100% |
| low | >=70% | >=70% | >=70% | >=80% | >=60% | 100% | >=95% | 100% |

具体套用规则：取 `risk_overrides.<risk>` 下的覆盖值，与 `gate` 默认值
合并（覆盖值优先），按合并后的阈值逐项比对步骤 1-3 的实际值。

### 步骤 5：判定 PASS/FAIL

任一检查未过 -> FAIL，输出失败原因与修复建议；全部通过 -> PASS。

判定 FAIL 的条件（任一即 FAIL）：

- `unimplemented_rules` 非空（spec 规则未实现）
- `orphan_annotations` 非空（孤儿注解）
- 单测通过率 < 阈值
- 行覆盖率 / 分支覆盖率 < 阈值
- 契约测试通过率 < 阈值
- `require_displayname_match` 为 true 且 `displayname_mismatch_count` > 0
- Spec 规则覆盖率 < 100%

## 输出（GateResult）

```markdown
## Gate Result: PASS | FAIL

### 单测明细
- 总数: N | 通过: N | 失败: N
- 行覆盖率: NN% (阈值 >=NN%) | 分支覆盖率: NN% (阈值 >=70%)
- 通过率: NN% (阈值 100%)

### 契约测试明细
- 总数: N | 通过: N | 失败: N
- 通过率: NN% (阈值 >=NN%)

### Spec 规则覆盖矩阵
- 规则总数: N | 已注解数: N | 未实现规则: [R2, R3]
- 孤儿注解: []
- DisplayName 对齐数: N / N

### 失败原因与修复建议（仅 FAIL 时）
- [FAIL] unimplemented_rules: R2 -> 在 XxxService.method 上补 @Spec(rule="R2")
- [FAIL] line_coverage 65% < 90% (high) -> 补 XxxService.transfer 的边界用例
```

## 契约不变量

- FAIL 时 `fail_reasons` 必须非空且含可执行修复建议（指明文件/方法/规则）
- `spec_coverage.unimplemented_rules` > 0 时必须 FAIL
- `spec_coverage.orphan_annotations` > 0 时必须 FAIL
- `after_implement` 触发时，FAIL 必须阻断提交（见下方阻断指令）

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

当检测到当前环境无 `java` / `mvn` 可执行（或用户项目非 Java 项目）时，
**降级为仅做 `@Spec` 静态扫描**，跳过步骤 1（mvn test）与步骤 3
（@DisplayName 解析，因无单测可读），仅执行步骤 2（调用扫描脚本）与
步骤 4 的 Spec 覆盖率阈值判定（`spec_rule_coverage_min: 100`）。

降级时必须在输出中明确告知：

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

- [ ] mvn test 已执行（或降级模式已说明）
- [ ] 扫描脚本已运行，JSON 已读取
- [ ] `unimplemented_rules` / `orphan_annotations` 已校验
- [ ] `@DisplayName` 一致性已校验（非降级模式）
- [ ] 风险阈值已套用并逐项比对
- [ ] GateResult 已输出（PASS 或 FAIL + 阻断指令）
