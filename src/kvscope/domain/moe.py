"""Domain model for static Mixture-of-Experts weight metadata."""

from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, model_validator

from kvscope.domain.base import DomainModel

PositiveInt = Annotated[StrictInt, Field(gt=0)]


class MoEWeightAnalysis(DomainModel):
    """Separate total model weights from per-token active parameter metadata."""

    total_parameter_count: PositiveInt
    active_parameter_count: PositiveInt | None = None
    num_experts: PositiveInt | None = None
    num_experts_per_tok: PositiveInt | None = None
    resident_weight_basis: Literal["total_parameter_count"] = "total_parameter_count"

    @model_validator(mode="after")
    def validate_metadata(self) -> Self:
        """Validate metadata relationships at this report boundary."""
        if (
            self.active_parameter_count is not None
            and self.active_parameter_count > self.total_parameter_count
        ):
            raise ValueError("active_parameter_count must not exceed total parameters")
        if (
            self.num_experts is not None
            and self.num_experts_per_tok is not None
            and self.num_experts_per_tok > self.num_experts
        ):
            raise ValueError("num_experts_per_tok must not exceed num_experts")
        return self
