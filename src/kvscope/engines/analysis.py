"""Combined Phase 7 memory feasibility assessment entry point."""

from kvscope.calculators.kv_cache import KVCacheEstimate
from kvscope.calculators.weights import WeightMemoryEstimate
from kvscope.domain.constraints import ConstraintPolicy
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.report import MemoryFeasibilityReport
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate
from kvscope.engines.aggregation import aggregate_memory_requirements
from kvscope.engines.constraints import analyze_memory_constraints
from kvscope.engines.feasibility import evaluate_memory_feasibility


def assess_memory_feasibility(
    *,
    weights: WeightMemoryEstimate,
    kv_cache: KVCacheEstimate,
    runtime_overhead: RuntimeOverheadEstimate,
    hardware_budget: HardwareMemoryBudget,
    constraint_policy: ConstraintPolicy | None = None,
    strict: bool = False,
) -> MemoryFeasibilityReport:
    """Assess overall LLM deployment memory feasibility across Phase 7 engines."""
    aggregation = aggregate_memory_requirements(
        weights=weights,
        kv_cache=kv_cache,
        runtime_overhead=runtime_overhead,
        strict=strict,
    )
    feasibility = evaluate_memory_feasibility(
        requirement=aggregation,
        hardware_budget=hardware_budget,
        strict=strict,
    )
    constraints = analyze_memory_constraints(
        aggregation=aggregation,
        hardware_budget=hardware_budget,
        feasibility=feasibility,
        policy=constraint_policy,
    )

    return MemoryFeasibilityReport(
        schema_version="v0.1",
        aggregation=aggregation,
        feasibility=feasibility,
        constraint_analysis=constraints,
    )
