"""Recommendation domain object used by analysis reports."""

from typing import Annotated, TypeAlias

from pydantic import Field, StrictFloat, StrictInt, StrictStr

from kvscope.domain.base import DomainModel

RecommendationValue: TypeAlias = StrictFloat | StrictInt | StrictStr
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class Recommendation(DomainModel):
    """A deterministic, explainable suggested configuration change."""

    recommendation_id: Annotated[StrictStr, Field(min_length=1)]
    title: Annotated[StrictStr, Field(min_length=1)]
    explanation: Annotated[StrictStr, Field(min_length=1)]
    parameter: Annotated[StrictStr, Field(min_length=1)]
    current_value: RecommendationValue | None = None
    suggested_value: RecommendationValue | None = None
    estimated_savings_bytes: NonNegativeInt | None = None
    priority: NonNegativeInt = 0
    evidence_ids: list[StrictStr] = Field(default_factory=list)
