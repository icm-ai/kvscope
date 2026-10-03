# Workload sensitivity sweep

`kvscope sweep` varies exactly one inference workload dimension at a time and
runs the same static feasibility analysis for each value. It can evaluate one
or more explicit hardware/backend target pairs; every other model, target, and
workload setting remains fixed.

Sweep context length:

```bash
uv run kvscope sweep qwen-example \
  --target generic-discrete-8gib=vllm \
  --target generic-discrete-16gib=vllm \
  --parameter-count 4000000000 \
  --contexts 2048 4096 8192 \
  --format markdown
```

Sweep active sequence count at a fixed context length:

```bash
uv run kvscope sweep qwen-example \
  --target generic-discrete-16gib=vllm \
  --parameter-count 4000000000 \
  --context 4096 \
  --active-sequences 1 2 4 \
  --format json
```

Provide at least two distinct positive values. Values and target pairs retain
the supplied order. Context and active-sequence sweeps are mutually exclusive;
the command does not form a Cartesian product. Terminal, JSON, and Markdown
formats show feasibility, confidence, requirement and recommended-headroom
ranges, plus the primary constraint. They also summarize changes in each target's
user-facing feasibility status between adjacent supplied samples. These are
sampled brackets, not exact thresholds: the report preserves input order and
does not sort, interpolate, extrapolate, or recommend settings. If status does
not change between a pair, that pair produces no transition entry. Versioned
JSON output follows `workload-sweep-v0.1.json` and nests the same per-target
feasibility reports used by `kvscope compare`.

The Python API is `sweep_workload(...)` in `kvscope.api`. It takes a resolved
model, an `InferenceConfig`, one or more `DeploymentTarget` objects, one
`WorkloadSweepDimension`, and an ordered sequence of values. It returns each
point with the full deployment comparison report and provenance. It is a
sensitivity report, not an optimizer: it does not search unprovided values,
start a backend, benchmark hardware, or tune settings automatically.
