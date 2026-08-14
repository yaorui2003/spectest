# [PROJECT_NAME] 宪法

## 核心原则

### I. Spec Traceability (NON-NEGOTIABLE)
<!-- PRE-SEEDED BY testing-tdd PRESET - DO NOT REMOVE. 此原则由 testing-tdd 预置，配合 testing 扩展的 @Spec 注解与门禁使用。-->

所有业务代码 MUST 用 @Spec 注解标注其实现的 Spec 规则，格式：

    @Spec(capability="<capability>", rule="<RULE_ID>")

规则：

- 每条 spec.md 中 business_rules 的规则 MUST 至少有一个 @Spec 注解对应
- 实现该规则的每个 public 方法 MUST 携带至少一个 @Spec 注解
- @Spec 的 rule 编号 MUST 严格匹配 spec.md 中的规则编号（如 R1、R2）
- 单测 MUST 在 @DisplayName 中标注对应规则编号（如 @DisplayName("R1-转账金额为0应拒绝")）
- contracts/ 中的接口契约 MUST 列出该接口实现的规则编号清单

rationale: 门禁通过扫描 @Spec 注解自动校验"Spec 能力点 -> 代码实现"覆盖完整性，
防止规则遗漏实现；单测侧通过 @DisplayName 标注实现双向对齐，支撑 Spec-Code-Test
三角一致性校验。本原则是 testing 扩展门禁逻辑的运行时依据。

### II. 中文文档与代码注释 (NON-NEGOTIABLE)
<!-- PRE-SEEDED BY testing-tdd PRESET - DO NOT REMOVE. -->

项目所有 spec 文档（spec.md、plan.md、data-model.md、contracts/、tasks.md）
MUST 使用中文撰写。代码注释、API 文档、README 可中英混用，但业务语义描述
（规则、验收标准、数据模型语义）MUST 用中文。

**代码重要部分 MUST 加中文注释**：
- 实现高风险规则（资金/权限/原子性/数据完整性，由 @Spec 注解或 impact
  risk_level=high 识别）的 public 方法，MUST 在方法头加中文注释说明业务
  语义与约束
- 核心业务逻辑分支（金额校验、状态流转、事务边界）MUST 在关键行加中文
  行注释说明意图
- 异常抛出点 MUST 注释说明业务原因（而非仅技术原因）

rationale: 团队以中文为工作语言，业务语义用中文确保理解的准确性与一致性，
避免翻译歧义导致的实现偏差。代码注释聚焦"为什么"（业务意图）而非"做什么"
（代码自描述），关键路径注释支撑后续审计与对抗测试定位。

### III. 测试技术栈 (NON-NEGOTIABLE)
<!-- PRE-SEEDED BY testing-tdd PRESET - DO NOT REMOVE. 此原则由 testing-tdd 预置，配合 testing 扩展门禁 scan_test_stack 强制。-->

Java 项目的测试技术栈 MUST 遵守以下约定（testing 扩展门禁 run_gate 的 scan_test_stack
硬校验依据）：

- **必需**：JUnit 4/5（`org.junit.jupiter`）+ Mockito（`@Mock`/`@InjectMocks`/
  `MockitoExtension`）+ Surefire（`mvn test` 生成 surefire-reports）+ JaCoCo
  （line/branch/method/instruction/complexity 覆盖率，`target/site/jacoco/jacoco.xml`）
- **禁用**：PowerMock（覆盖率失真，检出即 FAIL）；`@SpringBootTest` 起容器
  （单测用 Mockito、契约测试用 WireMock，均不起容器；并发/集成类测试也用纯
  JUnit + Mockito + Thread/ExecutorService，不起容器）

rationale: 技术栈是门禁覆盖率/通过率指标真实性的前提，禁用项会造成覆盖率失真
或拖慢执行。本原则是公司测试规范，由 testing 扩展门禁强制（scan_test_stack 检出
禁用项即 FAIL）。缺 JaCoCo/surefire 报告亦判定 FAIL（不降级）。

### [PRINCIPLE_4_NAME]
<!-- 按需添加更多原则。不需要的原则可删除此占位符。 -->
[PRINCIPLE_4_DESCRIPTION]

### [PRINCIPLE_5_NAME]
[PRINCIPLE_5_DESCRIPTION]

## [SECTION_2_NAME]

[SECTION_2_CONTENT]

## [SECTION_3_NAME]

[SECTION_3_CONTENT]

## Governance

[GOVERNANCE_RULES]

**Version**: [CONSTITUTION_VERSION] | **Ratified**: [RATIFICATION_DATE] | **Last Amended**: [LAST_AMENDED_DATE]
