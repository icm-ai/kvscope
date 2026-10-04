# Reproducible experiment identity

KVScope keeps report and calibration JSON models distinct while sharing their
in-process identity field semantics. `AnalysisInferenceConfig` and
`CalibrationInferenceConfig` remain independent frozen, extra-forbid wire model
classes at their original import paths. Both inherit the same finite ten-field
configuration declaration from `domain.experiment_identity`.

## Persisted inference configuration

Fields are serialized and compared in this exact order:

| Order | Field | Contract |
|---:|---|---|
| 1 | `context_length` | strict integer, greater than zero |
| 2 | `batch_size` | strict integer, greater than zero |
| 3 | `max_num_seqs` | strict integer, greater than zero |
| 4 | `active_sequences` | strict integer, greater than zero; effective value used by the workload |
| 5 | `prefix_tokens` | strict integer, zero or greater |
| 6 | `multimodal_tokens` | strict integer, zero or greater |
| 7 | `weight_dtype` | non-empty strict string; projected from enum `.value` |
| 8 | `kv_dtype` | non-empty strict string; projected from enum `.value` |
| 9 | `graph_capture_enabled` | strict boolean |
| 10 | `cpu_offload_bytes` | strict integer, zero or greater |

`active_sequences` is the explicit `active_sequences_override` when present;
otherwise it is `max(batch_size, max_num_seqs)`. The raw override, its source,
and `safety_margin_ratio` are not persisted identity fields. An override equal
to the natural effective value therefore does not create a distinct identity.
Dtype strings are not stripped, normalized, or restricted beyond the existing
non-empty-string validation.

## Identity comparison and unknown values

The comparison order is required IDs (`model_id`, `backend_profile_id`,
`hardware_profile_id`), the ten configuration fields above, `backend_version`,
then model fingerprints (`model_revision`, `model_config_digest`). Every
mismatch is retained as `<field>: report=<repr>, measurement=<repr>`; config
mismatches use the `inference_config.<field>` prefix.

| Information | Matching / unknown policy |
|---|---|
| Required IDs and configuration | Any differing value is a mismatch; other diagnostics are still collected. |
| Backend version | Both known and equal is satisfied; either side unknown adds the existing warning and makes identity partial unless a mismatch takes precedence; known unequal is a mismatch. |
| Model revision and config digest | Compare each fingerprint only when both sides know it. Any differing common fingerprint is a mismatch. If at least one is common and all common values match, this condition is satisfied even if another fingerprint is one-sided. |
| No common fingerprint | Adds the existing warning and makes identity partial. |
| Missing report provenance | Identity is unavailable, with the existing missing-provenance warning; no identity is guessed. |

State priority is `unavailable` for absent provenance, then `mismatch` if any
mismatch exists, then `partial` if backend version or common-fingerprint
information is incomplete, otherwise `verified`. Thus a common matching revision
with a one-sided digest can be verified; disjoint revision-only and digest-only
metadata is partial. `verified` means the compared identity conditions passed,
not that all optional metadata is populated.

Identity verification is distinct from comparison status and from calibration
fit's exact-scope requirement. An incomplete report remains
`incomplete_report` regardless of identity. A complete report with partial
identity may still be comparable, with confidence capped at medium. Calibration
fit continues to require identical complete measurement scopes, including
optional fingerprint values.

## Code seam

```text
InferenceConfig
  -> domain.experiment_identity.project_inference_config
  -> existing AnalysisInferenceConfig in prepare_static_workload

AnalysisProvenance + CalibrationMeasurement
  -> typed ExperimentIdentityView values
  -> domain.experiment_identity.verify_experiment_identity
  -> existing CalibrationIdentityVerification / CalibrationComparison
```

The identity module is pure in-process domain code. It does not import engines,
calibration, serialization, or CLI modules and performs no I/O.
