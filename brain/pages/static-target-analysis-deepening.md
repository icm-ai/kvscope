---
id: static-target-analysis-deepening
title: "单目标静态分析编排深化"
category: decision
status: active
tags: [architecture, analysis, refactoring]
created: "2026-10-03T18:35:32"
updated: "2026-10-08T07:44:31"
---

<!-- compiled_truth -->
## 决定与理由

静态分析的共享计算与 provenance 归属 engines 内的共同 module，通过准备 workload 与评估 target 的 seam 供 analyze、compare、sweep 复用。目标是集中计算政策、减少重复，而非只移动文件或建立通用 CLI 框架。

## 长期约束

- recommendation 复用 baseline 已计算的 estimates；跨目标共享权重不得退化为逐目标重算，也不引入全局缓存。
- 保持报告与公开 interface、公式、profile、证据/警告/诊断顺序及调用方输入顺序。共同计算不代表各入口应统一异常优先级；CLI 与 comparison 的既有错误路径必须分别保留。
- MoE active 参数描述每 token 计算量，不是驻留权重；内存估算仍使用总参数量。
- 架构验收除质量门禁外，还需证明政策真正集中、跨入口行为等价和计算复用；测试全绿不能单独证明 module 的 depth 与 locality 得到改善。

## 关联

身份投影边界见 [[reproducible-experiment-identity]]；保留 [[multi-target-deployment-comparison]]、[[workload-sensitivity-sweep]] 与 [[moe-weight-analysis]] 的业务边界。


## Timeline

- time: 2026-10-03T18:35:32
  kind: decision
  summary: "Created this page: 单目标静态分析编排深化"
  source: "用户选择按顺序实施架构候选，先实施第一个，并要求独立验收与审阅"
  affects: [static-target-analysis-deepening]

- time: 2026-10-03T18:35:32
  kind: decision
  summary: "记录用户选择的首项架构改造及行为兼容要求"
  source: "本轮架构实施交接请求"
  affects: [static-target-analysis-deepening]

- time: 2026-10-03T20:43:29
  kind: decision
  summary: "保留首项交接安排；更新后续候选授权状态为③④独立worktree并行实施"
  source: "用户要求提供③④与首项相同规格的文件化实施提示词"
  affects: [static-target-analysis-deepening]

- time: 2026-10-08T07:44:31
  kind: decision
  summary: "移除已结束的实施安排，保留长期决策、理由与兼容/验证边界"
  source: "用户确认按Brain保留与归档建议整理"
  affects: [static-target-analysis-deepening]
