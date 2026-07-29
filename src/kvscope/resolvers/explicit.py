"""Resolver for explicit mappings and already normalized ModelSpec objects."""

from collections.abc import Mapping
from copy import deepcopy
from typing import cast

from kvscope.domain.model import ModelSpec
from kvscope.resolvers.base import RawModelConfig, ResolveContext


class ExplicitConfigResolver:
    resolver_id = "explicit_config"

    def can_resolve(self, source: object) -> bool:
        return isinstance(source, (ModelSpec, Mapping))

    def resolve(self, source: object, context: ResolveContext) -> RawModelConfig:
        if isinstance(source, ModelSpec):
            data = source.model_dump(mode="python")
            return RawModelConfig(
                model_id=source.model_id,
                raw_config=data,
                source_type="explicit",
                source_location=None,
                revision=context.revision,
                resolved_revision=context.revision,
            )
        data = deepcopy(dict(cast(Mapping[str, object], source)))
        model_id = data.get("model_id")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("explicit config requires a non-empty model_id")
        return RawModelConfig(
            model_id=model_id,
            raw_config=data,
            source_type="explicit",
            revision=context.revision,
            resolved_revision=context.revision,
        )
