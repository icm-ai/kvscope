"""Public package metadata for KVScope.

Phase 0 provides the importable package boundary. Analysis APIs are introduced
in later implementation phases.
"""

__version__ = "0.1.0"

from kvscope.api import resolve_model
from kvscope.domain import ModelSource, ModelSpec, ResolvedModel

__all__ = ["ModelSource", "ModelSpec", "ResolvedModel", "__version__", "resolve_model"]
