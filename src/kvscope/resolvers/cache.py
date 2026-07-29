"""Versioned, atomic cache for fetched model configs."""

import json
import os
import tempfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

CACHE_SCHEMA_VERSION = "0.1"


def cache_root(cache_dir: Path | None) -> Path:
    return cache_dir or (Path.home() / ".cache" / "kvscope" / "models")


def cache_key(model_id: str, revision: str | None) -> str:
    return sha256(f"{model_id}\0{revision or 'main'}".encode()).hexdigest()


def read_cache(
    model_id: str, revision: str | None, directory: Path | None
) -> dict[str, Any] | None:
    path = cache_root(directory) / f"{cache_key(model_id, revision)}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != CACHE_SCHEMA_VERSION
    ):
        return None
    if payload.get("model_id") != model_id or payload.get("requested_revision") != (
        revision or "main"
    ):
        return None
    return payload


def write_cache(
    model_id: str,
    revision: str | None,
    raw_config: dict[str, Any],
    resolved_revision: str | None,
    directory: Path | None,
) -> None:
    root = cache_root(directory)
    root.mkdir(parents=True, exist_ok=True)
    content = json.dumps(
        raw_config, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "model_id": model_id,
        "requested_revision": revision or "main",
        "resolved_revision": resolved_revision,
        "raw_config": raw_config,
        "fetched_at": datetime.now(UTC).isoformat(),
        "source": "huggingface",
        "content_digest": sha256(content.encode()).hexdigest(),
    }
    target = root / f"{cache_key(model_id, revision)}.json"
    fd, temporary = tempfile.mkstemp(prefix=".kvscope-", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
