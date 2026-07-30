"""Domain objects for hardware memory budget estimation."""

from typing import Annotated

from pydantic import Field, StrictInt

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import Confidence, MemoryTopology
from kvscope.domain.ranges import ByteRange

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class HardwareMemoryBudget(DomainModel):
    """Memory budget analysis result for a hardware profile."""

    physical_total_bytes: NonNegativeInt

    os_reserve: ByteRange
    display_reserve: ByteRange
    background_process_reserve: ByteRange
    device_specific_reserve: ByteRange
    user_reserve: ByteRange

    total_non_model_reserve: ByteRange

    allocatable_before_headroom: ByteRange
    recommended_headroom: ByteRange
    recommended_allocatable: ByteRange

    memory_topology: MemoryTopology
    confidence: Confidence
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
