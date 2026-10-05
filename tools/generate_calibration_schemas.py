#!/usr/bin/env python3
"""Generate/check published JSON Schemas from calibration Pydantic models."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kvscope.calibration.artifacts import (  # noqa: E402
    CALIBRATION_ARTIFACTS,
    KindPolicy,
)

SCHEMA_DIR = ROOT / "src" / "kvscope" / "schemas"


def generated_schema(artifact: Any) -> dict[str, Any]:
    """Build one self-contained Draft 2020-12 schema from its model."""
    schema = artifact.model_type.model_json_schema(
        mode="validation", ref_template="#/$defs/{model}"
    )
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    kind_policy = artifact.kind_policy
    if artifact.output_kind is not None:
        properties = schema.setdefault("properties", {})
        properties["kind"] = {"const": artifact.output_kind, "type": "string"}
        if kind_policy is KindPolicy.OUTPUT_REQUIRED:
            schema.setdefault("required", []).append("kind")
    return schema


def render(schema: dict[str, Any]) -> str:
    """Render stable, reviewable JSON with a terminal newline."""
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    """Generate schemas or report drift without changing files."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    failures: list[str] = []
    for artifact in CALIBRATION_ARTIFACTS:
        path = SCHEMA_DIR / artifact.schema_filename
        expected = generated_schema(artifact)
        if args.check:
            try:
                actual = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                failures.append(f"{path.name}: unavailable or invalid JSON ({exc})")
                continue
            if actual != expected:
                failures.append(f"{path.name}: schema drift")
        else:
            path.write_text(render(expected), encoding="utf-8")
    if failures:
        print("Calibration schema check failed:", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        return 1
    print(
        f"{'Checked' if args.check else 'Generated'} "
        f"{len(CALIBRATION_ARTIFACTS)} calibration schemas."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
