"""Tests for kvscope.api and kvscope.errors module exports and exception hierarchy."""


import kvscope.api as api
from kvscope.errors import (
    InvalidModelConfigError,
    KVScopeError,
    ModelResolutionError,
    ProfileValidationError,
    UnsupportedArchitectureError,
)


def test_api_exports() -> None:
    """Verify all symbols exported in api.__all__ are accessible."""
    assert hasattr(api, "__all__")
    for name in api.__all__:
        assert hasattr(api, name)


def test_exception_hierarchy() -> None:
    """Verify exception hierarchy in kvscope.errors."""
    assert issubclass(ModelResolutionError, KVScopeError)
    assert issubclass(InvalidModelConfigError, KVScopeError)
    assert issubclass(InvalidModelConfigError, ValueError)
    assert issubclass(UnsupportedArchitectureError, KVScopeError)
    assert issubclass(UnsupportedArchitectureError, ValueError)
    assert issubclass(ProfileValidationError, KVScopeError)
    assert issubclass(ProfileValidationError, ValueError)

    err = ModelResolutionError("model not found")
    assert str(err) == "model not found"
