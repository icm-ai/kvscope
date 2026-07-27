"""Hardware domain objects."""

from typing import Annotated

from pydantic import Field, StrictFloat, StrictInt, StrictStr, model_validator

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import MemoryTopology

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class HardwareSpec(DomainModel):
    """Describes memory capacity and static capabilities of a device."""

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
    def validate_memory_reserve(self) -> "HardwareSpec":
        """Reject a system reserve larger than the physical memory capacity."""
        if self.default_system_reserve_bytes > self.total_memory_bytes:
            raise ValueError(
                "default_system_reserve_bytes must not exceed total_memory_bytes"
            )
        return self
