## @Spec 注解强制执行（testing-tdd preset 追加段）

> 本段由 testing-tdd preset 以 append 策略追加到核心 `/speckit.implement` 命令。
> 与上方核心指令一同执行，落实宪法 Principle I（Spec Traceability 置首）。

实现 Java 业务代码时，以下规则 MUST 遵守：

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
| JUnit5 单测 | `java-unit-test-template` | @DisplayName("R<n>-<描述>") 格式、given/when/then 三段式、断言业务语义（禁弱断言） |
| 契约测试 | `contract-test-template` | WireMock stub + **HTTP 客户端调用被测接口**（RestTemplate/WebClient）+ **断言响应码**（assertEquals(expectedStatus, response.getStatusCode())）+ **断言响应体**（业务字段）+ 每接口 1 正向 + 每错误码 1 反向。**禁 `assertTrue(true)` 空断言** |

> **注意**：模板提供的是**约定载体**（注解格式、命名规则、断言风格），而非项目特定的
> 技术栈骨架。AI 应参考约定生成符合项目实际技术栈的代码，而非机械复制模板中的
> Spring/JPA/WireMock 骨架或 `{{var}}` 占位符。硬约束由 gate 的
> @DisplayName/@Spec 一致性校验与技术栈硬校验保证。

### 3. 测试侧对齐（MUST）

- 单测 `@DisplayName` MUST 标注规则编号：`@DisplayName("R1-<描述>")`
- 与代码侧 `@Spec(rule="R1")` 双向对齐

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
>
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
- 对抗用例存在性由 AI 在对抗阶段自检 + 关键路径清单核对（run_gate 不校验
  此条，这是 AI 自律约束）

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
