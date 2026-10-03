"""Domain models for one-dimensional workload sensitivity sweeps."""

from enum import StrEnum
from typing import Annotated

from pydantic import Field, StrictInt, StrictStr

from kvscope.domain.base import DomainModel
from kvscope.domain.comparison import DeploymentComparisonReport
from kvscope.domain.enums import ProductFeasibilityStatus


class WorkloadSweepDimension(StrEnum):
    """The inference setting varied by a workload sweep."""

    CONTEXT_LENGTH = "context_length"
    ACTIVE_SEQUENCES = "active_sequences"


class WorkloadSweepPoint(DomainModel):
    """Comparison results for one value of a swept inference setting."""

    value: Annotated[StrictInt, Field(gt=0)]
    comparison: DeploymentComparisonReport


class WorkloadSweepTransition(DomainModel):
    """Observed product-feasibility change between adjacent sampled points."""

    target_id: Annotated[StrictStr, Field(min_length=1)]
    hardware_profile_id: Annotated[StrictStr, Field(min_length=1)]
    backend_profile_id: Annotated[StrictStr, Field(min_length=1)]
    from_value: Annotated[StrictInt, Field(gt=0)]
    to_value: Annotated[StrictInt, Field(gt=0)]
    from_status: ProductFeasibilityStatus
    to_status: ProductFeasibilityStatus


class WorkloadSweepReport(DomainModel):
    """Ordered sweep results and observed transitions across deployment targets."""

    schema_version: StrictStr = "v0.1"
    model_id: Annotated[StrictStr, Field(min_length=1)]
    parameter_count: Annotated[StrictInt, Field(gt=0)]
    dimension: WorkloadSweepDimension
    points: Annotated[list[WorkloadSweepPoint], Field(min_length=2)]
    transitions: list[WorkloadSweepTransition]
