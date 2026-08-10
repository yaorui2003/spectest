package com.speckit.testing;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * {@link Spec} 的容器注解，支持 {@code @Repeatable}。
 *
 * <p>保留策略 {@code RUNTIME}，目标 {@code {METHOD, TYPE}}，字段 {@code Spec[] value()}。
 *
 * @see Spec
 */
@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.METHOD, ElementType.TYPE})
public @interface Specs {

    /** 同一目标上的多条 {@link Spec} 注解。 */
    Spec[] value();
}
