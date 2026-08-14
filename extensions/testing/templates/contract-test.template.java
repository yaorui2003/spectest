/**
 * 契约测试参考骨架（speckit.testing 提供，基于 WireMock）。占位符 {{var}} 由 AI 填充。
 *
 * 约定（MUST）：每接口 1 正向 + 每错误码 1 反向；真正调用被测接口（WireMock stub + HTTP 客户端调用
 * + 断言响应码/响应体），禁 assertTrue(true) 空断言；@DisplayName 标规则编号。技术栈见宪法 Principle III。
 */
package {{package}}.contract;

import com.github.tomakehurst.wiremock.junit5.WireMockExtension;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.post;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig;
import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * {{contract_interface}} 契约测试。基于契约 mock，不起容器。
 */
class {{contract_name}}ContractTest {

    @RegisterExtension
    static WireMockExtension wireMock = WireMockExtension.newInstance()
            .options(wireMockConfig().dynamicPort())
            .build();

    private final RestTemplate restTemplate = new RestTemplate();

    @Test
    @DisplayName("{{rule_id}}-{{description}}")
    void should{{scenario_name}}() {
        // given -- 契约 mock 桩（正向/错误响应）
        wireMock.stubFor(post(urlEqualTo("{{contract_path}}"))
                .willReturn(aResponse()
                        .withStatus({{http_status}})
                        .withHeader("Content-Type", "application/json")
                        .withBody("{\"code\":\"{{error_code}}\",\"message\":\"{{error_message}}\"}")));

        // when -- HTTP 客户端调用被测接口（必须发真实请求，不能只 stub）
        ResponseEntity<String> response = restTemplate.postForEntity(
                wireMock.getRuntimeInfo().getHttpBaseUrl() + "{{contract_path}}",
                {{request_body}}, String.class);

        // then -- 断言响应码 + 响应体业务字段（禁 assertTrue(true) 空断言）
        assertEquals({{http_status}}, response.getStatusCode().value());
        // 解析响应体后断言业务字段：assertEquals("{{error_code}}", body.code)
    }
}
