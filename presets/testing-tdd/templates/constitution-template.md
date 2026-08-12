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

### II. 中文文档要求 (NON-NEGOTIABLE)
<!-- PRE-SEEDED BY testing-tdd PRESET - DO NOT REMOVE. -->

项目所有 spec 文档（spec.md、plan.md、data-model.md、contracts/、tasks.md）
MUST 使用中文撰写。代码注释、API 文档、README 可中英混用，但业务语义描述
（规则、验收标准、数据模型语义）MUST 用中文。

rationale: 团队以中文为工作语言，业务语义用中文确保理解的准确性与一致性，
避免翻译歧义导致的实现偏差。

### [PRINCIPLE_3_NAME]
<!-- 按需添加更多原则。不需要的原则可删除此占位符。 -->
[PRINCIPLE_3_DESCRIPTION]

### [PRINCIPLE_4_NAME]
[PRINCIPLE_4_DESCRIPTION]

## [SECTION_2_NAME]

[SECTION_2_CONTENT]

## [SECTION_3_NAME]

[SECTION_3_CONTENT]

## Governance

[GOVERNANCE_RULES]

**Version**: [CONSTITUTION_VERSION] | **Ratified**: [RATIFICATION_DATE] | **Last Amended**: [LAST_AMENDED_DATE]
