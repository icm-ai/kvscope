"""Domain models for comparing static deployment targets."""

from typing import Annotated

from pydantic import Field, StrictInt, StrictStr

from kvscope.domain.backend import BackendProfile
from kvscope.domain.base import DomainModel
from kvscope.domain.config import InferenceConfig
from kvscope.domain.hardware import HardwareProfile
from kvscope.domain.report import MemoryFeasibilityReport


class DeploymentTarget(DomainModel):
    """One explicitly selected hardware/backend target for static analysis."""

    target_id: Annotated[StrictStr, Field(min_length=1)]
    hardware: HardwareProfile
    backend: BackendProfile
    backend_version: StrictStr | None = None


class DeploymentTargetResult(DomainModel):
    """Feasibility analysis for one selected deployment target."""

    target_id: Annotated[StrictStr, Field(min_length=1)]
    hardware_profile_id: Annotated[StrictStr, Field(min_length=1)]
    backend_profile_id: Annotated[StrictStr, Field(min_length=1)]
    backend_version: StrictStr | None = None
    report: MemoryFeasibilityReport


class DeploymentComparisonReport(DomainModel):
    """Ordered comparison of one workload across explicit deployment targets."""

    schema_version: StrictStr = "v0.1"
    model_id: Annotated[StrictStr, Field(min_length=1)]
    model_revision: StrictStr | None = None
    model_config_digest: StrictStr | None = None
    parameter_count: Annotated[StrictInt, Field(gt=0)]
    inference_config: InferenceConfig
    targets: Annotated[list[DeploymentTargetResult], Field(min_length=1)]
