"""Memory Aggregator engine for combining weights, KV Cache, and runtime overhead."""

from kvscope.calculators.kv_cache import KVCacheEstimate
from kvscope.calculators.weights import WeightMemoryEstimate
from kvscope.domain.aggregation import (
    MemoryAggregationResult,
    MemoryComponentRequirement,
)
from kvscope.domain.enums import Confidence
from kvscope.domain.evidence import Evidence
from kvscope.domain.ranges import ByteRange, add_byte_ranges
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate
from kvscope.errors import MissingMemoryComponentError

_CONFIDENCE_ORDER: dict[Confidence, int] = {
    Confidence.EXACT: 4,
    Confidence.HIGH: 3,
    Confidence.MEDIUM: 2,
    Confidence.LOW: 1,
    Confidence.UNKNOWN: 0,
}


def _min_confidence(*confidences: Confidence) -> Confidence:
    """Return the lowest confidence level from the given arguments."""
    if not confidences:
        return Confidence.UNKNOWN
    return min(confidences, key=lambda c: _CONFIDENCE_ORDER[c])


def aggregate_memory_requirements(
    *,
    weights: WeightMemoryEstimate,
    kv_cache: KVCacheEstimate,
    runtime_overhead: RuntimeOverheadEstimate,
    strict: bool = False,
) -> MemoryAggregationResult:
    """Aggregate weights, allocated KV cache, and runtime overhead into total
    requirement.

    This function does NOT recalculate any sub-component, apply alignment, or add
    budget-side reserves (OS/display/headroom).
    """
    resident_bytes = weights.resident_weight_bytes
    weights_range = ByteRange.exact(resident_bytes)
    weights_comp = MemoryComponentRequirement(
        component="resident_weights",
        memory=weights_range,
        confidence=weights.confidence,
        source_id=None,
        assumptions=list(weights.assumptions),
        warnings=list(weights.warnings),
        evidence=[],
    )

    kv_allocated = kv_cache.allocated_bytes
    kv_range = ByteRange.exact(kv_allocated)
    kv_comp = MemoryComponentRequirement(
        component="kv_cache",
        memory=kv_range,
        confidence=Confidence.EXACT,
        source_id=None,
        assumptions=[],
        warnings=[],
        evidence=[],
    )

    runtime_range = runtime_overhead.total_runtime_overhead
    runtime_comp = MemoryComponentRequirement(
        component="runtime_overhead",
        memory=runtime_range,
        confidence=runtime_overhead.confidence,
        source_id=runtime_overhead.backend_profile_id,
        assumptions=list(runtime_overhead.assumptions),
        warnings=list(runtime_overhead.warnings),
        evidence=list(runtime_overhead.evidence),
    )

    # Check completeness
    missing: list[str] = []
    if runtime_overhead.is_partial:
        missing.extend(runtime_overhead.missing_components or ["runtime_overhead"])

    is_partial = len(missing) > 0

    if strict and is_partial:
        raise MissingMemoryComponentError(
            f"Incomplete memory requirement: missing {missing}"
        )

    known_subtotal = add_byte_ranges(weights_range, kv_range, runtime_range)

    # Deduplicate assumptions and warnings preserving order
    all_assumptions: list[str] = []
    for comp_assumptions in (weights_comp.assumptions, runtime_comp.assumptions):
        for item in comp_assumptions:
            if item not in all_assumptions:
                all_assumptions.append(item)

    all_warnings: list[str] = []
    for comp_warnings in (weights_comp.warnings, runtime_comp.warnings):
        for item in comp_warnings:
            if item not in all_warnings:
                all_warnings.append(item)

    # Deduplicate evidence deterministically
    all_evidence: list[Evidence] = []
    seen_evidence_ids: set[str] = set()
    for ev in runtime_comp.evidence:
        ev_key = f"{ev.evidence_id}:{ev.source_type}:{ev.source}"
        if ev_key not in seen_evidence_ids:
            seen_evidence_ids.add(ev_key)
            all_evidence.append(ev)

    # Calculate dominant components
    component_ranges = [
        ("resident_weights", weights_range),
        ("kv_cache", kv_range),
        ("runtime_overhead", runtime_range),
    ]

    # Max expected bytes with tie-breaking order
    dominant_expected = max(
        component_ranges,
        key=lambda item: item[1].expected_bytes,
    )[0]

    # Max upper bytes with tie-breaking order
    dominant_upper = max(
        component_ranges,
        key=lambda item: item[1].upper_bytes,
    )[0]

    if is_partial:
        total_requirement = None
        agg_confidence = Confidence.UNKNOWN
    else:
        total_requirement = known_subtotal
        agg_confidence = _min_confidence(
            weights.confidence, Confidence.EXACT, runtime_overhead.confidence
        )

    return MemoryAggregationResult(
        schema_version="v0.1",
        resident_weights=weights_comp,
        kv_cache=kv_comp,
        runtime_overhead=runtime_comp,
        known_subtotal=known_subtotal,
        total_requirement=total_requirement,
        is_partial=is_partial,
        missing_components=missing,
        dominant_component_expected=dominant_expected,
        dominant_component_upper=dominant_upper,
        confidence=agg_confidence,
        assumptions=all_assumptions,
        warnings=all_warnings,
        evidence=all_evidence,
    )
