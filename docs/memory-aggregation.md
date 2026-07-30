# Memory Aggregation in KVScope

Memory Aggregator unifies weights, allocated KV Cache, and runtime overhead into a single total runtime requirement:

```text
Resident Weight Memory + Allocated KV Cache Memory + Total Runtime Overhead = Total Runtime Memory Requirement
```

## Key Principles

- **Pure Aggregation**: Memory Aggregator does NOT recompute weights, KV Cache, or runtime overhead, and does NOT add budget-side reserves (OS reserve, display reserve, recommended headroom).
- **Resident Weights**: Uses actual resident weight memory size, never disk artifact storage size.
- **Allocated KV Cache**: Uses block-aligned allocated bytes (`allocated_bytes`), not unaligned `raw_bytes`.
- **Partial Estimation**: If any required component is partial (`is_partial=True`), total requirement is set to `None` and status is marked `UNKNOWN`.
