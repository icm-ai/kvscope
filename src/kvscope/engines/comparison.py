"""Static comparison of one workload across explicit hardware/backend targets."""

from collections.abc import Sequence

from kvscope.domain.comparison import (
    DeploymentComparisonReport,
    DeploymentTarget,
    DeploymentTargetResult,
)
from kvscope.domain.config import InferenceConfig
from kvscope.domain.model_source import ResolvedModel
from kvscope.engines.static_analysis import (
    assess_static_target,
    prepare_static_workload,
)


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

    parameter_count = model.spec.parameter_count
    if parameter_count is None:
        raise ValueError("model parameter_count is required for target comparison")
    prepared = prepare_static_workload(model, inference_config)
    # Comparison historically validates MoE before any target estimate.
    if prepared.moe_analysis_error is not None:
        raise prepared.moe_analysis_error

    results: list[DeploymentTargetResult] = []
    for target in targets:
        assessment = assess_static_target(
            prepared, target, user_reserve_bytes=user_reserve_bytes
        )
        results.append(
            DeploymentTargetResult(
                target_id=target.target_id,
                hardware_profile_id=target.hardware.profile_id,
                backend_profile_id=target.backend.profile_id,
                backend_version=target.backend_version,
                report=assessment.report,
            )
        )

    return DeploymentComparisonReport(
        model_id=model.source.model_id,
        model_revision=model.source.resolved_revision,
        model_config_digest=model.source.config_digest,
        parameter_count=parameter_count,
        inference_config=inference_config,
        targets=results,
    )
