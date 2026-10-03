"""Presentation helpers for static MoE weight metadata."""

from kvscope.domain.moe import MoEWeightAnalysis


def _analysis_values(analysis: MoEWeightAnalysis) -> tuple[str, str, str]:
    """Return display-ready optional active-parameter and expert counts."""
    active = (
        str(analysis.active_parameter_count)
        if analysis.active_parameter_count is not None
        else "unknown"
    )
    experts = (
        str(analysis.num_experts) if analysis.num_experts is not None else "unknown"
    )
    selected = (
        str(analysis.num_experts_per_tok)
        if analysis.num_experts_per_tok is not None
        else "unknown"
    )
    return active, experts, selected


def format_moe_weight_analysis_terminal(analysis: MoEWeightAnalysis) -> str:
    """Render MoE parameter counts and explain resident-weight treatment."""
    active, experts, selected = _analysis_values(analysis)
    return "\n".join(
        [
            "--- MoE Weight Metadata ---",
            f"Total parameters:              {analysis.total_parameter_count}",
            f"Active parameters per token:   {active}",
            f"Experts:                       {experts}",
            f"Experts selected per token:   {selected}",
            "Resident weight estimate uses total parameters; active parameters do "
            "not imply that inactive expert weights are offloaded.",
        ]
    )


def format_moe_weight_analysis_markdown(analysis: MoEWeightAnalysis) -> str:
    """Render MoE metadata as a Markdown section with explicit residency caveat."""
    active, experts, selected = _analysis_values(analysis)
    return "\n".join(
        [
            "## MoE Weight Metadata",
            "",
            f"- Total parameters: `{analysis.total_parameter_count}`",
            f"- Active parameters per token: `{active}`",
            f"- Experts: `{experts}`",
            f"- Experts selected per token: `{selected}`",
            "- Resident-weight basis: `total_parameter_count`",
            "",
            "Active parameters describe per-token computation, not resident VRAM; "
            "inactive expert weights are not assumed to be offloaded.",
        ]
    )
