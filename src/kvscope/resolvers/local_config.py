"""Safe local JSON config resolver."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from kvscope.errors import ModelConfigParseError, ModelSourceNotFoundError
from kvscope.resolvers.base import RawModelConfig, ResolveContext

MAX_CONFIG_BYTES = 10 * 1024 * 1024


def config_digest(config: dict[str, Any]) -> str:
    """Hash canonical JSON without retaining a second mutable input."""
    payload = json.dumps(
        config, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return sha256(payload).hexdigest()


class LocalConfigResolver:
    resolver_id = "local_config"

    def can_resolve(self, source: object) -> bool:
        if isinstance(source, Path):
            return True
        if not isinstance(source, str):
            return False
        path = Path(source)
        return (
            path.exists()
            or path.suffix.lower() == ".json"
            or source.startswith(("/", "./", "../", "~"))
            or "\\" in source
        )

    def resolve(self, source: object, context: ResolveContext) -> RawModelConfig:
        path = Path(source) if isinstance(source, (str, Path)) else Path(str(source))
        if path.is_dir():
            path = path / "config.json"
        if not path.exists():
            raise ModelSourceNotFoundError(
                f"local model config was not found: {path.name}",
                code="local_source_not_found",
                source=str(path),
                resolver_id=self.resolver_id,
                suggestion="Provide a config.json path or an existing model directory.",
            )
        if not path.is_file():
            raise ModelSourceNotFoundError(
                "local source is not a file or directory",
                code="local_source_invalid",
                source=str(path),
            )
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ModelConfigParseError(
                "cannot stat local config",
                code="local_permission_error",
                source=str(path),
            ) from exc
        if size > MAX_CONFIG_BYTES:
            raise ModelConfigParseError(
                f"local config exceeds {MAX_CONFIG_BYTES} bytes",
                code="local_config_too_large",
                source=str(path),
            )
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ModelConfigParseError(
                "local config is not valid UTF-8",
                code="local_invalid_utf8",
                source=str(path),
            ) from exc
        except PermissionError as exc:
            raise ModelConfigParseError(
                "permission denied reading local config",
                code="local_permission_error",
                source=str(path),
            ) from exc
        try:
            config = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ModelConfigParseError(
                "local config is invalid JSON",
                code="local_invalid_json",
                source=str(path),
            ) from exc
        if not isinstance(config, dict):
            raise ModelConfigParseError(
                "config.json top level must be an object",
                code="local_config_not_object",
                source=str(path),
            )
        model_id = config.get("model_id")
        if not isinstance(model_id, str) or not model_id:
            model_id = path.parent.name
        return RawModelConfig(
            model_id=model_id,
            raw_config=dict(config),
            source_type="local",
            source_location=str(path.resolve()),
            revision=context.revision,
            resolved_revision=context.revision,
            evidence=[],
            warnings=[],
        )
