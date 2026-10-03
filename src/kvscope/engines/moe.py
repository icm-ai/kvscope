"""Static analysis of model-level Mixture-of-Experts metadata."""

from kvscope.domain.model import ModelSpec
from kvscope.domain.moe import MoEWeightAnalysis


def analyze_moe_weight_structure(model: ModelSpec) -> MoEWeightAnalysis | None:
    """Summarize known MoE counts without treating active parameters as resident size.

    Returns ``None`` when the model has no expert or active-parameter metadata.
    Resident weight estimation continues to use the model's total parameter count.
    """
    has_moe_metadata = any(
        value is not None
        for value in (
            model.active_parameter_count,
            model.num_experts,
            model.num_experts_per_tok,
        )
    )
    if not has_moe_metadata:
        return None
    if model.parameter_count is None:
        raise ValueError("parameter_count is required for MoE weight analysis")
    return MoEWeightAnalysis(
        total_parameter_count=model.parameter_count,
        active_parameter_count=model.active_parameter_count,
        num_experts=model.num_experts,
        num_experts_per_tok=model.num_experts_per_tok,
    )
