"""Optional Hugging Face config metadata resolver."""

import json

from kvscope.errors import (
    ModelConfigParseError,
    ModelResolutionError,
    OfflineCacheMissError,
    OptionalDependencyMissingError,
)
from kvscope.resolvers.base import RawModelConfig, ResolveContext
from kvscope.resolvers.cache import read_cache, write_cache


class HuggingFaceConfigResolver:
    resolver_id = "huggingface_config"

    def __init__(self, registry_ids: set[str] | None = None) -> None:
        self._registry_ids = registry_ids or set()

    def can_resolve(self, source: object) -> bool:
        if (
            not isinstance(source, str)
            or not source
            or source.startswith(("/", "./", "../", "~"))
        ):
            return False
        return "/" in source and source not in self._registry_ids

    def resolve(self, source: object, context: ResolveContext) -> RawModelConfig:
        if not isinstance(source, str):
            raise ModelResolutionError(
                "Hugging Face source must be a repository ID", code="invalid_hf_source"
            )
        cached = read_cache(source, context.revision, context.cache_dir)
        if cached is not None:
            config = cached.get("raw_config")
            if isinstance(config, dict):
                return RawModelConfig(
                    model_id=source,
                    raw_config=dict(config),
                    source_type="huggingface",
                    source_location=source,
                    revision=context.revision,
                    resolved_revision=cached.get("resolved_revision"),
                    from_cache=True,
                    warnings=["Loaded from local cache."],
                )
        if context.offline:
            raise OfflineCacheMissError(
                f"no cached Hugging Face config for {source}",
                code="offline_cache_miss",
                source=source,
                resolver_id=self.resolver_id,
                suggestion="Run once online or provide an explicit/local config.",
            )
        try:
            from huggingface_hub import (  # type: ignore[import-not-found]
                HfApi,
                hf_hub_download,
            )
        except ImportError as exc:
            raise OptionalDependencyMissingError(
                "huggingface_hub is required for Hugging Face model IDs",
                code="optional_dependency_missing",
                source=source,
                resolver_id=self.resolver_id,
                suggestion='Install with `pip install "kvscope[huggingface]"`.',
            ) from exc
        try:
            filename = hf_hub_download(
                repo_id=source,
                filename="config.json",
                revision=context.revision,
                local_files_only=False,
            )
        except Exception as exc:  # library exception classes vary by supported versions
            name = type(exc).__name__.lower()
            if "gated" in name or "auth" in name or "token" in name:
                code = "authentication_required"
            elif "revision" in name or "ref" in name:
                code = "revision_not_found"
            elif "repository" in name or "repo" in name or "notfound" in name:
                code = "repository_not_found"
            else:
                code = "network_unavailable"
            raise ModelResolutionError(
                f"unable to fetch config for {source}: {code}",
                code=code,
                source=source,
                resolver_id=self.resolver_id,
                suggestion=(
                    "Use a local config, explicit mapping, or check the "
                    "revision/network."
                ),
            ) from exc
        try:
            config = json.loads(open(filename, encoding="utf-8").read())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelConfigParseError(
                f"Hugging Face config for {source} is malformed",
                code="config_malformed",
                source=source,
                resolver_id=self.resolver_id,
            ) from exc
        if not isinstance(config, dict):
            raise ModelConfigParseError(
                "Hugging Face config top level must be an object",
                code="config_not_object",
                source=source,
            )
        resolved_revision = context.revision
        try:
            info = HfApi().model_info(source, revision=context.revision)
            resolved_revision = getattr(info, "sha", None) or resolved_revision
        except Exception:
            # The config itself is still valid; provenance remains requested revision.
            pass
        write_cache(
            source, context.revision, config, resolved_revision, context.cache_dir
        )
        return RawModelConfig(
            model_id=source,
            raw_config=dict(config),
            source_type="huggingface",
            source_location=source,
            revision=context.revision,
            resolved_revision=resolved_revision,
        )
