# Spec 追溯矩阵: {{capability}}

> 本模板由 speckit.testing 扩展提供（templates/spec-trace-matrix.md）。
> 由 `speckit.testing.report` 命令生成，产出物路径 `specs/{{feature}}/docs/test-report.md`。
> 每行一条 SpecRule（FR-001..FR-xxx，顶层锚），引用而非重生成 ImpactReport。

**能力**: {{capability}}
**生成日期**: {{date}}
**引用影响分析**: `specs/{{feature}}/docs/impact-report.md`
**引用门禁结果**: `specs/{{feature}}/docs/gate-result.md`

---

## 追溯矩阵

| Spec 规则（FR 顶层锚） | 描述 | 代码位置（@Spec） | 单测规则标注 |
|---|---|---|---|
| {{rule_id}} | {{description}} | {{code_location}} | {{unit_test_annotation}} |
| FR-001 | 金额>0 | {{service_class}}.{{method_name}}:{{line}} | FR-001-R1-转账金额为0应抛出INVALID_AMOUNT |
| FR-002 | 转出账户存在 | {{service_class}}.{{method_name}}:{{line}} | FR-002-R1-转出账户不存在应抛出ACCOUNT_NOT_FOUND |

> 单测规则标注 = JUnit5 `@DisplayName("FR-xxx-Rm-...")` 或 JUnit4 测试方法级
> `@Spec(rule="FR-xxx-Rm")`。

---

## 覆盖统计

| 维度 | 数值 |
|------|------|
| Spec 规则总数 | {{spec_rules_total}} |
| @Spec 注解覆盖规则数 | {{annotated_count}} |
| 单测规则标注对齐数 | {{displayname_aligned}} |
| 未实现规则 | {{unimplemented_rules}} |
| 孤儿注解 | {{orphan_annotations}} |
| 规则覆盖率 | {{coverage_percent}}% |

---

## 测试结果摘要

| 维度 | 总数 | 通过 | 失败 | 通过率 |
|------|------|------|------|--------|
| 单测 | {{unit_total}} | {{unit_passed}} | {{unit_failed}} | {{unit_pass_rate}}% |

| 覆盖率维度 | 实际值 | 阈值 | 结果 |
|------------|--------|------|------|
| 单测行覆盖率 | {{line_coverage}}% | {{line_coverage_min}}% | {{line_coverage_verdict}} |
| 单测分支覆盖率 | {{branch_coverage}}% | {{branch_coverage_min}}% | {{branch_coverage_verdict}} |
| Spec 规则覆盖率 | {{spec_coverage_percent}}% | 100% | {{spec_coverage_verdict}} |

**门禁判定**: {{gate_verdict}}

---

## 契约不变量自检

- [ ] 追溯矩阵覆盖 spec.md 全部 FR 段规则（顶层锚 FR-xxx）
- [ ] 每行代码位置（@Spec）与扫描脚本输出一致
- [ ] 每行单测规则标注（@DisplayName FR-xxx-Rm 或测试方法级 @Spec rule=FR-xxx-Rm）与 @Spec
      顶层锚（FR-xxx）按 FR 前缀双向对齐
- [ ] 引用而非重生成 ImpactReport