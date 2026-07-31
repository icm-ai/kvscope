# KVScope Recommendation Governance Policy

## Policy Configuration

`RecommendationPolicy` controls the behavior of candidate generation, capacity back-solving, and candidate acceptance/ranking:

```python
class RecommendationPolicy(BaseModel):
    target_budget: RecommendationBudgetTarget = RECOMMENDED
    target_safety_level: RecommendationSafetyLevel = EXPECTED_SAFE
    maximum_candidates: int = 10

    allow_context_reduction: bool = True
    allow_sequence_reduction: bool = True
    allow_kv_dtype_change: bool = True
    allow_weight_dtype_change: bool = True
    allow_disable_graph_capture: bool = True

    require_medium_confidence_for_strong: bool = True
    allow_advisory_candidates: bool = True
    minimum_expected_savings_bytes: int = 1
```

---

## Candidate Acceptance & Rejection Criteria

### Rejection Rules
- `savings.expected_bytes <= 0`: Rejected (`NO_MEMORY_IMPROVEMENT`).
- `after_status_rank > before_status_rank`: Rejected (`STATUS_NOT_IMPROVED`).
- Candidate violates `minimum_context_length` or `minimum_active_sequences`.
- Candidate produces a partial estimate (`CANDIDATE_ESTIMATE_PARTIAL`).

### Deterministic Ranking Order
1. Target Reached (`GUARANTEED_FEASIBLE` or `EXPECTED_FEASIBLE`)
2. After-Recomputation Risk Status Rank
3. Recommendation Strength (`REQUIRED` < `STRONG` < `CONDITIONAL` < `ADVISORY` < `INFORMATIONAL`)
4. Eligibility (`ELIGIBLE` < `ADVISORY_ONLY` < `INELIGIBLE`)
5. Tradeoff Severity (`NONE` < `LOW` < `MEDIUM` < `HIGH` < `UNKNOWN`)
6. Guaranteed Savings > 0
7. Expected Savings Descending (integer bytes)
8. Parameter Change Magnitude (smaller change preferred)
9. Action Code Rank
10. Candidate ID (lexicographical tiebreaker)
