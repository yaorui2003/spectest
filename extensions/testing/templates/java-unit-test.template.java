/**
 * JUnit5 + Mockito 单测参考骨架（speckit.testing 提供）。占位符 {{var}} 由 AI 填充。
 *
 * 约定（MUST）：每条规则的单测标 @DisplayName("{{rule_id}}-{{description}}") 与 @Spec 双向对齐；
 * 断言业务语义（错误码/状态变更），禁弱断言（仅 assertNotNull）；外部依赖 Mock。技术栈见宪法 Principle III。
 */
package {{package}};

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * {{service_class}} 单元测试。@DisplayName 标规则编号以便门禁扫描对齐。
 */
@ExtendWith(MockitoExtension.class)
class {{service_class}}Test {

    @Mock
    private {{dependency_interface}} {{dependency_field}};

    @InjectMocks
    private {{service_class}} {{service_field}};

    @Test
    @DisplayName("{{rule_id}}-{{description}}")
    void should{{scenario_name}}() {
        // given -- 构造入参与 Mock 返回
        // when({{dependency_field}}.findById({{param1}})).thenReturn({{fixture}});

        // when -- 调用被测方法，断言业务语义
        {{business_exception}} thrown = assertThrows({{business_exception}}.class, () ->
            {{service_field}}.{{method_name}}(/* {{params}} */));

        // then -- 断言错误码 / 状态变更（禁仅 assertNotNull）
        assertEquals("{{error_code}}", thrown.getCode());
        verify({{dependency_field}}, org.mockito.Mockito.never()).save(org.mockito.ArgumentMatchers.any());
    }
}
