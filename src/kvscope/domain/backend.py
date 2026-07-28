"""Backend domain objects."""

from typing import Annotated

from pydantic import Field, StrictFloat, StrictInt, StrictStr, model_validator

from kvscope.domain.base import DomainModel
from kvscope.domain.dtypes import KVDType
from kvscope.domain.enums import Confidence

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
Ratio = Annotated[StrictFloat, Field(ge=0, le=1)]


class BackendSpec(DomainModel):
    """Describes backend-specific memory reservations and KV capabilities."""

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
    def validate_ratios(self) -> "BackendSpec":
        """Ensure cumulative memory overhead ratios do not exceed 100%."""
        if self.workspace_ratio + self.allocator_margin_ratio > 1.0:
            raise ValueError(
                "workspace_ratio + allocator_margin_ratio must not exceed 1.0"
            )
        return self

