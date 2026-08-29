"""Opt-in execution of local calibration observation commands."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from kvscope.calibration.schema import (
    CalibrationMeasurement,
    CalibrationObservation,
    CalibrationRunFailure,
    CalibrationRunManifest,
    CalibrationRunResult,
)
from kvscope.domain.evidence import Evidence
from kvscope.errors import CalibrationRunnerError


def _canonical_digest(value: object) -> str:
    """Return a stable SHA-256 digest without persisting sensitive command values."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolve_local_path(path_value: str, base_directory: Path) -> Path:
    """Resolve one manifest-relative local path without opening network locations."""
    if "://" in path_value:
        raise CalibrationRunnerError(
            f"Runner paths must be local file paths, not URLs: {path_value}",
            code="non_local_path",
        )
    path = Path(path_value)
    return path if path.is_absolute() else base_directory / path


def _read_observation(path: Path) -> CalibrationObservation:
    """Load a fresh observation JSON written by the local command."""
    try:
        raw_value: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationRunnerError(
            "Local command completed without writing its observation JSON.",
            code="observation_missing",
        ) from exc
    except UnicodeDecodeError as exc:
        raise CalibrationRunnerError(
            "Local command observation JSON is not UTF-8.",
            code="observation_invalid_encoding",
        ) from exc
    except json.JSONDecodeError as exc:
        raise CalibrationRunnerError(
            "Local command observation JSON is invalid at "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}",
            code="observation_invalid_json",
        ) from exc
    if not isinstance(raw_value, dict):
        raise CalibrationRunnerError(
            "Local command observation JSON root must be an object.",
            code="observation_invalid_root",
        )
    try:
        return CalibrationObservation.model_validate(raw_value)
    except ValidationError as exc:
        raise CalibrationRunnerError(
            f"Local command observation JSON does not match v0.1: {exc}",
            code="observation_invalid_schema",
        ) from exc


def _runner_environment(
    manifest: CalibrationRunManifest, observation_path: Path
) -> dict[str, str]:
    """Construct an environment while recording names rather than secret values."""
    environment = dict(os.environ) if manifest.inherit_environment else {}
    if not manifest.inherit_environment:
        for name in manifest.environment_names:
            if name in os.environ:
                environment[name] = os.environ[name]
    environment["KVSCOPE_OBSERVATION_PATH"] = str(observation_path)
    return environment


def run_calibration_manifest(
    manifest: CalibrationRunManifest,
    *,
    manifest_directory: str | Path = ".",
) -> CalibrationRunResult:
    """Run a declared local argv command and import its repeated observations.

    ``command`` is always passed as an argv sequence with ``shell=False``. The
    runner never records stdout, stderr, environment values, or command text in
    the result; it records stable digests and non-sensitive failure categories.
    """
    base_directory = Path(manifest_directory)
    observation_path = _resolve_local_path(
        manifest.observation_json_path, base_directory
    )
    working_directory = (
        _resolve_local_path(manifest.working_directory, base_directory)
        if manifest.working_directory is not None
        else base_directory
    )
    if not working_directory.is_dir():
        raise CalibrationRunnerError(
            f"Runner working directory does not exist: {working_directory}",
            code="working_directory_missing",
        )
    observation_path.parent.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(UTC)
    successful_measurements: list[CalibrationMeasurement] = []
    failures: list[CalibrationRunFailure] = []
    command_digest = _canonical_digest(manifest.command)
    manifest_digest = _canonical_digest(manifest.model_dump(mode="json"))
    runner_evidence = Evidence(
        evidence_id=f"{manifest.run_id}-runner",
        source_type="local_runner",
        source=(
            f"Local argv runner; command_sha256={command_digest}; "
            f"environment_names={','.join(sorted(manifest.environment_names))}"
        ),
        notes="Command output and environment values are intentionally not retained.",
    )

    for sample_index in range(1, manifest.repetitions + 1):
        observation_path.unlink(missing_ok=True)
        try:
            completed = subprocess.run(
                manifest.command,
                cwd=working_directory,
                env=_runner_environment(manifest, observation_path),
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=manifest.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            failures.append(
                CalibrationRunFailure(
                    sample_index=sample_index,
                    code="command_timeout",
                    return_code=None,
                    message="Local command exceeded the configured timeout.",
                )
            )
            continue
        except OSError as exc:
            failures.append(
                CalibrationRunFailure(
                    sample_index=sample_index,
                    code="command_execution_error",
                    return_code=None,
                    message=(
                        "Local command could not be executed: "
                        f"{exc.__class__.__name__}."
                    ),
                )
            )
            continue

        if completed.returncode != 0:
            failures.append(
                CalibrationRunFailure(
                    sample_index=sample_index,
                    code="command_nonzero_exit",
                    return_code=completed.returncode,
                    message="Local command returned a nonzero exit status.",
                )
            )
            continue
        try:
            observation = _read_observation(observation_path)
        except CalibrationRunnerError as exc:
            failures.append(
                CalibrationRunFailure(
                    sample_index=sample_index,
                    code=exc.code,
                    return_code=None,
                    message=str(exc),
                )
            )
            continue

        template = manifest.measurement
        successful_measurements.append(
            CalibrationMeasurement(
                schema_version="v0.1",
                record_id=f"{template.record_id_prefix}-{sample_index}",
                collected_at=observation.observed_at,
                backend_profile_id=template.backend_profile_id,
                backend_version=template.backend_version,
                hardware_profile_id=template.hardware_profile_id,
                model_id=template.model_id,
                model_revision=template.model_revision,
                model_config_digest=template.model_config_digest,
                inference_config=template.inference_config,
                observed_peak_memory_bytes=observation.observed_peak_memory_bytes,
                measurement_source=template.measurement_source,
                measurement_method=template.measurement_method,
                confidence=template.confidence,
                notes=template.notes or observation.notes,
                evidence=[*template.evidence, *observation.evidence, runner_evidence],
            )
        )

    completed_at = datetime.now(UTC)
    selected = (
        max(
            successful_measurements,
            key=lambda item: item.observed_peak_memory_bytes,
        )
        if successful_measurements
        else None
    )
    warnings: list[str] = []
    if failures:
        warnings.append(
            f"{len(failures)} of {manifest.repetitions} local runner samples failed."
        )
    if not successful_measurements:
        warnings.append(
            "No valid observations were collected; no measurement was selected."
        )

    return CalibrationRunResult(
        run_id=manifest.run_id,
        manifest_digest=manifest_digest,
        command_digest=command_digest,
        started_at=started_at,
        completed_at=completed_at,
        successful_measurements=successful_measurements,
        failures=failures,
        selected_measurement_id=selected.record_id if selected is not None else None,
        conservative_peak_memory_bytes=(
            selected.observed_peak_memory_bytes if selected is not None else None
        ),
        warnings=warnings,
        evidence=[runner_evidence],
    )
