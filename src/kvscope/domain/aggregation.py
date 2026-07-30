"""Domain objects for memory requirement aggregation."""

from pydantic import Field, StrictStr

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import Confidence
from kvscope.domain.evidence import Evidence
from kvscope.domain.ranges import ByteRange


class MemoryComponentRequirement(DomainModel):
    """An individual memory component's requirements and metadata."""

    component: StrictStr
    memory: ByteRange
    confidence: Confidence
    source_id: StrictStr | None = None
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class MemoryAggregationResult(DomainModel):
    """Aggregated memory requirements across weights, KV Cache, and runtime overhead."""

    schema_version: StrictStr = "v0.1"

    resident_weights: MemoryComponentRequirement
    kv_cache: MemoryComponentRequirement
    runtime_overhead: MemoryComponentRequirement

    known_subtotal: ByteRange
    total_requirement: ByteRange | None = None

    is_partial: bool = False
    missing_components: list[StrictStr] = Field(default_factory=list)

    dominant_component_expected: StrictStr | None = None
    dominant_component_upper: StrictStr | None = None

    confidence: Confidence
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
