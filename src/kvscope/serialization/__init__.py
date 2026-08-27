"""Report serialization namespace for KVScope."""

from kvscope.serialization.calibration import (
    format_calibration_comparison_terminal,
    serialize_calibration_comparison_json,
    serialize_calibration_comparison_markdown,
)
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

__all__ = [
    "format_budget_terminal",
    "format_calibration_comparison_terminal",
    "format_feasibility_report_terminal",
    "format_overhead_terminal",
    "serialize_budget_to_json",
    "serialize_budget_to_markdown",
    "serialize_calibration_comparison_json",
    "serialize_calibration_comparison_markdown",
    "serialize_feasibility_report_json",
    "serialize_feasibility_report_markdown",
    "serialize_overhead_to_json",
    "serialize_overhead_to_markdown",
]
