/**
 * 单测参考骨架（speckit.testing 提供）。占位符 {{var}} 由 AI 填充。
 *
 * 约定（MUST）：规则标注双通道（与 JUnit 版本无关）——
 *  JUnit5：@DisplayName("{{rule_id}}-{{description}}")，rule_id = 顶层锚 FR-xxx
 *          的子编号（如 FR-001-R1）；
 *  JUnit4：测试方法上标 @Spec(rule="FR-001", description="<场景>")，
 *          @Spec 为 spec-kit 自定义注解（SOURCE，静态扫描），JUnit4 项目同样可用；
 * 断言业务语义（错误码/状态变更/副作用 verify），禁弱断言（仅 assertNotNull）；
 * 外部依赖 Mock，禁 @Autowired / @SpringBootTest 起容器。技术栈见宪法 Principle III。
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
 * {{service_class}} 单元测试。JUnit5 模板；JUnit4 项目改为：
 *   import org.junit.Test; import org.junit.runner.RunWith;
 *   import org.mockito.junit.MockitoJUnitRunner;
 *   @RunWith(MockitoJUnitRunner.class) + @Test + 方法上 @Spec(rule="FR-xxx")。
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