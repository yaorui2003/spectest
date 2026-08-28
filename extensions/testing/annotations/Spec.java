package com.speckit.testing;

import java.lang.annotation.ElementType;
import java.lang.annotation.Repeatable;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Spec 注解：标注代码实现的 Spec 业务规则。
 *
 * <p>本注解供 testing 扩展的源码静态扫描（scan_spec_annotations）使用，
 * 语义约定如下：
 *
 * <ul>
 *   <li>{@code capability}：对应 spec.md 的 capability 名，非空。
 *   <li>{@code rule}：规则编号，格式 {@code ^FR-\d+$}（如 {@code FR-001}）——
 *       顶层锚，永不携带 {@code -R} 子编号，必须严格匹配 spec.md
 *       {@code ### Functional Requirements} 段的 FR 编号（保留前导零）。
 *   <li>{@code description}：规则实现说明，自由文本，默认空串。
 * </ul>
 *
 * <p>门禁扫描采用源码正则扫描（见 research.md 决策 6），不依赖反射；
 * {@code SOURCE} 保留策略：注解仅存于源码、编译时丢弃，符合纯静态扫描实际用途，
 * 不污染 class 文件。未来若引入运行时反射校验再改回 {@code RUNTIME}。
 *
 * <p>同一方法可携带多条 {@code @Spec}（{@link Repeatable}）。
 *
 * <p>使用示例：
 * <pre>{@code
 * @Spec(capability = "transfer", rule = "FR-001", description = "金额校验")
 * public TransferResult transfer(String from, String to, BigDecimal amount) {
 *     // 代码侧 @Spec 永远只写顶层锚 FR-xxx；测试侧子场景编号由
 *     // @DisplayName("FR-xxx-Rm-...")（JUnit5）或测试方法级
 *     // @Spec(rule="FR-xxx-Rm", ...)（JUnit4）标注
 * }
 * }</pre>
 */
@Retention(RetentionPolicy.SOURCE)
@Target({ElementType.METHOD, ElementType.TYPE})
@Repeatable(Specs.class)
public @interface Spec {

    /** 对应 spec.md 的 capability 名，非空。 */
    String capability();

    /** 规则编号，顶层锚格式 {@code ^FR-\d+$}（如 {@code FR-001}），永不携带子编号。 */
    String rule();

    /** 规则实现说明，自由文本，默认空串。 */
    String description() default "";
}
