# Runtime calibration

KVScope separates static estimates from observed runtime memory. Calibration
artifacts are local, versioned JSON evidence; they never change an active
backend profile automatically.

## Phase 10a: compare imported measurements

Generate a complete feasibility report, then compare it with a separately
collected local measurement record:

```bash
uv run kvscope analyze qwen-example \
  --hardware generic-discrete-16gib \
  --backend vllm \
  --parameter-count 4000000000 \
  --context 4096 \
  --format json > report.json

uv run kvscope calibrate compare \
  --report-json report.json \
  --measurement-json examples/calibration-measurement-v0.1.json \
  --format markdown
```

`CalibrationMeasurement` uses positive integer bytes and preserves nullable
unknown identity fields. The report's `provenance` is compared against model,
backend, hardware, and inference settings. Mismatches and legacy reports
without provenance are non-comparable; partial identity verification caps
confidence at `medium`.

## Phase 10b: opt-in local runner

`kvscope calibrate run` runs only the local argv sequence declared in a
`CalibrationRunManifest`. It calls `subprocess` with `shell=False`, requires an
explicit timeout, and supplies the observation destination through
`KVSCOPE_OBSERVATION_PATH`. It intentionally does not retain command output or
environment variable values; JSON results retain command and manifest SHA-256
digests only.

The external command must already be installed and must write this JSON object
to `KVSCOPE_OBSERVATION_PATH` before exiting successfully:

```json
{
  "schema_version": "v0.1",
  "observation_id": "local-tool-run-001",
  "observed_at": "2026-01-01T12:00:00Z",
  "observed_peak_memory_bytes": 123456789,
  "evidence": [
    {
      "evidence_id": "tool-export-001",
      "source_type": "local_measurement",
      "source": "redacted local tool export"
    }
  ],
  "notes": null
}
```

A manifest contains an argv list, not a shell string. Relative paths are
resolved relative to the manifest file:

```json
{
  "schema_version": "v0.1",
  "run_id": "my-local-vllm-run",
  "command": ["/absolute/path/to/my-local-observer"],
  "observation_json_path": "observation.json",
  "repetitions": 3,
  "timeout_seconds": 600,
  "working_directory": null,
  "inherit_environment": true,
  "environment_names": ["CUDA_VISIBLE_DEVICES"],
  "measurement": {
    "record_id_prefix": "my-local-vllm-run",
    "backend_profile_id": "vllm-generic-unverified-v0",
    "backend_version": "0.6.6",
    "hardware_profile_id": "generic-discrete-16gib",
    "model_id": "my-model",
    "model_revision": "my-revision",
    "model_config_digest": null,
    "inference_config": {
      "context_length": 4096,
      "batch_size": 1,
      "max_num_seqs": 1,
      "active_sequences": 1,
      "prefix_tokens": 0,
      "multimodal_tokens": 0,
      "weight_dtype": "fp16",
      "kv_dtype": "fp16",
      "graph_capture_enabled": false,
      "cpu_offload_bytes": 0
    },
    "measurement_source": "local runner",
    "measurement_method": "external observation JSON",
    "confidence": "high",
    "notes": null,
    "evidence": []
  },
  "notes": "Run only in a controlled local environment."
}
```

Run it with:

```bash
uv run kvscope calibrate run --manifest-json run.json --format json > run-result.json
```

Every successful sample becomes a measurement record. The selected peak is the
maximum successful sample, not an average. Failed samples retain a non-sensitive
failure code; a run with no successful samples exits nonzero and produces no
measurement conclusion. KVScope cannot sandbox a user command: operators must
enforce their own local no-network policy for the selected backend.

## Scoped fitting and review

Fit only comparisons that are `comparable` with `identity_verification` equal to
`verified` and have exactly the same backend/version, hardware, model identity,
and inference configuration:

```bash
uv run kvscope calibrate fit \
  --comparison-json comparison-1.json \
  --comparison-json comparison-2.json \
  --comparison-json comparison-3.json \
  --format json > candidate.json
```

The candidate's reserve is an exact interval of
`max(0, observed_peak - predicted_expected_total)` across the supplied samples.
It never attempts to identify generic backend coefficients. Fewer than three
samples produce `insufficient_data`; that candidate cannot be accepted.

A reviewer can record a decision:

```bash
uv run kvscope calibrate review \
  --candidate-json candidate.json \
  --reviewer alice \
  --decision accepted \
  --notes "Three reproducible local observations." \
  --format json > review.json
```

An accepted review artifact binds the candidate SHA-256 digest and reviewer
identity, but does **not** promote, overwrite, or alter any backend profile.
Profile promotion and generalized formula fitting remain future work.

## Schemas and limitations

Published schemas live in `src/kvscope/schemas/`; frozen Pydantic models perform
runtime validation without adding a JSON Schema runtime dependency. KVScope does
not download models, execute remote model code, add inference-backend
libraries, inspect backend logs, or automatically tune deployment settings.
