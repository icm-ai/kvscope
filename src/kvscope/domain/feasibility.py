"""Feasibility result domain object."""

from typing import Annotated

from pydantic import Field, StrictFloat, StrictInt, model_validator

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import FeasibilityStatus, RiskLevel

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class FeasibilityResult(DomainModel):
    """A decision result without performing the decision calculation."""

    status: FeasibilityStatus
    risk: RiskLevel
    required_bytes: NonNegativeInt
    available_bytes: NonNegativeInt
    headroom_bytes: StrictInt
    headroom_ratio: StrictFloat | None = None

    @model_validator(mode="after")
    def validate_headroom(self) -> "FeasibilityResult":
        """Keep the reported headroom consistent with the two byte totals."""
        if self.headroom_bytes != self.available_bytes - self.required_bytes:
            raise ValueError(
                "headroom_bytes must equal available_bytes - required_bytes"
            )
        return self
