# KVScope

KVScope is a lightweight, explainable toolkit for estimating LLM inference
memory and understanding KV Cache behavior across models and hardware.

> Phase 0 is repository bootstrap. The calculation and analysis APIs are not
> implemented yet, and estimates must not be inferred from this release.

## Current status

The repository currently provides:

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
