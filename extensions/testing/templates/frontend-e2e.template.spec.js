/**
 * Playwright 确定性 e2e 参考骨架（speckit.testing 提供）。占位符 {{var}} 由 AI 填充。
 *
 * 确定性约定（MUST，前端 e2e 为可选实施；如实施必须遵守）：
 * - 禁真实外部依赖：一切不稳定外部依赖（HTTP API / WebSocket 推送 / 第三方
 *   AI 接口等）必须拦截并注入固定数据，按项目实际选择拦截目标：
 *   * 通用主路径：HTTP API 经 page.route 返回固定 JSON（页面 API 请求）；
 *   * 仅当项目有 WS 推送：WS 事件经固定序列注入（page.routeWebSocket /
 *     STOMP mock / stub 后端），禁等待真实推送；
 *   * 仅当项目有第三方 AI/LLM 接口：才需要 stub 它（route 固定 JSON 或后端起
 *     stub 模式），没有则不 stub。
 * - 超时断言：每个 waitFor/toBeVisible 带显式超时；断言"出现/消失"双向成对
 *   （await expect(locator).toBeVisible({ timeout: 5000 }) 与 await expect(locator).toBeHidden()）。
 * - 用例结构引用 e2e-case-template（GWT：Given/When/Then）生成的 functional case set，
 *   预期文案与后端契约错误码一致。
 * - 用例元数据：每条用例注释 // covered_rules: FR-001,FR-002 供选择执行解析。
 *
 * 选择执行（7.6 / 9.9）：impact 受影响规则与用例 covered_rules 求交后只跑命中用例，
 * 避免全量慢跑：
 *   npx playwright test --grep TC-01
 * 多用例：npx playwright test --grep "TC-01|TC-02"
 * 真实链路 e2e（连真实后端/第三方）仅手工/定时慢跑，不进门禁。
 */
const { test, expect } = require('@playwright/test');

/**
 * TC-01 {{场景标题}}
 * covered_rules: FR-001,FR-002
 * 来源：impact-report.md 功能测试案例集（e2e-case-template 生成）
 */
test('TC-01 {{场景标题}}', async ({ page }) => {
  // Given -- 前置条件：页面 API 请求 stub 为固定 JSON（通用主路径）
  await page.route('**/api/**', (route) =>
    route.fulfill({
      // TODO: 替换为后端实际路径与响应结构（固定值，与契约错误码一致）
      json: { code: '{{error_code}}', message: '{{固定提示文案}}' },
    }),
  );

  // When -- 用户操作步骤（按 e2e-case-template 的 When 序列）
  await page.goto('/{{route_path}}');
  await page.getByPlaceholder('{{输入框占位文案}}').fill('{{具体输入值}}');
  await page.getByRole('button', { name: '{{按钮文案}}' }).click();

  // Then -- 断言出现（显式超时，文案与后端契约一致）
  await expect(page.getByText('{{预期提示文案}}')).toBeVisible({ timeout: 5000 });
  // Then -- 断言消失（双向成对）
  await expect(page.getByTestId('{{loading_element}}')).toBeHidden({ timeout: 5000 });
});

/**
 * TC-02 {{场景标题}}（仅当项目有 WS 推送时的扩展示例，无 WS 则删除本用例）
 * covered_rules: FR-001,FR-007
 */
test('TC-02 {{场景标题}}', async ({ page }) => {
  // Given -- WebSocket 固定序列注入（确定性；需 Playwright >= 1.48 的 routeWebSocket）
  await page.routeWebSocket('**/ws/**', (ws) => {
    // TODO: 按固定序列回发业务帧（CONNECTED / MESSAGE / ERROR），禁真实后端推送
    ws.onMessage(() => {
      // 示例：首次连接回 CONNECTED，随后回业务事件帧（按用例需要扩展）
      ws.send('{"frame":"CONNECTED"}');
    });
  });

  // Given -- 或后端起 stub 模式（application-test.yml + @MockBean 对应 Service，二选一）
  await page.goto('/{{route_path}}');

  // When -- 触发依赖 WS 事件的用户操作
  await page.getByRole('button', { name: '{{按钮文案}}' }).click();

  // Then -- 断言出现 / 消失双向（显式超时）
  await expect(page.getByText('{{预期状态文案}}')).toBeVisible({ timeout: 5000 });
  await expect(page.getByText('{{预期消失文案}}')).toBeHidden({ timeout: 5000 });
});

/**
 * TC-03 {{场景标题}}（异常路径：后端错误码 -> 前端提示）
 * covered_rules: FR-002,FR-004
 */
test('TC-03 {{场景标题}}', async ({ page }) => {
  // Given -- 后端返回契约错误码（与 spec.md Error Code Definitions 一致）
  await page.route('**/api/**', (route) =>
    route.fulfill({
      status: 400,
      // TODO: 替换为实际错误响应结构
      json: { code: '{{error_code}}', message: '{{固定错误文案}}' },
    }),
  );

  await page.goto('/{{route_path}}');

  // When -- 触发会失败的提交操作
  await page.getByRole('button', { name: '{{按钮文案}}' }).click();

  // Then -- 断言错误提示出现（显式超时）+ 提交按钮恢复可用（消失双向）
  await expect(page.getByText('{{固定错误文案}}')).toBeVisible({ timeout: 5000 });
  await expect(page.getByTestId('{{loading_element}}')).toBeHidden({ timeout: 5000 });
});

/**
 * 自检清单：
 * - [ ] 每条用例注释 // covered_rules: FR-xxx,... 且规则存在于 impact 受影响规则（顶层锚 FR-xxx 格式）
 * - [ ] 选择器与 impact 案例集"组件"字段一致（testid 优先，前端有 data-testid 必须用）
 * - [ ] 无真实外部依赖调用：HTTP API / WS / 第三方接口均已 stub（按项目实际）
 * - [ ] 每个可见断言带显式 timeout，出现/消失断言成对
 * - [ ] 预期文案与后端契约错误码一致，无含糊表述
 */
