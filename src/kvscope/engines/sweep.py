"""Static sensitivity sweeps over one explicitly selected workload dimension."""

from collections.abc import Sequence

from kvscope.domain.comparison import DeploymentTarget
from kvscope.domain.config import InferenceConfig
from kvscope.domain.model_source import ResolvedModel
from kvscope.domain.sweep import (
    WorkloadSweepDimension,
    WorkloadSweepPoint,
    WorkloadSweepReport,
    WorkloadSweepTransition,
)
from kvscope.engines.comparison import _evaluate_deployment_targets


def sweep_workload(
    *,
    model: ResolvedModel,
    inference_config: InferenceConfig,
    targets: Sequence[DeploymentTarget],
    dimension: WorkloadSweepDimension,
    values: Sequence[int],
    user_reserve_bytes: int = 0,
) -> WorkloadSweepReport:
    """Compare explicit targets across user-selected values of one workload axis.

    The model, targets, and all other inference settings remain fixed. Results
    preserve the supplied value and target order; no search or ranking is done.
    """
    if not isinstance(dimension, WorkloadSweepDimension):
        raise ValueError("dimension must be a supported workload sweep dimension")
    if len(values) < 2:
        raise ValueError("a workload sweep requires at least two values")
    if any(type(value) is not int for value in values):
        raise ValueError("sweep values must be positive integers")
    if any(value <= 0 for value in values):
        raise ValueError("sweep values must be positive integers")
    if len(set(values)) != len(values):
        raise ValueError("sweep values must be unique")
    if model.spec.parameter_count is None:
        raise ValueError("model parameter_count is required for workload sweep")

    points: list[WorkloadSweepPoint] = []
    for value in values:
        if dimension is WorkloadSweepDimension.CONTEXT_LENGTH:
            scenario_config = inference_config.model_copy(
                update={"context_length": value}
            )
        else:
            scenario_config = inference_config.model_copy(
                update={"active_sequences_override": value}
            )
        comparison = _evaluate_deployment_targets(
            model=model,
            inference_config=scenario_config,
            targets=targets,
            user_reserve_bytes=user_reserve_bytes,
        )
        points.append(WorkloadSweepPoint(value=value, comparison=comparison))

    transitions: list[WorkloadSweepTransition] = []
    for previous_point, current_point in zip(points, points[1:]):
        previous_by_target = {
            target.target_id: target
            for target in previous_point.comparison.targets
        }
        for current_target in current_point.comparison.targets:
            previous_target = previous_by_target[current_target.target_id]
            previous_status = previous_target.report.feasibility.product_status
            current_status = current_target.report.feasibility.product_status
            if previous_status == current_status:
                continue
            transitions.append(
                WorkloadSweepTransition(
                    target_id=current_target.target_id,
                    hardware_profile_id=current_target.hardware_profile_id,
                    backend_profile_id=current_target.backend_profile_id,
                    from_value=previous_point.value,
                    to_value=current_point.value,
                    from_status=previous_status,
                    to_status=current_status,
                )
            )

    return WorkloadSweepReport(
        model_id=model.source.model_id,
        parameter_count=model.spec.parameter_count,
        dimension=dimension,
        points=points,
        transitions=transitions,
    )
