"""Published calibration schemas stay complete and locally self-contained."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from pydantic import ValidationError as RuntimeValidationError

from kvscope.calibration.artifacts import (
    CALIBRATION_ARTIFACTS,
    COMPARISON,
    MEASUREMENT,
    OBSERVATION,
    PROFILE_CANDIDATE,
    REVIEW_DECISION,
    RUN_MANIFEST,
    RUN_RESULT,
    CalibrationArtifact,
    apply_loader_kind,
    serialize_artifact_json,
)
from kvscope.calibration.schema import CalibrationObservation

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "src" / "kvscope" / "schemas"


def test_all_calibration_schemas_are_draft_2020_12_and_self_contained() -> None:
    """Every declared artifact schema validates as a complete local schema."""
    assert len(CALIBRATION_ARTIFACTS) == 7
    for artifact in CALIBRATION_ARTIFACTS:
        schema = json.loads((SCHEMA_DIR / artifact.schema_filename).read_text())
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"].endswith("2020-12/schema")
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for item in validator.iter_errors({}):
            assert item.validator == "required"
        for reference in _local_references(schema):
            assert reference.startswith("#/$defs/")
            assert reference.removeprefix("#/$defs/") in schema["$defs"]


def test_generated_schemas_have_no_drift() -> None:
    """The checked-in schema assets exactly match model-derived generation."""
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/generate_calibration_schemas.py"),
            "--check",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generation_tracks_model_field_changes() -> None:
    """A model-side field addition appears in the generation result."""
    from pydantic import BaseModel

    from kvscope.calibration.artifacts import CalibrationArtifact, KindPolicy

    script = ROOT / "tools/generate_calibration_schemas.py"
    spec = importlib.util.spec_from_file_location("schema_generator", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generated_schema = module.generated_schema

    class ExtendedArtifact(BaseModel):
        schema_version: str
        additional_fact: int

    descriptor = CalibrationArtifact(
        "extended", ExtendedArtifact, "unused.json", None, KindPolicy.IGNORE
    )
    # Pydantic's generated properties are the source: no parallel field inventory.
    schema = generated_schema(descriptor)
    assert "additional_fact" in schema["properties"]
    assert descriptor.model_type.model_fields["additional_fact"].annotation is int


def assert_artifact_valid(artifact: CalibrationArtifact[Any], instance: object) -> None:
    """Assert a concrete serialized artifact satisfies its published schema."""
    schema = json.loads((SCHEMA_DIR / artifact.schema_filename).read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def test_kinds_are_required_only_for_canonical_audit_outputs() -> None:
    """The kind envelope preserves legacy input while auditing canonical output."""
    by_name = {artifact.name: artifact for artifact in CALIBRATION_ARTIFACTS}
    for artifact in (by_name["comparison"], by_name["profile_candidate"]):
        schema = json.loads((SCHEMA_DIR / artifact.schema_filename).read_text())
        assert "kind" not in schema["required"]
        assert schema["properties"]["kind"]["const"] == artifact.output_kind
    for artifact in (by_name["run_result"], by_name["review_decision"]):
        schema = json.loads((SCHEMA_DIR / artifact.schema_filename).read_text())
        assert "kind" in schema["required"]
        assert schema["properties"]["kind"]["const"] == artifact.output_kind
    assert (
        MEASUREMENT.output_kind
        is RUN_MANIFEST.output_kind
        is OBSERVATION.output_kind
        is None
    )
    assert COMPARISON.output_kind == "calibration_comparison"
    assert RUN_RESULT.output_kind == "calibration_run_result"
    assert PROFILE_CANDIDATE.output_kind == "calibration_profile_candidate"
    assert REVIEW_DECISION.output_kind == "calibration_review_decision"


@pytest.mark.parametrize("artifact", [OBSERVATION, RUN_RESULT, REVIEW_DECISION])
def test_audit_only_artifacts_cannot_be_loaded(
    artifact: CalibrationArtifact[Any],
) -> None:
    """Internal kind policy rejects artifacts without a public import contract."""
    with pytest.raises(ValueError, match="is not loadable"):
        apply_loader_kind({}, artifact)


def _observation_data() -> dict[str, Any]:
    return {
        "schema_version": "v0.1",
        "observation_id": "观测",
        "observed_at": "2025-01-15T12:00:00Z",
        "observed_peak_memory_bytes": 250,
        "evidence": [
            {"evidence_id": "observer", "source_type": "local", "source": "test"}
        ],
        "notes": None,
    }


def test_artifact_without_kind_serializes_bare_unicode_json() -> None:
    """The no-discriminator contract preserves the entire canonical bare model."""
    observation = CalibrationObservation.model_validate(_observation_data())
    serialized = serialize_artifact_json(observation, OBSERVATION, indent=4)
    assert "观测" in serialized
    assert json.loads(serialized) == observation.model_dump(mode="json")
    assert "kind" not in json.loads(serialized)
    assert_artifact_valid(OBSERVATION, json.loads(serialized))


def test_schema_format_checker_really_checks_date_time() -> None:
    """Passing a FormatChecker is not enough if its optional checker is absent."""
    assert "date-time" in FormatChecker().checkers
    data = _observation_data()
    assert_artifact_valid(OBSERVATION, data)
    data["observed_at"] = "2025-01-15T12:00:00"
    with pytest.raises(ValidationError):
        assert_artifact_valid(OBSERVATION, data)
    with pytest.raises(RuntimeValidationError, match="timezone offset"):
        CalibrationObservation.model_validate(data)


def test_schema_integer_does_not_replace_runtime_strict_integer() -> None:
    """Integral floats satisfy JSON Schema but remain rejected at the runtime seam."""
    data = _observation_data()
    data["observed_peak_memory_bytes"] = 1.0
    assert_artifact_valid(OBSERVATION, data)
    with pytest.raises(RuntimeValidationError):
        CalibrationObservation.model_validate(data)


def _local_references(value: object) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            references.append(ref)
        for child in value.values():
            references.extend(_local_references(child))
    elif isinstance(value, list):
        for child in value:
            references.extend(_local_references(child))
    return references
