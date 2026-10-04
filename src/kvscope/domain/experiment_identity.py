"""Shared field semantics and comparison policy for experiment identity."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field, StrictBool, StrictInt, StrictStr

from kvscope.domain.base import DomainModel
from kvscope.domain.config import InferenceConfig

PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]


class ExperimentConfigIdentity(DomainModel):
    """The fixed persisted ten-field inference configuration identity."""

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


def project_inference_config(config: InferenceConfig) -> ExperimentConfigIdentity:
    """Project runtime settings onto the persisted ten-field identity contract."""
    return ExperimentConfigIdentity(
        context_length=config.context_length,
        batch_size=config.batch_size,
        max_num_seqs=config.max_num_seqs,
        active_sequences=config.active_sequences,
        prefix_tokens=config.prefix_tokens,
        multimodal_tokens=config.multimodal_tokens,
        weight_dtype=config.weight_dtype.value,
        kv_dtype=config.kv_dtype.value,
        graph_capture_enabled=config.graph_capture_enabled,
        cpu_offload_bytes=config.cpu_offload_bytes,
    )


class ExperimentIdentityState(StrEnum):
    """Report-to-measurement identity state, independent of comparison status."""

    VERIFIED = "verified"
    PARTIAL = "partial"
    MISMATCH = "mismatch"
    UNAVAILABLE = "unavailable"


class ExperimentIdentityView(DomainModel):
    """Typed, in-process identity values from a report or measurement."""

    model_id: NonEmptyStr
    backend_profile_id: NonEmptyStr
    hardware_profile_id: NonEmptyStr
    inference_config: ExperimentConfigIdentity
    backend_version: StrictStr | None
    model_revision: StrictStr | None
    model_config_digest: StrictStr | None


class ExperimentIdentityResult(DomainModel):
    """Identity decision with deterministic diagnostics and warnings."""

    state: ExperimentIdentityState
    mismatches: tuple[StrictStr, ...] = ()
    warnings: tuple[StrictStr, ...] = ()


def _mismatch(field_name: str, report_value: object, measurement_value: object) -> str:
    return f"{field_name}: report={report_value!r}, measurement={measurement_value!r}"


def verify_experiment_identity(
    report: ExperimentIdentityView | None,
    measurement: ExperimentIdentityView,
) -> ExperimentIdentityResult:
    """Compare explicit required, configuration, version, and fingerprint fields."""
    if report is None:
        return ExperimentIdentityResult(
            state=ExperimentIdentityState.UNAVAILABLE,
            warnings=(
                "The feasibility report has no provenance, so its model, backend, "
                "hardware, and inference configuration cannot be verified.",
            ),
        )

    mismatches: list[str] = []
    warnings: list[str] = []
    required_values = (
        ("model_id", report.model_id, measurement.model_id),
        (
            "backend_profile_id",
            report.backend_profile_id,
            measurement.backend_profile_id,
        ),
        (
            "hardware_profile_id",
            report.hardware_profile_id,
            measurement.hardware_profile_id,
        ),
    )
    for field_name, report_value, measurement_value in required_values:
        if report_value != measurement_value:
            mismatches.append(_mismatch(field_name, report_value, measurement_value))

    report_config = report.inference_config
    measurement_config = measurement.inference_config
    config_values = (
        (
            "context_length",
            report_config.context_length,
            measurement_config.context_length,
        ),
        ("batch_size", report_config.batch_size, measurement_config.batch_size),
        ("max_num_seqs", report_config.max_num_seqs, measurement_config.max_num_seqs),
        (
            "active_sequences",
            report_config.active_sequences,
            measurement_config.active_sequences,
        ),
        (
            "prefix_tokens",
            report_config.prefix_tokens,
            measurement_config.prefix_tokens,
        ),
        (
            "multimodal_tokens",
            report_config.multimodal_tokens,
            measurement_config.multimodal_tokens,
        ),
        ("weight_dtype", report_config.weight_dtype, measurement_config.weight_dtype),
        ("kv_dtype", report_config.kv_dtype, measurement_config.kv_dtype),
        (
            "graph_capture_enabled",
            report_config.graph_capture_enabled,
            measurement_config.graph_capture_enabled,
        ),
        (
            "cpu_offload_bytes",
            report_config.cpu_offload_bytes,
            measurement_config.cpu_offload_bytes,
        ),
    )
    for field_name, config_report_value, config_measurement_value in config_values:
        if config_report_value != config_measurement_value:
            mismatches.append(
                _mismatch(
                    f"inference_config.{field_name}",
                    config_report_value,
                    config_measurement_value,
                )
            )

    is_partial = False
    if report.backend_version is None or measurement.backend_version is None:
        is_partial = True
        warnings.append(
            "backend_version is unknown in the report or measurement; identity "
            "verification is partial."
        )
    elif report.backend_version != measurement.backend_version:
        mismatches.append(
            _mismatch(
                "backend_version", report.backend_version, measurement.backend_version
            )
        )

    common_fingerprint = False
    fingerprints = (
        ("model_revision", report.model_revision, measurement.model_revision),
        (
            "model_config_digest",
            report.model_config_digest,
            measurement.model_config_digest,
        ),
    )
    for (
        field_name,
        fingerprint_report_value,
        fingerprint_measurement_value,
    ) in fingerprints:
        if fingerprint_report_value is None or fingerprint_measurement_value is None:
            continue
        common_fingerprint = True
        if fingerprint_report_value != fingerprint_measurement_value:
            mismatches.append(
                _mismatch(
                    field_name,
                    fingerprint_report_value,
                    fingerprint_measurement_value,
                )
            )
    if not common_fingerprint:
        is_partial = True
        warnings.append(
            "No common model revision or config digest is available; identity "
            "verification is partial."
        )

    if mismatches:
        state = ExperimentIdentityState.MISMATCH
    elif is_partial:
        state = ExperimentIdentityState.PARTIAL
    else:
        state = ExperimentIdentityState.VERIFIED
    return ExperimentIdentityResult(
        state=state,
        mismatches=tuple(mismatches),
        warnings=tuple(warnings),
    )
