# KVScope

KVScope is a lightweight, explainable toolkit for estimating LLM inference
memory, KV Cache requirements, hardware memory budgets, and backend runtime overhead.

> Phase 6 provides Hardware Registry, Backend Profile resolution, Hardware Memory Budgeting, and pure-formula Runtime Overhead Estimation with explicit uncertainty ranges. It never downloads weights, executes remote model code, or calls backend runtimes.

## Current status

The repository currently provides:

- `resolve_model()`, `resolve_hardware_profile()`, `resolve_backend_profile()`;
- `estimate_weight_memory()`, `estimate_kv_cache()`, `estimate_hardware_memory_budget()`, and `estimate_runtime_overhead()`;
- Hardware Registry & Backend Registry with built-in profiles and version-specifier matching;
- Uncertainty interval arithmetic (`ByteRange`, `RatioRange`) with integer-byte math;
- Terminal, JSON, and Markdown formatters and CLI subcommands (`kvscope hardware`, `kvscope backend`, `kvscope estimate-overhead`);
- A Python 3.11+ `src/` layout;
- pytest, coverage, mypy, ruff, pre-commit, and GitHub Actions configuration.

InferPilot, feasibility decisions, recommendations, inference services, Web UI, benchmarks, and automatic tuning are explicitly out of scope for Phase 6.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
kvscope --version
kvscope hardware list
kvscope backend list
kvscope estimate-overhead --backend vllm --hardware generic-discrete-16gib --weight-bytes 14000000000 --params 7000000000
```

## Development checks

```bash
ruff check .
mypy src/kvscope
pytest --cov=kvscope --cov-report=term-missing
pre-commit run --all-files
```

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the
planned v0.1 delivery stages and [CONTRIBUTING.md](CONTRIBUTING.md) for the
contribution workflow.
