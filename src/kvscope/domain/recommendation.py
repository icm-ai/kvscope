from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, TypeAlias

from pydantic import Field, StrictBool, StrictInt, StrictStr

from kvscope.calculators.kv_cache import KVCacheEstimate
from kvscope.calculators.weights import WeightMemoryEstimate
from kvscope.domain.backend import BackendProfile
from kvscope.domain.base import DomainModel
from kvscope.domain.config import InferenceConfig
from kvscope.domain.dtypes import WeightDType
from kvscope.domain.enums import (
    Confidence,
    InternalFeasibilityStatus,
    ProductFeasibilityStatus,
)
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import HardwareProfile
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.model import ModelSpec
from kvscope.domain.ranges import ByteRange
from kvscope.domain.runtime_overhead import (
    RuntimeOverheadEstimate,
    RuntimeOverheadOverrides,
)
from kvscope.domain.signed_ranges import SignedByteRange

if TYPE_CHECKING:
    from kvscope.domain.report import MemoryFeasibilityReport


class RecommendationEligibility(StrEnum):
    """Eligibility status of an evaluation baseline for formal recommendations."""

    ELIGIBLE = "eligible"
    ADVISORY_ONLY = "advisory_only"
    INELIGIBLE = "ineligible"


class RecommendationEligibilityResult(DomainModel):
    """Outcome of recommendation eligibility determination."""

    eligibility: RecommendationEligibility
    reason_codes: list[StrictStr] = Field(default_factory=list)
    confidence: Confidence
    warnings: list[StrictStr] = Field(default_factory=list)


class RecommendationStrength(StrEnum):
    """Formality and urgency level of a recommendation candidate."""

    REQUIRED = "required"
    STRONG = "strong"
    CONDITIONAL = "conditional"
    ADVISORY = "advisory"
    INFORMATIONAL = "informational"


class RecommendationAction(StrEnum):
    """Categorical classification of recommended changes or data requests."""

    REDUCE_CONTEXT_LENGTH = "reduce_context_length"
    REDUCE_ACTIVE_SEQUENCES = "reduce_active_sequences"
    CHANGE_KV_DTYPE = "change_kv_dtype"
    CHANGE_WEIGHT_DTYPE = "change_weight_dtype"
    DISABLE_GRAPH_CAPTURE = "disable_graph_capture"

    COMPLETE_ESTIMATE_REQUIRED = "complete_estimate_required"
    PROVIDE_BACKEND_VERSION = "provide_backend_version"
    PROVIDE_QUANTIZATION_METADATA = "provide_quantization_metadata"
    CALIBRATE_RUNTIME_OVERHEAD = "calibrate_runtime_overhead"
    NO_CHANGE_REQUIRED = "no_change_required"


class RecommendationBudgetTarget(StrEnum):
    """Memory budget target used for safe parameter back-solving and recommendations."""

    RECOMMENDED = "recommended"
    ALLOCATABLE_CEILING = "allocatable_ceiling"


class RecommendationSafetyLevel(StrEnum):
    """Target risk boundary used for safe parameter back-solving."""

    GUARANTEED_SAFE = "guaranteed_safe"
    EXPECTED_SAFE = "expected_safe"


class TradeoffSeverity(StrEnum):
    """Severity classification for operational tradeoffs incurred."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class CandidateVerificationStatus(StrEnum):
    """Evaluation status of a recommendation candidate after forward re-computation."""

    VERIFIED = "verified"
    ADVISORY_ONLY = "advisory_only"
    NOT_EVALUABLE = "not_evaluable"
    REJECTED = "rejected"


class WorkloadConstraints(DomainModel):
    """Hard constraints imposed by the user workload or business requirements."""

    minimum_context_length: StrictInt = Field(default=1, ge=1)
    minimum_active_sequences: StrictInt = Field(default=1, ge=1)

    allowed_weight_dtypes: list[StrictStr] | None = None
    allowed_kv_dtypes: list[StrictStr] | None = None

    preserve_graph_capture: bool = False

    model_max_context_length: StrictInt | None = Field(default=None, ge=1)

    require_at_least_product_status: ProductFeasibilityStatus | None = None


class RecommendationPolicy(DomainModel):
    """Governance policy for recommendation generation and candidate filtering."""

    target_budget: RecommendationBudgetTarget = RecommendationBudgetTarget.RECOMMENDED

    target_safety_level: RecommendationSafetyLevel = (
        RecommendationSafetyLevel.EXPECTED_SAFE
    )

    maximum_candidates: StrictInt = Field(default=10, ge=1)

    allow_context_reduction: bool = True
    allow_sequence_reduction: bool = True
    allow_kv_dtype_change: bool = True
    allow_weight_dtype_change: bool = True
    allow_disable_graph_capture: bool = True

    require_medium_confidence_for_strong: bool = True
    allow_advisory_candidates: bool = True

    minimum_expected_savings_bytes: StrictInt = Field(default=1, ge=0)


class WeightRecomputeRequest(DomainModel):
    """Structured context required to recompute weight memory for a candidate."""

    parameter_count: StrictInt
    quantized_parameter_count: StrictInt | None = None
    unquantized_parameter_count: StrictInt | None = None
    weight_dtype: WeightDType | None = None
    unquantized_dtype: WeightDType | None = None
    group_size: StrictInt | None = None
    scale_bytes: StrictInt = 2
    zero_point_bytes: StrictInt = 0
    quant_bits: int | None = None
    metadata_bytes: StrictInt = 0
    alignment_bytes: StrictInt = 0


class RuntimeRecomputeRequest(DomainModel):
    """Structured context required to recompute runtime overhead for a candidate."""

    resident_weight_bytes: StrictInt = Field(ge=0)
    parameter_count: StrictInt | None = Field(default=None, ge=0)
    graph_capture_enabled: bool = False
    user_overrides: RuntimeOverheadOverrides | None = None
    allow_incomplete_profile: bool = False


class RecommendationContext(DomainModel):
    """Immutable evaluation context required to generate candidates."""

    model: ModelSpec
    inference_config: InferenceConfig

    current_weight_estimate: WeightMemoryEstimate
    current_kv_estimate: KVCacheEstimate
    current_runtime_estimate: RuntimeOverheadEstimate
    hardware_budget: HardwareMemoryBudget

    backend_profile: BackendProfile | None = None
    hardware_profile: HardwareProfile | None = None

    weight_recompute_request: WeightRecomputeRequest | None = None
    runtime_recompute_request: RuntimeRecomputeRequest | None = None

    workload_constraints: WorkloadConstraints = Field(
        default_factory=WorkloadConstraints
    )


class ParameterChange(DomainModel):
    """Single parameter modification introduced by a recommendation candidate."""

    parameter: StrictStr
    before: StrictInt | StrictStr | StrictBool
    after: StrictInt | StrictStr | StrictBool
    unit: StrictStr | None = None


class CandidateMemoryImpact(DomainModel):
    """Quantified memory impact of a recommendation candidate."""

    before_requirement: ByteRange
    after_requirement: ByteRange
    savings: SignedByteRange

    before_headroom_recommended: SignedByteRange
    after_headroom_recommended: SignedByteRange

    before_status: InternalFeasibilityStatus
    after_status: InternalFeasibilityStatus


class RecommendationCandidate(DomainModel):
    """Evaluated parameter modification proposed to improve feasibility or headroom."""

    candidate_id: Annotated[StrictStr, Field(min_length=1)]
    action: RecommendationAction
    strength: RecommendationStrength

    title: Annotated[StrictStr, Field(min_length=1)]
    explanation: Annotated[StrictStr, Field(min_length=1)]

    changes: list[ParameterChange] = Field(default_factory=list)

    impact: CandidateMemoryImpact | None = None

    eligibility: RecommendationEligibility
    confidence: Confidence

    source_constraint_codes: list[StrictStr] = Field(default_factory=list)
    tradeoff_severity: TradeoffSeverity = TradeoffSeverity.NONE
    tradeoffs: list[StrictStr] = Field(default_factory=list)
    assumptions: list[StrictStr] = Field(default_factory=list)
    warnings: list[StrictStr] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)

    verification_status: CandidateVerificationStatus
    rejection_reason: StrictStr | None = None


class RejectedRecommendationCandidate(DomainModel):
    """Structure recording a candidate that was evaluated but rejected."""

    candidate_id: StrictStr
    action: RecommendationAction
    reason_code: StrictStr
    explanation: StrictStr
    changes: list[ParameterChange] = Field(default_factory=list)


class ContextLimitResult(DomainModel):
    """Back-solved maximum context length limits under safe memory budgets."""

    guaranteed_safe_max_context: StrictInt | None = None
    expected_safe_max_context: StrictInt | None = None
    allocatable_ceiling_max_context: StrictInt | None = None

    current_context: StrictInt
    fixed_tokens: StrictInt
    block_size: StrictInt | None = None

    limiting_budget: StrictStr = "recommended_allocatable"
    verified: bool = True

    assumptions: list[StrictStr] = Field(default_factory=list)
    warnings: list[StrictStr] = Field(default_factory=list)


class ActiveSequenceLimitResult(DomainModel):
    """Back-solved maximum active sequence count limits under safe memory budgets."""

    guaranteed_safe_max_sequences: StrictInt | None = None
    expected_safe_max_sequences: StrictInt | None = None
    allocatable_ceiling_max_sequences: StrictInt | None = None

    current_active_sequences: StrictInt
    effective_tokens_per_sequence: StrictInt

    controlling_parameter: StrictStr | None = "active_sequences"
    verified: bool = True

    assumptions: list[StrictStr] = Field(default_factory=list)
    warnings: list[StrictStr] = Field(default_factory=list)


class SafeParameterLimits(DomainModel):
    """Container for back-solved parameter capacity limits."""

    context: ContextLimitResult | None = None
    active_sequences: ActiveSequenceLimitResult | None = None


class RecommendationReport(DomainModel):
    """Structured report containing recommendations and safe limits."""

    schema_version: StrictStr = "v0.1"

    eligibility: RecommendationEligibilityResult

    baseline_report: MemoryFeasibilityReport

    primary_recommendation: RecommendationCandidate | None = None
    alternatives: list[RecommendationCandidate] = Field(default_factory=list)
    rejected_candidates: list[RejectedRecommendationCandidate] = Field(
        default_factory=list
    )

    safe_limits: SafeParameterLimits | None = None
    combined_changes_may_be_required: bool = False

    assumptions: list[StrictStr] = Field(default_factory=list)
    warnings: list[StrictStr] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


# Legacy Phase 1 Recommendation model for backward compatibility
RecommendationValue: TypeAlias = float | int | str
NonNegativeInt = Annotated[int, Field(ge=0)]


class Recommendation(DomainModel):
    """A deterministic, explainable suggested configuration change (Phase 1 legacy)."""

    recommendation_id: Annotated[StrictStr, Field(min_length=1)]
    title: Annotated[StrictStr, Field(min_length=1)]
    explanation: Annotated[StrictStr, Field(min_length=1)]
    parameter: Annotated[StrictStr, Field(min_length=1)]
    current_value: RecommendationValue | None = None
    suggested_value: RecommendationValue | None = None
    estimated_savings_bytes: NonNegativeInt | None = None
    priority: NonNegativeInt = 0
    evidence_ids: list[StrictStr] = Field(default_factory=list)
