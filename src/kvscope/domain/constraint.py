"""Constraint domain object used by analysis reports."""

from typing import Annotated, TypeAlias

from pydantic import Field, StrictFloat, StrictInt, StrictStr

from kvscope.domain.base import DomainModel

ConstraintValue: TypeAlias = StrictFloat | StrictInt | StrictStr


class Constraint(DomainModel):
    """A named, explainable limitation found during analysis."""

    code: Annotated[StrictStr, Field(min_length=1)]
    title: Annotated[StrictStr, Field(min_length=1)]
    severity: Annotated[StrictStr, Field(min_length=1)]
    component: Annotated[StrictStr, Field(min_length=1)]
    current_value: ConstraintValue
    threshold: ConstraintValue | None = None
    explanation: Annotated[StrictStr, Field(min_length=1)]
