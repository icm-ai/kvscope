# Versioned schemas

KVScope ships JSON schemas alongside the frozen Pydantic boundary models. JSON
reports are the rendering source of truth; all memory values are integer bytes.

- `calibration-record-v0.1.json` defines a local peak-memory measurement record
  imported by `kvscope calibrate compare`.
- `feasibility-report-v0.1.json` defines the report consumed by calibration comparison.
- `deployment-comparison-v0.1.json` defines multi-target static comparison output.
- `workload-sweep-v0.1.json` defines one-dimensional workload sensitivity reports and sampled feasibility transitions.
- `calibration-run-v0.1.json` defines an explicit local argv runner manifest.
- `calibration-profile-candidate-v0.1.json` defines review-only scoped empirical
  reserve candidates; it is not a backend profile schema.

The runtime does not add a JSON Schema validator dependency. Local calibration
inputs are strictly validated by the matching frozen Pydantic model, including
its schema-version and cross-field constraints.
