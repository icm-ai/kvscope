---
id: phase-10b-local-runner-boundary
title: "Phase 10b 本地外部 runner 边界"
category: decision
status: active
tags: [calibration, phase-10b]
created: "2026-08-28T07:55:26"
updated: "2026-08-28T07:55:26"
---

<!-- compiled_truth -->
## 决定

Phase 10b 允许显式 opt-in 的本地外部 runner 采集运行时峰值内存。核心库仍保持轻量，不依赖或导入 torch、transformers、vLLM、CUDA，也不执行远程模型代码。

## 边界

- runner 只运行用户明确指定的本地命令；不自动下载模型、不访问网络、不启动未声明的后端。
- 采集产物必须是可导入的版本化 calibration record，并保留命令、环境和原始 evidence。
- 拟合只能生成待审核候选 profile；未经人工审核和显式发布，绝不修改现有 profile。
- 自动调优仍不在范围内。

## 影响

该决定解除“完全不做 benchmark / backend 启动”的旧限制，但只对受控的本地 Phase 10b runner 例外。


## Timeline

- time: 2026-08-28T07:55:26
  kind: decision
  summary: "Created this page: Phase 10b 本地外部 runner 边界"
  source: "用户在 2026-06-22 的范围确认"
  affects: [phase-10b-local-runner-boundary]

- time: 2026-08-28T07:55:26
  kind: decision
  summary: "记录用户批准的 opt-in 本地 runner 范围"
  source: "用户确认选项 1"
  affects: [phase-10b-local-runner-boundary]
