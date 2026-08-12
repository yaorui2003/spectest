# Speckit Testing 扩展

> Spec 驱动测试先行验证，含 `@Spec` 注解追溯与自动门禁。

## 概述

本扩展为 spec-kit 增加"Spec 驱动测试先行"能力，通过 4 个命令 + 2 个强制钩子
+ 5 个代码/文档模板 + `@Spec` 注解，实现 **Spec-Code-Test 三角一致性**
自动校验。

核心理念：**Spec 是唯一事实来源，contracts 是测试与代码的共同输入，
测试先行，`@Spec` 注解打通追溯链路。**

## 命令

| 命令 | 触发方式 | 作用 |
|------|----------|------|
| `/speckit.testing.impact` | 手动 / `before_plan` 钩子（自动） | 变更影响分析 + 风险分级 + 受影响规则编号 |
| `/speckit.testing.plan` | 手动（plan 之后、tasks 之前） | 测试计划文档（用例清单 + 验收阈值） |
| `/speckit.testing.gate` | 手动 / `after_implement` 钩子（自动） | 单测 + 契约测试 + @Spec 扫描 + 一致性校验 |
| `/speckit.testing.report` | 手动（gate 通过后） | 测试结果 + Spec 追溯矩阵 |

## 钩子

| 钩子 | 时机 | 绑定命令 | optional |
|------|------|----------|----------|
| `before_plan` | `speckit.plan` 执行前 | `speckit.testing.impact` | false（自动） |
| `after_implement` | `speckit.implement` 执行后 | `speckit.testing.gate` | false（自动） |

## 全链路流程

```
spec.md 更新
  └─[before_plan 自动]─> testing.impact（影响分析 + 风险分级）
      └─> speckit.plan（生成 contracts/）
          └─> testing.plan（测试计划，手动）
              └─> speckit.tasks（带 [R1]..[Rn] 标签的任务）
                  └─> speckit.implement（契约测试 -> 单测 -> 业务代码 @Spec）
                      └─[after_implement 自动]─> testing.gate（门禁）
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

## 配套预设 testing-tdd

扩展只加新能力（命令/钩子/扫描），**不改 spec-kit 核心行为**。要让
`/speckit.constitution` 自动预置 Principle VI、`/speckit.tasks` 强制 TDD
（消灭核心 "Tests OPTIONAL"）、`/speckit.implement` 强制 @Spec + 引用模板，
需配套安装 `testing-tdd` 预设：

| 覆盖 | 策略 | 作用 |
|------|------|------|
| `constitution-template` | replace | 预置 Principle VI（Spec Traceability） |
| `tasks-template` | replace | 测试 REQUIRED，消灭 OPTIONAL 矛盾，测试任务前置 |
| `speckit.implement` 命令 | append | 强制 @Spec 注解 + resolve java-service-template 等模板 |

详见 `presets/testing-tdd/`。

## 安装

两种方式：

**方式 A（推荐，dev 直装，调试期快速迭代）**：

```bash
# 装扩展
specify extension add --dev <spec-kit>/extensions/testing
# 装配套预设
specify preset add --dev <spec-kit>/presets/testing-tdd --priority 10
```

**方式 B（bundle 一键装，发布期）**：

```bash
specify bundle install speckit-testing   # 一键装扩展 + 预设
```

> 调试期建议方式 A（改源码直接生效，无需重装）。

## 配置

门禁阈值与风险分级配置于
`.specify/extensions/testing/testing-config.yml`（首次安装时从模板复制）。

| 风险 | 行覆盖率 | 单测通过率 | 契约通过率 |
|------|----------|------------|------------|
| high | >=90% | 100% | 100% |
| medium | >=80% | 100% | >=95% |
| low | >=70% | 100% | >=95% |

## 宪法依据

本扩展的治理基础是项目宪法 Principle VI（Spec Traceability）：
所有业务代码 MUST 用 `@Spec` 注解标注其实现的 Spec 规则。

## 许可证

MIT
