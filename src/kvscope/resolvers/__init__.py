"""Model configuration resolution public namespace."""

from kvscope.resolvers.base import RawModelConfig, ResolveContext
from kvscope.resolvers.chain import ResolverChain, resolve_model
from kvscope.resolvers.explicit import ExplicitConfigResolver
from kvscope.resolvers.huggingface import HuggingFaceConfigResolver
from kvscope.resolvers.local_config import MAX_CONFIG_BYTES, LocalConfigResolver
from kvscope.resolvers.registry import BuiltinRegistryResolver

__all__ = [
    "BuiltinRegistryResolver",
    "ExplicitConfigResolver",
    "HuggingFaceConfigResolver",
    "LocalConfigResolver",
    "MAX_CONFIG_BYTES",
    "RawModelConfig",
    "ResolveContext",
    "ResolverChain",
    "resolve_model",
]
