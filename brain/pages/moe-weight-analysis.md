---
id: moe-weight-analysis
title: "静态 MoE 权重分析边界"
category: decision
status: active
tags: [moe, weights, analysis]
created: "2026-10-03T09:48:03"
updated: "2026-10-03T09:48:03"
---

<!-- compiled_truth -->
## Decision

When MoE metadata is available, feasibility reports expose total parameters, active parameters per token, expert count, and selected experts per token as separate structural facts. The resident weight estimate continues to use total parameter count; active parameter count is not converted into an active/resident VRAM estimate.

## Boundaries

- Include the optional MoE analysis in analyze, compare, and sweep feasibility reports when expert or active-parameter metadata is available.
- The report is explanatory metadata only and must not reduce resident weight bytes or alter feasibility calculations.
- State that all model weights are treated as resident unless an explicit offload model is supplied; this feature does not model expert placement, offload, routing execution, or benchmark behavior.
- Validate active parameter count against total count and selected-expert count against total experts through the existing ModelSpec validation boundary.

## Rationale

Per-token activated parameters describe computation, not which expert weights are resident in device memory. Conflating them would understate memory requirements for ordinary deployments where all experts are loaded.


## Timeline

- time: 2026-10-03T09:48:03
  kind: decision
  summary: "Created this page: 静态 MoE 权重分析边界"
  source: "用户确认静态 MoE 权重分析接口与边界"
  affects: [moe-weight-analysis]

- time: 2026-10-03T09:48:03
  kind: decision
  summary: Record the agreed MoE metadata report and total-parameter residency rule.
  source: User approved MoE analysis seam and output boundary
  affects: [moe-weight-analysis]
