## @Spec 注解强制执行（testing-tdd preset 追加段）

> 本段由 testing-tdd preset 以 append 策略追加到核心 `/speckit.implement` 命令。
> 与上方核心指令一同执行，落实宪法 Principle I（Spec Traceability 置首）。

实现 Java 业务代码时，以下规则 MUST 遵守：

### 0. 参考生成物（测试代码对齐依据）

生成测试代码时，除 tasks.md 任务清单外，MUST 参考以下已有生成物：

| 生成物 | 必需性 | 用途 |
|---|---|---|
| `test-plan.md`（speckit.testing.plan 产物） | IF EXISTS（存在则 MUST 参考） | 测试用例清单 UT-xx / CT-xx 与验收阈值——按清单生成测试（每条 SpecRule 至少 3 条单测：正常/异常/边界；每个 Contract 至少 1 正向 + 每错误码 1 反向），用例数量/场景与 test-plan.md 对齐，不臆造 |
| `contracts/`（speckit.plan 产物） | REQUIRED | 接口契约（正向请求 + 错误码清单），契约测试依据 |
| `data-model.md`（speckit.plan 产物） | IF EXISTS | 字段约束，单测边界值依据 |

> test-plan.md 缺失时（未运行 speckit.testing.plan），测试按 contracts/ +
> business_rules 自行推导，并在产物中注明。

### 1. @Spec 注解（MUST）

每个实现 Spec 规则的 public 方法 MUST 标注 `@Spec` 注解：

```java
@Spec(capability = "<capability>", rule = "<RULE_ID>", description = "<说明>")
public Result someMethod(...) { ... }
```

- 同一方法实现多条规则时，用多条 `@Spec`（`@Repeatable`）
- `rule` 编号 MUST 严格匹配 spec.md 的 business_rules（如 R1、R2）
- 缺失 `@Spec` 的规则会被 testing 扩展的 `speckit.testing.gate` 扫描判定 FAIL

### 2. 模板约定参考（MUST）

生成代码时 MUST 参考 testing 扩展提供的模板约定（非机械复制骨架）：

| 产物 | 参考模板 | 约定要点（MUST 遵守） |
|------|----------|----------------------|
| Java Service 业务代码 | `java-service-template` | @Spec 注解格式（capability + rule + description） |
| JUnit5 单测 | `java-unit-test-template` | @DisplayName("R<n>-<描述>") 格式、given/when/then 三段式、断言业务语义（禁弱断言：禁 `assertTrue(result.contains("1"))` 式橡皮断言）；新测试用 STRICT（Mockito strict stubs），存量 LENIENT 用例标注原因 |
| 契约测试 | `contract-test-template` | WireMock stub + **HTTP 客户端调用被测接口**（RestTemplate/WebClient）+ **断言响应码**（assertEquals(expectedStatus, response.getStatusCode())）+ **断言响应体**（业务字段）+ 每接口 1 正向 + 每错误码 1 反向。**禁 `assertTrue(true)` 空断言**；契约测试断言的事件类型 MUST 在 spec.md 或 contracts 中定义（禁对不存在事件类型的永真断言） |

> **注意**：模板提供的是**约定载体**（注解格式、命名规则、断言风格），而非项目特定的
> 技术栈骨架。AI 应参考约定生成符合项目实际技术栈的代码，而非机械复制模板中的
> Spring/JPA/WireMock 骨架或 `{{var}}` 占位符。硬约束由 gate 的
> @DisplayName/@Spec 一致性校验与技术栈硬校验保证。

### 3. 测试侧对齐（MUST）

- 单测 `@DisplayName` MUST 标注规则编号：`@DisplayName("R1-<描述>")`
- 与代码侧 `@Spec(rule="R1")` 双向对齐
- **直接测试覆盖（8.1 约定）**：每条业务规则（spec.md Business Rules 行）
  MUST 有至少 1 个**直接单测**——测试类直接实例化/驱动实现该规则的主类；
  **禁止仅以编排类间接覆盖替代**（如核心生成链 agent 只被
  OrchestratorImplTest 间接触碰）

### 4. 技术栈约定（MUST）

| 组件 | 作用 | 必需性 |
|------|------|--------|
| JUnit 4/5 | 测试框架 | REQUIRED |
| Mockito | Mock 依赖（@Mock / @InjectMocks / MockitoExtension） | REQUIRED |
| Surefire（mvn test） | 测试执行 + surefire-reports 生成 | REQUIRED |
| JaCoCo | 覆盖率插桩（line/branch/method/instruction/complexity） | REQUIRED |

**禁用**：
- **PowerMock** -- 覆盖率失真，门禁硬校验检出即 FAIL
- **`@SpringBootTest` 起容器** -- 单测用 Mockito、契约测试用 WireMock，均不起容器

> **不得改门禁脚本（严重违规）**：实现阶段若测试因上述禁用项 FAIL，必须修正
> **测试代码**（改用 Mockito / WireMock，**包括并发/集成类测试也用纯 JUnit +
> Mockito + Thread/ExecutorService，不起 `@SpringBootTest` 容器**），**绝不可
> 修改 `extensions/testing/scripts/` 下的扫描脚本或 `run_gate` 来加豁免 / 绕过
> 判定**。改脚本让门禁通过 = 绕过门禁。脚本若有真实 bug，须回 spec-kit 源
> 修复并重装扩展，不在用户项目内就地打补丁（v0.4 试点已出现此反例）。

### 5. 产出顺序（TDD，MUST）

1. **单测**（基于骨架方法签名，Mockito mock 依赖）-- 可立即编写 + 运行（Red）
2. **契约测试**（基于 contracts/，WireMock contract mock）-- 可立即编写 + 运行（Red）
3. **业务代码**（带 @Spec 注解，TDD 让测试通过）（Green）

> **单测先行前提**：骨架先行（tasks-template Phase 2 的 T010-T014 骨架任务）
> 保证单测可编译（TDD 的 Red = 断言失败而非编译失败）。

#### 5.1 Red 判定三条件（命令级硬规则）

**Red 证据 = 同时满足**：

1. `mvn test-compile` **EXIT=0**（骨架接口与测试签名一致）；
2. 运行 `mvn test -Dtest=<XxxTest>` 且输出含 **断言失败特征**（`Failures: N>0`
   或 `AssertionFailedError` / `expected: ... but was: ...`）；
3. **编译错误（COMPILATION ERROR / cannot find symbol）不是 Red**——是骨架
   未完成，回补骨架后再验 1+2。

**禁止**：用 `mvn compile`（仅 main）或 `mvn test-compile` 通过汇报 Red；
禁止在编译失败时陈述"断言失败"（编译失败时断言未运行）。

**测试编译失败 -> 回补骨架（Phase 2 骨架任务），不得进入 Green**——先对齐
骨架接口与测试签名，再验 Red 三条件。

- **插桩日志（System.out/logger 调试输出）验收前删除**（对账后移除）

> 违反上述任一规则，`after_implement` 钩子触发的 `speckit.testing.gate` 会判定
> FAIL 并阻断提交，输出具体修复建议。

### 6. 第 4.5 阶段：对抗测试 + 覆盖率达标（RECOMMENDED）

> 本阶段在业务代码 Green 之后、gate 之前执行，为**可选**阶段，由
> `testing-config.yml` 的 `adversarial.enabled` 开关控制（默认 true）。
> 目标：用真实测试数据把 JaCoCo 覆盖率推到套用阈值，而非堆砌通过用例
> （直击试点 P0 #6 覆盖率低）。

#### 6.1 覆盖率自检

TDD Red-Green 完成（业务代码 Green）后，先调用 `run_gate --check-only`
子模式做覆盖率自检：只跑 `mvn clean test` + 解析，**不写 gate-result.md**，
输出当前覆盖率 vs 套用阈值差距 + 未覆盖类/方法清单，作为补测方向依据。

#### 6.2 关键路径必测（独立 MUST，与 gate 阈值脱钩）

impact 标记为 `high` 风险等级的规则（涉及资金/权限/原子性/数据完整性）的
public 方法，**MUST 至少有 1 条对抗用例**。此约束独立于 gate 覆盖率阈值——
即使 gate 覆盖率达标，high 风险规则方法若无对抗用例仍判定不合规。

- 对抗用例 MUST 标 `@DisplayName("Rn-对抗-<描述>")`，保持 @Spec/@DisplayName
  双向对齐
- 此约束由 **run_gate 硬判**（v0.5）：`testing-config.yml` 的
  `adversarial.critical_path_required` 控制——`true`（默认）时 high 风险规则
  0 对抗用例 -> gate FAIL（阻断）；`false` 时降级为 advisory（gate 跳过对抗
  硬判，仅统计不阻断）
- **禁止直接改 test 适配 code**（漂移处置铁律，见 speckit.testing.gate 步骤 3
  决策矩阵）：gate 判定与测试结果不符时，先归因（改 spec/code/test 哪个、
  为什么），绝不通过放宽断言/删断言/改测试适配代码来让 gate 通过

#### 6.3 渐进式轮次（max_iterations 上限）

`adversarial.max_iterations`（默认 3）控制循环上限，每轮末重跑
`run_gate --check-only` 看是否达标：

| 轮次 | 目的 | 用例类型 |
|---|---|---|
| 第 1 轮 | 攻破自己代码 | 四类对抗：①反例与非法输入（null/超长/非法类型/越权）②边界与边界外（边界值分析 + 边界外溢出）③异常路径与错误分支（每个 throw/catch 分支补用例）④并发/时序竞态（仅 high 风险规则，如"先查累计再插"竞态） |
| 第 2 轮 | 目的性覆盖率补洞 | 针对 JaCoCo 未覆盖的类/方法（含辅助类：DTO getter/setter、枚举、异常处理器、Controller、main 类）补用例 |
| 第 3 轮 | 兜底 | 继续补洞 + 可选重构业务代码（拆方法/消分支死角/简化逻辑） |

- 达标 -> 跳出循环，进 gate（正式 `run_gate`，写 gate-result.md）
- 未达标且未超 max_iterations -> 下一轮
- 超限仍未达标 -> **如实进 gate**，gate 会 FAIL（不伪造数据，直击 P0 #1）

### 7. 前端测试约定（改动 .vue/.js/.ts 时 MUST）

> 前端改动（.vue/.js/.ts）时测试任务 **REQUIRED**（tasks-template 前端任务
> 区，双标签 [USx] [Rn] 保留）。gate 只校验后端单测/契约测试，前端侧靠以下
> 约定自律：

- **组件/API 测试**：改动 .vue/.js 必有对应组件测试（**vitest** +
  @vue/test-utils + happy-dom），`describe("R<n>-<描述>")` 对齐 spec.md 规则
  编号（@Spec 仅限 Java，前端用命名规范对齐）；api 层（WS 连接/断连/降级）
  同样必测
- **e2e MUST 确定性**：stub LLM（route stub 返回固定 JSON，或后端起 stub
  模式 + `@MockBean` LLMService）+ WS 事件固定序列注入，**禁真实 LLM**；
  真实链路 e2e 仅手工/定时慢跑，**不进门禁**
- **e2e 选择执行**（避免全量慢跑）：只跑 impact functional case set 中
  covered_rules 与受影响规则求交命中的用例：
  `npx playwright test --grep <命中用例 ID>`（如 `--grep E2E-01,E2E-03`）
- 实现完成后，`after_implement` 钩子触发的 `speckit.testing.impact` 会生成
  **功能测试案例集**（TC-xx / e2e 用例带 covered_rules，写入
  `specs/<feature>/docs/impact-report.md`），供前端 e2e 编写与选择执行——
  实现时无需为此写 e2e 代码
- 后端错误码 / 校验行为 / 返回文案 MUST 与前端提示文案约定一致（功能测试
  案例集中的预期结果以后端实际行为为准）
- 接口响应 MUST 包含前端展示所需字段（如交易流水号、脱敏账号、剩余余额），
  否则前端无法呈现案例集中的预期结果
