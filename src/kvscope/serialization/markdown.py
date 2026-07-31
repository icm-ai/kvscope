"""Markdown serialization for KVScope estimates and budget reports."""

from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.ranges import ByteRange
from kvscope.domain.recommendation import RecommendationReport
from kvscope.domain.report import MemoryFeasibilityReport
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate
from kvscope.domain.signed_ranges import SignedByteRange
from kvscope.domain.units import bytes_to_gib


def _md_range(br: ByteRange) -> str:
    exp_gib = bytes_to_gib(br.expected_bytes)
    if br.is_exact:
        return f"`{br.expected_bytes}` B ({exp_gib:.2f} GiB)"
    low_gib = bytes_to_gib(br.lower_bytes)
    up_gib = bytes_to_gib(br.upper_bytes)
    return f"`{br.expected_bytes}` B ({exp_gib:.2f} GiB) _[{low_gib:.2f}-{up_gib:.2f}]_"


def _row(name: str, br: ByteRange, is_bold: bool = False) -> str:
    l_g = bytes_to_gib(br.lower_bytes)
    e_g = bytes_to_gib(br.expected_bytes)
    u_g = bytes_to_gib(br.upper_bytes)
    exp_b = br.expected_bytes
    if is_bold:
        b_name = f"**{name}**"
        return (
            f"| {b_name} | **{l_g:.2f}** | **{e_g:.2f}** | **{u_g:.2f}** | `{exp_b}` |"
        )
    return f"| {name} | {l_g:.2f} | {e_g:.2f} | {u_g:.2f} | `{exp_b}` |"


def _sbr_row(name: str, sbr: SignedByteRange) -> str:
    l_g = float(sbr.lower_bytes) / (1024**3)
    e_g = float(sbr.expected_bytes) / (1024**3)
    u_g = float(sbr.upper_bytes) / (1024**3)
    exp_b = sbr.expected_bytes
    return f"| {name} | {l_g:.2f} | {e_g:.2f} | {u_g:.2f} | `{exp_b}` |"


def serialize_budget_to_markdown(budget: HardwareMemoryBudget) -> str:
    """Serialize HardwareMemoryBudget to Markdown format."""
    tot_gib = bytes_to_gib(budget.physical_total_bytes)
    tot_str = f"`{budget.physical_total_bytes}` B ({tot_gib:.2f} GiB)"
    alloc_str = _md_range(budget.allocatable_before_headroom)
    lines: list[str] = [
        "# KVScope Hardware Memory Budget Report",
        "",
        f"- **Memory Topology**: `{budget.memory_topology.value}`",
        f"- **Physical Total Memory**: {tot_str}",
        f"- **Confidence**: `{budget.confidence.value}`",
        "",
        "## Non-Model Reserves Breakdown",
        "",
        "| Component | Lower (GiB) | Expected (GiB) | Upper (GiB) | Bytes (Expected) |",
        "| :--- | :--- | :--- | :--- | :--- |",
        _row("OS Reserve", budget.os_reserve),
        _row("Display Reserve", budget.display_reserve),
        _row("Background Process Reserve", budget.background_process_reserve),
        _row("Device-Specific Reserve", budget.device_specific_reserve),
        _row("User Reserve", budget.user_reserve),
        _row("Total Non-Model Reserve", budget.total_non_model_reserve, is_bold=True),
        "",
        "## Allocatable Memory Summary",
        "",
        f"- **Allocatable (Before Headroom)**: {alloc_str}",
        f"- **Recommended Headroom**: {_md_range(budget.recommended_headroom)}",
        f"- **Recommended Allocatable**: {_md_range(budget.recommended_allocatable)}",
    ]

    if budget.warnings:
        lines.append("")
        lines.append("### Warnings")
        lines.append("")
        for w in budget.warnings:
            lines.append(f"> [!WARNING]\n> {w}")

    return "\n".join(lines)


def serialize_overhead_to_markdown(estimate: RuntimeOverheadEstimate) -> str:
    """Serialize RuntimeOverheadEstimate to Markdown format."""
    ver_str = estimate.backend_version_specifier or "N/A"
    lines: list[str] = [
        "# KVScope Runtime Overhead Report",
        "",
        f"- **Backend Profile**: `{estimate.backend_profile_id}` ({ver_str})",
        f"- **Hardware Profile**: `{estimate.hardware_profile_id}`",
        f"- **Confidence**: `{estimate.confidence.value}`",
        "",
        "## Runtime Overhead Component Breakdown",
        "",
        "| Component | Lower (GiB) | Expected (GiB) | Upper (GiB) | Bytes (Expected) |",
        "| :--- | :--- | :--- | :--- | :--- |",
        _row("Base Runtime", estimate.base_runtime),
        _row("Parameter-Scaled Overhead", estimate.parameter_scaled_overhead),
        _row("Workspace (Resident Weights)", estimate.workspace),
        _row("Graph Capture Reserve", estimate.graph_capture),
        _row("Backend Buffers", estimate.backend_buffers),
        _row(
            "Subtotal (Before Margin)",
            estimate.subtotal_before_allocator_margin,
            is_bold=True,
        ),
        _row("Allocator Margin", estimate.allocator_margin),
        _row("Total Runtime Overhead", estimate.total_runtime_overhead, is_bold=True),
    ]

    if estimate.warnings:
        lines.append("")
        lines.append("### Warnings")
        lines.append("")
        for w in estimate.warnings:
            lines.append(f"> [!WARNING]\n> {w}")

    return "\n".join(lines)


def serialize_feasibility_report_markdown(report: MemoryFeasibilityReport) -> str:
    """Serialize MemoryFeasibilityReport to Markdown format."""
    agg = report.aggregation
    feas = report.feasibility
    con = report.constraint_analysis

    lines: list[str] = [
        "# KVScope Memory Feasibility Report",
        "",
        f"- **Product Status**: `{feas.product_status.value.upper()}`",
        f"- **Internal Status**: `{feas.internal_status.value}`",
        f"- **Confidence**: `{feas.confidence.value.upper()}`",
        f"- **Primary Boundary**: `{feas.primary_boundary or 'N/A'}`",
        f"- **Explanation**: {feas.explanation}",
        "",
    ]

    if agg.is_partial:
        lines.extend(
            [
                "> [!WARNING]",
                "> **Partial Estimate**: Memory requirement calculation is incomplete.",
                f"> Missing components: `{agg.missing_components}`",
                "",
            ]
        )

    header_row = (
        "| Component | Lower (GiB) | Expected (GiB) | Upper (GiB) | Bytes (Expected) |"
    )
    sep_row = "| :--- | :--- | :--- | :--- | :--- |"

    lines.extend(
        [
            "## Memory Requirement Breakdown",
            "",
            header_row,
            sep_row,
            _row("Resident Weights", agg.resident_weights.memory),
            _row("Allocated KV Cache", agg.kv_cache.memory),
            _row("Runtime Overhead", agg.runtime_overhead.memory),
            _row("Known Subtotal", agg.known_subtotal, is_bold=True),
        ]
    )

    if not agg.is_partial and agg.total_requirement is not None:
        lines.append(_row("Total Requirement", agg.total_requirement, is_bold=True))

    tot_gib = bytes_to_gib(feas.physical_total_bytes)
    tot_row = (
        f"| Physical Total Memory | {tot_gib:.2f} | {tot_gib:.2f} | "
        f"{tot_gib:.2f} | `{feas.physical_total_bytes}` |"
    )
    budget_header_row = (
        "| Budget Tier | Lower (GiB) | Expected (GiB) | Upper (GiB) | Bytes |"
    )
    lines.extend(
        [
            "",
            "## Hardware Memory Budget",
            "",
            budget_header_row,
            sep_row,
            tot_row,
            _row("Allocatable (Before Headroom)", feas.allocatable_before_headroom),
            _row("Recommended Allocatable", feas.recommended_allocatable, is_bold=True),
        ]
    )

    boundary_header_row = (
        "| Boundary Level | Lower (GiB) | Expected (GiB) | Upper (GiB) | Bytes |"
    )
    lines.extend(
        [
            "",
            "## Memory Headroom / Deficit Range",
            "",
            boundary_header_row,
            sep_row,
        ]
    )
    if feas.headroom_vs_physical is not None:
        lines.append(_sbr_row("Versus Physical Memory", feas.headroom_vs_physical))
    if feas.headroom_vs_allocatable is not None:
        lines.append(
            _sbr_row("Versus Allocatable Budget", feas.headroom_vs_allocatable)
        )
    if feas.headroom_vs_recommended is not None:
        lines.append(
            _sbr_row("Versus Recommended Budget", feas.headroom_vs_recommended)
        )

    lines.extend(
        [
            "",
            "## Identified Constraints",
            "",
        ]
    )
    if not con.constraints:
        lines.append("_No active risk constraints identified._")
    else:
        lines.extend(
            [
                "| Severity | Code | Component | Explanation |",
                "| :--- | :--- | :--- | :--- |",
            ]
        )
        for c in con.constraints:
            comp_str = c.component or "N/A"
            c_sev = c.severity.value.upper()
            lines.append(f"| `{c_sev}` | `{c.code}` | `{comp_str}` | {c.explanation} |")

    if feas.warnings:
        lines.extend(["", "### Warnings", ""])
        for w in feas.warnings:
            lines.append(f"> [!WARNING]\n> {w}")

    if feas.evidence:
        lines.extend(["", "### Evidence", ""])
        for ev in feas.evidence:
            lines.append(
                f"- **[{ev.evidence_id}]** {ev.source} _(Type: {ev.source_type})_"
            )

    return "\n".join(lines)


def format_recommendation_report_markdown(report: RecommendationReport) -> str:
    """Serialize a RecommendationReport to Markdown format."""
    prod_st = report.baseline_report.feasibility.product_status.value
    int_st = report.baseline_report.feasibility.internal_status.value
    lines: list[str] = [
        "# KVScope Recommendation Report",
        "",
        "## Baseline Assessment",
        "",
        f"- **Eligibility**: `{report.eligibility.eligibility.value}`",
        f"- **Baseline Product Feasibility**: `{prod_st}`",
        f"- **Baseline Internal Feasibility**: `{int_st}`",
        f"- **Baseline Confidence**: `{report.eligibility.confidence.value}`",
        "",
    ]

    p = report.primary_recommendation
    if p is not None:
        lines.extend(
            [
                "## Primary Recommendation",
                "",
                f"### {p.title}",
                "",
                f"- **Action**: `{p.action.value}`",
                f"- **Strength**: `{p.strength.value}`",
                f"- **Confidence**: `{p.confidence.value}`",
                f"- **Tradeoff Severity**: `{p.tradeoff_severity.value}`",
                "",
                p.explanation,
                "",
            ]
        )
        if p.changes:
            lines.extend(
                [
                    "#### Parameter Changes",
                    "",
                    "| Parameter | Before | After | Unit |",
                    "| :--- | :--- | :--- | :--- |",
                ]
            )
            for chg in p.changes:
                u_str = chg.unit or "N/A"
                p_str = chg.parameter
                lines.append(
                    f"| `{p_str}` | `{chg.before}` | `{chg.after}` | `{u_str}` |"
                )

            lines.append("")

        if p.impact is not None:
            b_st = p.impact.before_status.value
            a_st = p.impact.after_status.value
            hdr = (
                "| Metric | Lower (GiB) | Expected (GiB) | Upper (GiB) | "
                "Bytes (Expected) |"
            )
            lines.extend(
                [
                    "#### Memory Impact Breakdown",
                    "",
                    hdr,
                    "| :--- | :--- | :--- | :--- | :--- |",
                    _sbr_row("Expected Savings", p.impact.savings),
                    _row("Baseline Requirement", p.impact.before_requirement),
                    _row("Candidate Requirement", p.impact.after_requirement),
                    _sbr_row(
                        "Baseline Headroom (Recommended)",
                        p.impact.before_headroom_recommended,
                    ),
                    _sbr_row(
                        "Candidate Headroom (Recommended)",
                        p.impact.after_headroom_recommended,
                    ),
                    "",
                    f"- **Before Feasibility Status**: `{b_st}`",
                    f"- **After Feasibility Status**: `{a_st}`",
                    "",
                ]
            )
        if p.tradeoffs:
            lines.extend(["#### Operational Tradeoffs", ""])
            for t in p.tradeoffs:
                lines.append(f"- {t}")
            lines.append("")

    if report.safe_limits is not None:
        lines.extend(["## Safe Parameter Capacity Limits", ""])
        c_lim = report.safe_limits.context
        if c_lim is not None:
            g_c = (
                f"`{c_lim.guaranteed_safe_max_context}` tokens"
                if c_lim.guaranteed_safe_max_context
                else "N/A"
            )
            e_c = (
                f"`{c_lim.expected_safe_max_context}` tokens"
                if c_lim.expected_safe_max_context
                else "N/A"
            )
            a_c = (
                f"`{c_lim.allocatable_ceiling_max_context}` tokens"
                if c_lim.allocatable_ceiling_max_context
                else "N/A"
            )
            lines.extend(
                [
                    "### Context Length Capacity",
                    f"- **Current Context**: `{c_lim.current_context}` tokens",
                    f"- **Guaranteed Safe Maximum**: {g_c}",
                    f"- **Expected Safe Maximum**: {e_c}",
                    f"- **Allocatable Ceiling Maximum**: {a_c}",
                    "",
                ]
            )

        s_lim = report.safe_limits.active_sequences
        if s_lim is not None:
            g_s = (
                f"`{s_lim.guaranteed_safe_max_sequences}`"
                if s_lim.guaranteed_safe_max_sequences
                else "N/A"
            )
            e_s = (
                f"`{s_lim.expected_safe_max_sequences}`"
                if s_lim.expected_safe_max_sequences
                else "N/A"
            )
            a_s = (
                f"`{s_lim.allocatable_ceiling_max_sequences}`"
                if s_lim.allocatable_ceiling_max_sequences
                else "N/A"
            )
            curr_seqs = s_lim.current_active_sequences
            lines.extend(
                [
                    "### Active Sequence Capacity",
                    f"- **Current Active Sequences**: `{curr_seqs}`",
                    f"- **Guaranteed Safe Maximum**: {g_s}",
                    f"- **Expected Safe Maximum**: {e_s}",
                    f"- **Allocatable Ceiling Maximum**: {a_s}",
                    "",
                ]
            )

    if report.alternatives:
        lines.extend(
            [
                "## Alternative Recommendations",
                "",
                "| Action | Strength | Title | Tradeoff Severity |",
                "| :--- | :--- | :--- | :--- |",
            ]
        )
        for alt in report.alternatives:
            act_v = alt.action.value
            str_v = alt.strength.value
            trd_v = alt.tradeoff_severity.value
            lines.append(f"| `{act_v}` | `{str_v}` | {alt.title} | `{trd_v}` |")
        lines.append("")

    if report.warnings:
        lines.extend(["### Warnings", ""])
        for w in report.warnings:
            lines.append(f"> [!WARNING]\n> {w}")

    return "\n".join(lines)


serialize_recommendation_report_markdown = format_recommendation_report_markdown
