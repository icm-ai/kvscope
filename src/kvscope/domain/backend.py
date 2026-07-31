"""Backend domain objects and profiles."""

from decimal import Decimal
from typing import Annotated, Self

from pydantic import Field, StrictFloat, StrictInt, StrictStr, model_validator

from kvscope.domain.base import DomainModel
from kvscope.domain.dtypes import KVDType
from kvscope.domain.enums import Confidence, MemoryTopology, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.ranges import ByteRange, RatioRange

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
Ratio = Annotated[StrictFloat, Field(ge=0, le=1)]


class BackendMemoryModel(DomainModel):
    """Memory overhead parameters for an inference backend."""

    base_runtime: ByteRange = Field(default_factory=lambda: ByteRange.exact(0))
    per_billion_parameters: ByteRange = Field(
        default_factory=lambda: ByteRange.exact(0)
    )
    workspace_ratio_of_resident_weights: RatioRange = Field(
        default_factory=lambda: RatioRange.exact(Decimal("0"))
    )
    graph_capture_reserve: ByteRange = Field(default_factory=lambda: ByteRange.exact(0))
    backend_buffers: ByteRange = Field(default_factory=lambda: ByteRange.exact(0))
    allocator_margin_ratio_of_subtotal: RatioRange = Field(
        default_factory=lambda: RatioRange.exact(Decimal("0"))
    )

    kv_block_size: Annotated[StrictInt, Field(gt=0)] | None = None
    graph_capture_supported: bool = True

    @model_validator(mode="after")
    def validate_allocator_margin(self) -> Self:
        """Validate that allocator margin ratio upper bound is < 1.0."""
        if self.allocator_margin_ratio_of_subtotal.upper >= Decimal("1.0"):
            raise ValueError(
                "allocator_margin_ratio_of_subtotal upper bound must be < 1.0"
            )
        return self


class BackendProfile(DomainModel):
    """Structured specifications and memory model for an inference backend framework."""

    schema_version: StrictStr = "0.1"
    profile_id: Annotated[StrictStr, Field(min_length=1)]

    backend_id: Annotated[StrictStr, Field(min_length=1)]
    display_name: Annotated[StrictStr, Field(min_length=1)]
    aliases: list[StrictStr] = Field(default_factory=list)

    version_specifier: StrictStr | None = None

    supported_memory_topologies: list[MemoryTopology] = Field(default_factory=list)
    supported_vendors: list[StrictStr] = Field(default_factory=list)
    supported_families: list[StrictStr] = Field(default_factory=list)

    memory_model: BackendMemoryModel

    supported_weight_dtypes: list[StrictStr] = Field(default_factory=list)
    supported_kv_dtypes: list[StrictStr] = Field(default_factory=list)

    notes: list[StrictStr] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Confidence = Confidence.UNKNOWN
    status: ProfileStatus = ProfileStatus.UNVERIFIED

    def to_spec(self) -> "BackendSpec":
        """Convert BackendProfile to legacy BackendSpec for calculators."""
        kv_dtypes: list[KVDType] = []
        for d in self.supported_kv_dtypes:
            try:
                kv_dtypes.append(KVDType(d.lower()))
            except ValueError:
                pass
        return BackendSpec(
            backend_id=self.backend_id,
            version_constraint=self.version_specifier,
            base_overhead_bytes=self.memory_model.base_runtime.expected_bytes,
            overhead_per_billion_parameters_bytes=self.memory_model.per_billion_parameters.expected_bytes,
            graph_capture_reserve_bytes=self.memory_model.graph_capture_reserve.expected_bytes,
            workspace_ratio=float(
                self.memory_model.workspace_ratio_of_resident_weights.expected
            ),
            allocator_margin_ratio=float(
                self.memory_model.allocator_margin_ratio_of_subtotal.expected
            ),
            kv_block_size=self.memory_model.kv_block_size,
            supports_kv_dtypes=kv_dtypes,
            supports_cpu_offload=False,
            confidence=self.confidence,
            evidence_ids=[e.evidence_id for e in self.evidence],
        )


class BackendSpec(DomainModel):
    """Describes backend-specific memory reservations (v0.1 legacy spec)."""

    backend_id: Annotated[StrictStr, Field(min_length=1)]
    version_constraint: StrictStr | None = None

    base_overhead_bytes: NonNegativeInt
    overhead_per_billion_parameters_bytes: NonNegativeInt
    graph_capture_reserve_bytes: NonNegativeInt
    workspace_ratio: Ratio
    allocator_margin_ratio: Ratio

    kv_block_size: Annotated[StrictInt, Field(gt=0)] | None = None
    supports_kv_dtypes: list[KVDType]
    supports_cpu_offload: bool
    confidence: Confidence
    evidence_ids: list[StrictStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ratios(self) -> Self:
        """Ensure cumulative memory overhead ratios do not exceed 100%."""
        if self.workspace_ratio + self.allocator_margin_ratio > 1.0:
            raise ValueError(
                "workspace_ratio + allocator_margin_ratio must not exceed 1.0"
            )
        return self
