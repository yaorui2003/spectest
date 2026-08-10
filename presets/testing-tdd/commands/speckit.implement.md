## @Spec 注解强制执行（testing-tdd preset 追加段）

> 本段由 testing-tdd preset 以 append 策略追加到核心 `/speckit.implement` 命令。
> 与上方核心指令一同执行，落实宪法 Principle VI（Spec Traceability）。

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

### 2. 代码模板（MUST resolve）

生成代码时 MUST resolve testing 扩展提供的模板：

| 产物 | resolve 模板名 | 说明 |
|------|----------------|------|
| Java Service 业务代码 | `java-service-template` | 含 @Spec 注解占位符 |
| JUnit5 单测 | `java-unit-test-template` | 含 @DisplayName 规则标注 |
| 契约测试 | `contract-test-template` | 基于 contract mock，不需服务启动 |

### 3. 测试侧对齐（MUST）

- 单测 `@DisplayName` MUST 标注规则编号：`@DisplayName("R1-<描述>")`
- 与代码侧 `@Spec(rule="R1")` 双向对齐

### 4. 产出顺序（TDD，MUST）

1. 契约测试（基于 contracts/，contract mock）— 可立即编写 + 运行
2. 单测（基于契约方法签名，mock 依赖）— 可立即编写 + 运行
3. 业务代码（带 @Spec 注解，TDD 让测试通过）

> 违反上述任一规则，`after_implement` 钩子触发的 `speckit.testing.gate` 会判定
> FAIL 并阻断提交，输出具体修复建议。
