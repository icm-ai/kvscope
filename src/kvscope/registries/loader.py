"""Safe loaders and validators for KVScope registry entries and profile files."""

import json
from pathlib import Path
from typing import Any

from kvscope.domain.backend import BackendProfile
from kvscope.domain.hardware import HardwareProfile
from kvscope.errors import ProfileValidationError, RegistryValidationError

MAX_PROFILE_FILE_SIZE_BYTES = 1_048_576  # 1 MB


def safe_load_file_content(path: Path) -> Any:
    """Safely load JSON or YAML file content with file size and path checks."""
    resolved_path = path.resolve()
    if not resolved_path.exists():
        raise RegistryValidationError(
            f"File does not exist: {path}",
            code="registry_file_not_found",
            source=str(path),
        )
    if not resolved_path.is_file():
        raise RegistryValidationError(
            f"Path is not a regular file: {path}",
            code="registry_not_a_file",
            source=str(path),
        )
    stat = resolved_path.stat()
    if stat.st_size > MAX_PROFILE_FILE_SIZE_BYTES:
        err_msg = (
            f"File size exceeds limit ({stat.st_size} > "
            f"{MAX_PROFILE_FILE_SIZE_BYTES} bytes): {path}"
        )
        raise RegistryValidationError(
            err_msg,
            code="registry_file_too_large",
            source=str(path),
        )

    content = resolved_path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise RegistryValidationError(
                f"Invalid JSON content in {path}: {exc}",
                code="registry_json_parse_error",
                source=str(path),
            ) from exc
    elif path.suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RegistryValidationError(
                "YAML registry files require PyYAML",
                code="registry_dependency_missing",
            ) from exc
        try:
            return yaml.safe_load(content)
        except Exception as exc:
            raise RegistryValidationError(
                f"Invalid YAML content in {path}: {exc}",
                code="registry_yaml_parse_error",
                source=str(path),
            ) from exc
    else:
        raise RegistryValidationError(
            f"Unsupported profile file format ({path.suffix}): {path}",
            code="registry_unsupported_format",
            source=str(path),
        )


def validate_entry(entry: Any, *, path: Path | None = None) -> dict[str, Any]:
    """Validate a legacy model registry entry dictionary."""
    if not isinstance(entry, dict):
        raise RegistryValidationError(
            "registry entry must be an object",
            code="registry_invalid_entry",
            source=str(path or ""),
        )
    required = ("schema_version", "kind", "id", "config", "source", "confidence")
    missing = [key for key in required if key not in entry]
    if missing:
        raise RegistryValidationError(
            f"registry entry missing: {', '.join(missing)}",
            code="registry_missing_field",
            source=str(path or ""),
        )
    if entry["schema_version"] != "0.1" or entry["kind"] != "model":
        raise RegistryValidationError(
            "unsupported registry schema or kind",
            code="registry_schema_invalid",
            source=str(path or ""),
        )
    if (
        not isinstance(entry["id"], str)
        or not entry["id"]
        or not isinstance(entry["config"], dict)
    ):
        raise RegistryValidationError(
            "registry id and config are invalid",
            code="registry_value_invalid",
            source=str(path or ""),
        )
    source = entry["source"]
    if not isinstance(source, dict) or not source.get("type"):
        raise RegistryValidationError(
            "registry entry must include a source",
            code="registry_source_missing",
            source=str(path or ""),
        )
    if entry["confidence"] not in {"exact", "high", "medium", "low", "unknown"}:
        raise RegistryValidationError(
            "registry confidence is invalid",
            code="registry_confidence_invalid",
            source=str(path or ""),
        )
    aliases = entry.get("aliases", [])
    if not isinstance(aliases, list) or not all(
        isinstance(alias, str) for alias in aliases
    ):
        raise RegistryValidationError(
            "registry aliases must be strings",
            code="registry_alias_invalid",
            source=str(path or ""),
        )
    return dict(entry)


def parse_hardware_profile(
    data: Any, *, source_path: Path | str | None = None
) -> HardwareProfile:
    """Validate and parse raw dictionary/data into a HardwareProfile domain model."""
    if not isinstance(data, dict):
        raise ProfileValidationError(
            f"Hardware profile data must be a dictionary, got {type(data).__name__}"
        )
    if data.get("schema_version") != "0.1":
        raise ProfileValidationError(
            f"Unsupported hardware profile schema version: {data.get('schema_version')}"
        )
    try:
        return HardwareProfile.model_validate(data)
    except Exception as exc:
        raise ProfileValidationError(
            f"Invalid hardware profile data from {source_path or 'input'}: {exc}"
        ) from exc


def parse_backend_profile(
    data: Any, *, source_path: Path | str | None = None
) -> BackendProfile:
    """Validate and parse raw dictionary/data into a BackendProfile domain model."""
    if not isinstance(data, dict):
        raise ProfileValidationError(
            f"Backend profile data must be a dictionary, got {type(data).__name__}"
        )
    if data.get("schema_version") != "0.1":
        raise ProfileValidationError(
            f"Unsupported backend profile schema version: {data.get('schema_version')}"
        )
    try:
        return BackendProfile.model_validate(data)
    except Exception as exc:
        raise ProfileValidationError(
            f"Invalid backend profile data from {source_path or 'input'}: {exc}"
        ) from exc


class ModelRegistry:
    """In-memory model registry loaded explicitly, never during package import."""

    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self.entries: dict[str, dict[str, Any]] = {}
        self.aliases: dict[str, str] = {}
        for entry in entries or []:
            self.add(entry)

    def add(self, raw: dict[str, Any]) -> None:
        entry = validate_entry(raw)
        entry_id = entry["id"]
        if entry_id in self.entries:
            raise RegistryValidationError(
                f"duplicate registry id: {entry_id}", code="registry_duplicate_id"
            )
        names = [entry_id, *entry.get("aliases", [])]
        if any(name in self.aliases for name in names):
            raise RegistryValidationError(
                "duplicate registry alias", code="registry_duplicate_alias"
            )
        self.entries[entry_id] = entry
        for name in names:
            self.aliases[name] = entry_id

    @classmethod
    def from_directory(cls, directory: Path) -> "ModelRegistry":
        entries: list[dict[str, Any]] = []
        if directory.exists():
            for path in sorted(directory.iterdir()):
                if path.suffix in {".json", ".yaml", ".yml"}:
                    loaded = safe_load_file_content(path)
                    if isinstance(loaded, list):
                        entries.extend(loaded)
                    else:
                        entries.append(loaded)
        return cls(entries)

    def get(self, model_id: str) -> dict[str, Any] | None:
        target = self.aliases.get(model_id)
        return self.entries.get(target) if target else None
