# 测试计划: {{capability}}

> 本模板由 speckit.testing 扩展提供（templates/test-plan-template.md）。
> 由 `speckit.testing.plan` 命令生成，产出物路径 `specs/{{feature}}/docs/test-plan.md`。
> 占位符统一使用 {{var}} 双花括号格式，由 AI 在 plan 阶段填充。

**能力**: {{capability}}
**模块**: {{module}}
**风险等级**: {{risk_level}}
**生成日期**: {{date}}
**引用影响分析**: `specs/{{feature}}/docs/impact-report.md`

---

## 1. 场景与风险

- **场景**: {{scenario_description}}
- **变更类型**: {{change_type}}（new_capability / modify_rule / remove_rule）
- **受影响规则**: {{affected_rules}}（示例：FR-001, FR-002, FR-003）
- **风险定级依据**: {{risk_rationale}}
  - 涉及资金 / 权限 / 数据完整性 -> high
  - 业务流转 -> medium
  - 校验类 -> low

---

## 2. 验收阈值（按风险分级）

> 阈值来自 `testing-config.yml`，按 `ImpactReport.risk_level` 套用 `risk_overrides`。

| 风险 | 行覆盖率 | 分支覆盖率 | 方法覆盖率 | 指令覆盖率 | 复杂度覆盖率 | 单测通过率 | Spec 规则覆盖率 |
|------|----------|------------|------------|------------|--------------|------------|------------------|
| high | >=90% | >=70% | >=90% | >=90% | >=80% | 100% | 100% |
| medium | >=80% | >=70% | >=80% | >=85% | >=70% | 100% | 100% |
| low | >=70% | >=70% | >=70% | >=80% | >=60% | 100% | 100% |

**本次套用阈值**（risk_level = {{risk_level}}）：

| 维度 | 阈值 |
|------|------|
| 单测行覆盖率 | {{line_coverage_min}}% |
| 单测分支覆盖率 | {{branch_coverage_min}}% |
| 单测通过率 | {{unit_pass_rate_min}}% |
| Spec 规则覆盖率 | {{spec_rule_coverage_min}}% |
| 规则标注对齐 | {{require_displayname_match}} |

---

## 3. 单测用例清单（UT-xx）

> 每条 SpecRule 至少 3 条单测（B/C/E 必含，D 视设计文档可用性）。规则标注
> 双通道：JUnit5 `@DisplayName("FR-xxx-Rm-<描述>")` / JUnit4 测试方法级
> `@Spec(rule="FR-xxx", description="<场景>")`（@Spec 锚永远只写顶层 FR-xxx）。

| 用例 ID | 规则 | 规则标注 | 场景 | 被测方法 |
|---------|------|----------|------|----------|
| {{unit_case}} | {{rule_id}} | {{rule_id}}-{{description}} | {{unit_scenario}} | {{method_name}} |
| UT-01 | FR-001 | FR-001-R1-转账金额为0应抛出INVALID_AMOUNT | 异常 | AccountService.transfer |
| UT-02 | FR-002 | FR-002-R1-转出账户不存在应抛出ACCOUNT_NOT_FOUND | 异常 | AccountService.transfer |
| UT-03 | FR-001 | FR-001-R2-正常转账应原子扣减与入账 | 正常 | AccountService.transfer |
| UT-04 | FR-001 | FR-001-R3-转账金额为下限0.01应成功 | 边界 | AccountService.transfer |

**单测总数**: {{unit_test_count}}

---

## 4. 排期建议

> 单测先行（骨架先行已保证单测可编译）；高风险规则优先。

| 阶段 | 内容 | 用例数 | 建议工期 |
|------|------|--------|----------|
| 1. 单测编写 | UT-xx 骨架 + Mock 依赖 | {{unit_test_count}} | {{unit_schedule}} |
| 2. 业务代码实现 | Service + @Spec 注解 | - | {{impl_schedule}} |
| 3. 门禁执行 | speckit.testing.gate | - | {{gate_schedule}} |
| 4. 报告生成 | speckit.testing.report | - | {{report_schedule}} |

---

## 5. 契约不变量自检

- [ ] 每条 SpecRule 至少 3 条单测（B / C / E 必含）
- [ ] 验收阈值与 `ImpactReport.risk_level` 匹配（高->90%/100%，中->80%，
      低->70%）
- [ ] 单测规则标注格式为 `FR-xxx-Rm-<描述>`（JUnit5 @DisplayName）或测试
      方法级 `@Spec(rule="FR-xxx")`（JUnit4），与代码侧 @Spec 顶层锚对齐