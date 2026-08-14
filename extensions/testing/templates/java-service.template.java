/**
 * Java Service 参考骨架（speckit.testing 提供）。占位符 {{var}} 由 AI 在 speckit.implement 阶段填充。
 *
 * 约定（MUST）：实现 spec.md business_rules 的每个 public 方法标注 @Spec；rule 编号
 * 严格匹配 spec.md；同一方法多规则用多条 @Spec（@Repeatable）。技术栈与禁用项见宪法 Principle III。
 */
package {{package}};

import com.speckit.testing.Spec;

/**
 * {{capability}} 能力的 Service 实现。
 */
public class {{service_class}} {

    @Spec(capability = "{{capability}}", rule = "{{rule_id}}", description = "{{description}}")
    // @Spec 可重复（@Repeatable）标注同一方法的多条规则，例如：
    // @Spec(capability = "{{capability}}", rule = "{{rule_id_2}}", description = "{{description_2}}")
    public {{return_type}} {{method_name}}(/* {{params}} */) {
        // TODO 实现规则 {{rule_id}}（{{description}}）的业务逻辑
        throw new UnsupportedOperationException("占位符未填充：由 AI 在 speckit.implement 阶段填充");
    }
}
