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
- **受影响规则**: {{affected_rules}}（示例：FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007）
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
| CT-01 | 正常转账 | POST /api/v1/accounts/transfer | 200 | 0000 | FR-001 |
| CT-02 | 金额为0 | POST /api/v1/accounts/transfer | 400 | INVALID_AMOUNT | FR-001 |
| CT-03 | 金额为负 | POST /api/v1/accounts/transfer | 400 | INVALID_AMOUNT | FR-001 |
| CT-04 | 转出账号不存在 | POST /api/v1/accounts/transfer | 404 | ACCOUNT_NOT_FOUND | FR-002 |
| CT-05 | 转出账号冻结 | POST /api/v1/accounts/transfer | 403 | ACCOUNT_FROZEN | FR-003 |
| CT-06 | 余额不足 | POST /api/v1/accounts/transfer | 422 | INSUFFICIENT_BALANCE | FR-004 |
| CT-07 | 转入账号不存在 | POST /api/v1/accounts/transfer | 404 | ACCOUNT_NOT_FOUND | FR-005 |
| CT-08 | 自转账 | POST /api/v1/accounts/transfer | 400 | SELF_TRANSFER_NOT_ALLOWED | FR-007 |

**契约测试总数**: {{contract_test_count}}

---

## 4. 单测用例清单（UT-xx）

> 每条 SpecRule 至少 1 条单测；@DisplayName 格式 `FR-xxx-Rm-<描述>`（顶层锚
> FR-xxx + 子编号 Rm，@Spec 锚永远只写顶层 FR-xxx）。

| 用例 ID | 规则 | @DisplayName | 场景 | 被测方法 |
|---------|------|--------------|------|----------|
| {{unit_case}} | {{rule_id}} | {{rule_id}}-{{description}} | {{unit_scenario}} | {{method_name}} |
| UT-01 | FR-001 | FR-001-R1-转账金额为0应抛出INVALID_AMOUNT | 异常 | AccountService.transfer |
| UT-02 | FR-002 | FR-002-R1-转出账户不存在应抛出ACCOUNT_NOT_FOUND | 异常 | AccountService.transfer |
| UT-03 | FR-003 | FR-003-R1-转出账户冻结应抛出ACCOUNT_FROZEN | 异常 | AccountService.transfer |
| UT-04 | FR-004 | FR-004-R1-余额不足应抛出INSUFFICIENT_BALANCE | 异常 | AccountService.transfer |
| UT-05 | FR-005 | FR-005-R1-转入账户不存在应抛出ACCOUNT_NOT_FOUND | 异常 | AccountService.transfer |
| UT-06 | FR-006 | FR-006-R1-正常转账应原子扣减与入账 | 正常 | AccountService.transfer |
| UT-07 | FR-007 | FR-007-R1-自转账应抛出SELF_TRANSFER_NOT_ALLOWED | 异常 | AccountService.transfer |

**单测总数**: {{unit_test_count}}

---

## 4.5 业务规则细分（Rule Breakdown，可选参考层）

> **仅供参考，plan 可不跑**：本段不承载权威（规则权威源 = spec.md
> `### Functional Requirements` 段顶层锚 FR-xxx），仅帮助测试作者把 FR 拆成
> 可测子场景；**无本段时测试作者按 FR 自编号**（@DisplayName 用
> `FR-xxx-Rm-<场景>`，m 从 1 在该 FR 内连续）。
>
> **细分规则 MUST 约束**（每条细分规则 MUST 同时满足，不满足即删/改）：
> ① **一个可断言行为**——能用 1 句"输入 X 时系统必须 Y"描述且可写断言验证，
> 不可断言语的聚合需求（性能/日志/可用性）不得编号；② **来源 FR 必须存在**——
> 指向 spec.md FR 段真实存在的 FR-xxx 条目；③ **错误码来自 contracts/**——
> 关联错误码 MUST 出现在对应接口契约错误码清单中（plan 未跑时本字段可空）；
> ④ **编号规则** `FR-xxx-R<m>`，m 从 1 在该 FR 内连续（仅测试侧/细分段使用
> 子编号；@Spec 锚永远只写顶层 FR-xxx）；⑤ **粒度对齐宽松**——不要求 1:1，
> 锚在 FR 级。
>
> **反例提示**：禁止把"弱断言可过的描述"细分（如"系统应记录日志"）；禁止把
> 多个行为揉成一条（"校验金额并更新余额"应拆两条）。

| 细分编号 | 来源 FR | 规则描述 | 关联错误码 |
|----------|---------|----------|------------|
| {{breakdown_id}} | {{breakdown_source_fr}} | {{breakdown_description}} | {{breakdown_error_code}} |
| FR-001-R1 | FR-001 | 转账金额必须大于0 | INVALID_AMOUNT |
| FR-001-R2 | FR-001 | 转出账户必须存在 | ACCOUNT_NOT_FOUND |

**细分规则总数**: {{breakdown_count}}

---

## 5. 前端测试项（TC-xx，e2e 规划）【可选】

> 前端测试/e2e 为**可选实施**：本段仅在项目含前端代码且团队选择实施前端
> 测试规划时填写；纯后端项目或不需要时删除本段。e2e 测试**规划**用，
> **不进门槛**（gate 仅校验后端单测/契约测试）。本清单为规划级简版（编号 +
> 场景 + 类型 + 覆盖规则）；详细测试步骤 / 预期结果由实现后的
> `speckit.testing.impact` 生成，写入 `specs/{{feature}}/docs/impact-report.md`
> 的「功能测试案例集（e2e 规划）」段，供前端 e2e 测试 AI（如 Playwright）使用。

| 用例 ID | 场景 | 测试类型 | 覆盖规则 |
|---------|------|----------|----------|
| {{tc_case}} | {{tc_scenario}} | {{tc_type}} | {{rule_id}} |
| TC-01 | 正常转账全流程 | 功能测试 (正向) | FR-001 |
| TC-02 | 转账金额校验提示 | 异常测试 | FR-001 |
| TC-03 | 冻结账户转账提示 | 异常测试 | FR-001 |
| TC-04 | 余额不足提示 | 异常测试 | FR-001 |
| TC-05 | 转账成功结果展示 | 功能测试 (正向) | FR-001 |
| TC-06 | 转账确认弹窗交互 | 交互测试 | FR-001 |

**前端测试项总数**: {{tc_case_count}}

---

## 6. 排期建议

> 单测先行（骨架先行已保证单测可编译），契约测试次之（验证接口契约），业务代码最后（带 @Spec 注解）。
> e2e 为可选规划项：后端实现并过门槛后，如需实施前端 e2e，由 e2e 测试 AI 基于
> impact-report.md 的功能测试案例集编写前端 e2e 脚本，不进本排期的 TDD 阶段（不做不 FAIL）。

| 阶段 | 内容 | 用例数 | 建议工期 |
|------|------|--------|----------|
| 1. 单测编写 | UT-xx 骨架 + Mock 依赖 | {{unit_test_count}} | {{unit_schedule}} |
| 2. 契约测试编写 | CT-xx 骨架 + contract mock 桩 | {{contract_test_count}} | {{contract_schedule}} |
| 3. 业务代码实现 | Service + @Spec 注解 | - | {{impl_schedule}} |
| 4. 门禁执行 | speckit.testing.gate | - | {{gate_schedule}} |
| 5. 报告生成 | speckit.testing.report | - | {{report_schedule}} |
| 6. 前端 e2e 规划（可选） | 转发功能测试案例集给 e2e 测试 AI | {{tc_case_count}} | {{e2e_schedule}} |

---

## 7. 契约不变量自检

- [ ] 每个 Contract 至少 1 条正向 + 每错误码 1 条反向契约测试
- [ ] 每条 SpecRule 至少 1 条单测
- [ ] 验收阈值与 `ImpactReport.risk_level` 匹配（高->90%/100%，中->80%/95%，低->70%/95%）
- [ ] 单测 @DisplayName 格式为 `FR-xxx-Rm-<描述>`（顶层锚 FR-xxx + 子编号 Rm）
- [ ] 每条 TC 覆盖规则存在于 spec.md `### Functional Requirements` 段
      （顶层锚 FR-xxx；兼容旧 spec 的 `## Business Rules` 段）
- [ ] TC 为规划级简版（不含步骤/预期），详细内容由 impact 生成，不重复展开
