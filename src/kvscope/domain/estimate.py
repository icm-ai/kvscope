"""Memory estimate domain objects."""

from typing import Annotated

from pydantic import Field, StrictInt, StrictStr, model_validator

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import Confidence

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class EstimateComponent(DomainModel):
    """One explainable memory component, expressed in integer bytes."""

    name: Annotated[StrictStr, Field(min_length=1)]
    bytes: NonNegativeInt
    lower_bound_bytes: NonNegativeInt | None = None
    upper_bound_bytes: NonNegativeInt | None = None
    confidence: Confidence
    formula: StrictStr | None = None
    evidence_ids: list[StrictStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bounds(self) -> "EstimateComponent":
        """Ensure a component estimate is consistent with its optional bounds."""
        if (
            self.lower_bound_bytes is not None
            and self.upper_bound_bytes is not None
            and self.lower_bound_bytes > self.upper_bound_bytes
        ):
            raise ValueError("lower_bound_bytes must not exceed upper_bound_bytes")
        if (
            self.lower_bound_bytes is not None and self.bytes < self.lower_bound_bytes
        ) or (
            self.upper_bound_bytes is not None and self.bytes > self.upper_bound_bytes
        ):
            raise ValueError("bytes must be within estimate bounds")
        return self


class MemoryEstimate(DomainModel):
    """Memory decomposition used as the report's bytes-level fact source."""

    weights: EstimateComponent
    kv_cache: EstimateComponent
    runtime_overhead: EstimateComponent
    graph_capture: EstimateComponent
    workspace: EstimateComponent
    system_reserve: EstimateComponent
    safety_margin: EstimateComponent
    total: EstimateComponent
