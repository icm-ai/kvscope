"""Exception hierarchy for KVScope.

Concrete error behavior is intentionally deferred until the resolver and
calculation phases.
"""


class KVScopeError(Exception):
    """Base exception for expected KVScope errors."""


class ModelResolutionError(KVScopeError):
    """Raised when a model source cannot be resolved."""


class InvalidModelConfigError(KVScopeError):
    """Raised when model configuration data is invalid."""


class UnsupportedArchitectureError(KVScopeError):
    """Raised when a model architecture is not supported."""


class ProfileValidationError(KVScopeError):
    """Raised when a hardware or backend profile is invalid."""
