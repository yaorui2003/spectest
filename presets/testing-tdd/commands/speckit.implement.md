## @Spec 注解强制执行（testing-tdd preset 追加段）

> 本段由 testing-tdd preset 以 append 策略追加到核心 `/speckit.implement` 命令。
> 与上方核心指令一同执行，落实宪法 Principle I（Spec Traceability 置首）。

实现 Java 业务代码时，以下规则 MUST 遵守：

### 1. 参考生成物（测试代码对齐依据）

| 生成物 | 必需性 | 用途 |
|---|---|---|
| `specs/<feature>/docs/test-plan.md`（speckit.testing.plan 产物） | IF EXISTS（存在则 MUST 参考） | 单测用例清单 UT-xx 与验收阈值——按清单生成测试（每条 SpecRule 至少 3 条单测：正常/异常/边界），用例数量/场景与 test-plan.md 对齐，不臆造 |
| `contracts/`（speckit.plan 产物） | REQUIRED | 接口契约（错误码清单），单测异常用例依据 |
| `data-model.md`（speckit.plan 产物） | IF EXISTS | 字段约束，单测边界值依据 |

> test-plan.md 缺失时（未运行 speckit.testing.plan），测试按 contracts/ +
> spec.md FR 段自行推导，并在产物中注明。

### 2. @Spec 注解（MUST）

每个实现 Spec 规则的 public 方法 MUST 标注 `@Spec` 注解：

```java
@Spec(capability = "<capability>", rule = "<RULE_ID>", description = "<说明>")
public Result someMethod(...) { ... }
```

- 同一方法实现多条规则时，用多条 `@Spec`（`@Repeatable`）
- `rule` 编号 MUST 严格匹配 spec.md `### Functional Requirements` 段的顶层锚
  （如 FR-001、FR-002），**永不携带 -R 子编号**
- 缺失 `@Spec` 的规则会被 testing 扩展的 `speckit.testing.gate` 扫描判定 FAIL

> **模板约定参考**（MUST，非机械复制）：生成代码时参考 testing 扩展模板——
> 「Java Service 业务代码」参考 `java-service-template`（@Spec 注解格式）；
> 「单测」参考 `java-unit-test-template`（规则标注双通道 + given/when/then 三段式
> + 断言业务语义，禁弱断言）。模板提供的是约定载体（注解格式/命名/断言风格），
> 而非项目特定技术栈骨架，AI 按项目实际技术栈生成，硬约束由 gate 校验。

### 3. 测试侧对齐（MUST，规则标注双通道）

- **JUnit5**：单测 `@DisplayName("FR-001-R1-<场景>")` 标注子场景编号
- **JUnit4**：测试方法上标 `@Spec(rule="FR-001", description="<场景>")`
  （@Spec 为 spec-kit 自定义注解，与 JUnit 版本无关，JUnit4 项目同样可用）
- 与代码侧 `@Spec(rule="FR-001")` 按顶层锚双向对齐（无 plan 时测试作者自编号）
- **直接测试覆盖**：每条业务规则（spec.md FR 段行）MUST 有至少 1 个**直接
  单测**——测试类直接实例化/驱动实现该规则的主类；禁止仅以编排类间接覆盖
  替代

### 4. 可测性设计约定（MUST）

业务代码设计时避免以下 4 类影响可测性的情况：

1. **构造方法做事过多**——构造函数只做字段赋值/依赖注入，不承载业务逻辑，
   便于测试直接实例化
2. **过多全局变量/静态方法**——静态状态难以 mock 且测试间易互相污染；优先
   实例方法 + 依赖注入
3. **过多外部依赖**——单类依赖过多外部服务时测试准备成本高；适当拆分/接口化，
   便于 Mockito mock
4. **过多条件语句（复杂分支）**——复杂分支难以全覆盖；拆分为小方法降低圈
   复杂度，便于边界测试

### 5. 技术栈约定（MUST）

| 组件 | 作用 | 必需性 |
|------|------|--------|
| JUnit 4/5 | 测试框架 | REQUIRED |
| Mockito | Mock 依赖（@Mock / @InjectMocks / MockitoExtension 或 MockitoJUnitRunner） | REQUIRED |
| Surefire（mvn test） | 测试执行 + surefire-reports 生成 | REQUIRED |
| JaCoCo | 覆盖率插桩 | REQUIRED |

**禁用**（scan_test_stack 检出即 FAIL）：

- **PowerMock** —— 覆盖率失真
- **`@SpringBootTest` 起容器** —— 单测用 Mockito，不起容器
- **`@Autowired`** —— 测试须显式 Mock/构造注入，不起 Spring 容器

> **不得改门禁脚本（严重违规）**：实现阶段若测试因上述禁用项 FAIL，必须修正
> **测试代码**（改用 Mockito；并发/集成类测试也用纯 JUnit + Mockito +
> Thread/ExecutorService，不起容器），**绝不可修改
> `extensions/testing/scripts/` 下的扫描脚本或 `run_gate` 来加豁免 / 绕过
> 判定**。改脚本让门禁通过 = 绕过门禁。脚本若有真实 bug，须回 spec-kit 源
> 修复并重装扩展，不在用户项目内就地打补丁。

### 6. 产出顺序（TDD，MUST）

1. **单测**（基于骨架方法签名，Mockito mock 依赖）—— 可立即编写 + 运行（Red）
2. **业务代码**（带 @Spec 注解，TDD 让测试通过）（Green）

> **单测先行前提**：骨架先行（tasks-template Phase 2 的 T010-T014 骨架任务）
> 保证单测可编译（TDD 的 Red = 断言失败而非编译失败）。

#### 6.1 Red 判定三条件（命令级硬规则）

**Red 证据 = 同时满足**：

1. `mvn test-compile` **EXIT=0**（骨架接口与测试签名一致）；
2. 运行 `mvn test -Dtest=<XxxTest>` 且输出含 **断言失败特征**（`Failures: N>0`
   或 `AssertionFailedError` / `expected: ... but was: ...`）；
3. **编译错误（COMPILATION ERROR / cannot find symbol）不是 Red**——是骨架
   未完成，回补骨架后再验 1+2。

**禁止**：用 `mvn compile`（仅 main）或 `mvn test-compile` 通过汇报 Red；
禁止在编译失败时陈述"断言失败"（编译失败时断言未运行）。测试编译失败 ->
回补骨架（Phase 2 骨架任务），不得进入 Green。

- **插桩日志（System.out/logger 调试输出）验收前删除**

> 违反上述任一规则，`after_implement` 钩子触发的 `speckit.testing.gate` 会判定
> FAIL 并阻断提交，输出具体修复建议。

#### 6.2 收尾约定（提测前）

- **提测前完成单测**：所有功能代码提交前，对应单测 MUST 已完成并通过
- **核心模块增量代码单测必过**：核心模块的增量代码（git diff 新增/修改行）
  单测 MUST 覆盖并通过（与门禁 diff coverage 概念呼应）
- **不可测代码适当时机重构**：发现难以测试的代码（高耦合/静态依赖/构造复杂），
  在适当时机重构以提升可测性，而非绕过测试

### 7. 第 4.5 阶段：对抗测试 + 覆盖率达标（RECOMMENDED）

> 本阶段在业务代码 Green 之后、gate 之前执行，为**可选**阶段，由
> `testing-config.yml` 的 `adversarial.enabled` 开关控制（默认 true）。
> 目标：用真实测试数据把 JaCoCo 覆盖率推到套用阈值，而非堆砌通过用例。

#### 7.1 覆盖率自检

TDD Red-Green 完成（业务代码 Green）后，先调用 `run_gate --check-only`
子模式做覆盖率自检：只跑 `mvn clean test` + 解析，**不写 gate-result.md**，
输出当前覆盖率 vs 套用阈值差距 + 未覆盖类/方法清单，作为补测方向依据。

#### 7.2 关键路径必测（独立 MUST，与 gate 阈值脱钩）

impact 标记为 `high` 风险等级的规则（涉及资金/权限/原子性/数据完整性）的
public 方法，**MUST 至少有 1 条对抗用例**。此约束独立于 gate 覆盖率阈值。

- 对抗用例 MUST 标规则标注（`@DisplayName("FR-xxx-Rm-对抗-<描述>")` 或
  JUnit4 测试方法级 `@Spec(rule="FR-xxx", description="对抗-<描述>")`），
  保持双向对齐
- 此约束由 **run_gate 硬判**：`testing-config.yml` 的
  `adversarial.critical_path_required` 控制——`true`（默认）时 high 风险规则
  0 对抗用例 -> gate FAIL（阻断）；`false` 时降级为 advisory
- **禁止直接改 test 适配 code**（漂移处置铁律，见 speckit.testing.gate 步骤 3
  决策矩阵）：gate 判定与测试结果不符时，先归因，绝不通过放宽断言/删断言/
  改测试适配代码来让 gate 通过

#### 7.3 渐进式轮次（max_iterations 上限）

`adversarial.max_iterations`（默认 3）控制循环上限，每轮末重跑
`run_gate --check-only` 看是否达标：

| 轮次 | 目的 | 用例类型 |
|---|---|---|
| 第 1 轮 | 攻破自己代码 | 四类对抗：①反例与非法输入（null/超长/非法类型/越权）②边界与边界外（边界值分析 + 边界外溢出）③异常路径与错误分支（每个 throw/catch 分支补用例）④并发/时序竞态（仅 high 风险规则） |
| 第 2 轮 | 目的性覆盖率补洞 | 针对 JaCoCo 未覆盖的类/方法（含辅助类：DTO getter/setter、枚举、异常处理器、Controller、main 类）补用例 |
| 第 3 轮 | 兜底 | 继续补洞 + 可选重构业务代码（拆方法/消分支死角/简化逻辑） |

- 达标 -> 跳出循环，进 gate（正式 `run_gate`，写 gate-result.md）
- 未达标且未超 max_iterations -> 下一轮
- 超限仍未达标 -> **如实进 gate**，gate 会 FAIL（不伪造数据）