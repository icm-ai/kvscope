"""Provenance models for model resolution."""

from typing import Any

from pydantic import Field, StrictStr

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import Confidence
from kvscope.domain.evidence import Evidence
from kvscope.domain.model import ModelSpec


class ResolverAttempt(DomainModel):
    """One resolver decision in a resolver chain."""

    resolver_id: StrictStr
    matched: bool
    succeeded: bool
    error_code: StrictStr | None = None
    message: StrictStr | None = None


class ModelSource(DomainModel):
    """Traceable origin of a normalized model specification."""

    model_id: StrictStr
    source_type: StrictStr
    source_location: StrictStr | None = None
    requested_revision: StrictStr | None = None
    resolved_revision: StrictStr | None = None
    resolver_id: StrictStr
    adapter_id: StrictStr
    config_digest: StrictStr
    loaded_at: StrictStr
    from_cache: bool = False
    confidence: Confidence
    evidence: list[Evidence] = Field(default_factory=list)
    attempts: list[ResolverAttempt] = Field(default_factory=list)


class ResolvedModel(DomainModel):
    """A ModelSpec together with its raw configuration and provenance."""

    spec: ModelSpec
    source: ModelSource
    raw_config: dict[str, Any]
    resolver_id: StrictStr
    adapter_id: StrictStr
    confidence: Confidence
    warnings: list[str] = Field(default_factory=list)
    attempts: list[ResolverAttempt] = Field(default_factory=list)
