# Speckit Testing 扩展

> Spec 驱动测试先行验证，含 `@Spec` 注解追溯、自动门禁（脚本化）与对抗测试。
> 版本 1.1.2（v0.4.x 维护：#5 禁改门禁脚本 + #6 bash/ps @Repeatable 修复 + #1 error_codes 噪声修复 + 审计 P1 反向 @Spec->DisplayName 检查 + P4 bash/ps @Spec parity 补全）。

## 概述

本扩展为 spec-kit 增加"Spec 驱动测试先行"能力，通过 4 个命令 + 2 个强制钩子
+ 5 个代码/文档模板 + 5 组三语言脚本（含 `run_gate` 门禁编排）+ `@Spec` 注解，
实现 **Spec-Code-Test 三角一致性**自动校验。

核心改造（v0.4）：**门禁全脚本化**--`run_gate` 把 gate 的全部确定性逻辑
（mvn clean test + 4 步校验 + 阈值比对 + PASS/FAIL 判定 + 写 gate-result.md）
下沉到脚本，AI 仅读 stdout 判定 JSON 不能改判，直击试点 P0「Agent 伪造覆盖率」。

核心理念：**Spec 是唯一事实来源，contracts 是测试与代码的共同输入，
测试先行，`@Spec` 注解打通追溯链路，门禁由脚本判定不由 AI 自报。**

## 命令

| 命令 | 触发方式 | 作用 |
|------|----------|------|
| `/speckit.testing.impact` | 手动 / `after_implement` 钩子（自动，impact 在前） | 变更影响分析 + 风险分级 + 受影响规则编号 |
| `/speckit.testing.plan` | 手动（plan 之后、tasks 之前） | 测试计划文档（用例清单 + 验收阈值） |
| `/speckit.testing.gate` | 手动 / `after_implement` 钩子（自动，gate 在后） | AI 调 `run_gate` 脚本（全逻辑下沉）+ 仅读结果判定 PASS/FAIL |
| `/speckit.testing.report` | 手动（gate 通过后） | 测试结果 + Spec 追溯矩阵 |

## 钩子

| 钩子 | 时机 | 绑定命令 | optional |
|------|------|----------|----------|
| `after_implement` | `speckit.implement` 执行后 | `speckit.testing.impact` -> `speckit.testing.gate`（列表形式，按序执行） | false（自动） |

## 全链路流程

```
spec.md 更新
  └─> speckit.plan（生成 contracts/ + plan.md + data-model.md）
      └─> testing.plan（测试计划，手动，依赖已有 md）
          └─> speckit.tasks（骨架先行 -> 单测任务 -> 契约测试任务 -> 业务代码）
              └─> speckit.implement
                  ├─ 1. 骨架（mvn compile 通过）
                  ├─ 2. 单测（JUnit5 + Mockito，@DisplayName 标规则，先 Red）
                  ├─ 3. 契约测试（WireMock + HTTP 客户端调用 + 断言响应，不起容器）
                  ├─ 4. 业务代码（@Spec 注解，TDD 让测试 Green）
                  └─ 5.【第 4.5 阶段·对抗测试 + 覆盖率达标，可选】
                      ├─ 调 run_gate --check-only 跑覆盖率自检
                      ├─ 第 1 轮：四类对抗（反例/边界/异常路径/并发竞态）
                      ├─ 第 2 轮起：目的性覆盖率补洞（辅助类/未覆盖分支）
                      ├─ 关键路径必测：high 风险规则方法 MUST 至少 1 条对抗用例
                      └─ 循环上限 max_iterations（默认 3），超限如实进 gate FAIL
                  └─[after_implement 自动]─> testing.impact（影响分析 + 风险分级）
                      └─> testing.gate（AI 调 run_gate 脚本：mvn clean test + 4 步校验
                          + 阈值比对 + 脚本写 gate-result.md，AI 仅读结果）
                          └─ PASS ─> testing.report（追溯矩阵，手动）
```

## @Spec 注解

业务代码用 `@Spec` 注解标注其实现的 Spec 规则：

```java
@Spec(capability = "transfer", rule = "R1", description = "金额校验")
public TransferResult transfer(...) { ... }
```

门禁通过扫描 `@Spec` 注解自动校验"Spec 规则 -> 代码实现"覆盖完整性，
单测侧通过 `@DisplayName("R1-...")` 实现双向对齐。

## 测试技术栈（必需前置）

本扩展门禁针对 Java 项目，以下技术栈为**必需前置条件**：

| 组件 | 作用 | 必需性 |
|------|------|--------|
| JUnit 4/5 | 测试框架 | REQUIRED |
| Mockito | Mock 依赖（@Mock / @InjectMocks） | REQUIRED |
| Surefire | 测试执行 + surefire-reports 生成 | REQUIRED |
| JaCoCo | 覆盖率插桩（line/branch/method/instruction/complexity） | REQUIRED |

**禁用**：PowerMock（覆盖率失真）、`@SpringBootTest` 起容器。

> 缺 JaCoCo/surefire 报告 -> 门禁 FAIL（不降级）。输出 pom.xml 配置参考。
> 唯一降级：非 Java 项目（无 java/mvn）-> @Spec 静态扫描。

## 门禁脚本化（run_gate，v0.4 核心）

v0.3 的 gate 由 AI 编排 4 个脚本 + AI 比对阈值 + AI 写 gate-result.md，试点证明
AI 会伪造（声称 96% 实际 62.9%）。v0.4 把 gate 的**全部确定性逻辑下沉到
`run_gate` 脚本**（三语言 sh/ps/py 字节级等价），AI 仅读结果不能改判：

| 维度 | v0.3（AI 编排） | v0.4（脚本编排） |
|---|---|---|
| mvn test | AI 跑 | run_gate 跑，强制 `mvn clean test`（杜绝 target 残留污染） |
| 4 脚本调用 | AI 逐个调 | run_gate 内部串行调 |
| @DisplayName 解析 | AI 解析 | run_gate 内联解析 |
| 阈值比对 / PASS/FAIL 判定 | AI | run_gate |
| gate-result.md 写入 | AI 写 | run_gate 脚本直接写 |
| AI 角色 | 全权 | 仅读 stdout JSON + 按判定输出指令 |

`run_gate` 9 步职责：0.检查 impact-report.md 存在 / 1.mvn clean test /
2.scan_test_stack / 3.parse_test_results / 4.scan_spec_annotations /
5.内联解析 @DisplayName / 6.读 risk_level+config / 7.逐项比对阈值 /
8.写 gate-result.md + stdout 输出判定 JSON。

`run_gate --check-only` 子模式：供 implement 第 4.5 阶段对抗测试调用，
只跑不写，输出覆盖率与阈值差距 JSON。

> 直击 P0：#1 Agent 伪造覆盖率（脚本判定）/ #2 target 残留污染（强制 clean）
> / #3 impact 未生成（前置检查 impact-report.md 存在）。
> 注：脚本化是"给 AI 真实数据 + 降低伪造难度 + 可审计"，非硬强制（AI 仍可不
> 调脚本而自行声称，真正强制需改执行模型）。

## 对抗测试（v0.4 新增）

在常规 TDD 用例（正常/异常/边界）之外，AI 主动生成的"试图攻破自己代码"的
补充用例集。目标：用真实测试数据把 JaCoCo 覆盖率推到套用阈值，而非堆砌通过用例。

| 轮次 | 目的 | 用例类型 |
|---|---|---|
| 第 1 轮 | 攻破自己代码 | 反例/边界/异常路径/并发竞态（仅 high 风险规则） |
| 第 2 轮 | 目的性覆盖率补洞 | 辅助类（DTO/枚举/异常处理器/Controller）+ 未覆盖分支 |
| 第 3 轮 | 兜底 | 继续补洞 + 可选重构 |

**关键路径必测**（独立 MUST，与 gate 阈值脱钩）：impact 标记 high 风险规则
（资金/权限/原子性/数据完整性）的 public 方法 MUST 至少 1 条对抗用例。

## 配套预设 testing-tdd

扩展只加新能力（命令/钩子/扫描），**不改 spec-kit 核心行为**。要让
`/speckit.constitution` 自动预置 Principle I（Spec Traceability，置首）、
`/speckit.tasks` 强制 TDD
（消灭核心 "Tests OPTIONAL"）、`/speckit.implement` 强制 @Spec + 引用模板，
需配套安装 `testing-tdd` 预设：

| 覆盖 | 策略 | 作用 |
|------|------|------|
| `constitution-template` | replace | 预置 Principle I（Spec Traceability 置首）+ Principle II（中文文档 + 代码重要部分中文注释，v0.4 扩展） |
| `spec-template` | replace | 加 `## Business Rules`（REQUIRED）+ Error Code Definitions（可选） |
| `tasks-template` | replace | 测试 REQUIRED + 骨架先行 + 单测先行 + 双标签 `[US1] [R1]`（v0.4） |
| `speckit.implement` 命令 | append | 强制 @Spec 注解 + 约定参考 + 技术栈 + 单测先行 + 第 4.5 阶段对抗测试（v0.4） |

详见 `presets/testing-tdd/`。

## 安装

三种方式，任选其一：

**方式 A（直装，推荐给终端用户，装在任何标准 spec-kit 上）**：

```bash
# 装扩展
specify extension add testing \
  --from https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-1.1.2.zip
# 装配套预设（预设会 replace 核心模板：宪法 / spec-template / tasks / implement）
specify preset add testing-tdd \
  --from https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-tdd-1.1.2.zip
```

> `extension add --from` 对非 catalog 来源会弹"Untrusted Source"确认，属正常安全提示，
> 按 `y` 继续即可。

**方式 A'（大陆网络备选，GitHub 直连被墙时）**：`--from` 用 python 下载且无重试，
大陆网络下可能超时。改用 curl（自动重试）下载 + `--dev` 本地安装：

```bash
# 下载并解压（--retry 应对间歇性连接失败）
curl -fsS --retry 8 --retry-all-errors -o /tmp/ext-testing.zip \
  https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-1.1.2.zip
curl -fsS --retry 8 --retry-all-errors -o /tmp/ext-preset.zip \
  https://raw.githubusercontent.com/yaorui2003/spectest/main/releases/testing-tdd-1.1.2.zip
mkdir -p /tmp/ext-testing /tmp/ext-preset
python3 -c "import zipfile; zipfile.ZipFile('/tmp/ext-testing.zip').extractall('/tmp/ext-testing')"
python3 -c "import zipfile; zipfile.ZipFile('/tmp/ext-preset.zip').extractall('/tmp/ext-preset')"

# 安装（注意 --dev 是 flag，路径作参数）
specify extension add /tmp/ext-testing --dev
specify preset add testing-tdd --dev /tmp/ext-preset --priority 10
```

> 也可在 `/etc/hosts` 固定 `185.199.111.133 raw.githubusercontent.com` 提升 raw 直连
> 稳定性（需 sudo，一次性）。GitHub Release 版 URL：
> `https://github.com/yaorui2003/spectest/releases/download/v1.1.2/testing-1.1.2.zip`。

**方式 B（dev 直装，调试期快速迭代）**：

```bash
# 装扩展
specify extension add --dev <spec-kit>/extensions/testing
# 装配套预设
specify preset add --dev <spec-kit>/presets/testing-tdd --priority 10
```

**方式 C（bundle 一键装，发布期，需扩展与预设已可解析）**：

```bash
specify bundle install speckit-testing   # 一键装扩展 + 预设
```

> 调试期建议方式 B（改源码直接生效，无需重装）。

## 卸载 / 切回普通 spec-kit

在任意标准 spec-kit 项目上，装上的东西可干净移除、恢复原样：

```bash
specify preset remove testing-tdd    # 移除预设，宪法/模板恢复 spec-kit 默认
specify extension remove testing     # 移除扩展，命令/钩子/配置全部卸载
```

> 只想临时停用（保留安装）可用 `specify preset disable testing-tdd` /
> `specify extension disable testing`，随时 `enable` 恢复。
> `extension remove` 同样有确认提示，按 `y` 继续。

## 配置

门禁阈值与风险分级配置于
`.specify/extensions/testing/testing-config.yml`（首次安装时从模板复制）。

| 风险 | 行覆盖率 | 方法覆盖率 | 指令覆盖率 | 复杂度覆盖率 | 单测通过率 | 契约通过率 |
|------|----------|------------|------------|--------------|------------|------------|
| high | >=90% | >=90% | >=90% | >=80% | 100% | 100% |
| medium | >=80% | >=80% | >=85% | >=70% | 100% | >=95% |
| low | >=70% | >=70% | >=80% | >=60% | 100% | >=95% |

v0.4 新增 `adversarial` 段：

```yaml
adversarial:
  enabled: true              # 是否启用对抗测试阶段（默认 true）
  max_iterations: 3          # 循环上限（默认 3）
  critical_path_required: true # high 风险规则方法 MUST 至少 1 条对抗用例
```

## 产物路径（v0.4 统一）

4 个产物统一存放于 `specs/<feature>/docs/*.md`（废弃 v0.3 的
`.specify/extensions/testing/` 路径）：

| 产物 | 路径 |
|---|---|
| 测试计划 | `specs/<feature>/docs/test-plan.md` |
| 影响报告 | `specs/<feature>/docs/impact-report.md` |
| 门禁结果 | `specs/<feature>/docs/gate-result.md`（run_gate 脚本写） |
| 测试报告 | `specs/<feature>/docs/test-report.md` |

## 宪法依据

本扩展的治理基础是项目宪法 Principle I（Spec Traceability，置首）：
所有业务代码 MUST 用 `@Spec` 注解标注其实现的 Spec 规则。
Principle II（中文文档 + 代码重要部分中文注释）要求高风险规则方法加中文注释
说明业务语义，支撑后续审计与对抗测试定位。

## 许可证

MIT
