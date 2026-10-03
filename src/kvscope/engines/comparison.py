"""Static comparison of one workload across explicit hardware/backend targets."""

from collections.abc import Sequence

from kvscope.calculators.hardware_budget import estimate_hardware_memory_budget
from kvscope.calculators.kv_cache import estimate_kv_cache
from kvscope.calculators.overhead import estimate_runtime_overhead
from kvscope.calculators.weights import estimate_weight_memory
from kvscope.domain.comparison import (
    DeploymentComparisonReport,
    DeploymentTarget,
    DeploymentTargetResult,
)
from kvscope.domain.config import InferenceConfig
from kvscope.domain.model_source import ResolvedModel
from kvscope.domain.report import AnalysisInferenceConfig, AnalysisProvenance
from kvscope.engines.analysis import assess_memory_feasibility


def compare_deployment_targets(
    *,
    model: ResolvedModel,
    inference_config: InferenceConfig,
    targets: Sequence[DeploymentTarget],
    user_reserve_bytes: int = 0,
) -> DeploymentComparisonReport:
    """Assess a shared model/workload against two or more explicit targets.

    Results preserve the caller-supplied target order; KVScope does not infer a
    single winner from estimates whose uncertainty intervals may overlap.
    """
    if len(targets) < 2:
        raise ValueError("comparison requires at least two deployment targets")
    return _evaluate_deployment_targets(
        model=model,
        inference_config=inference_config,
        targets=targets,
        user_reserve_bytes=user_reserve_bytes,
    )


def _evaluate_deployment_targets(
    *,
    model: ResolvedModel,
    inference_config: InferenceConfig,
    targets: Sequence[DeploymentTarget],
    user_reserve_bytes: int,
) -> DeploymentComparisonReport:
    """Evaluate one or more targets for a single shared workload."""
    if not targets:
        raise ValueError("at least one deployment target is required")
    target_ids = [target.target_id for target in targets]
    if len(target_ids) != len(set(target_ids)):
        raise ValueError("deployment target target_id values must be unique")

    model_spec = model.spec
    if model_spec.parameter_count is None:
        raise ValueError("model parameter_count is required for target comparison")

    resident_weights = estimate_weight_memory(
        parameter_count=model_spec.parameter_count,
        dtype=inference_config.weight_dtype,
    )
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

    results: list[DeploymentTargetResult] = []
    for target in targets:
        kv_cache = estimate_kv_cache(
            model_spec, inference_config, target.backend.to_spec()
        )
        hardware_budget = estimate_hardware_memory_budget(
            target.hardware, user_reserve_bytes=user_reserve_bytes
        )
        runtime_overhead = estimate_runtime_overhead(
            backend=target.backend,
            hardware=target.hardware,
            resident_weight_bytes=resident_weights.resident_weight_bytes,
            parameter_count=model_spec.parameter_count,
            graph_capture_enabled=inference_config.graph_capture_enabled,
        )
        provenance = AnalysisProvenance(
            model_id=model.source.model_id,
            model_revision=model.source.resolved_revision,
            model_config_digest=model.source.config_digest,
            backend_profile_id=target.backend.profile_id,
            backend_version=target.backend_version,
            hardware_profile_id=target.hardware.profile_id,
            inference_config=inference_provenance,
        )
        report = assess_memory_feasibility(
            weights=resident_weights,
            kv_cache=kv_cache,
            runtime_overhead=runtime_overhead,
            hardware_budget=hardware_budget,
            provenance=provenance,
        )
        results.append(
            DeploymentTargetResult(
                target_id=target.target_id,
                hardware_profile_id=target.hardware.profile_id,
                backend_profile_id=target.backend.profile_id,
                backend_version=target.backend_version,
                report=report,
            )
        )

    return DeploymentComparisonReport(
        model_id=model.source.model_id,
        model_revision=model.source.resolved_revision,
        model_config_digest=model.source.config_digest,
        parameter_count=model_spec.parameter_count,
        inference_config=inference_config,
        targets=results,
    )
