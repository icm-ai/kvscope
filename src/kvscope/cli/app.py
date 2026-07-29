"""Small CLI surface for model inspection."""

import argparse
import json
import sys
from collections.abc import Sequence

from kvscope import __version__
from kvscope.api import resolve_model


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser while retaining the bootstrap command behavior."""
    parser = argparse.ArgumentParser(
        prog="kvscope", description="Inspect LLM model configuration metadata."
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("command", nargs="?", help="inspect-model")
    parser.add_argument("source", nargs="?")
    parser.add_argument("--revision")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not arguments:
        parser.print_help()
        return 0
    parsed = parser.parse_args(arguments)
    if parsed is None or parsed.command != "inspect-model":
        return 0
    if not parsed.source:
        parser.error("inspect-model requires SOURCE")
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
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0
