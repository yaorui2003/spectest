## TDD 强制执行（testing-tdd preset）— 覆盖下方任何冲突指令

**测试是必需的（REQUIRED），非可选（NOT optional）。** 忽略下方核心模板中任何 "Tests are OPTIONAL" 的表述。

强制规则：

- 对每个功能/实现任务，MUST 先生成对应测试任务（如 "为 XXX 编写失败的单元测试"）
- 测试任务 MUST 排在对应实现任务之前（Red-Green 顺序）
- 每个 user story 阶段的内部顺序：测试任务（先红）-> 实现任务（后绿）
- 单测 MUST 在 @DisplayName 中标注 Spec 规则编号（如 `@DisplayName("R1-...")`）
- 契约测试 MUST 覆盖每个接口的正向 + 每个错误码反向

> 本段由 testing-tdd preset 以 wrap 策略前置，覆盖核心模板的 OPTIONAL 默认。
> 下方 {CORE_TEMPLATE} 为核心 tasks-template 原文，其中 "Tests are OPTIONAL"
> 已被本段废止。

---

{CORE_TEMPLATE}
