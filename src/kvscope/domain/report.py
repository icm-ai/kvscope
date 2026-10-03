from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field, StrictBool, StrictInt, StrictStr

from kvscope.domain.aggregation import MemoryAggregationResult
from kvscope.domain.backend import BackendSpec
from kvscope.domain.base import DomainModel
from kvscope.domain.config import InferenceConfig
from kvscope.domain.constraint import Constraint
from kvscope.domain.constraints import ConstraintAnalysis
from kvscope.domain.estimate import MemoryEstimate
from kvscope.domain.evidence import Evidence
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.hardware import HardwareSpec
from kvscope.domain.model import ModelSpec
from kvscope.domain.moe import MoEWeightAnalysis
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


class AnalysisInferenceConfig(DomainModel):
    """Frozen runtime settings required to reproduce a feasibility report."""

    context_length: Annotated[StrictInt, Field(gt=0)]
    batch_size: Annotated[StrictInt, Field(gt=0)]
    max_num_seqs: Annotated[StrictInt, Field(gt=0)]
    active_sequences: Annotated[StrictInt, Field(gt=0)]
    prefix_tokens: Annotated[StrictInt, Field(ge=0)]
    multimodal_tokens: Annotated[StrictInt, Field(ge=0)]
    weight_dtype: Annotated[StrictStr, Field(min_length=1)]
    kv_dtype: Annotated[StrictStr, Field(min_length=1)]
    graph_capture_enabled: StrictBool
    cpu_offload_bytes: Annotated[StrictInt, Field(ge=0)]


class AnalysisProvenance(DomainModel):
    """Identity and runtime inputs required to audit a feasibility report."""

    model_id: Annotated[StrictStr, Field(min_length=1)]
    model_revision: StrictStr | None
    model_config_digest: StrictStr | None
    backend_profile_id: Annotated[StrictStr, Field(min_length=1)]
    backend_version: StrictStr | None
    hardware_profile_id: Annotated[StrictStr, Field(min_length=1)]
    inference_config: AnalysisInferenceConfig


class MemoryFeasibilityReport(DomainModel):
    """Combined Phase 7 report containing aggregation, feasibility, and constraints."""

    schema_version: StrictStr = "v0.1"
    provenance: AnalysisProvenance | None = None
    moe_weight_analysis: MoEWeightAnalysis | None = None
    aggregation: MemoryAggregationResult
    feasibility: FeasibilityResult
    constraint_analysis: ConstraintAnalysis
