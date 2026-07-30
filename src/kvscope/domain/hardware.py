"""Hardware domain objects and profiles."""

from decimal import Decimal
from math import ceil
from typing import Annotated, Literal, Self

from pydantic import Field, StrictFloat, StrictInt, StrictStr, model_validator

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import Confidence, MemoryTopology, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.ranges import ByteRange, RatioRange
from kvscope.domain.units import BYTES_PER_GIB, BYTES_PER_MIB

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
MemoryUnit = Literal["bytes", "KiB", "MiB", "GiB"]

UNIT_MULTIPLIERS: dict[MemoryUnit, int] = {
    "bytes": 1,
    "KiB": 1024,
    "MiB": BYTES_PER_MIB,
    "GiB": BYTES_PER_GIB,
}


class MemoryQuantityInput(DomainModel):
    """Memory quantity in human-friendly format or explicit bytes."""

    value: Decimal
    unit: MemoryUnit

    @model_validator(mode="after")
    def validate_positive_value(self) -> Self:
        """Validate that memory quantity value is positive."""
        if self.value <= 0:
            raise ValueError("Memory quantity value must be strictly positive (> 0)")
        return self

    def to_bytes(self) -> int:
        """Convert quantity value and unit to integer bytes using ceiling."""
        multiplier = UNIT_MULTIPLIERS[self.unit]
        byte_val = self.value * multiplier
        return int(ceil(byte_val))


class HardwareReserveProfile(DomainModel):
    """Breakdown of non-model memory reserves on a hardware device."""

    os_reserve: ByteRange = Field(default_factory=lambda: ByteRange.exact(0))
    display_reserve: ByteRange = Field(default_factory=lambda: ByteRange.exact(0))
    background_process_reserve: ByteRange = Field(
        default_factory=lambda: ByteRange.exact(0)
    )
    device_specific_reserve: ByteRange = Field(
        default_factory=lambda: ByteRange.exact(0)
    )


class HardwareProfile(DomainModel):
    """Structured specifications and memory reserve guidelines for a hardware device."""

    schema_version: StrictStr = "0.1"
    profile_id: Annotated[StrictStr, Field(min_length=1)]

    name: Annotated[StrictStr, Field(min_length=1)]
    vendor: Annotated[StrictStr, Field(min_length=1)]
    family: StrictStr | None = None
    aliases: list[StrictStr] = Field(default_factory=list)

    memory_topology: MemoryTopology
    total_memory: MemoryQuantityInput

    reserves: HardwareReserveProfile = Field(default_factory=HardwareReserveProfile)
    recommended_headroom_ratio: RatioRange = Field(
        default_factory=lambda: RatioRange.exact(Decimal("0.10"))
    )

    supported_backend_ids: list[StrictStr] = Field(default_factory=list)
    notes: list[StrictStr] = Field(default_factory=list)

    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Confidence = Confidence.UNKNOWN
    status: ProfileStatus = ProfileStatus.UNVERIFIED

    @model_validator(mode="after")
    def validate_headroom_ratio(self) -> Self:
        """Validate that recommended headroom ratio is strictly less than 1.0."""
        if self.recommended_headroom_ratio.upper >= Decimal("1.0"):
            raise ValueError("recommended_headroom_ratio upper bound must be < 1.0")
        return self

    @property
    def total_memory_bytes(self) -> int:
        """Total memory in integer bytes."""
        return self.total_memory.to_bytes()


class HardwareSpec(DomainModel):
    """Describes memory capacity and static capabilities (v0.1 legacy spec)."""

    hardware_id: Annotated[StrictStr, Field(min_length=1)]
    vendor: Annotated[StrictStr, Field(min_length=1)]
    device_family: Annotated[StrictStr, Field(min_length=1)]
    name: Annotated[StrictStr, Field(min_length=1)]

    memory_topology: MemoryTopology
    total_memory_bytes: Annotated[StrictInt, Field(gt=0)]
    default_system_reserve_bytes: NonNegativeInt

    memory_bandwidth_gbps: Annotated[StrictFloat, Field(ge=0)] | None = None
    compute_capability: StrictStr | None = None
    supported_backends: list[StrictStr] = Field(default_factory=list)
    notes: list[StrictStr] = Field(default_factory=list)
    evidence_ids: list[StrictStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_memory_reserve(self) -> Self:
        """Reject a system reserve larger than the physical memory capacity."""
        if self.default_system_reserve_bytes > self.total_memory_bytes:
            raise ValueError(
                "default_system_reserve_bytes must not exceed total_memory_bytes"
            )
        return self
