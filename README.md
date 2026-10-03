# KVScope

KVScope is a lightweight, explainable toolkit for estimating LLM inference
memory, KV Cache requirements, hardware memory budgets, and backend runtime overhead.

KVScope performs static, explainable memory analysis. It never downloads weights
or executes remote model code. As an explicit opt-in exception, the Phase 10b
calibration runner can execute only a user-declared local argv command; it does
not automatically launch a backend or modify backend profiles.

## Current status

The repository currently provides:

- Model, hardware, and backend profile resolution;
- Weight, KV cache, hardware-budget, and runtime-overhead estimates using integer bytes and explicit uncertainty intervals;
- Feasibility assessment, constraint analysis, safe context/concurrency limits, and recommendation generation;
- Built-in generic, unverified vLLM and llama.cpp profiles for preliminary planning;
- Terminal, JSON, and Markdown outputs, including `kvscope analyze`, multi-target `kvscope compare`, and one-axis `kvscope sweep`;
- A Python 3.11+ `src/` layout;
- pytest, coverage, mypy, ruff, pre-commit, and GitHub Actions configuration.

The bundled backend profiles are not calibrated measurements. Treat their results as
planning guidance and validate the selected model, backend version, and hardware
with a benchmark before deployment.

## Quick start

```bash
uv sync --extra dev
uv run kvscope backend list
uv run kvscope analyze qwen-example \
  --hardware generic-discrete-16gib \
  --backend vllm \
  --parameter-count 4000000000 \
  --context 4096 \
  --recommend
```

`--parameter-count` is required when the resolved model config does not include
one. Use `--format json` or `--format markdown` to emit machine-readable or
shareable output.

To compare one workload across hardware/backend profile pairs, use
`kvscope compare`; see [docs/deployment-comparison.md](docs/deployment-comparison.md).
To inspect how context length or active sequence count changes feasibility, use
`kvscope sweep`; see [docs/workload-sweep.md](docs/workload-sweep.md).
To compare an existing complete JSON report with a locally collected peak-memory
record, use `kvscope calibrate compare`. Phase 10b also provides an opt-in local
runner, scoped candidate fitting, and human review artifacts. These never promote
or modify backend profiles automatically. See [docs/calibration.md](docs/calibration.md)
for commands, limitations, and the local runner security boundary.

## Development checks

```bash
uv run ruff check .
uv run mypy src/kvscope
uv run pytest --cov=kvscope --cov-report=term-missing
uv run pre-commit run --all-files
```

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the
planned v0.1 delivery stages and [CONTRIBUTING.md](CONTRIBUTING.md) for the
contribution workflow.
