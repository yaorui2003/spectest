# Spec 追溯矩阵: {{capability}}

> 本模板由 speckit.testing 扩展提供（templates/spec-trace-matrix.md）。
> 由 `speckit.testing.report` 命令生成，产出物路径 `specs/{{feature}}/docs/test-report.md`。
> 每行一条 SpecRule（R1..Rn），引用而非重生成 ImpactReport。

**能力**: {{capability}}
**生成日期**: {{date}}
**引用影响分析**: `specs/{{feature}}/docs/impact-report.md`
**引用门禁结果**: `specs/{{feature}}/docs/gate-result.md`

---

## 追溯矩阵

| Spec 规则 | 描述 | 代码位置（@Spec） | 单测（@DisplayName） | 契约测试 |
|---|---|---|---|---|
| {{rule_id}} | {{description}} | {{code_location}} | {{unit_test_display_name}} | {{contract_test_ids}} |
| R1 | 金额>0 | {{service_class}}.{{method_name}}:{{line}} | UT-01: R1-转账金额为0应抛出INVALID_AMOUNT | CT-02, CT-03 |
| R2 | 转出账户存在 | {{service_class}}.{{method_name}}:{{line}} | UT-02: R2-转出账户不存在应抛出ACCOUNT_NOT_FOUND | CT-04 |
| R3 | 转出未冻结 | {{service_class}}.{{method_name}}:{{line}} | UT-03: R3-转出账户冻结应抛出ACCOUNT_FROZEN | CT-05 |
| R4 | 余额充足 | {{service_class}}.{{method_name}}:{{line}} | UT-04: R4-余额不足应抛出INSUFFICIENT_BALANCE | CT-06 |
| R5 | 转入账户存在 | {{service_class}}.{{method_name}}:{{line}} | UT-05: R5-转入账户不存在应抛出ACCOUNT_NOT_FOUND | CT-07 |
| R6 | 原子操作 | {{service_class}}.{{method_name}}:{{line}} | UT-06: R6-正常转账应原子扣减与入账 | CT-01 |
| R7 | 禁止自转 | {{service_class}}.{{method_name}}:{{line}} | UT-07: R7-自转账应抛出SELF_TRANSFER_NOT_ALLOWED | CT-08 |

---

## 覆盖统计

| 维度 | 数值 |
|------|------|
| Spec 规则总数 | {{spec_rules_total}} |
| @Spec 注解覆盖规则数 | {{annotated_count}} |
| 单测 @DisplayName 对齐数 | {{displayname_aligned}} |
| 契约测试覆盖规则数 | {{contract_covered_count}} |
| 未实现规则 | {{unimplemented_rules}} |
| 孤儿注解 | {{orphan_annotations}} |
| 规则覆盖率 | {{coverage_percent}}% |

---

## 测试结果摘要

| 维度 | 总数 | 通过 | 失败 | 通过率 |
|------|------|------|------|--------|
| 单测 | {{unit_total}} | {{unit_passed}} | {{unit_failed}} | {{unit_pass_rate}}% |
| 契约测试 | {{contract_total}} | {{contract_passed}} | {{contract_failed}} | {{contract_pass_rate}}% |

| 覆盖率维度 | 实际值 | 阈值 | 结果 |
|------------|--------|------|------|
| 单测行覆盖率 | {{line_coverage}}% | {{line_coverage_min}}% | {{line_coverage_verdict}} |
| 单测分支覆盖率 | {{branch_coverage}}% | {{branch_coverage_min}}% | {{branch_coverage_verdict}} |
| Spec 规则覆盖率 | {{spec_coverage_percent}}% | 100% | {{spec_coverage_verdict}} |

**门禁判定**: {{gate_verdict}}

---

## 契约不变量自检

- [ ] 追溯矩阵覆盖 spec.md 全部 business_rules 规则
- [ ] 每行代码位置（@Spec）与扫描脚本输出一致
- [ ] 每行单测 @DisplayName 与 @Spec 规则编号双向对齐
- [ ] 引用而非重生成 ImpactReport
