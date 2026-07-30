# Feasibility Engine in KVScope

Feasibility Engine compares requirement ranges against a three-tiered hardware budget:

1. **Physical Total**: Total physical memory on device.
2. **Allocatable Before Headroom**: Physical memory minus non-model system reserves (OS, display, background, device).
3. **Recommended Allocatable**: Allocatable before headroom minus recommended safety headroom.

## Internal vs Product Status Mapping

- `GUARANTEED_FEASIBLE` -> `FEASIBLE`
- `EXPECTED_FEASIBLE` -> `TIGHT`
- `CONDITIONAL_FEASIBLE` -> `TIGHT`
- `HEADROOM_EXCEEDED` -> `TIGHT`
- `ALLOCATABLE_EXCEEDED` -> `INFEASIBLE`
- `PHYSICAL_MEMORY_EXCEEDED` -> `INFEASIBLE`
- `UNKNOWN` -> `UNKNOWN`
