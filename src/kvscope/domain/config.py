"""Inference configuration domain objects."""

from typing import Annotated

from pydantic import Field, StrictFloat, StrictInt

from kvscope.domain.base import DomainModel
from kvscope.domain.dtypes import KVDType, WeightDType

PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class InferenceConfig(DomainModel):
    """Validated workload and precision settings for an inference request."""

    weight_dtype: WeightDType
    kv_dtype: KVDType

    context_length: PositiveInt
    batch_size: PositiveInt = 1
    max_num_seqs: PositiveInt = 1

    prefix_tokens: NonNegativeInt = 0
    multimodal_tokens: NonNegativeInt = 0

    cpu_offload_bytes: NonNegativeInt = 0
    graph_capture_enabled: bool = True
    safety_margin_ratio: Annotated[StrictFloat, Field(ge=0, le=1)] = 0.05
    active_sequences_override: PositiveInt | None = None

    @property
    def active_sequences(self) -> int:
        """Return active sequence count for KV budgeting.

        Uses explicit `active_sequences_override` if set; otherwise defaults
        to `max(batch_size, max_num_seqs)`.
        """
        if self.active_sequences_override is not None:
            return self.active_sequences_override
        return max(self.batch_size, self.max_num_seqs)

    @property
    def active_sequences_source(self) -> str:
        """Trace how active_sequences was determined."""
        if self.active_sequences_override is not None:
            return "explicit"
        if self.batch_size > self.max_num_seqs:
            return "batch_size"
        if self.max_num_seqs > self.batch_size:
            return "max_num_seqs"
        return "equal"
