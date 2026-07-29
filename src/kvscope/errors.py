"""Exception hierarchy for KVScope.

Concrete error behavior is intentionally deferred until the resolver and
calculation phases.
"""


class KVScopeError(Exception):
    """Base exception for expected KVScope errors."""


class ModelResolutionError(KVScopeError):
    """Raised when a model source cannot be resolved."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "model_resolution_error",
        source: object | None = None,
        resolver_id: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.code = code
        self.source = source
        self.resolver_id = resolver_id
        self.suggestion = suggestion
        super().__init__(message)


class ModelSourceNotFoundError(ModelResolutionError):
    """A requested local, remote, or registry source does not exist."""


class ModelConfigParseError(ModelResolutionError):
    """A config exists but cannot be parsed as a valid JSON object."""


class ModelConfigConflictError(ModelResolutionError):
    """Equivalent aliases in a config contain conflicting values."""


class OfflineCacheMissError(ModelResolutionError):
    """Offline resolution has no matching cached configuration."""


class OptionalDependencyMissingError(ModelResolutionError):
    """An optional resolver dependency is not installed."""


class RegistryValidationError(ModelResolutionError, ValueError):
    """A registry entry violates the registry schema or uniqueness rules."""


class InvalidModelConfigError(KVScopeError, ValueError):
    """Raised when model configuration data is invalid."""


class UnsupportedArchitectureError(ModelResolutionError, ValueError):
    """Raised when a model architecture is not supported."""


class ProfileValidationError(KVScopeError, ValueError):
    """Raised when a hardware or backend profile is invalid."""
