# Versioned schemas

KVScope ships JSON schemas alongside the frozen Pydantic boundary models. JSON
reports are the rendering source of truth; all memory values are integer bytes.

- `calibration-record-v0.1.json` defines a local peak-memory measurement record
  imported by `kvscope calibrate compare`.
- `feasibility-report-v0.1.json` defines the report consumed by that comparison.

The runtime does not add a JSON Schema validator dependency. Local calibration
inputs are strictly validated by the matching frozen Pydantic model, including
its schema-version and cross-field constraints.
