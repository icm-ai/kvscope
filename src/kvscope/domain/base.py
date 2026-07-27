"""Shared configuration for immutable Pydantic domain models."""

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Base class for strict, immutable boundary models."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
