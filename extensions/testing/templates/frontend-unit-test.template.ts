/**
 * Vitest + @vue/test-utils + happy-dom 单测参考骨架（speckit.testing 提供）。占位符 {{var}} 由 AI 填充。
 *
 * 技术栈（MUST）：
 * - vitest + @vue/test-utils + happy-dom（DOM 环境用 happy-dom，禁真实浏览器/Chromium 起容器）
 * - 安装：npm i -D vitest @vue/test-utils happy-dom；package.json 加 "test": "vitest run"
 * - 组件引用 .vue 需 vitest/vite 插件解析（@vitejs/plugin-vue），Vite 项目开箱可用
 *
 * 追溯规范（MUST）：describe("R<n>-<规则描述>", ...) 对齐 spec.md Business Rules 编号。
 * @Spec 注解仅限 Java 业务代码；前端不注解，用 describe 命名规范对齐（设计定案）。
 *
 * 弱断言禁令（MUST）：每条用例必须有具体业务语义断言
 * （expect(wrapper.text()).toContain(...) / toHaveBeenCalledWith / toBe(...)），禁仅 expect(...).toBeTruthy()。
 *
 * 覆盖三类（前端改动 MUST 覆盖对应层）：
 *   a) api 层：pipelineWs 连接 / 断连 / 降级轮询（mock @stomp/stompjs Client）
 *   b) 组件层：AgentScopeWorkbench 状态聚合（挂载 -> 推事件 -> 断言渲染）、
 *      PipelineReport 渲染、按钮禁用态
 *   c) 工具层：纯函数
 *
 * 执行：npm test（vitest run）
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';

// TODO: 替换为实际模块路径（如 '@/api/index'）
import { pipelineWs } from '{{api_module_path}}';

// mock @stomp/stompjs Client：不依赖真实 WebSocket 连接（确定性测试）
vi.mock('@stomp/stompjs', () => ({
  Client: vi.fn(() => ({
    activate: vi.fn(),
    deactivate: vi.fn(),
    subscribe: vi.fn().mockReturnValue({ id: 'sub-{{n}}' }),
    publish: vi.fn(),
  })),
}));

// ===== a) api 层：pipelineWs 连接 / 断连 / 降级轮询 =====
describe('R{{n}}-{{规则描述}}：pipelineWs 连接 / 断连 / 降级轮询', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // TODO: 替换为实际初始化（新建 Client 实例并连接）
    pipelineWs.connect({ sessionId: '{{session_id}}' });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    pipelineWs.disconnect();
  });

  it('连接成功 -> 订阅会话 topic', () => {
    // when -- 触发 STOMP onConnect 回调
    // TODO: 替换为实际触发方式（如 pipelineWs 内部回调 / 注入事件）

    // then -- 断言订阅了正确 topic（业务语义，禁仅 toBeTruthy）
    expect(pipelineWs.{{stomp_client}}.subscribe).toHaveBeenCalledWith(
      '/topic/browser-session/{{session_id}}',
      expect.any(Function),
    );
  });

  it('断连 -> 清理订阅并置空闲', () => {
    // when -- 主动断连
    pipelineWs.disconnect();

    // then -- 断言状态回退 + 连接释放
    expect(pipelineWs.{{state_field}}).toBe('idle'); // TODO: 替换为实际状态字段/枚举
    expect(pipelineWs.{{stomp_client}}.deactivate).toHaveBeenCalled();
  });

  it('连接失败 -> 降级为轮询（确定性，不等待真实网络）', () => {
    // when -- 触发 onStompError / 连接超时
    // TODO: 替换为实际降级触发方式
    vi.advanceTimersByTime({{poll_interval_ms}});

    // then -- 断言降级轮询已启动（业务语义）
    expect(pipelineWs.{{polling_flag}}).toBe(true); // TODO: 替换为实际降级标识
  });
});

// ===== b) 组件层：状态聚合与渲染 =====
// TODO: 替换为实际组件路径（如 '@/components/AgentScopeWorkbench.vue'）
import AgentScopeWorkbench from '{{component_path}}';
import PipelineReport from '{{pipeline_report_path}}';

describe('R{{n}}-{{规则描述}}：AgentScopeWorkbench 状态聚合', () => {
  it('挂载 -> 推送 WS 事件 -> 断言状态渲染', async () => {
    // given -- 挂载组件，stub 子组件隔离依赖
    const wrapper = mount(AgentScopeWorkbench, {
      props: { sessionId: '{{session_id}}' },
      global: { stubs: { EmbeddedBrowser: true, PipelineReport: true } },
    });

    // when -- 推入一条 WS 事件（模拟后端推送）
    // TODO: 替换为实际事件源（如 pipelineWs.onMessage 回调 / 组件方法）
    await wrapper.vm.$nextTick();

    // then -- 断言具体状态文案渲染（弱断言禁令：禁仅 toBeTruthy）
    expect(wrapper.text()).toContain('{{预期状态文案}}');
  });

  it('运行中 -> 操作按钮禁用', async () => {
    const wrapper = mount(AgentScopeWorkbench, {
      props: { sessionId: '{{session_id}}' },
      global: { stubs: { EmbeddedBrowser: true, PipelineReport: true } },
    });

    // given -- 处于运行中状态
    await wrapper.setProps({ running: true }); // TODO: 替换为实际 props

    // then -- 断言禁用态（业务语义，禁仅断言按钮存在）
    expect(wrapper.find('button[data-test="start"]').attributes('disabled')).toBeDefined();
  });
});

describe('R{{n}}-{{规则描述}}：PipelineReport 渲染', () => {
  it('传入报告数据 -> 渲染关键指标文案', () => {
    // given -- 报告数据与后端返回结构一致
    const wrapper = mount(PipelineReport, {
      props: {
        // TODO: 替换为实际报告结构（与后端返回一致）
        report: { total: {{total}}, passed: {{passed}}, failed: {{failed}} },
      },
    });

    // then -- 断言具体指标文案（禁仅 toBeTruthy）
    expect(wrapper.text()).toContain('{{预期指标文案，如"通过 12"}}');
  });
});

// ===== c) 工具层：纯函数 =====
// TODO: 替换为实际工具模块路径（如 '@/utils/format'）
import { {{util_fn}} } from '{{utils_module_path}}';

describe('R{{n}}-{{规则描述}}：{{util_fn}} 纯函数', () => {
  it('正常输入 -> 期望输出', () => {
    expect({{util_fn}}({{input_fixture}})).toEqual({{expected_output}});
  });

  it('边界输入 -> 期望兜底', () => {
    expect({{util_fn}}({{edge_input}})).toBe({{expected_fallback}});
  });
});

/**
 * 自检清单：
 * - [ ] 每条 describe 命名 R<n>-<规则描述> 对齐 spec.md Business Rules 编号
 * - [ ] api / 组件 / 工具三层各自至少 1 条用例（仅涉及单层时可裁剪并说明）
 * - [ ] 无弱断言：每条 it 至少一个 toContain / toBe / toHaveBeenCalledWith 等具体断言
 * - [ ] 外部依赖（WS / HTTP / 定时器）全部 mock，禁真实网络
 */
