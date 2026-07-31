"""Exception hierarchy for KVScope."""


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


class HardwareProfileError(KVScopeError):
    """Base class for hardware profile resolution and validation errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "hardware_profile_error",
        profile_id: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.code = code
        self.profile_id = profile_id
        self.suggestion = suggestion
        super().__init__(message)


class HardwareProfileNotFoundError(HardwareProfileError):
    """A requested hardware profile was not found in registry or paths."""


class HardwareProfileConflictError(HardwareProfileError):
    """Hardware profile ID or alias conflicts with existing entries."""


class BackendProfileError(KVScopeError):
    """Base class for backend profile resolution and validation errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "backend_profile_error",
        backend_id: str | None = None,
        version: str | None = None,
        hardware_id: str | None = None,
        profile_id: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.code = code
        self.backend_id = backend_id
        self.version = version
        self.hardware_id = hardware_id
        self.profile_id = profile_id
        self.suggestion = suggestion
        super().__init__(message)


class BackendProfileNotFoundError(BackendProfileError):
    """A requested backend profile was not found."""


class BackendProfileAmbiguousError(BackendProfileError):
    """Multiple backend profiles matched with equal top priority."""


class BackendVersionMismatchError(BackendProfileError):
    """Backend version specifier does not match the requested backend version."""


class IncompleteBackendProfileError(BackendProfileError):
    """A profile is marked incomplete and requires explicit override or flag."""


class RuntimeOverheadInputError(KVScopeError):
    """Raised when inputs to runtime overhead estimation are invalid."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "runtime_overhead_input_error",
        field_name: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.code = code
        self.field_name = field_name
        self.suggestion = suggestion
        super().__init__(message)


class UnsupportedMemoryTopologyError(KVScopeError):
    """Raised when a memory topology is unsupported by a backend or profile."""


class MemoryAggregationError(KVScopeError):
    """Base exception for memory aggregation errors."""


class MissingMemoryComponentError(MemoryAggregationError):
    """Raised when a required memory component is missing in strict mode."""


class InvalidMemoryEstimateError(MemoryAggregationError):
    """Raised when a component estimate contains invalid data."""


class FeasibilityEvaluationError(KVScopeError):
    """Base exception for feasibility evaluation errors."""


class IncompleteRequirementError(FeasibilityEvaluationError):
    """Raised when strict mode detects an incomplete requirement."""


class ConstraintAnalysisError(KVScopeError):
    """Base exception for constraint analysis errors."""


class RecommendationError(KVScopeError):
    """Base exception for recommendation engine errors."""


class RecommendationIneligibleError(RecommendationError):
    """Raised when recommendations are requested for an ineligible baseline."""


class RecommendationContextError(RecommendationError):
    """Raised when recommendation context or inputs are invalid or inconsistent."""


class SafeLimitCalculationError(RecommendationError):
    """Raised when safe parameter back-solving encounters an error."""


class CandidateEvaluationError(RecommendationError):
    """Raised when candidate evaluation fails."""


class UnsupportedRecommendationActionError(RecommendationError):
    """Raised when an unsupported recommendation action is requested."""
