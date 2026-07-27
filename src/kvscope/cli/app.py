"""Minimal KVScope command-line entry point for Phase 0."""

import argparse
import sys
from collections.abc import Sequence

from kvscope import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the Phase 0 command-line parser."""
    parser = argparse.ArgumentParser(
        prog="kvscope",
        description="Analyze LLM inference memory and KV cache (coming soon).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the KVScope CLI and return a process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not arguments:
        parser.print_help()
        return 0
    parser.parse_args(arguments)
    return 0
