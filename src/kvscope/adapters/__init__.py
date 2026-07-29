"""Architecture adapters used by the model resolver."""

from kvscope.adapters.adapters import (
    ADAPTERS,
    DeepSeekAdapter,
    GenericDecoderAdapter,
    LlamaAdapter,
    QwenAdapter,
)

__all__ = [
    "ADAPTERS",
    "DeepSeekAdapter",
    "GenericDecoderAdapter",
    "LlamaAdapter",
    "QwenAdapter",
]
