# Offline runtime calibration records (Phase 10a)

Phase 10a imports a peak-memory measurement that was already collected by a
user or external tool, then compares it to a complete KVScope feasibility
report. It is offline analysis only: KVScope does not start a backend, run a
benchmark, read logs, access the network, or change a backend profile.

## Compare a report and measurement

First retain the JSON feasibility report produced by the same static-analysis
configuration:

```bash
uv run kvscope analyze qwen-example \
  --hardware generic-discrete-16gib \
  --backend vllm \
  --parameter-count 4000000000 \
  --context 4096 \
  --format json > report.json
```

Record a real observed peak in the versioned format, then compare only local
files:

```bash
uv run kvscope calibrate compare \
  --report-json report.json \
  --measurement-json examples/calibration-measurement-v0.1.json \
  --format markdown
```

`terminal`, `json`, and `markdown` are supported. JSON is the stable,
versioned fact source (`kind: "calibration_comparison"`,
`schema_version: "v0.1"`). The command exits with status 3 after rendering a
structured result if the report is partial; it does not calculate a total-memory
error in that case.

## Measurement record format

`src/kvscope/schemas/calibration-record-v0.1.json` is the published schema and
`examples/calibration-measurement-v0.1.json` is a validation-ready, redacted
example. Every record includes:

- schema version, stable record ID, and timezone-aware collection timestamp;
- backend profile ID, nullable backend version, and hardware profile ID;
- model ID plus nullable revision and config digest;
- context, batch/concurrency, dtype, graph-capture, and offload settings;
- strictly positive `observed_peak_memory_bytes` (integer bytes only);
- measurement source, method, explicit confidence, notes, and at least one
  evidence entry.

Use `null` for an unknown backend version, revision, digest, or note. Do not use
`0`, an empty string, or `high` confidence to stand in for unknown information.
When the backend version or both model revision and config digest are unknown,
the record cannot claim `high` or `exact` confidence.

## Interpreting the result

The comparison uses `aggregation.total_requirement`, not an individual memory
component. It reports whether the observed peak is inside the prediction
interval, exact signed byte deltas `observed - predicted` for lower/expected/
upper boundaries, and an exact relative-error fraction against the expected
boundary. Fractions are stored as integer numerator and denominator bytes, not
binary floating point.

`kvscope analyze --format json` emits a frozen `provenance` object containing
model ID/revision/config digest, backend profile/version, hardware profile, and
the inference settings used to form the report. Calibration compares every
known value. A mismatch is rejected without calculating an error conclusion;
unknown optional identity values produce an explicitly `partial` verification
and cap confidence at `medium`. Legacy reports without provenance are rejected
as `identity_unverified`. A partial report, a report without
`total_requirement`, or invalid local JSON is likewise explicitly rejected or
downgraded; it never yields an optimistic conclusion.

## Why this does not alter profiles

One peak observation is evidence, not a universal runtime model. Backend
versions, driver/runtime state, allocator behavior, quantization artifacts,
workload shape, and measurement tooling can all change observed memory. Phase
10a keeps raw measurements and error analysis auditable for manual review.
Automatic fitting, profile/reserve updates, backend launch, benchmark capture,
log ingestion, and network collection are intentionally deferred to Phase 10b.
