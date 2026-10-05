"""Finite internal contracts for the published calibration artifact family.

This module is deliberately not a plugin registry: the descriptors enumerate the
seven versioned artifacts supported by KVScope and are consumed by loaders,
serializers, and schema tooling.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from kvscope.calibration.schema import (
    CalibrationComparison,
    CalibrationMeasurement,
    CalibrationObservation,
    CalibrationProfileCandidate,
    CalibrationReviewDecision,
    CalibrationRunManifest,
    CalibrationRunResult,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class KindPolicy(StrEnum):
    """How a loader treats an optional serialized ``kind`` discriminator."""

    IGNORE = "ignore"
    OPTIONAL_MATCH = "optional_match"
    OUTPUT_REQUIRED = "output_required"
    NOT_LOADABLE = "not_loadable"


@dataclass(frozen=True, slots=True)
class CalibrationArtifact(Generic[ModelT]):
    """Immutable descriptor for one supported calibration artifact."""

    name: str
    model_type: type[ModelT]
    schema_filename: str
    output_kind: str | None
    kind_policy: KindPolicy


MEASUREMENT = CalibrationArtifact(
    "measurement",
    CalibrationMeasurement,
    "calibration-record-v0.1.json",
    None,
    KindPolicy.IGNORE,
)
RUN_MANIFEST = CalibrationArtifact(
    "run_manifest",
    CalibrationRunManifest,
    "calibration-run-v0.1.json",
    None,
    KindPolicy.IGNORE,
)
OBSERVATION = CalibrationArtifact(
    "observation",
    CalibrationObservation,
    "calibration-observation-v0.1.json",
    None,
    KindPolicy.NOT_LOADABLE,
)
COMPARISON = CalibrationArtifact(
    "comparison",
    CalibrationComparison,
    "calibration-comparison-v0.1.json",
    "calibration_comparison",
    KindPolicy.OPTIONAL_MATCH,
)
RUN_RESULT = CalibrationArtifact(
    "run_result",
    CalibrationRunResult,
    "calibration-run-result-v0.1.json",
    "calibration_run_result",
    KindPolicy.OUTPUT_REQUIRED,
)
PROFILE_CANDIDATE = CalibrationArtifact(
    "profile_candidate",
    CalibrationProfileCandidate,
    "calibration-profile-candidate-v0.1.json",
    "calibration_profile_candidate",
    KindPolicy.OPTIONAL_MATCH,
)
REVIEW_DECISION = CalibrationArtifact(
    "review_decision",
    CalibrationReviewDecision,
    "calibration-review-v0.1.json",
    "calibration_review_decision",
    KindPolicy.OUTPUT_REQUIRED,
)

CALIBRATION_ARTIFACTS: tuple[CalibrationArtifact[Any], ...] = (
    MEASUREMENT,
    RUN_MANIFEST,
    OBSERVATION,
    COMPARISON,
    RUN_RESULT,
    PROFILE_CANDIDATE,
    REVIEW_DECISION,
)


def apply_loader_kind(data: dict[str, Any], artifact: CalibrationArtifact[Any]) -> None:
    """Apply the established kind compatibility policy in-place."""
    kind = data.pop("kind", None)
    if artifact.kind_policy is KindPolicy.OPTIONAL_MATCH and kind is not None:
        if kind != artifact.output_kind:
            raise ValueError(artifact.output_kind)
    elif artifact.kind_policy in {KindPolicy.OUTPUT_REQUIRED, KindPolicy.NOT_LOADABLE}:
        raise ValueError(f"{artifact.name} is not loadable")


def serialize_artifact_json(
    model: BaseModel, artifact: CalibrationArtifact[Any], indent: int
) -> str:
    """Dump model JSON with the descriptor's canonical output discriminator."""
    data: dict[str, Any] = json.loads(model.model_dump_json())
    if artifact.output_kind is not None:
        data["kind"] = artifact.output_kind
    return json.dumps(data, ensure_ascii=False, indent=indent)
