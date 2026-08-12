/**
 * 本模板由 speckit.testing 扩展提供（templates/java-unit-test.template.java）。
 *
 * 用途：JUnit5 + Mockito 单元测试骨架模板。
 * 项目首次接入扩展时，将本文件复制到 src/test/java/{{package}}/ 下并填充占位符。
 *
 * 技术栈约定（必需前置）：
 *   - JUnit 5（org.junit.jupiter）+ Mockito（@Mock/@InjectMocks/MockitoExtension）
 *   - 禁用 PowerMock（覆盖率失真）
 *   - 禁用 @SpringBootTest 起容器（单测基于 Mockito，不起容器）
 *   - JaCoCo 覆盖率报告必需（target/site/jacoco/jacoco.xml）
 *
 * 占位符（{{var}} 双花括号，由 AI 填充）：
 *   - {{package}}             : 测试包名
 *   - {{capability}}          : 能力名（如 transfer）
 *   - {{rule_id}}             : 规则编号 R\d+（如 R1）
 *   - {{service_class}}       : 被测 Service 类名
 *   - {{service_field}}       : 被测对象字段名（小驼峰）
 *   - {{repository_interface}} : 依赖的 Repository 接口名
 *   - {{repository_field}}    : Repository 字段名（小驼峰）
 *   - {{method_name}}         : 被测方法名
 *   - {{description}}         : @DisplayName 中的规则描述（如 转账金额为0应抛出INVALID_AMOUNT）
 *   - {{error_code}}          : 期望错误码
 *
 * 约束（来自 contracts/spec-annotation.md 语义规则 5 + data-model.md TestCase）：
 *   1. 单测 MUST 在 @DisplayName 中标注对应规则编号，格式 R<n>-<描述>。
 *   2. 每条 @Spec 注解应有对应 @DisplayName 单测（双向对齐）。
 *   3. 每条 SpecRule 至少 1 条单测（正常/异常/边界）。
 *   4. 断言业务语义（错误码 / 状态变更），禁止仅用 assertNotNull 等弱断言。
 *   5. 外部依赖（DB/RPC）必须 Mock，单测不依赖真实基础设施。
 */
package {{package}};

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * {{service_class}} 单元测试。
 *
 * 每条业务规则对应一个测试方法骨架，@DisplayName 标注规则编号以便门禁扫描对齐。
 */
@ExtendWith(MockitoExtension.class)
class {{service_class}}Test {

    @Mock
    private {{repository_interface}} {{repository_field}};

    @InjectMocks
    private {{service_class}} {{service_field}};

    // ===== 每条 Spec 规则一个测试方法骨架，按下例复制扩展 =====

    /**
     * {{rule_id}}: {{description}}
     * 场景：异常 / 边界（示例：金额为 0 应拒绝）
     */
    @Test
    @DisplayName("{{rule_id}}-{{description}}")
    void should{{scenario_name}}() {
        // given —— 构造入参与 Mock 返回
        // when({{repository_field}}.findById({{param1}})).thenReturn({{account_fixture}});

        // when —— 调用被测方法，断言抛出业务异常
        {{business_exception}} thrown = assertThrows({{business_exception}}.class, () -> {
            {{service_field}}.{{method_name}}({{param1}}, {{param2}}, {{param3}});
        });

        // then —— 断言业务语义：错误码匹配（禁止仅 assertNotNull）
        assertEquals("{{error_code}}", thrown.getCode());
        // 验证副作用：违规场景不应触发状态变更
        verify({{repository_field}}, never()).debit(any(), any());
        verify({{repository_field}}, never()).credit(any(), any());
    }

    /**
     * {{rule_id}}: {{description}} —— 正常路径骨架
     * 场景：正常（示例：合法转账应成功并原子扣减/入账）
     */
    @Test
    @DisplayName("{{rule_id}}-{{description}}")
    void should{{scenario_name_ok}}() {
        // given
        // when({{repository_field}}.findById({{param1}})).thenReturn({{from_account_fixture}});
        // when({{repository_field}}.findById({{param2}})).thenReturn({{to_account_fixture}});

        // when
        {{return_type}} result = {{service_field}}.{{method_name}}({{param1}}, {{param2}}, {{param3}});

        // then —— 断言业务语义：状态变更 / 返回结构
        // verify({{repository_field}}).debit({{param1}}, {{param3}});
        // verify({{repository_field}}).credit({{param2}}, {{param3}});
        // assertEquals("0000", result.getCode());
        // assertNotNull(result.getTxnNo());
    }

    // ===== 复制上方骨架为每条规则 R1..Rn 各补一个测试方法 =====
}
