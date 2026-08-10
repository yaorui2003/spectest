package com.speckit.testing;

import java.lang.annotation.ElementType;
import java.lang.annotation.Repeatable;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Spec 注解：标注代码实现的 Spec 业务规则。
 *
 * <p>语义见 {@code specs/001-speckit-testing-ext/contracts/spec-annotation.md}：
 *
 * <ul>
 *   <li>{@code capability}：对应 spec.md 的 capability 名，非空。
 *   <li>{@code rule}：规则编号，格式 {@code ^R\d+$}（如 {@code R1}），必须匹配
 *       spec.md business_rules 规则编号。
 *   <li>{@code description}：规则实现说明，自由文本，默认空串。
 * </ul>
 *
 * <p>门禁扫描采用源码正则扫描（见 research.md 决策 6），不依赖反射；
 * {@code RUNTIME} 保留策略为未来运行时校验场景预留。
 *
 * <p>同一方法可携带多条 {@code @Spec}（{@link Repeatable}）。
 *
 * <p>使用示例：
 * <pre>{@code
 * @Spec(capability = "transfer", rule = "R1", description = "金额校验")
 * @Spec(capability = "transfer", rule = "R7", description = "自转账校验")
 * public TransferResult transfer(String from, String to, BigDecimal amount) {
 *     // ...
 * }
 * }</pre>
 */
@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.METHOD, ElementType.TYPE})
@Repeatable(Specs.class)
public @interface Spec {

    /** 对应 spec.md 的 capability 名，非空。 */
    String capability();

    /** 规则编号，格式 {@code ^R\d+$}（如 {@code R1}）。 */
    String rule();

    /** 规则实现说明，自由文本，默认空串。 */
    String description() default "";
}
