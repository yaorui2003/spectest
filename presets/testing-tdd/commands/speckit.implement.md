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
| 契约测试 | `contract-test-template` | WireMock contract mock（不起容器）、每接口 1 正向 + 每错误码 1 反向 |

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

### 5. 产出顺序（TDD，MUST）

1. **单测**（基于骨架方法签名，Mockito mock 依赖）-- 可立即编写 + 运行（Red）
2. **契约测试**（基于 contracts/，WireMock contract mock）-- 可立即编写 + 运行（Red）
3. **业务代码**（带 @Spec 注解，TDD 让测试通过）（Green）

> **单测先行前提**：骨架先行（tasks-template Phase 2 的 T010-T014 骨架任务）
> 保证单测可编译（TDD 的 Red = 断言失败而非编译失败）。
>
> 违反上述任一规则，`after_implement` 钩子触发的 `speckit.testing.gate` 会判定
> FAIL 并阻断提交，输出具体修复建议。
