---
id: multi-target-deployment-comparison
title: "多目标部署静态对比"
category: decision
status: active
tags: [comparison, feasibility, cli]
created: "2026-10-01T23:33:35"
updated: "2026-10-01T23:46:46"
---

<!-- compiled_truth -->
## Decision

KVScope provides `compare_deployment_targets` and `kvscope compare` to statically assess one resolved model and inference workload against multiple explicitly selected hardware/backend profile pairs.

## Boundaries

- Reuse existing estimation and feasibility engines; do not start inference backends or benchmark hardware.
- Compare explicitly supplied profile pairs, not an implicit hardware/backend Cartesian product.
- Require at least two unique target IDs and apply one identical inference configuration and user reserve to every target.
- Preserve per-target provenance, uncertainty, confidence, constraints, and warnings in the versioned report.
- Preserve caller-supplied target order; do not claim a single winner when uncertainty intervals overlap.
- Comparison describes memory feasibility only, not runtime performance.

## Rationale

A single `analyze` invocation assesses one target. Explicit multi-target comparison helps users choose deployment hardware/backend before runtime validation while staying within KVScope static-analysis scope.


## Timeline

- time: 2026-10-01T23:33:35
  kind: decision
  summary: "Created this page: 多目标部署静态对比"
  source: "用户批准开发多硬件/后端部署方案对比功能"
  affects: [multi-target-deployment-comparison]

- time: 2026-10-01T23:33:35
  kind: decision
  summary: "记录用户批准的多硬件/后端静态对比功能及范围边界"
  source: "用户要求按照建议开始并完成"
  affects: [multi-target-deployment-comparison]

- time: 2026-10-01T23:46:46
  kind: decision
  summary: "将方案收敛为保留输入顺序的显式目标比较，避免重叠区间产生虚假赢家"
  source: "实现过程中确认的不确定区间处理语义"
  affects: [multi-target-deployment-comparison]
