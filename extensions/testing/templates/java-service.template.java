/**
 * 本模板由 speckit.testing 扩展提供（templates/java-service.template.java）。
 *
 * 用途：Java Service 业务代码骨架模板，含 @Spec 注解占位符。
 * 项目首次接入 speckit.testing 扩展时，将本文件复制到业务代码目录并填充占位符。
 *
 * 占位符统一使用 {{var}} 双花括号格式，由 AI Agent 在 speckit.implement 阶段填充：
 *   - {{package}}             : Java 包名（如 com.example.transfer）
 *   - {{capability}}          : spec.md 中的能力名（如 transfer）
 *   - {{service_class}}       : Service 类名（如 AccountService）
 *   - {{method_name}}         : 方法名（如 transfer）
 *   - {{rule_id}}             : 规则编号，格式 ^R\d+$（如 R1、R7）
 *   - {{description}}         : @Spec 注解中对该规则实现的说明
 *   - {{error_code}}          : 违反规则时返回的错误码（如 INVALID_AMOUNT）
 *   - {{return_type}}         : 返回类型（如 TransferResult）
 *
 * 约束（来自 contracts/spec-annotation.md 语义规则）：
 *   1. spec.md 中每条 business_rules 规则 MUST 至少有一个 @Spec 注解对应。
 *   2. 实现规则的每个 public 方法 MUST 携带至少一个 @Spec。
 *   3. @Spec 的 rule 编号 MUST 严格匹配 spec.md（否则标记为孤儿注解，门禁 FAIL）。
 *   4. 同一方法可有多条 @Spec（@Repeatable），覆盖矩阵列出全部不去重。
 *
 * 下方以银行转账 AccountService 为示例结构（参考 contracts/spec-annotation.md 6.3 节）。
 */
package {{package}};

import com.speckit.testing.Spec;
import com.speckit.testing.Specs;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;

/**
 * {{capability}} 能力的 Service 实现。
 *
 * 类级 @Spec 表示该类整体实现某规则；方法级 @Spec 更精确，优先使用方法级。
 */
@Service
public class {{service_class}} {

    @Autowired
    private {{repository_interface}} {{repository_field}};

    /**
     * {{method_name}} 方法实现多条 Spec 规则。
     *
     * 示例结构对应银行转账场景（spec.md capability=transfer，规则 R1~R7）。
     * 每条规则用 @Spec 注解显式标注，方法体内用注释指明对应规则编号的实现位置。
     *
     * @param {{param1}} 转出账户（示例：fromAccount）
     * @param {{param2}} 转入账户（示例：toAccount）
     * @param {{param3}} 转账金额（示例：amount）
     * @return {{return_type}} 业务结果（示例：TransferResult）
     * @throws {{business_exception}} 违反业务规则时抛出，含错误码
     */
    @Transactional(rollbackFor = Exception.class)
    @Spec(capability = "{{capability}}", rule = "{{rule_id}}", description = "{{description}}")
    // @Spec 可重复标注多条规则，例如：
    // @Spec(capability = "{{capability}}", rule = "{{rule_id_2}}", description = "{{description_2}}")
    // @Spec(capability = "{{capability}}", rule = "{{rule_id_3}}", description = "{{description_3}}")
    public {{return_type}} {{method_name}}({{param_type1}} {{param1}},
                                           {{param_type2}} {{param2}},
                                           {{param_type3}} {{param3}}) {
        // {{rule_id}}: {{description}} —— 规则校验
        // 示例（R1 金额校验）：
        // if ({{param3}} == null || {{param3}}.compareTo(BigDecimal.ZERO) <= 0) {
        //     throw new {{business_exception}}("{{error_code}}", "转账金额必须大于0");
        // }

        // {{rule_id_2}}: {{description_2}} —— 规则校验
        // 示例（R7 自转账校验）：
        // if ({{param1}}.equals({{param2}})) {
        //     throw new {{business_exception}}("SELF_TRANSFER_NOT_ALLOWED", "不可自转账");
        // }

        // ... 其余规则实现（R2 账户存在性 / R3 冻结 / R4 余额 / R5 转入存在） ...

        // {{rule_id_3}}: {{description_3}} —— 原子操作收尾
        // 示例（R6 原子操作）：
        // {{repository_field}}.debit({{param1}}, {{param3}});
        // {{repository_field}}.credit({{param2}}, {{param3}});
        // return {{return_type}}.success(generateTxnNo());
        throw new UnsupportedOperationException("模板占位符未填充：请由 AI 在 speckit.implement 阶段填充");
    }
}
