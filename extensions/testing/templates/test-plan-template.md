# 测试计划: {{capability}}

> 本模板由 speckit.testing 扩展提供（templates/test-plan-template.md）。
> 由 `speckit.testing.plan` 命令生成，产出物路径 `specs/{{feature}}/test-plan.md`。
> 占位符统一使用 {{var}} 双花括号格式，由 AI 在 plan 阶段填充。

**能力**: {{capability}}
**模块**: {{module}}
**风险等级**: {{risk_level}}
**生成日期**: {{date}}
**引用影响分析**: `specs/{{feature}}/impact-report.json`

---

## 1. 场景与风险

- **场景**: {{scenario_description}}
- **变更类型**: {{change_type}}（new_capability / modify_rule / remove_rule）
- **受影响规则**: {{affected_rules}}（示例：R1, R2, R3, R4, R5, R6, R7）
- **风险定级依据**: {{risk_rationale}}
  - 涉及资金 / 权限 / 数据完整性 -> high
  - 业务流转 -> medium
  - 校验类 -> low

---

## 2. 验收阈值（按风险分级）

> 阈值来自 `contracts/testing-config.md`，按 `ImpactReport.risk_level` 套用 `risk_overrides`。

| 风险 | 行覆盖率 | 分支覆盖率 | 方法覆盖率 | 指令覆盖率 | 复杂度覆盖率 | 单测通过率 | 契约通过率 | Spec 规则覆盖率 |
|------|----------|------------|------------|------------|--------------|------------|------------|------------------|
| high | >=90% | >=70% | >=90% | >=90% | >=80% | 100% | 100% | 100% |
| medium | >=80% | >=70% | >=80% | >=85% | >=70% | 100% | >=95% | 100% |
| low | >=70% | >=70% | >=70% | >=80% | >=60% | 100% | >=95% | 100% |

**本次套用阈值**（risk_level = {{risk_level}}）：

| 维度 | 阈值 |
|------|------|
| 单测行覆盖率 | {{line_coverage_min}}% |
| 单测分支覆盖率 | {{branch_coverage_min}}% |
| 单测通过率 | {{unit_pass_rate_min}}% |
| 契约测试通过率 | {{contract_pass_rate_min}}% |
| Spec 规则覆盖率 | {{spec_rule_coverage_min}}% |
| @DisplayName 对齐 | {{require_displayname_match}} |

---

## 3. 契约测试用例清单（CT-xx）

> 每个 Contract 至少 1 条正向 + 每错误码 1 条反向；每条标注规则编号。

| 用例 ID | 场景 | 接口 | HTTP 状态 | 响应码 | 覆盖规则 |
|---------|------|------|-----------|--------|----------|
| {{contract_case}} | {{contract_scenario}} | {{contract_interface}} | {{http_status}} | {{response_code}} | {{rule_id}} |
| CT-01 | 正常转账 | POST /api/v1/accounts/transfer | 200 | 0000 | R6 |
| CT-02 | 金额为0 | POST /api/v1/accounts/transfer | 400 | INVALID_AMOUNT | R1 |
| CT-03 | 金额为负 | POST /api/v1/accounts/transfer | 400 | INVALID_AMOUNT | R1 |
| CT-04 | 转出账号不存在 | POST /api/v1/accounts/transfer | 404 | ACCOUNT_NOT_FOUND | R2 |
| CT-05 | 转出账号冻结 | POST /api/v1/accounts/transfer | 403 | ACCOUNT_FROZEN | R3 |
| CT-06 | 余额不足 | POST /api/v1/accounts/transfer | 422 | INSUFFICIENT_BALANCE | R4 |
| CT-07 | 转入账号不存在 | POST /api/v1/accounts/transfer | 404 | ACCOUNT_NOT_FOUND | R5 |
| CT-08 | 自转账 | POST /api/v1/accounts/transfer | 400 | SELF_TRANSFER_NOT_ALLOWED | R7 |

**契约测试总数**: {{contract_test_count}}

---

## 4. 单测用例清单（UT-xx）

> 每条 SpecRule 至少 1 条单测；@DisplayName 格式 `R<n>-<描述>`。

| 用例 ID | 规则 | @DisplayName | 场景 | 被测方法 |
|---------|------|--------------|------|----------|
| {{unit_case}} | {{rule_id}} | {{rule_id}}-{{description}} | {{unit_scenario}} | {{method_name}} |
| UT-01 | R1 | R1-转账金额为0应抛出INVALID_AMOUNT | 异常 | AccountService.transfer |
| UT-02 | R2 | R2-转出账户不存在应抛出ACCOUNT_NOT_FOUND | 异常 | AccountService.transfer |
| UT-03 | R3 | R3-转出账户冻结应抛出ACCOUNT_FROZEN | 异常 | AccountService.transfer |
| UT-04 | R4 | R4-余额不足应抛出INSUFFICIENT_BALANCE | 异常 | AccountService.transfer |
| UT-05 | R5 | R5-转入账户不存在应抛出ACCOUNT_NOT_FOUND | 异常 | AccountService.transfer |
| UT-06 | R6 | R6-正常转账应原子扣减与入账 | 正常 | AccountService.transfer |
| UT-07 | R7 | R7-自转账应抛出SELF_TRANSFER_NOT_ALLOWED | 异常 | AccountService.transfer |

**单测总数**: {{unit_test_count}}

---

## 5. 排期建议

> 单测先行（骨架先行已保证单测可编译），契约测试次之（验证接口契约），业务代码最后（带 @Spec 注解）。

| 阶段 | 内容 | 用例数 | 建议工期 |
|------|------|--------|----------|
| 1. 单测编写 | UT-xx 骨架 + Mock 依赖 | {{unit_test_count}} | {{unit_schedule}} |
| 2. 契约测试编写 | CT-xx 骨架 + contract mock 桩 | {{contract_test_count}} | {{contract_schedule}} |
| 3. 业务代码实现 | Service + @Spec 注解 | - | {{impl_schedule}} |
| 4. 门禁执行 | speckit.testing.gate | - | {{gate_schedule}} |
| 5. 报告生成 | speckit.testing.report | - | {{report_schedule}} |

---

## 6. 契约不变量自检

- [ ] 每个 Contract 至少 1 条正向 + 每错误码 1 条反向契约测试
- [ ] 每条 SpecRule 至少 1 条单测
- [ ] 验收阈值与 `ImpactReport.risk_level` 匹配（高->90%/100%，中->80%/95%，低->70%/95%）
- [ ] 单测 @DisplayName 格式为 `R<n>-<描述>`
