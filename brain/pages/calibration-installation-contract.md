---
id: calibration-installation-contract
title: "校准产物的干净安装验收与轻量运行时依赖例外"
category: decision
status: active
tags: [calibration, packaging, verification]
created: "2026-10-05T11:31:51"
updated: "2026-10-08T07:44:31"
---

<!-- compiled_truth -->
## 决定与理由

校准契约必须通过干净、非 editable wheel 的真实安装边界验证。源码 dev 环境可能掩盖未声明依赖，pip check 也不能发现未声明的 import；二者均不能替代已安装 console script、schema 与 profile 资源的验证。

## 依赖与契约边界

- 既有后端版本解析使用轻量库 packaging，必须声明运行时依赖；不得借此扩展为推理后端、重量级库或核心网络访问。
- jsonschema 与 RFC3339 格式支持只属于 dev 依赖，不能进入生产启动路径。FormatChecker 的可选 date-time checker 可能未注册，测试必须验证其实际生效；冻结 Pydantic 模型仍是运行时 authority。
- 规范 schema 与历史兼容 loader 并不完全等价，不为追求静态一致而收紧既有输入。静态 schema 不能代替 strict integer、跨字段 confidence/range、身份与 fit/review 政策。
- runner 结果保留摘要、环境名称与 evidence，不保留命令明文、stdout/stderr 或环境值。accepted review 只绑定候选事实，不自动修改 profile。

## 安装与覆盖率验证

- 依赖 wheelhouse 单独预备；正式构建、安装和校准测试全程离线。安装测试默认执行，缺少预备依赖应失败，不 skip 或使用源码 fallback。
- 从源码外 cwd 运行安装的 console script，证明 import、schema 和 profile 均来自安装环境；验证 analyze → run/export → compare → fit → review 及关键失败路径，并检查 profile 树前后不变。
- 源码子进程进入临时 cwd 时，覆盖率配置必须仍明确指向项目 pyproject.toml；自动发现可能把 branch 与 statement-only 数据混合，使测试全通过而汇总失败。
- 干净安装环境须清除源码 import 与 coverage 注入污染；其测试事实不能冒充源码 coverage 数据。

## 关联

身份与 exact-scope 区分见 [[reproducible-experiment-identity]]；本地 opt-in 执行范围见 [[phase-10b-local-runner-boundary]]。


## Timeline

- time: 2026-10-05T11:31:51
  kind: decision
  summary: "Created this page: 校准产物的干净安装验收与轻量运行时依赖例外"
  source: "用户于2026-10-05确认授权修复④安装阻断及补齐测试"
  affects: [calibration-installation-contract]

- time: 2026-10-05T11:31:51
  kind: decision
  summary: "记录④安装验收规则及用户授权的 packaging 轻量依赖例外"
  source: "用户确认授权；04-independent-review.md 的F1–F3"
  affects: [calibration-installation-contract]

- time: 2026-10-05T19:53:00
  kind: decision
  summary: "记录远程CI暴露的跨cwd子进程覆盖率配置约束"
  source: "CI run 37268486530；本地回归红→绿"
  affects: [calibration-installation-contract]

- time: 2026-10-08T07:44:31
  kind: decision
  summary: "移除已结束的实施安排，保留长期决策、理由与兼容/验证边界"
  source: "用户确认按Brain保留与归档建议整理"
  affects: [calibration-installation-contract]
