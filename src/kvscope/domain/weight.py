"""Domain objects for explainable model-weight memory estimates."""

from typing import Annotated

from pydantic import Field, StrictInt, model_validator

from kvscope.domain.base import DomainModel

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class WeightArtifactSummary(DomainModel):
    """Already-parsed artifact byte counts supplied by an upstream resolver."""

    payload_bytes: NonNegativeInt
    metadata_bytes: NonNegativeInt = 0
    alignment_bytes: NonNegativeInt = 0

    @property
    def storage_bytes(self) -> int:
        """Return the supplied artifact storage size in integer bytes."""
        return self.payload_bytes + self.metadata_bytes + self.alignment_bytes

    @model_validator(mode="after")
    def validate_payload_presence(self) -> "WeightArtifactSummary":
        """Reject an empty artifact summary."""
        if self.storage_bytes <= 0:
            raise ValueError("artifact summary must contain at least one byte")
        return self
