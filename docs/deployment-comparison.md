# Multi-target deployment comparison

`kvscope compare` evaluates one resolved model and one fixed inference workload
against two or more explicitly selected hardware/backend pairs. It reuses the
static estimate and feasibility engines; it does not launch a backend or run a
benchmark.

```bash
uv run kvscope compare qwen-example \
  --target generic-discrete-8gib=vllm \
  --target generic-discrete-16gib=vllm \
  --backend-version 0.6.6 \
  --parameter-count 4000000000 \
  --context 4096 \
  --format markdown
```

Repeat `--target HARDWARE_PROFILE=BACKEND_PROFILE` for each target. Targets are
explicit pairs rather than an implicit Cartesian product. A single optional
`--backend-version` is applied to every selected backend. The same model,
context, batch, concurrency, dtypes, token counts, graph-capture setting, and
user reserve are used for every target.

The `--format json` output is the versioned `deployment-comparison-v0.1.json`
fact source. It records the model identity, config digest, resolved parameter
count, and shared workload. Each target includes its hardware/backend identity
and a complete feasibility report with provenance, uncertainty intervals,
confidence, constraints, and warnings. Terminal and Markdown formats summarize
requirement ranges, headroom versus the recommended allocation, feasibility,
confidence, and the primary constraint.

Results preserve the supplied target order. KVScope does not invent a single
winner when estimates have overlapping uncertainty intervals; compare the
reported feasibility and memory ranges, then validate the chosen setup on the
target machine. Built-in generic backend profiles remain unverified planning
templates.

The Python API accepts already resolved profiles so callers control exactly
which targets are compared:

```python
from kvscope.api import (
    DeploymentTarget,
    InferenceConfig,
    KVDType,
    WeightDType,
    compare_deployment_targets,
    resolve_backend_profile,
    resolve_hardware_profile,
    resolve_model,
)

model = resolve_model("qwen-example")
model = model.model_copy(
    update={"spec": model.spec.model_copy(update={"parameter_count": 4_000_000_000})}
)
config = InferenceConfig(
    weight_dtype=WeightDType.FP16,
    kv_dtype=KVDType.FP16,
    context_length=4096,
)
hardware_8gib = resolve_hardware_profile("generic-discrete-8gib").profile
hardware_16gib = resolve_hardware_profile("generic-discrete-16gib").profile
backend_8gib = resolve_backend_profile("vllm", hardware=hardware_8gib).profile
backend_16gib = resolve_backend_profile("vllm", hardware=hardware_16gib).profile

result = compare_deployment_targets(
    model=model,
    inference_config=config,
    targets=[
        DeploymentTarget(
            target_id="8gib-vllm",
            hardware=hardware_8gib,
            backend=backend_8gib,
        ),
        DeploymentTarget(
            target_id="16gib-vllm",
            hardware=hardware_16gib,
            backend=backend_16gib,
        ),
    ],
)
```

At least two targets with unique IDs are required. `model` must be a
`ResolvedModel` and must provide a parameter count (or the caller must override
it before comparison).
