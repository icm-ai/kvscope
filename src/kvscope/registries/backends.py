"""In-memory Backend Registry with validation and conflict detection."""

from pathlib import Path

from kvscope.domain.backend import BackendProfile
from kvscope.domain.enums import ProfileStatus
from kvscope.errors import BackendProfileError, ProfileValidationError
from kvscope.registries.loader import parse_backend_profile, safe_load_file_content

DEFAULT_BACKEND_PROFILES_DIR = (
    Path(__file__).resolve().parents[3] / "profiles" / "backends"
)


class BackendRegistry:
    """In-memory registry of Backend Profiles."""

    def __init__(self, profiles: list[BackendProfile] | None = None) -> None:
        self.profiles: dict[str, BackendProfile] = {}
        self.alias_map: dict[str, str] = {}
        for profile in profiles or []:
            self.add(profile)

    def add(self, profile: BackendProfile, *, allow_synthetic: bool = False) -> None:
        """Validate and register a BackendProfile."""
        profile_id = profile.profile_id
        if profile_id in self.profiles or profile_id in self.alias_map:
            raise BackendProfileError(
                f"Backend profile ID '{profile_id}' conflicts with entry or alias.",
                profile_id=profile_id,
            )

        for alias in profile.aliases:
            if alias in self.profiles or alias in self.alias_map:
                raise BackendProfileError(
                    f"Backend profile alias '{alias}' conflicts with ID or alias.",
                    profile_id=profile_id,
                )

        if not profile.evidence:
            raise ProfileValidationError(
                f"Backend profile '{profile_id}' must contain evidence."
            )

        if profile.status == ProfileStatus.DEPRECATED and not profile.notes:
            raise ProfileValidationError(
                f"Deprecated backend profile '{profile_id}' must provide notes."
            )

        if not allow_synthetic:
            for ev in profile.evidence:
                if ev.source_type == "synthetic_test":
                    err = (
                        f"Synthetic profile '{profile_id}' with "
                        "source_type='synthetic_test' not allowed."
                    )
                    raise ProfileValidationError(err)

        self.profiles[profile_id] = profile
        self.alias_map[profile_id] = profile_id
        for alias in profile.aliases:
            self.alias_map[alias] = profile_id

    @classmethod
    def from_directory(
        cls, directory: Path, *, allow_synthetic: bool = False
    ) -> "BackendRegistry":
        """Load backend profiles from a local directory."""
        registry = cls()
        if directory.exists() and directory.is_dir():
            for path in sorted(directory.iterdir()):
                if path.suffix in {".json", ".yaml", ".yml"}:
                    raw = safe_load_file_content(path)
                    if isinstance(raw, list):
                        for item in raw:
                            prof = parse_backend_profile(item, source_path=path)
                            registry.add(prof, allow_synthetic=allow_synthetic)
                    elif isinstance(raw, dict):
                        prof = parse_backend_profile(raw, source_path=path)
                        registry.add(prof, allow_synthetic=allow_synthetic)
        return registry

    def get(self, identifier: str) -> BackendProfile | None:
        """Retrieve a BackendProfile by ID or alias."""
        target_id = self.alias_map.get(identifier)
        if not target_id:
            return None
        return self.profiles.get(target_id)

    def list_profiles(self) -> list[BackendProfile]:
        """Return a sorted list of registered backend profiles."""
        return sorted(self.profiles.values(), key=lambda p: p.profile_id)


_DEFAULT_BACKEND_REGISTRY: BackendRegistry | None = None


def get_default_backend_registry() -> BackendRegistry:
    """Get or lazily initialize the default built-in BackendRegistry."""
    global _DEFAULT_BACKEND_REGISTRY
    if _DEFAULT_BACKEND_REGISTRY is None:
        _DEFAULT_BACKEND_REGISTRY = BackendRegistry.from_directory(
            DEFAULT_BACKEND_PROFILES_DIR, allow_synthetic=False
        )
    return _DEFAULT_BACKEND_REGISTRY
