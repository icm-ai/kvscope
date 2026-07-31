# KVScope Recommendation Engine Specifications

## Overview

The Phase 8 **Recommendation Engine** analyzes Phase 7 structured `MemoryFeasibilityReport` and `ConstraintAnalysis` results to generate counterfactual configuration modification candidates and safe parameter capacity limits.

Recommendations are purely advisory; KVScope **never** automatically applies, executes, or writes back configurations.

---

## Core Design Rules

1. **Structured Input Only**: Recommendation logic relies exclusively on structured domain status, constraint codes, budget ranges, and re-computation contexts. Text warning parsing is strictly forbidden.
2. **Forward Engine Verification**: Every proposed parameter candidate is re-calculated through forward calls to Phase 1–7 engines (`estimate_kv_cache`, `estimate_weight_memory`, `estimate_runtime_overhead`, `assess_memory_feasibility`).
3. **Pure Functions**: Input context objects (`InferenceConfig`, `ModelSpec`, etc.) are never mutated.
4. **Partial Safeguards**: If `aggregation.is_partial` is True or feasibility status is `UNKNOWN`, `RecommendationEligibility` is `INELIGIBLE`. Numeric context/sequence values are suppressed, and `COMPLETE_ESTIMATE_REQUIRED` is emitted.
5. **Low-Confidence Safeguards**: Baseline reports with `LOW` or `UNKNOWN` confidence yield `ADVISORY_ONLY` eligibility. Candidates carry low-confidence warnings and cannot use `REQUIRED` or `STRONG` strength.
6. **Default Budget Target**: Parameter back-solving defaults to `recommended_allocatable`. `ALLOCATABLE_CEILING` is marked as experimental.

---

## Recommendation Actions

| Action Code | Description | Tradeoffs |
| :--- | :--- | :--- |
| `reduce_context_length` | Reduces text context length to fit within safe KV budget. | Context window size reduced. |
| `reduce_active_sequences` | Reduces active sequence concurrency. | Serving concurrency and throughput reduced. |
| `change_kv_dtype` | Switches KV Cache storage data type (e.g., FP16 to FP8). | Precision impact; backend kernel dependency. |
| `change_weight_dtype` | Quantizes resident model weights (e.g., FP16 to INT4). | Output model quality impact; artifact required. |
| `disable_graph_capture` | Disables backend CUDA/HIP graph capture. | CPU launch overhead increased. |
| `complete_estimate_required` | Emitted when baseline estimate is partial. | N/A |
| `no_change_required` | Emitted when baseline configuration is guaranteed feasible. | N/A |

---

## Python API Usage

```python
from kvscope import (
    generate_recommendations,
    RecommendationContext,
    RecommendationPolicy,
)

report = generate_recommendations(
    context=recommendation_context,
    baseline_report=feasibility_report,
    policy=RecommendationPolicy(
        target_budget="recommended",
        target_safety_level="expected_safe",
    ),
)

print(report.primary_recommendation)
```

---

## Verification & Eligibility Distinction

- **Candidate Verification (`verification_status = VERIFIED`)**: Describes computational validation (mathematical re-computation passed via Phase 1–7 forward engines).
- **Recommendation Eligibility (`eligibility = ADVISORY_ONLY`)**: Describes trust in the underlying inputs (e.g. low-confidence hardware/backend profiles).

Candidate verification and advisory-only eligibility can coexist when computational re-calculation is verified, but underlying input confidence requires advisory-only guidance.

