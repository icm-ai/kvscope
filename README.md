# KVScope

KVScope is a lightweight, explainable toolkit for estimating LLM inference
memory and understanding KV Cache behavior across models and hardware.

> Phase 5 provides static model configuration resolution. It never downloads
> weights or executes remote model code.

## Current status

The repository currently provides:

- `resolve_model()` for explicit, local, Hugging Face, and registry sources;
- offline, revision-aware metadata caching and architecture adapters;

- a Python 3.11+ `src/` layout;
- the package and CLI entry point;
- reserved module boundaries for domain, resolver, calculator, engine,
  registry, calibration, and serialization layers;
- pytest, coverage, mypy, ruff, pre-commit, and GitHub Actions configuration.

InferPilot, model downloads, inference services, Web UI, benchmarks, and
automatic tuning are explicitly out of scope.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
kvscope --version
kvscope --help
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
