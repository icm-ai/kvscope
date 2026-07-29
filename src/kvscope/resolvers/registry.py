"""Built-in model registry resolver."""

from pathlib import Path

from kvscope.errors import ModelSourceNotFoundError, RegistryValidationError
from kvscope.registries.loader import ModelRegistry
from kvscope.resolvers.base import RawModelConfig, ResolveContext


class BuiltinRegistryResolver:
    resolver_id = "builtin_registry"

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        directory = Path(__file__).parents[3] / "profiles" / "models"
        self.registry = registry or ModelRegistry.from_directory(directory)

    def can_resolve(self, source: object) -> bool:
        return isinstance(source, str) and self.registry.get(source) is not None

    def resolve(self, source: object, context: ResolveContext) -> RawModelConfig:
        if not isinstance(source, str):
            raise ModelSourceNotFoundError(
                "registry source must be a model id", code="registry_source_invalid"
            )
        entry = self.registry.get(source)
        if entry is None:
            raise ModelSourceNotFoundError(
                f"model is not in the built-in registry: {source}",
                code="registry_not_found",
                source=source,
            )
        entry_revision = entry.get("source", {}).get("revision")
        if (
            context.revision is not None
            and entry_revision is not None
            and context.revision != entry_revision
        ):
            raise RegistryValidationError(
                f"registry entry does not cover requested revision {context.revision}",
                code="registry_revision_mismatch",
                source=source,
                resolver_id=self.resolver_id,
            )
        config = dict(entry["config"])
        config.setdefault("model_id", entry["id"])
        config.setdefault("model_type", entry.get("architecture", ""))
        return RawModelConfig(
            model_id=entry["id"],
            raw_config=config,
            source_type="registry",
            source_location=entry.get("source", {}).get("repository") or entry["id"],
            revision=context.revision,
            resolved_revision=entry_revision,
            warnings=[],
        )
