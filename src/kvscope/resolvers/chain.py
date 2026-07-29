"""Deterministic model resolver chain and adapter selection."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kvscope.adapters import ADAPTERS, GenericDecoderAdapter
from kvscope.domain.enums import Confidence
from kvscope.domain.model import ModelSpec
from kvscope.domain.model_source import ModelSource, ResolvedModel, ResolverAttempt
from kvscope.errors import ModelResolutionError, UnsupportedArchitectureError
from kvscope.resolvers.base import ModelResolver, RawModelConfig, ResolveContext
from kvscope.resolvers.explicit import ExplicitConfigResolver
from kvscope.resolvers.huggingface import HuggingFaceConfigResolver
from kvscope.resolvers.local_config import LocalConfigResolver, config_digest
from kvscope.resolvers.registry import BuiltinRegistryResolver


class ResolverChain:
    """Resolve one source, stopping on the first matched resolver failure."""

    def __init__(self, resolvers: Sequence[ModelResolver] | None = None) -> None:
        if resolvers is None:
            registry = BuiltinRegistryResolver()
            resolvers = (
                ExplicitConfigResolver(),
                LocalConfigResolver(),
                HuggingFaceConfigResolver(set(registry.registry.aliases)),
                registry,
            )
        self.resolvers = tuple(resolvers)

    def resolve(
        self, source: object, context: ResolveContext | None = None
    ) -> ResolvedModel:
        context = context or ResolveContext()
        attempts: list[ResolverAttempt] = []
        raw: RawModelConfig | None = None
        resolver_id = ""
        for resolver in self.resolvers:
            matched = resolver.can_resolve(source)
            if not matched:
                attempts.append(
                    ResolverAttempt(
                        resolver_id=resolver.resolver_id, matched=False, succeeded=False
                    )
                )
                continue
            try:
                raw = resolver.resolve(source, context)
            except ModelResolutionError as exc:
                attempts.append(
                    ResolverAttempt(
                        resolver_id=resolver.resolver_id,
                        matched=True,
                        succeeded=False,
                        error_code=exc.code,
                        message=str(exc),
                    )
                )
                raise
            except Exception as exc:
                attempts.append(
                    ResolverAttempt(
                        resolver_id=resolver.resolver_id,
                        matched=True,
                        succeeded=False,
                        error_code="resolver_error",
                        message=str(exc),
                    )
                )
                raise ModelResolutionError(
                    str(exc),
                    code="resolver_error",
                    source=source,
                    resolver_id=resolver.resolver_id,
                ) from exc
            attempts.append(
                ResolverAttempt(
                    resolver_id=resolver.resolver_id, matched=True, succeeded=True
                )
            )
            resolver_id = resolver.resolver_id
            break
        if raw is None:
            raise ModelResolutionError(
                f"no resolver can handle source {source!r}",
                code="no_resolver",
                source=source,
                suggestion=(
                    "Use a local config, explicit mapping, registry id, or a "
                    "Hugging Face repo id."
                ),
            )
        if isinstance(source, ModelSpec):
            spec = source
            adapter_id = source.architecture
        else:
            adapter = self._select_adapter(raw, context.allow_generic)
            spec = adapter.adapt(raw)
            adapter_id = adapter.adapter_id
        warnings = list(raw.warnings)
        confidence = (
            Confidence.HIGH
            if raw.source_type in {"local", "huggingface"}
            else Confidence.MEDIUM
        )
        if raw.source_type == "explicit":
            confidence = (
                Confidence.HIGH
                if all(
                    key in raw.raw_config
                    for key in (
                        "num_hidden_layers",
                        "hidden_size",
                        "num_attention_heads",
                    )
                )
                else Confidence.MEDIUM
            )
        if raw.source_type == "registry":
            confidence = (
                Confidence(str(raw.raw_config.get("confidence", "high")))
                if raw.raw_config.get("confidence") in {x.value for x in Confidence}
                else Confidence.HIGH
            )
        if adapter_id == "generic_decoder":
            confidence = min(
                confidence,
                Confidence.MEDIUM,
                key=lambda item: list(Confidence).index(item),
            )
            warnings.append(
                "Generic adapter was used; architecture-specific fields "
                "may be incomplete."
            )
        if raw.raw_config.get("vision_config") or raw.raw_config.get("visual"):
            warnings.append(
                "Multimodal configuration detected; ModelSpec describes "
                "the language decoder only."
            )
        digest = config_digest(raw.raw_config)
        source_info = ModelSource(
            model_id=raw.model_id,
            source_type=raw.source_type,
            source_location=raw.source_location,
            requested_revision=raw.revision,
            resolved_revision=raw.resolved_revision,
            resolver_id=resolver_id,
            adapter_id=adapter_id,
            config_digest=digest,
            loaded_at=datetime.now(UTC).isoformat(),
            from_cache=raw.from_cache,
            confidence=confidence,
            evidence=raw.evidence,
            attempts=attempts,
        )
        return ResolvedModel(
            spec=spec,
            source=source_info,
            raw_config=dict(raw.raw_config),
            resolver_id=resolver_id,
            adapter_id=adapter_id,
            confidence=confidence,
            warnings=warnings,
            attempts=attempts,
        )

    @staticmethod
    def _select_adapter(raw: RawModelConfig, allow_generic: bool) -> Any:
        matches = [adapter for adapter in ADAPTERS if adapter.can_adapt(raw.raw_config)]
        if matches:
            return sorted(
                matches, key=lambda adapter: (-adapter.priority, adapter.adapter_id)
            )[0]
        if not allow_generic:
            raise UnsupportedArchitectureError(
                "no architecture adapter recognizes this configuration",
                code="unsupported_architecture",
                source=raw.model_id,
                suggestion="Set allow_generic=True or provide a supported model_type.",
            )
        return GenericDecoderAdapter()


def resolve_model(
    source: str | Path | Mapping[str, Any] | ModelSpec,
    *,
    revision: str | None = None,
    offline: bool = False,
    cache_dir: Path | None = None,
    allow_generic: bool = True,
) -> ResolvedModel:
    """Resolve a model config without downloading or loading model weights."""
    return ResolverChain().resolve(
        source,
        ResolveContext(
            revision=revision,
            offline=offline,
            cache_dir=cache_dir,
            allow_generic=allow_generic,
        ),
    )
