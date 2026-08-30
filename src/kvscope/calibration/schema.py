"""Frozen domain models for offline calibration and opt-in local runner records."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import Confidence
from kvscope.domain.evidence import Evidence
from kvscope.domain.ranges import ByteRange
from kvscope.domain.signed_ranges import SignedByteRange

CALIBRATION_RECORD_SCHEMA_VERSION: Literal["v0.1"] = "v0.1"
CALIBRATION_COMPARISON_SCHEMA_VERSION: Literal["v0.1"] = "v0.1"
CALIBRATION_RUN_SCHEMA_VERSION: Literal["v0.1"] = "v0.1"
CALIBRATION_CANDIDATE_SCHEMA_VERSION: Literal["v0.1"] = "v0.1"
CALIBRATION_REVIEW_SCHEMA_VERSION: Literal["v0.1"] = "v0.1"

PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]


class CalibrationInferenceConfig(DomainModel):
    """Reproducible inference settings recorded with a peak-memory measurement."""

    context_length: PositiveInt
    batch_size: PositiveInt
    max_num_seqs: PositiveInt
    active_sequences: PositiveInt
    prefix_tokens: NonNegativeInt
    multimodal_tokens: NonNegativeInt
    weight_dtype: NonEmptyStr
    kv_dtype: NonEmptyStr
    graph_capture_enabled: StrictBool
    cpu_offload_bytes: NonNegativeInt


class CalibrationMeasurement(DomainModel):
    """An externally collected, local peak-memory measurement record."""

    schema_version: Literal["v0.1"]
    record_id: NonEmptyStr
    collected_at: datetime

    backend_profile_id: NonEmptyStr
    backend_version: StrictStr | None
    hardware_profile_id: NonEmptyStr

    model_id: NonEmptyStr
    model_revision: StrictStr | None
    model_config_digest: StrictStr | None
    inference_config: CalibrationInferenceConfig

    observed_peak_memory_bytes: PositiveInt
    measurement_source: NonEmptyStr
    measurement_method: NonEmptyStr
    confidence: Confidence
    notes: StrictStr | None
    evidence: Annotated[list[Evidence], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_reproducibility_confidence(self) -> Self:
        """Prevent unknown identity details from being reported as high confidence."""
        if self.collected_at.tzinfo is None:
            raise ValueError("collected_at must include a timezone offset")
        has_unknown_identity = self.backend_version is None or (
            self.model_revision is None and self.model_config_digest is None
        )
        if has_unknown_identity and self.confidence in {
            Confidence.EXACT,
            Confidence.HIGH,
        }:
            raise ValueError(
                "unknown backend version or model revision/config digest requires "
                "confidence no higher than medium"
            )
        return self


class CalibrationObservation(DomainModel):
    """One peak-memory observation written by a user-selected local command."""

    schema_version: Literal["v0.1"]
    observation_id: NonEmptyStr
    observed_at: datetime
    observed_peak_memory_bytes: PositiveInt
    evidence: Annotated[list[Evidence], Field(min_length=1)]
    notes: StrictStr | None

    @model_validator(mode="after")
    def validate_observed_at_timezone(self) -> Self:
        """Require a timezone-aware observation timestamp for auditability."""
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must include a timezone offset")
        return self


class CalibrationMeasurementTemplate(DomainModel):
    """Measurement metadata a local runner combines with each observation."""

    record_id_prefix: NonEmptyStr
    backend_profile_id: NonEmptyStr
    backend_version: StrictStr | None
    hardware_profile_id: NonEmptyStr
    model_id: NonEmptyStr
    model_revision: StrictStr | None
    model_config_digest: StrictStr | None
    inference_config: CalibrationInferenceConfig
    measurement_source: NonEmptyStr
    measurement_method: NonEmptyStr
    confidence: Confidence
    notes: StrictStr | None
    evidence: list[Evidence] = Field(default_factory=list)


class CalibrationRunManifest(DomainModel):
    """Explicit local command contract for a repeatable calibration run."""

    schema_version: Literal["v0.1"]
    run_id: NonEmptyStr
    command: Annotated[list[NonEmptyStr], Field(min_length=1)]
    observation_json_path: NonEmptyStr
    repetitions: PositiveInt = 1
    timeout_seconds: PositiveInt = 300
    working_directory: StrictStr | None
    inherit_environment: StrictBool = True
    environment_names: list[NonEmptyStr] = Field(default_factory=list)
    measurement: CalibrationMeasurementTemplate
    notes: StrictStr | None


class CalibrationRunFailure(DomainModel):
    """A non-sensitive failed runner attempt retained in the run result."""

    sample_index: PositiveInt
    code: NonEmptyStr
    return_code: StrictInt | None
    message: NonEmptyStr


class CalibrationRunResult(DomainModel):
    """Traceable outcome of repeated local observation collection."""

    schema_version: Literal["v0.1"] = CALIBRATION_RUN_SCHEMA_VERSION
    run_id: NonEmptyStr
    manifest_digest: NonEmptyStr
    command_digest: NonEmptyStr
    started_at: datetime
    completed_at: datetime
    successful_measurements: list[CalibrationMeasurement] = Field(default_factory=list)
    failures: list[CalibrationRunFailure] = Field(default_factory=list)
    selected_measurement_id: StrictStr | None
    conservative_peak_memory_bytes: PositiveInt | None
    exported_measurement_paths: list[StrictStr] = Field(default_factory=list)
    warnings: list[StrictStr] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class CalibrationComparisonStatus(StrEnum):
    """Whether an offline comparison could be formed from the source report."""

    COMPARABLE = "comparable"
    INCOMPLETE_REPORT = "incomplete_report"
    IDENTITY_MISMATCH = "identity_mismatch"
    IDENTITY_UNVERIFIED = "identity_unverified"


class CalibrationIdentityVerification(StrEnum):
    """How completely report provenance matches a measurement record."""

    VERIFIED = "verified"
    PARTIAL = "partial"
    MISMATCH = "mismatch"
    UNAVAILABLE = "unavailable"


class RelativeError(DomainModel):
    """An exact signed ratio stored as integer numerator and denominator bytes."""

    numerator_bytes: StrictInt
    denominator_bytes: PositiveInt


class CalibrationComparison(DomainModel):
    """Auditable comparison of one observed peak against a feasibility report."""

    schema_version: Literal["v0.1"] = CALIBRATION_COMPARISON_SCHEMA_VERSION
    status: CalibrationComparisonStatus
    measurement_record_id: NonEmptyStr
    report_schema_version: NonEmptyStr
    measurement: CalibrationMeasurement
    identity_verification: CalibrationIdentityVerification
    identity_mismatches: list[StrictStr] = Field(default_factory=list)

    predicted_total_requirement: ByteRange | None
    observed_peak_memory_bytes: PositiveInt
    observed_within_predicted_range: StrictBool | None
    delta_vs_lower_bytes: StrictInt | None
    delta_vs_expected_bytes: StrictInt | None
    delta_vs_upper_bytes: StrictInt | None
    signed_error: SignedByteRange | None
    relative_error_vs_expected: RelativeError | None

    confidence: Confidence
    assumptions: list[StrictStr] = Field(default_factory=list)
    warnings: list[StrictStr] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class CalibrationCandidateStatus(StrEnum):
    """Readiness of a scoped empirical calibration candidate."""

    SCOPED_ENVELOPE = "scoped_envelope"
    INSUFFICIENT_DATA = "insufficient_data"


class CalibrationCandidateScope(DomainModel):
    """Exact workload scope for a candidate that cannot claim generality."""

    backend_profile_id: NonEmptyStr
    backend_version: NonEmptyStr
    hardware_profile_id: NonEmptyStr
    model_id: NonEmptyStr
    model_revision: StrictStr | None
    model_config_digest: StrictStr | None
    inference_config: CalibrationInferenceConfig


class CalibrationProfileCandidate(DomainModel):
    """A human-review-only empirical reserve candidate, never an active profile."""

    schema_version: Literal["v0.1"] = CALIBRATION_CANDIDATE_SCHEMA_VERSION
    candidate_id: NonEmptyStr
    status: CalibrationCandidateStatus
    scope: CalibrationCandidateScope
    comparison_record_ids: Annotated[list[NonEmptyStr], Field(min_length=1)]
    sample_count: PositiveInt
    additional_reserve_bytes: ByteRange
    confidence: Confidence
    assumptions: list[StrictStr] = Field(default_factory=list)
    warnings: list[StrictStr] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class CalibrationReviewStatus(StrEnum):
    """A review decision over one immutable calibration candidate."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CalibrationReviewDecision(DomainModel):
    """Signed human decision artifact; acceptance does not promote a profile."""

    schema_version: Literal["v0.1"] = CALIBRATION_REVIEW_SCHEMA_VERSION
    review_id: NonEmptyStr
    candidate_id: NonEmptyStr
    candidate_digest: NonEmptyStr
    reviewer_id: NonEmptyStr
    reviewed_at: datetime
    status: CalibrationReviewStatus
    notes: NonEmptyStr

    @model_validator(mode="after")
    def validate_reviewed_at_timezone(self) -> Self:
        """Require a timezone-aware review time for an auditable decision."""
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must include a timezone offset")
        return self
