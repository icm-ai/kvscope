"""CLI entrypoint for KVScope hardware, backend, and estimation inspection."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import TypeAdapter

from kvscope import __version__
from kvscope.api import (
    KVCacheEstimate,
    WeightMemoryEstimate,
    assess_memory_feasibility,
    estimate_hardware_memory_budget,
    estimate_runtime_overhead,
    resolve_backend_profile,
    resolve_hardware_profile,
    resolve_model,
)
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate
from kvscope.registries.backends import get_default_backend_registry
from kvscope.registries.hardware import get_default_hardware_registry
from kvscope.serialization.json import (
    serialize_budget_to_json,
    serialize_feasibility_report_json,
    serialize_overhead_to_json,
)
from kvscope.serialization.markdown import (
    serialize_budget_to_markdown,
    serialize_feasibility_report_markdown,
    serialize_overhead_to_markdown,
)
from kvscope.serialization.terminal import (
    format_budget_terminal,
    format_feasibility_report_terminal,
    format_overhead_terminal,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with subcommands."""
    desc = (
        "LLM inference memory estimation, hardware budgeting, "
        "and backend overhead analysis CLI."
    )
    parser = argparse.ArgumentParser(
        prog="kvscope",
        description=desc,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Legacy inspect-model command support
    inspect_parser = subparsers.add_parser(
        "inspect-model", help="Inspect model configuration metadata."
    )
    inspect_parser.add_argument(
        "source", help="Model source (HF ID, local path, or config)"
    )
    inspect_parser.add_argument("--revision", help="Model revision/commit")
    inspect_parser.add_argument(
        "--offline", action="store_true", help="Force offline resolution"
    )
    inspect_parser.add_argument(
        "--format",
        choices=("terminal", "json", "text"),
        default="terminal",
        help="Output format",
    )

    # Hardware subcommands
    hw_parser = subparsers.add_parser(
        "hardware", help="Hardware registry & budget operations"
    )
    hw_sub = hw_parser.add_subparsers(dest="action", help="Hardware action")

    hw_sub.add_parser("list", help="List registered hardware profiles")

    hw_show = hw_sub.add_parser("show", help="Show hardware profile details")
    hw_show.add_argument("profile_id", help="Hardware Profile ID or alias")
    hw_show.add_argument("--format", choices=("terminal", "json"), default="terminal")

    hw_budget = hw_sub.add_parser("budget", help="Calculate hardware memory budget")
    hw_budget.add_argument("profile_id", help="Hardware Profile ID or alias")
    hw_budget.add_argument(
        "--user-reserve-bytes", type=int, default=0, help="User reserve in bytes"
    )
    hw_budget.add_argument(
        "--total-memory-bytes",
        type=int,
        default=None,
        help="Physical total memory override in bytes",
    )
    hw_budget.add_argument(
        "--format", choices=("terminal", "json", "markdown"), default="terminal"
    )

    # Backend subcommands
    backend_parser = subparsers.add_parser(
        "backend", help="Backend registry & profile operations"
    )
    backend_sub = backend_parser.add_subparsers(dest="action", help="Backend action")

    backend_sub.add_parser("list", help="List registered backend profiles")

    backend_show = backend_sub.add_parser("show", help="Show backend profile details")
    backend_show.add_argument("backend_id", help="Backend ID or alias")
    backend_show.add_argument(
        "--version", default=None, help="Backend version specifier"
    )
    backend_show.add_argument(
        "--format", choices=("terminal", "json"), default="terminal"
    )

    # Estimate overhead command
    overhead_parser = subparsers.add_parser(
        "estimate-overhead", help="Estimate backend runtime memory overhead"
    )
    overhead_parser.add_argument(
        "--backend", required=True, help="Backend ID or profile ID"
    )
    overhead_parser.add_argument(
        "--backend-version", default=None, help="Backend version string"
    )
    overhead_parser.add_argument(
        "--hardware", required=True, help="Hardware Profile ID or alias"
    )
    overhead_parser.add_argument(
        "--resident-weight-bytes",
        type=int,
        required=True,
        help="Resident weight in bytes",
    )
    overhead_parser.add_argument(
        "--parameter-count", type=int, default=None, help="Parameter count"
    )
    overhead_parser.add_argument(
        "--graph-capture",
        action="store_true",
        help="Enable CUDA/backend graph capture reserve",
    )
    overhead_parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Allow unverified or template profiles",
    )
    overhead_parser.add_argument(
        "--format", choices=("terminal", "json", "markdown"), default="terminal"
    )

    # Assess memory subcommand
    assess_parser = subparsers.add_parser(
        "assess-memory", help="Assess total memory feasibility and constraints"
    )
    assess_parser.add_argument(
        "--weights-json", required=True, help="Path to WeightMemoryEstimate JSON file"
    )
    assess_parser.add_argument(
        "--kv-cache-json", required=True, help="Path to KVCacheEstimate JSON file"
    )
    assess_parser.add_argument(
        "--runtime-overhead-json",
        required=True,
        help="Path to RuntimeOverheadEstimate JSON file",
    )
    assess_parser.add_argument(
        "--hardware-budget-json",
        required=True,
        help="Path to HardwareMemoryBudget JSON file",
    )
    assess_parser.add_argument(
        "--format", choices=("terminal", "json", "markdown"), default="terminal"
    )

    return parser


def _handle_inspect_model(parsed: argparse.Namespace) -> int:
    resolved = resolve_model(
        parsed.source, revision=parsed.revision, offline=parsed.offline
    )
    spec = resolved.spec
    result = {
        "model_id": spec.model_id,
        "architecture": spec.architecture,
        "layers": spec.num_hidden_layers,
        "hidden_size": spec.hidden_size,
        "attention_heads": spec.num_attention_heads,
        "kv_heads": spec.num_key_value_heads,
        "head_dim": spec.head_dim,
        "max_context": spec.max_position_embeddings,
        "source": resolved.source.source_type,
        "revision": resolved.source.resolved_revision,
        "resolver": resolved.resolver_id,
        "adapter": resolved.adapter_id,
        "confidence": resolved.confidence.value,
        "warnings": resolved.warnings,
    }
    if parsed.format == "json":
        import json

        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0


def _handle_hardware(parsed: argparse.Namespace) -> int:
    registry = get_default_hardware_registry()
    if parsed.action == "list":
        profiles = registry.list_profiles()
        print(f"Registered Hardware Profiles ({len(profiles)}):")
        for p in profiles:
            aliases_str = f" (aliases: {', '.join(p.aliases)})" if p.aliases else ""
            top = p.memory_topology.value
            tot = p.total_memory_bytes
            print(f"  - {p.profile_id}{aliases_str}: {p.name} [{top}, {tot} B]")
        return 0
    elif parsed.action == "show":
        resolved = resolve_hardware_profile(parsed.profile_id, allow_deprecated=True)
        if parsed.format == "json":
            print(resolved.profile.model_dump_json(indent=2))
        else:
            p = resolved.profile
            print(f"Hardware Profile: {p.profile_id}")
            print(f"  Name:            {p.name}")
            print(f"  Vendor:          {p.vendor}")
            print(f"  Topology:        {p.memory_topology.value}")
            print(f"  Total Memory:    {p.total_memory_bytes} B")
            print(f"  Confidence:      {p.confidence.value}")
            print(f"  Status:          {p.status.value}")
        return 0
    elif parsed.action == "budget":
        resolved = resolve_hardware_profile(parsed.profile_id, allow_deprecated=True)
        budget = estimate_hardware_memory_budget(
            resolved.profile,
            user_reserve_bytes=parsed.user_reserve_bytes,
            total_memory_override_bytes=parsed.total_memory_bytes,
        )
        if parsed.format == "json":
            print(serialize_budget_to_json(budget))
        elif parsed.format == "markdown":
            print(serialize_budget_to_markdown(budget))
        else:
            print(format_budget_terminal(budget))
        return 0
    return 0


def _handle_backend(parsed: argparse.Namespace) -> int:
    registry = get_default_backend_registry()
    if parsed.action == "list":
        profiles = registry.list_profiles()
        print(f"Registered Backend Profiles ({len(profiles)}):")
        for p in profiles:
            aliases_str = f" (aliases: {', '.join(p.aliases)})" if p.aliases else ""
            ver_str = f" [{p.version_specifier}]" if p.version_specifier else ""
            print(f"  - {p.profile_id}{aliases_str}: {p.display_name}{ver_str}")
        return 0
    elif parsed.action == "show":
        resolved = resolve_backend_profile(
            parsed.backend_id,
            version=parsed.version,
            allow_deprecated=True,
            allow_unverified=True,
        )
        if parsed.format == "json":
            print(resolved.profile.model_dump_json(indent=2))
        else:
            p = resolved.profile
            print(f"Backend Profile: {p.profile_id}")
            print(f"  Display Name:    {p.display_name}")
            print(f"  Backend ID:      {p.backend_id}")
            print(f"  Version Spec:    {p.version_specifier or 'N/A'}")
            print(f"  Confidence:      {p.confidence.value}")
            print(f"  Status:          {p.status.value}")
        return 0
    return 0


def _handle_estimate_overhead(parsed: argparse.Namespace) -> int:
    hw_res = resolve_hardware_profile(parsed.hardware, allow_deprecated=True)
    backend_res = resolve_backend_profile(
        parsed.backend,
        version=parsed.backend_version,
        hardware=hw_res.profile,
        allow_deprecated=True,
        allow_unverified=parsed.allow_incomplete,
    )
    overhead = estimate_runtime_overhead(
        backend=backend_res.profile,
        hardware=hw_res.profile,
        resident_weight_bytes=parsed.resident_weight_bytes,
        parameter_count=parsed.parameter_count,
        graph_capture_enabled=parsed.graph_capture,
        allow_incomplete_profile=parsed.allow_incomplete,
    )
    if parsed.format == "json":
        print(serialize_overhead_to_json(overhead))
    elif parsed.format == "markdown":
        print(serialize_overhead_to_markdown(overhead))
    else:
        print(format_overhead_terminal(overhead))
    return 0


def _handle_assess_memory(parsed: argparse.Namespace) -> int:
    weights_path = Path(parsed.weights_json)
    kv_path = Path(parsed.kv_cache_json)
    overhead_path = Path(parsed.runtime_overhead_json)
    budget_path = Path(parsed.hardware_budget_json)

    weights_estimate = TypeAdapter(WeightMemoryEstimate).validate_json(
        weights_path.read_text(encoding="utf-8")
    )
    kv_estimate = TypeAdapter(KVCacheEstimate).validate_json(
        kv_path.read_text(encoding="utf-8")
    )
    overhead_estimate = TypeAdapter(RuntimeOverheadEstimate).validate_json(
        overhead_path.read_text(encoding="utf-8")
    )
    budget_estimate = TypeAdapter(HardwareMemoryBudget).validate_json(
        budget_path.read_text(encoding="utf-8")
    )

    report = assess_memory_feasibility(
        weights=weights_estimate,
        kv_cache=kv_estimate,
        runtime_overhead=overhead_estimate,
        hardware_budget=budget_estimate,
    )

    if parsed.format == "json":
        print(serialize_feasibility_report_json(report))
    elif parsed.format == "markdown":
        print(serialize_feasibility_report_markdown(report))
    else:
        print(format_feasibility_report_terminal(report))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not arguments:
        parser.print_help()
        return 0

    parsed = parser.parse_args(arguments)
    if parsed is None:
        return 0

    if parsed.subcommand == "inspect-model":
        return _handle_inspect_model(parsed)
    elif parsed.subcommand == "hardware":
        return _handle_hardware(parsed)
    elif parsed.subcommand == "backend":
        return _handle_backend(parsed)
    elif parsed.subcommand == "estimate-overhead":
        return _handle_estimate_overhead(parsed)
    elif parsed.subcommand == "assess-memory":
        return _handle_assess_memory(parsed)
    else:
        # Backward compatibility for direct argument invocation
        if len(arguments) >= 2 and arguments[0] == "inspect-model":
            legacy_parsed = parser.parse_args(["inspect-model", *arguments[1:]])
            return _handle_inspect_model(legacy_parsed)

    return 0


if __name__ == "__main__":
    sys.exit(main())
