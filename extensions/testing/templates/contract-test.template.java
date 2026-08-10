/**
 * 本模板由 speckit.testing 扩展提供（templates/contract-test.template.java）。
 *
 * 用途：契约测试骨架模板，基于 contract mock（WireMock 或 MockServer）。
 * 项目首次接入扩展时复制到 src/test/java/{{package}}/contract/ 下并填充占位符。
 *
 * 特点（来自 commands.md speckit.testing.plan 契约不变量）：
 *   - 不需启动真实服务，基于 contract mock 验证接口契约。
 *   - 每个契约接口：1 条正向 + 每错误码 1 条反向。
 *   - @DisplayName 标注对应规则编号，便于门禁扫描对齐。
 *   - 断言 HTTP 状态码 + 响应体错误码 + 响应体结构；
 *     不断言真实业务数据变更（业务语义由单测覆盖）。
 *
 * 占位符（{{var}} 双花括号，由 AI 填充）：
 *   - {{package}}              : 测试包名
 *   - {{contract_name}}        : 契约名（如 Transfer）
 *   - {{contract_interface}}   : 契约接口（如 POST /api/v1/accounts/transfer）
 *   - {{contract_path}}       : 接口 path 部分（如 /api/v1/accounts/transfer）
 *   - {{rule_id}}              : 规则编号 R\d+
 *   - {{http_status}}          : 期望 HTTP 状态码
 *   - {{error_code}}           : 期望响应体错误码
 *   - {{request_body}}         : 正向请求体
 *   - {{request_body_invalid}} : 反向请求体
 */
package {{package}}.contract;

import com.github.tomakehurst.wiremock.junit5.WireMockExtension;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.okJson;
import static com.github.tomakehurst.wiremock.client.WireMock.post;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * {{contract_interface}} 契约测试。
 *
 * 每个错误码对应一条反向用例 + 1 条正向用例，@DisplayName 标注规则编号。
 * 基于契约 mock 桩，不依赖真实服务启动。
 */
class {{contract_name}}ContractTest {

    @RegisterExtension
    static WireMockExtension wireMock = WireMockExtension.newInstance()
            .options(wireMockConfig().dynamicPort())
            .build();

    private final RestTemplate restTemplate = new RestTemplate();

    /**
     * 正向用例：{{rule_id}} 期望成功
     * 断言：HTTP 200 + 响应体 code=0000 + 响应体结构含 txnNo
     */
    @Test
    @DisplayName("{{rule_id}}-{{positive_description}}")
    void shouldReturnSuccessOnValidRequest() {
        // given —— 契约 mock 桩：正向响应
        wireMock.stubFor(post(urlEqualTo("{{contract_path}}"))
                .willReturn(okJson("{\"code\":\"0000\",\"message\":\"success\",\"txnNo\":\"{{txn_no}}\"}")));

        // when
        ResponseEntity<String> response = restTemplate.postForEntity(
                wireMock.getRuntimeInfo().getHttpBaseUrl() + "{{contract_path}}",
                {{request_body}},
                String.class);

        // then —— 断言 HTTP 状态码 + 响应体错误码 + 响应体结构（不断言业务数据变更）
        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertNotNull(response.getBody());
        assertTrue(response.getBody().contains("\"code\":\"0000\""));
        assertTrue(response.getBody().contains("\"txnNo\""));
    }

    /**
     * 反向用例骨架：每个错误码复制一份
     * 断言：HTTP {{http_status}} + 响应体 code={{error_code}} + 响应体结构含 code/message
     */
    @Test
    @DisplayName("{{rule_id}}-{{negative_description}}")
    void shouldReturn{{error_code}}OnInvalidRequest() {
        // given —— 契约 mock 桩：错误响应
        wireMock.stubFor(post(urlEqualTo("{{contract_path}}"))
                .willReturn(aResponse()
                        .withStatus({{http_status}})
                        .withHeader("Content-Type", "application/json")
                        .withBody("{\"code\":\"{{error_code}}\",\"message\":\"{{error_message}}\"}")));

        // when
        ResponseEntity<String> response = restTemplate.postForEntity(
                wireMock.getRuntimeInfo().getHttpBaseUrl() + "{{contract_path}}",
                {{request_body_invalid}},
                String.class);

        // then —— 断言 HTTP 状态码 + 响应体错误码 + 响应体结构
        assertEquals(HttpStatus.valueOf({{http_status}}), response.getStatusCode());
        assertNotNull(response.getBody());
        assertTrue(response.getBody().contains("\"code\":\"{{error_code}}\""));
        assertTrue(response.getBody().contains("\"message\""));
        // 注意：契约测试不断言真实业务数据变更（如余额扣减），那是单测的职责
    }

    // ===== 为该接口每个错误码复制上方反向用例骨架 =====
    // 示例（银行转账，参考实践方案文档 8.4 节）：
    //   CT-01 正常转账       -> 200 code=0000                  [R6]
    //   CT-02 金额为0       -> 400 INVALID_AMOUNT              [R1]
    //   CT-03 金额为负      -> 400 INVALID_AMOUNT              [R1]
    //   CT-04 转出账号不存在 -> 404 ACCOUNT_NOT_FOUND           [R2]
    //   CT-05 转出账号冻结   -> 403 ACCOUNT_FROZEN             [R3]
    //   CT-06 余额不足       -> 422 INSUFFICIENT_BALANCE        [R4]
    //   CT-07 转入账号不存在 -> 404 ACCOUNT_NOT_FOUND           [R5]
    //   CT-08 自转账         -> 400 SELF_TRANSFER_NOT_ALLOWED  [R7]
}
