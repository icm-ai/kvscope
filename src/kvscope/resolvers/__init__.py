"""Model, hardware, and backend resolution public namespace."""

from kvscope.resolvers.backend import (
    BackendProfileCandidate,
    ResolvedBackendProfile,
    resolve_backend_profile,
)
from kvscope.resolvers.base import RawModelConfig, ResolveContext
from kvscope.resolvers.chain import ResolverChain, resolve_model
from kvscope.resolvers.explicit import ExplicitConfigResolver
from kvscope.resolvers.hardware import (
    ResolvedHardwareProfile,
    resolve_hardware_profile,
)
from kvscope.resolvers.huggingface import HuggingFaceConfigResolver
from kvscope.resolvers.local_config import MAX_CONFIG_BYTES, LocalConfigResolver
from kvscope.resolvers.registry import BuiltinRegistryResolver

__all__ = [
    "BackendProfileCandidate",
    "BuiltinRegistryResolver",
    "ExplicitConfigResolver",
    "HuggingFaceConfigResolver",
    "LocalConfigResolver",
    "MAX_CONFIG_BYTES",
    "RawModelConfig",
    "ResolveContext",
    "ResolvedBackendProfile",
    "ResolvedHardwareProfile",
    "ResolverChain",
    "resolve_backend_profile",
    "resolve_hardware_profile",
    "resolve_model",
]
