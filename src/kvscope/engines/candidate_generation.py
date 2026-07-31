"""Engine for generating raw recommendation candidate proposals."""

from dataclasses import dataclass, field

from kvscope.domain.dtypes import KVDType, WeightDType
from kvscope.domain.enums import ProductFeasibilityStatus
from kvscope.domain.recommendation import (
    ActiveSequenceLimitResult,
    ContextLimitResult,
    ParameterChange,
    RecommendationAction,
    RecommendationContext,
    RecommendationPolicy,
    RecommendationSafetyLevel,
    TradeoffSeverity,
)
from kvscope.domain.report import MemoryFeasibilityReport


@dataclass(frozen=True, slots=True)
class CandidateChangeProposal:
    """Raw parameter modification proposal prior to engine re-computation."""

    action: RecommendationAction
    changes: list[ParameterChange]
    title: str
    explanation: str
    tradeoff_severity: TradeoffSeverity
    tradeoffs: list[str] = field(default_factory=list)
    source_constraint_codes: list[str] = field(default_factory=list)
    is_advisory_data_requirement: bool = False
    data_requirement_code: str | None = None


def generate_candidate_proposals(
    *,
    context: RecommendationContext,
    baseline_report: MemoryFeasibilityReport,
    policy: RecommendationPolicy,
    safe_context_limit: ContextLimitResult | None,
    safe_sequence_limit: ActiveSequenceLimitResult | None,
) -> list[CandidateChangeProposal]:
    """Generate potential counterfactual parameter modification proposals."""
    proposals: list[CandidateChangeProposal] = []
    cfg = context.inference_config
    workload = context.workload_constraints
    constraint_codes = [c.code for c in baseline_report.constraint_analysis.constraints]

    # If baseline is FEASIBLE, no reduction candidates are generated

    product_status = baseline_report.feasibility.product_status

    if product_status == ProductFeasibilityStatus.FEASIBLE:
        return proposals

    # 1. Reduce Context Length Proposal
    if policy.allow_context_reduction and safe_context_limit is not None:
        target_context = (
            safe_context_limit.guaranteed_safe_max_context
            if policy.target_safety_level == RecommendationSafetyLevel.GUARANTEED_SAFE
            else safe_context_limit.expected_safe_max_context
        )
        if target_context is None:
            # Fallback to guaranteed if expected is None or vice versa
            target_context = (
                safe_context_limit.guaranteed_safe_max_context
                or safe_context_limit.expected_safe_max_context
            )

        if (
            target_context is not None
            and target_context < cfg.context_length
            and target_context >= workload.minimum_context_length
        ):
            proposals.append(
                CandidateChangeProposal(
                    action=RecommendationAction.REDUCE_CONTEXT_LENGTH,
                    changes=[
                        ParameterChange(
                            parameter="context_length",
                            before=cfg.context_length,
                            after=target_context,
                            unit="tokens",
                        )
                    ],
                    title=(
                        f"Reduce context length from {cfg.context_length} "
                        f"to {target_context} tokens"
                    ),
                    explanation=(
                        f"Reducing text context length from {cfg.context_length} "
                        f"to {target_context} tokens fits KV Cache requirement within "
                        "recommended allocatable memory."
                    ),
                    tradeoff_severity=TradeoffSeverity.MEDIUM,
                    tradeoffs=[
                        "Maximum prompt context window and long-document "
                        "processing capacity are reduced."
                    ],
                    source_constraint_codes=[
                        c
                        for c in constraint_codes
                        if "KV" in c or "MEMORY" in c or "BUDGET" in c
                    ],
                )
            )

    # 2. Reduce Active Sequences Proposal
    if policy.allow_sequence_reduction and safe_sequence_limit is not None:
        target_seqs = (
            safe_sequence_limit.guaranteed_safe_max_sequences
            if policy.target_safety_level == RecommendationSafetyLevel.GUARANTEED_SAFE
            else safe_sequence_limit.expected_safe_max_sequences
        )
        if target_seqs is None:
            target_seqs = (
                safe_sequence_limit.guaranteed_safe_max_sequences
                or safe_sequence_limit.expected_safe_max_sequences
            )

        if (
            target_seqs is not None
            and target_seqs < cfg.active_sequences
            and target_seqs >= workload.minimum_active_sequences
            and cfg.active_sequences_source in ("max_num_seqs", "batch_size")
        ):
            param_name = cfg.active_sequences_source

            proposals.append(
                CandidateChangeProposal(
                    action=RecommendationAction.REDUCE_ACTIVE_SEQUENCES,
                    changes=[
                        ParameterChange(
                            parameter=param_name,
                            before=cfg.active_sequences,
                            after=target_seqs,
                            unit="sequences",
                        )
                    ],
                    title=(
                        f"Reduce active sequence concurrency from "
                        f"{cfg.active_sequences} to {target_seqs}"
                    ),
                    explanation=(
                        f"Reducing concurrent active sequences from "
                        f"{cfg.active_sequences} to {target_seqs} reduces total "
                        "KV Cache memory footprint."
                    ),
                    tradeoff_severity=TradeoffSeverity.MEDIUM,
                    tradeoffs=[
                        "Serving concurrency and total token throughput are reduced."
                    ],
                    source_constraint_codes=[
                        c
                        for c in constraint_codes
                        if "KV" in c or "MEMORY" in c or "BUDGET" in c
                    ],
                )
            )

    # 3. Change KV Cache Dtype Proposal
    if policy.allow_kv_dtype_change:
        current_kv_dtype = cfg.kv_dtype
        # Supported KV dtypes from backend profile or standard fallbacks
        if context.backend_profile is not None:
            supported_kv_dtypes = []
            for d_str in context.backend_profile.supported_kv_dtypes:
                try:
                    supported_kv_dtypes.append(KVDType(d_str.lower()))
                except ValueError:
                    pass
        else:
            supported_kv_dtypes = [
                KVDType.FP16,
                KVDType.BF16,
                KVDType.FP8,
                KVDType.INT8,
            ]

        for dtype in supported_kv_dtypes:
            if dtype == current_kv_dtype:
                continue
            if (
                workload.allowed_kv_dtypes
                and dtype.value not in workload.allowed_kv_dtypes
            ):
                continue
            if dtype.bytes_per_element >= current_kv_dtype.bytes_per_element:
                continue

            savings_pct = (
                1 - dtype.bytes_per_element / current_kv_dtype.bytes_per_element
            ) * 100
            b_elem = current_kv_dtype.bytes_per_element
            t_elem = dtype.bytes_per_element
            proposals.append(
                CandidateChangeProposal(
                    action=RecommendationAction.CHANGE_KV_DTYPE,
                    changes=[
                        ParameterChange(
                            parameter="kv_dtype",
                            before=current_kv_dtype.value,
                            after=dtype.value,
                            unit=None,
                        )
                    ],
                    title=(
                        f"Switch KV Cache dtype from {current_kv_dtype.value} "
                        f"to {dtype.value}"
                    ),
                    explanation=(
                        f"Quantizing KV Cache storage from {current_kv_dtype.value} "
                        f"({b_elem} B/elem) to {dtype.value} ({t_elem} B/elem) "
                        f"reduces per-token memory allocation by {savings_pct:.0f}%."
                    ),
                    tradeoff_severity=(
                        TradeoffSeverity.LOW
                        if "8" in dtype.value
                        else TradeoffSeverity.MEDIUM
                    ),
                    tradeoffs=[
                        "Minor numerical precision impact on attention logits; "
                        "requires backend kernel compatibility."
                    ],
                    source_constraint_codes=[
                        c
                        for c in constraint_codes
                        if "KV" in c or "MEMORY" in c or "BUDGET" in c
                    ],
                )
            )

    # 4. Change Weight Dtype Proposal
    if policy.allow_weight_dtype_change:
        req = context.weight_recompute_request
        if req is not None and req.parameter_count > 0:
            # Complete metadata available for formal weight quantization proposal
            current_weight_dtype = req.weight_dtype or WeightDType.FP16
            target_weight_dtype = (
                WeightDType.INT4
                if current_weight_dtype != WeightDType.INT4
                else WeightDType.INT8
            )

            if target_weight_dtype != current_weight_dtype and (
                not workload.allowed_weight_dtypes
                or target_weight_dtype.value in workload.allowed_weight_dtypes
            ):
                proposals.append(
                    CandidateChangeProposal(
                        action=RecommendationAction.CHANGE_WEIGHT_DTYPE,
                        changes=[
                            ParameterChange(
                                parameter="weight_dtype",
                                before=current_weight_dtype.value,
                                after=target_weight_dtype.value,
                                unit=None,
                            )
                        ],
                        title=(
                            f"Quantize model weights from {current_weight_dtype.value} "
                            f"to {target_weight_dtype.value}"
                        ),
                        explanation=(
                            f"Recomputing model resident weights under "
                            f"{target_weight_dtype.value} group quantization "
                            "substantially reduces baseline weight memory."
                        ),
                        tradeoff_severity=(
                            TradeoffSeverity.HIGH
                            if target_weight_dtype == WeightDType.INT4
                            else TradeoffSeverity.MEDIUM
                        ),
                        tradeoffs=[
                            "Quantization affects output model quality; requires "
                            "specialized quantized weight artifact and kernel."
                        ],
                        source_constraint_codes=[
                            c
                            for c in constraint_codes
                            if "WEIGHT" in c or "MEMORY" in c or "BUDGET" in c
                        ],
                    )
                )
        else:
            # Missing quantization metadata -> emit advisory data requirement candidate
            proposals.append(
                CandidateChangeProposal(
                    action=RecommendationAction.PROVIDE_QUANTIZATION_METADATA,
                    changes=[],
                    title=(
                        "Provide weight quantization metadata for formal "
                        "Weight Dtype recommendations"
                    ),
                    explanation=(
                        "Weight quantization metadata (group size, parameter count, "
                        "scale bytes) is required to generate recomputed Weight "
                        "Dtype candidates."
                    ),
                    tradeoff_severity=TradeoffSeverity.NONE,
                    tradeoffs=[],
                    source_constraint_codes=[
                        c for c in constraint_codes if "WEIGHT" in c
                    ],
                    is_advisory_data_requirement=True,
                    data_requirement_code="PROVIDE_QUANTIZATION_METADATA",
                )
            )

    # 5. Disable Graph Capture Proposal
    if (
        policy.allow_disable_graph_capture
        and cfg.graph_capture_enabled
        and not workload.preserve_graph_capture
    ):
        proposals.append(
            CandidateChangeProposal(
                action=RecommendationAction.DISABLE_GRAPH_CAPTURE,
                changes=[
                    ParameterChange(
                        parameter="graph_capture_enabled",
                        before=True,
                        after=False,
                        unit=None,
                    )
                ],
                title="Disable CUDA/Backend Graph Capture",
                explanation=(
                    "Disabling runtime graph capture removes dedicated memory pool "
                    "buffer allocations and recalculates allocator headroom margins."
                ),
                tradeoff_severity=TradeoffSeverity.MEDIUM,
                tradeoffs=[
                    "Increases CPU launch overhead per iteration and may lower "
                    "peak execution throughput."
                ],
                source_constraint_codes=[
                    c
                    for c in constraint_codes
                    if "OVERHEAD" in c or "RUNTIME" in c or "BUDGET" in c
                ],
            )
        )

    return proposals
