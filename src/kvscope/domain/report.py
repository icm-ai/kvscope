"""Analysis report domain object."""

from datetime import datetime
from typing import Annotated

from pydantic import Field, StrictStr

from kvscope.domain.backend import BackendSpec
from kvscope.domain.base import DomainModel
from kvscope.domain.config import InferenceConfig
from kvscope.domain.constraint import Constraint
from kvscope.domain.estimate import MemoryEstimate
from kvscope.domain.evidence import Evidence
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.hardware import HardwareSpec
from kvscope.domain.model import ModelSpec
from kvscope.domain.recommendation import Recommendation


class AnalysisReport(DomainModel):
    """Immutable aggregate of all Phase 1 domain objects."""

    schema_version: Annotated[StrictStr, Field(min_length=1)]
    generated_at: datetime

    model: ModelSpec
    hardware: HardwareSpec
    backend: BackendSpec
    config: InferenceConfig

    estimate: MemoryEstimate
    feasibility: FeasibilityResult
    constraints: list[Constraint] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    warnings: list[StrictStr] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
