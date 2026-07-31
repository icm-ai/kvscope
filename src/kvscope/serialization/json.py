"""JSON serialization for KVScope estimates and budget reports."""

import json
from typing import Any

from pydantic import BaseModel

from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.recommendation import RecommendationReport
from kvscope.domain.report import MemoryFeasibilityReport
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate


def _dump_model(model: BaseModel) -> dict[str, Any]:
    """Dump pydantic model to dict, converting Decimal to string where necessary."""
    res = json.loads(model.model_dump_json())
    assert isinstance(res, dict)
    return res


def serialize_budget_to_json(budget: HardwareMemoryBudget, indent: int = 2) -> str:
    """Serialize HardwareMemoryBudget to a JSON string."""
    data = _dump_model(budget)
    data["kind"] = "hardware_memory_budget"
    return json.dumps(data, ensure_ascii=False, indent=indent)


def serialize_overhead_to_json(
    estimate: RuntimeOverheadEstimate, indent: int = 2
) -> str:
    """Serialize RuntimeOverheadEstimate to a JSON string."""
    data = _dump_model(estimate)
    data["kind"] = "runtime_overhead_estimate"
    return json.dumps(data, ensure_ascii=False, indent=indent)


def serialize_feasibility_report_json(
    report: MemoryFeasibilityReport, indent: int = 2
) -> str:
    """Serialize MemoryFeasibilityReport to a JSON string."""
    data = _dump_model(report)
    data["kind"] = "memory_feasibility_report"
    return json.dumps(data, ensure_ascii=False, indent=indent)


def serialize_recommendation_report_json(
    report: RecommendationReport, indent: int = 2
) -> str:
    """Serialize RecommendationReport to a JSON string."""
    data = _dump_model(report)
    data["kind"] = "recommendation_report"
    return json.dumps(data, ensure_ascii=False, indent=indent)


format_recommendation_report_json = serialize_recommendation_report_json
