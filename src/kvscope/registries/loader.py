"""Safe loader and validator for model registry entries."""

import json
from pathlib import Path
from typing import Any

from kvscope.errors import RegistryValidationError


def _load_file(path: Path) -> Any:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RegistryValidationError(
                "YAML registry files require PyYAML", code="registry_dependency_missing"
            ) from exc
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return None


def validate_entry(entry: Any, *, path: Path | None = None) -> dict[str, Any]:
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


class ModelRegistry:
    """In-memory registry loaded explicitly, never during package import."""

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
                    loaded = _load_file(path)
                    if isinstance(loaded, list):
                        entries.extend(loaded)
                    else:
                        entries.append(loaded)
        return cls(entries)

    def get(self, model_id: str) -> dict[str, Any] | None:
        target = self.aliases.get(model_id)
        return self.entries.get(target) if target else None
