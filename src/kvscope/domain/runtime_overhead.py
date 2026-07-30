"""Domain objects for runtime overhead estimation and overrides."""

from pydantic import Field, StrictStr

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import Confidence
from kvscope.domain.evidence import Evidence
from kvscope.domain.ranges import ByteRange, RatioRange


class RuntimeOverheadOverrides(DomainModel):
    """Explicit user overrides for individual components of runtime memory overhead."""

    base_runtime: ByteRange | None = None
    per_billion_parameters: ByteRange | None = None
    workspace_ratio: RatioRange | None = None
    graph_capture_reserve: ByteRange | None = None
    backend_buffers: ByteRange | None = None
    allocator_margin_ratio: RatioRange | None = None


class RuntimeOverheadEstimate(DomainModel):
    """Estimated runtime overhead breakdown and total memory requirement."""

    base_runtime: ByteRange
    parameter_scaled_overhead: ByteRange
    workspace: ByteRange
    graph_capture: ByteRange
    backend_buffers: ByteRange
    allocator_margin: ByteRange

    subtotal_before_allocator_margin: ByteRange
    total_runtime_overhead: ByteRange

    backend_profile_id: StrictStr
    backend_version_specifier: StrictStr | None
    hardware_profile_id: StrictStr

    confidence: Confidence
    is_partial: bool = False
    missing_components: list[StrictStr] = Field(default_factory=list)

    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
