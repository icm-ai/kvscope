"""Local-only loaders for calibration measurements and feasibility reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from kvscope.calibration.schema import CalibrationMeasurement
from kvscope.domain.report import MemoryFeasibilityReport
from kvscope.errors import CalibrationLoadError


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


def load_calibration_measurement(path: str | Path) -> CalibrationMeasurement:
    """Load and strictly validate a versioned measurement record from local JSON."""
    data = _read_local_json(path, label="Calibration measurement")
    try:
        return CalibrationMeasurement.model_validate(data)
    except ValidationError as exc:
        raise CalibrationLoadError(
            "Calibration measurement does not match calibration-record-v0.1.json: "
            f"{exc}",
            code="invalid_measurement_schema",
        ) from exc


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
