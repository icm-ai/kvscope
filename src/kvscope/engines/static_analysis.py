"""Shared orchestration for one workload against one deployment target."""

from dataclasses import dataclass

from kvscope.calculators.hardware_budget import estimate_hardware_memory_budget
from kvscope.calculators.kv_cache import KVCacheEstimate, estimate_kv_cache
from kvscope.calculators.overhead import estimate_runtime_overhead
from kvscope.calculators.weights import WeightMemoryEstimate, estimate_weight_memory
from kvscope.domain.comparison import DeploymentTarget
from kvscope.domain.config import InferenceConfig
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.model_source import ResolvedModel
from kvscope.domain.moe import MoEWeightAnalysis
from kvscope.domain.report import (
    AnalysisInferenceConfig,
    AnalysisProvenance,
    MemoryFeasibilityReport,
)
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate
from kvscope.engines.analysis import assess_memory_feasibility
from kvscope.engines.moe import analyze_moe_weight_structure


@dataclass(frozen=True, slots=True)
class PreparedStaticWorkload:
    """Workload-bound estimates and report projection shared across targets."""

    model: ResolvedModel
    inference_config: InferenceConfig
    parameter_count: int
    weights: WeightMemoryEstimate
    moe_weight_analysis: MoEWeightAnalysis | None
    moe_analysis_error: ValueError | None
    inference_provenance: AnalysisInferenceConfig


@dataclass(frozen=True, slots=True)
class StaticTargetAssessment:
    """One target's report and the estimates used to construct it."""

    report: MemoryFeasibilityReport
    weights: WeightMemoryEstimate
    kv_cache: KVCacheEstimate
    runtime_overhead: RuntimeOverheadEstimate
    hardware_budget: HardwareMemoryBudget


def prepare_static_workload(
    model: ResolvedModel, inference_config: InferenceConfig
) -> PreparedStaticWorkload:
    """Prepare workload-only weight, MoE, and provenance information once."""
    parameter_count = model.spec.parameter_count
    if parameter_count is None:
        raise ValueError("model parameter_count is required for target analysis")
    weights = estimate_weight_memory(
        parameter_count=parameter_count,
        dtype=inference_config.weight_dtype,
    )
    # Preserve analyze's historical target-estimate-before-MoE error ordering.
    # Comparison re-raises this stored validation error before target iteration.
    moe_analysis_error: ValueError | None = None
    try:
        moe_weight_analysis = analyze_moe_weight_structure(model.spec)
    except ValueError as exc:
        moe_weight_analysis = None
        moe_analysis_error = exc
    inference_provenance = AnalysisInferenceConfig(
        context_length=inference_config.context_length,
        batch_size=inference_config.batch_size,
        max_num_seqs=inference_config.max_num_seqs,
        active_sequences=inference_config.active_sequences,
        prefix_tokens=inference_config.prefix_tokens,
        multimodal_tokens=inference_config.multimodal_tokens,
        weight_dtype=inference_config.weight_dtype.value,
        kv_dtype=inference_config.kv_dtype.value,
        graph_capture_enabled=inference_config.graph_capture_enabled,
        cpu_offload_bytes=inference_config.cpu_offload_bytes,
    )
    return PreparedStaticWorkload(
        model=model,
        inference_config=inference_config,
        parameter_count=parameter_count,
        weights=weights,
        moe_weight_analysis=moe_weight_analysis,
        moe_analysis_error=moe_analysis_error,
        inference_provenance=inference_provenance,
    )


def assess_static_target(
    prepared: PreparedStaticWorkload,
    target: DeploymentTarget,
    user_reserve_bytes: int = 0,
) -> StaticTargetAssessment:
    """Estimate and assess a prepared workload for exactly one target."""
    model = prepared.model
    model_spec = model.spec
    parameter_count = prepared.parameter_count

    kv_cache = estimate_kv_cache(
        model_spec, prepared.inference_config, target.backend.to_spec()
    )
    hardware_budget = estimate_hardware_memory_budget(
        target.hardware, user_reserve_bytes=user_reserve_bytes
    )
    runtime_overhead = estimate_runtime_overhead(
        backend=target.backend,
        hardware=target.hardware,
        resident_weight_bytes=prepared.weights.resident_weight_bytes,
        parameter_count=parameter_count,
        graph_capture_enabled=prepared.inference_config.graph_capture_enabled,
    )
    # Analyze used to finish KV, budget, and runtime calculations before MoE.
    if prepared.moe_analysis_error is not None:
        raise prepared.moe_analysis_error
    provenance = AnalysisProvenance(
        model_id=model.source.model_id,
        model_revision=model.source.resolved_revision,
        model_config_digest=model.source.config_digest,
        backend_profile_id=target.backend.profile_id,
        backend_version=target.backend_version,
        hardware_profile_id=target.hardware.profile_id,
        inference_config=prepared.inference_provenance,
    )
    report = assess_memory_feasibility(
        weights=prepared.weights,
        kv_cache=kv_cache,
        runtime_overhead=runtime_overhead,
        hardware_budget=hardware_budget,
        provenance=provenance,
        moe_weight_analysis=prepared.moe_weight_analysis,
    )
    return StaticTargetAssessment(
        report=report,
        weights=prepared.weights,
        kv_cache=kv_cache,
        runtime_overhead=runtime_overhead,
        hardware_budget=hardware_budget,
    )
