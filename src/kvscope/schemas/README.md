# Versioned schemas

KVScope ships JSON schemas alongside the frozen Pydantic boundary models. JSON
reports are the rendering source of truth; all memory values are integer bytes.

- `calibration-record-v0.1.json` defines a local peak-memory measurement record
  imported by `kvscope calibrate compare`.
- `calibration-run-v0.1.json` defines a runner manifest (not a run result).
- `calibration-observation-v0.1.json` defines the JSON written by the explicitly
  selected local observation command.
- `calibration-comparison-v0.1.json` defines estimate/measurement comparison output.
- `calibration-run-result-v0.1.json` defines the runner audit result.
- `calibration-review-v0.1.json` defines the human review audit artifact.
- `feasibility-report-v0.1.json` defines feasibility reports consumed by
  calibration comparison, with optional MoE weight metadata.
- `deployment-comparison-v0.1.json` defines multi-target static comparison output.
- `workload-sweep-v0.1.json` defines one-dimensional workload sensitivity reports and sampled feasibility transitions.
- `moe-weight-analysis-v0.1.json` defines optional static MoE metadata attached
  to feasibility reports.
- `calibration-profile-candidate-v0.1.json` defines review-only scoped empirical
  reserve candidates; it is not a backend profile schema.

All seven calibration schemas use Draft 2020-12 and contain their nested `$defs`
locally. They are generated from Pydantic validation schemas with
`tools/generate_calibration_schemas.py`; `--check` compares complete parsed JSON.
`jsonschema` is a development/test-only dependency. Runtime calibration inputs are
still validated by frozen Pydantic models, not by a runtime JSON Schema validator.

| Schema | Canonical kind | Import behavior |
| --- | --- | --- |
| calibration-record-v0.1.json | absent | Public measurement loader removes any supplied `kind` for historical compatibility. |
| calibration-run-v0.1.json | absent | Public manifest loader removes any supplied `kind` for historical compatibility. |
| calibration-observation-v0.1.json | absent | Runner-internal input; no public loader. |
| calibration-comparison-v0.1.json | `calibration_comparison` optional | Public loader accepts absent/null kind; checks non-null kind. |
| calibration-run-result-v0.1.json | `calibration_run_result` required | Audit output; no public loader. |
| calibration-profile-candidate-v0.1.json | `calibration_profile_candidate` optional | Public loader accepts absent/null kind; checks non-null kind. |
| calibration-review-v0.1.json | `calibration_review_decision` required | Audit output; no public loader. |

Nullable identity and prediction fields use explicit null unions; fields remain
required unless their Pydantic model supplies a default. Static schemas capture
field types, bounds, enums, required fields, and local references, but cannot
replace custom runtime checks such as timezone awareness, confidence restrictions
for unknown identity, ordered ranges, or cross-artifact identity/fit policy.
JSON Schema integer validation also does not promise Pydantic `StrictInt`
identical behavior for every JSON numeric representation. Comparison/candidate
canonical schemas reject explicit null kind even though their legacy loaders
accept it. Dev tests include `rfc3339-validator` so `FormatChecker` actually has a
`date-time` checker; runtime timezone/confidence/range validators remain required.
