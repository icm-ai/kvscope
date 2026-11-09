# Repository presentation and maintenance

This document describes how to keep KVScope discoverable and maintainable while preserving the distinction between **static estimates** and **measured inference performance**.

## Recommended GitHub repository metadata

The suggestions below require a manual change in GitHub's repository **About** settings; merging this document will not apply them automatically.

**Description:** Explainable LLM inference memory, KV-cache, and hardware-budget estimator.

**Topics:** `llm-inference`, `kv-cache`, `memory-estimation`, `ai-infrastructure`, `llama-cpp`, `vllm`, `python`

**Homepage:** Leave unset unless a maintained project website is available.

## Documentation entry points

- [README](../README.md): capabilities, limitations, and verified development commands.
- [Deployment comparison](deployment-comparison.md): comparison across backends and hardware.
- [Workload sweep](workload-sweep.md): feasibility under changing workload assumptions.
- [MoE weight analysis](moe-weight-analysis.md): total versus active parameters.
- [Calibration](calibration.md): comparison with collected runtime observations and security boundaries.
- [Contributing](../CONTRIBUTING.md): contribution workflow.

## Release-readiness checklist

- [ ] Run the checks documented in the README.
- [ ] Review release notes and compatibility before declaring a stable version.
- [ ] Clearly distinguish estimated bytes from observed peak memory.
- [ ] Label bundled generic backend profiles as unverified planning inputs.
- [ ] Validate claims about specific hardware and backend versions with repeatable measurements.
- [ ] Check that examples do not imply automatic execution of downloaded weights or remote code.
- [ ] Confirm that documentation links and example commands remain valid.

## Maintenance policy

Keep a small number of current entry points and prefer linking existing documentation over duplicating it. Use reviewable pull requests for documentation changes. Do not rewrite repository history or silently modify published benchmark claims. Any changes to runtime behavior, defaults, or supported platforms require separate technical validation.
