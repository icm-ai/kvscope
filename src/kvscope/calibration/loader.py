"""Local-only loaders for calibration artifacts and feasibility reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from kvscope.calibration.artifacts import (
    COMPARISON,
    MEASUREMENT,
    PROFILE_CANDIDATE,
    RUN_MANIFEST,
    CalibrationArtifact,
    apply_loader_kind,
)
from kvscope.calibration.schema import (
    CalibrationComparison,
    CalibrationMeasurement,
    CalibrationProfileCandidate,
    CalibrationRunManifest,
)
from kvscope.domain.report import MemoryFeasibilityReport
from kvscope.errors import CalibrationLoadError

ArtifactModel = TypeVar("ArtifactModel", bound=BaseModel)


def _read_local_json(path: str | Path, *, label: str) -> dict[str, Any]:
    """Read one local JSON object and raise an actionable calibration error."""
    path_string = str(path)
    if "://" in path_string:
        raise CalibrationLoadError(
            f"{label} must be a local file path, not a URL: {path_string}",
            code="non_local_path",
        )
    local_path = Path(path)
    if not local_path.is_file():
        raise CalibrationLoadError(
            f"{label} file does not exist or is not a regular file: {local_path}",
            code="file_not_found",
        )
    try:
        raw_value = json.loads(local_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise CalibrationLoadError(
            f"{label} file is not valid UTF-8 JSON: {local_path}",
            code="invalid_encoding",
        ) from exc
    except json.JSONDecodeError as exc:
        raise CalibrationLoadError(
            f"{label} file contains invalid JSON at line {exc.lineno}, column "
            f"{exc.colno}: {exc.msg}",
            code="invalid_json",
        ) from exc
    if not isinstance(raw_value, dict):
        raise CalibrationLoadError(
            f"{label} JSON root must be an object: {local_path}",
            code="invalid_root",
        )
    return raw_value


def _load_model(
    path: str | Path,
    *,
    label: str,
    artifact: CalibrationArtifact[ArtifactModel],
    schema_name: str | None = None,
) -> ArtifactModel:
    """Load one Pydantic artifact using its centralized kind policy."""
    data = _read_local_json(path, label=label)
    try:
        apply_loader_kind(data, artifact)
    except ValueError as exc:
        expected_kind = str(exc)
        raise CalibrationLoadError(
            f"{label} has unexpected kind; expected {expected_kind!r}.",
            code="unexpected_artifact_kind",
        ) from exc
    try:
        return artifact.model_type.model_validate(data)
    except ValidationError as exc:
        raise CalibrationLoadError(
            f"{label} does not match {schema_name or 'its v0.1 schema'}: {exc}",
            code="invalid_artifact_schema",
        ) from exc


def load_calibration_measurement(path: str | Path) -> CalibrationMeasurement:
    """Load and strictly validate a versioned measurement record from local JSON."""
    return _load_model(
        path,
        label="Calibration measurement",
        artifact=MEASUREMENT,
        schema_name=MEASUREMENT.schema_filename,
    )


def load_calibration_run_manifest(path: str | Path) -> CalibrationRunManifest:
    """Load a strictly validated manifest for an explicit local runner command."""
    return _load_model(
        path,
        label="Calibration run manifest",
        artifact=RUN_MANIFEST,
    )


def load_calibration_comparison(path: str | Path) -> CalibrationComparison:
    """Load a JSON comparison emitted by ``kvscope calibrate compare``."""
    return _load_model(
        path,
        label="Calibration comparison",
        artifact=COMPARISON,
    )


def load_calibration_profile_candidate(path: str | Path) -> CalibrationProfileCandidate:
    """Load a local review-only empirical reserve candidate."""
    return _load_model(
        path,
        label="Calibration profile candidate",
        artifact=PROFILE_CANDIDATE,
    )


def load_memory_feasibility_report(path: str | Path) -> MemoryFeasibilityReport:
    """Load a JSON feasibility report emitted by ``kvscope analyze --format json``."""
    data = _read_local_json(path, label="Feasibility report")
    kind = data.pop("kind", None)
    if kind is not None and kind != "memory_feasibility_report":
        raise CalibrationLoadError(
            "Feasibility report has unexpected kind; expected "
            "'memory_feasibility_report'.",
            code="unexpected_report_kind",
        )
    if data.get("schema_version") != "v0.1":
        raise CalibrationLoadError(
            "Feasibility report schema_version must be 'v0.1' for calibration "
            "comparison.",
            code="unsupported_report_schema",
        )
    try:
        return MemoryFeasibilityReport.model_validate(data)
    except ValidationError as exc:
        raise CalibrationLoadError(
            f"Feasibility report does not match the v0.1 report schema: {exc}",
            code="invalid_report_schema",
        ) from exc
