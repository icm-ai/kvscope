# Constraint Analysis in KVScope

KVScope's Constraint Analyzer identifies operational risk factors, bottlenecks, and limitations during memory estimation without performing automated configuration tuning or parameter recommendations.

## 12 Supported Constraint Codes

1. `PARTIAL_MEMORY_ESTIMATE` (`CRITICAL`): Triggered when memory requirement estimation is incomplete (`is_partial=True`). Suppresses `LOW_CONFIDENCE_ESTIMATE` to avoid duplicate diagnostic noise.
2. `PHYSICAL_MEMORY_EXCEEDED` (`CRITICAL`): Triggered when optimistic memory requirement exceeds total physical hardware memory.
3. `ALLOCATABLE_MEMORY_EXCEEDED` (`CRITICAL`): Triggered when optimistic memory requirement exceeds maximum allocatable memory budget.
4. `RECOMMENDED_BUDGET_EXCEEDED` (`HIGH`): Triggered when requirement exceeds recommended safety allocatable budget (`HEADROOM_EXCEEDED`).
5. `REQUIREMENT_RANGE_CROSSES_BUDGET` (`MEDIUM`): Triggered when requirement interval crosses the recommended budget boundary.
6. `ZERO_RECOMMENDED_HEADROOM` (`MEDIUM`): Triggered when expected headroom equals zero.
7. `LOW_RECOMMENDED_HEADROOM` (`MEDIUM`): Triggered when expected headroom ratio is below configured policy threshold (default 10%).
8. `WEIGHT_MEMORY_DOMINANT` (`LOW`): Triggered when model weights account for >= 50% of total memory requirement.
9. `KV_CACHE_DOMINANT` (`LOW`): Triggered when KV Cache accounts for >= 50% of total memory requirement.
10. `RUNTIME_OVERHEAD_DOMINANT` (`LOW`): Triggered when runtime overhead accounts for >= 50% of total memory requirement.
11. `LOW_CONFIDENCE_ESTIMATE` (`LOW`): Triggered when feasibility confidence is LOW or UNKNOWN on a complete estimate.
12. `UNIFIED_MEMORY_VARIABILITY` (`INFO`): Triggered when hardware uses a unified memory topology.
