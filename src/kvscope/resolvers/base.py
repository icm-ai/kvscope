"""Shared resolver contracts and boundary objects."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from pydantic import Field, StrictStr

from kvscope.domain.base import DomainModel
from kvscope.domain.evidence import Evidence


class ResolveContext(DomainModel):
    """Options shared by every model source resolver."""

    revision: StrictStr | None = None
    offline: bool = False
    cache_dir: Path | None = None
    allow_generic: bool = True


class RawModelConfig(DomainModel):
    """Unmodified JSON metadata plus acquisition provenance."""

    model_id: StrictStr
    raw_config: dict[str, Any]
    source_type: StrictStr
    source_location: StrictStr | None = None
    revision: StrictStr | None = None
    resolved_revision: StrictStr | None = None
    from_cache: bool = False
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ArchitectureAdapter(Protocol):
    """Normalize one family of decoder configuration fields."""

    adapter_id: str
    supported_model_types: frozenset[str]
    priority: int

    def can_adapt(self, raw_config: Mapping[str, Any]) -> bool: ...

    def adapt(self, raw: RawModelConfig) -> Any: ...


class ModelResolver(Protocol):
    """Acquire raw configuration without loading weights or executing code."""

    resolver_id: str

    def can_resolve(self, source: object) -> bool: ...

    def resolve(self, source: object, context: ResolveContext) -> RawModelConfig: ...
