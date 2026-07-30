"""Unit tests for Phase 7 report serializers (JSON, Terminal, Markdown)."""

import json

from kvscope.domain.aggregation import (
    MemoryAggregationResult,
    MemoryComponentRequirement,
)
from kvscope.domain.constraints import (
    ConstraintAnalysis,
    ConstraintSeverity,
    MemoryConstraint,
)
from kvscope.domain.enums import (
    Confidence,
    InternalFeasibilityStatus,
    ProductFeasibilityStatus,
)
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.ranges import ByteRange
from kvscope.domain.report import MemoryFeasibilityReport
from kvscope.domain.signed_ranges import SignedByteRange
from kvscope.serialization.json import serialize_feasibility_report_json
from kvscope.serialization.markdown import serialize_feasibility_report_markdown
from kvscope.serialization.terminal import format_feasibility_report_terminal


def _make_dummy_report() -> MemoryFeasibilityReport:
    w_req = MemoryComponentRequirement(
        component="resident_weights",
        memory=ByteRange.exact(4 * 1024 * 1024 * 1024),
        confidence=Confidence.EXACT,
    )
    kv_req = MemoryComponentRequirement(
        component="kv_cache",
        memory=ByteRange.exact(2 * 1024 * 1024 * 1024),
        confidence=Confidence.EXACT,
    )
    ov_req = MemoryComponentRequirement(
        component="runtime_overhead",
        memory=ByteRange(
            lower_bytes=1073741824,
            expected_bytes=1610612736,
            upper_bytes=2147483648,
        ),
        confidence=Confidence.HIGH,
    )

    agg = MemoryAggregationResult(
        schema_version="v0.1",
        resident_weights=w_req,
        kv_cache=kv_req,
        runtime_overhead=ov_req,
        known_subtotal=ByteRange(
            lower_bytes=7516192768,
            expected_bytes=8053063680,
            upper_bytes=8589934592,
        ),
        total_requirement=ByteRange(
            lower_bytes=7516192768,
            expected_bytes=8053063680,
            upper_bytes=8589934592,
        ),
        is_partial=False,
        dominant_component_expected="resident_weights",
        dominant_component_upper="resident_weights",
        confidence=Confidence.HIGH,
    )

    feas = FeasibilityResult(
        schema_version="v0.1",
        internal_status=InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        product_status=ProductFeasibilityStatus.FEASIBLE,
        requirement=agg.total_requirement,
        known_subtotal=agg.known_subtotal,
        physical_total_bytes=17179869184,
        allocatable_before_headroom=ByteRange.exact(15032385536),
        recommended_allocatable=ByteRange.exact(12884901888),
        headroom_vs_physical=SignedByteRange(
            lower_bytes=8589934592,
            expected_bytes=9126805504,
            upper_bytes=9663676416,
        ),
        headroom_vs_allocatable=SignedByteRange(
            lower_bytes=6442450944,
            expected_bytes=6979321856,
            upper_bytes=7516192768,
        ),
        headroom_vs_recommended=SignedByteRange(
            lower_bytes=4294967296,
            expected_bytes=4831838208,
            upper_bytes=5368709120,
        ),
        confidence=Confidence.HIGH,
        is_actionable=True,
        primary_boundary="recommended_allocatable",
        explanation="Feasible",
    )

    constraint = MemoryConstraint(
        code="WEIGHT_MEMORY_DOMINANT",
        severity=ConstraintSeverity.LOW,
        category="breakdown",
        component="resident_weights",
        title="Weight Memory Dominant",
        explanation="Model weights constitute majority of memory.",
    )

    con = ConstraintAnalysis(
        schema_version="v0.1",
        primary_constraint=constraint,
        constraints=[constraint],
        dominant_component_expected="resident_weights",
        dominant_component_upper="resident_weights",
        confidence=Confidence.HIGH,
    )

    return MemoryFeasibilityReport(
        schema_version="v0.1",
        aggregation=agg,
        feasibility=feas,
        constraint_analysis=con,
    )


def test_serialize_feasibility_report_json():
    report = _make_dummy_report()
    json_str = serialize_feasibility_report_json(report)
    parsed = json.loads(json_str)
    assert parsed["kind"] == "memory_feasibility_report"
    assert parsed["feasibility"]["product_status"] == "feasible"
    assert parsed["feasibility"]["internal_status"] == "guaranteed_feasible"


def test_format_feasibility_report_terminal():
    report = _make_dummy_report()
    term_str = format_feasibility_report_terminal(report)
    assert "KVScope Memory Feasibility Report" in term_str
    assert "FEASIBLE" in term_str
    assert "guaranteed_feasible" in term_str
    assert "Resident Weights:" in term_str


def test_serialize_feasibility_report_markdown():
    report = _make_dummy_report()
    md_str = serialize_feasibility_report_markdown(report)
    assert "# KVScope Memory Feasibility Report" in md_str
    assert "| Resident Weights |" in md_str
    assert "| Physical Total Memory |" in md_str
