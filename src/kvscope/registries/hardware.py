"""In-memory Hardware Registry with validation and conflict detection."""

from pathlib import Path

from kvscope.domain.enums import ProfileStatus
from kvscope.domain.hardware import HardwareProfile
from kvscope.errors import HardwareProfileConflictError, ProfileValidationError
from kvscope.registries.loader import parse_hardware_profile, safe_load_file_content

DEFAULT_HARDWARE_PROFILES_DIR = (
    Path(__file__).resolve().parents[3] / "profiles" / "hardware"
)


class HardwareRegistry:
    """In-memory registry of Hardware Profiles."""

    def __init__(self, profiles: list[HardwareProfile] | None = None) -> None:
        self.profiles: dict[str, HardwareProfile] = {}
        self.alias_map: dict[str, str] = {}
        for profile in profiles or []:
            self.add(profile)

    def add(self, profile: HardwareProfile, *, allow_synthetic: bool = False) -> None:
        """Validate and register a HardwareProfile."""
        profile_id = profile.profile_id
        if profile_id in self.profiles or profile_id in self.alias_map:
            raise HardwareProfileConflictError(
                f"Hardware profile ID '{profile_id}' conflicts with entry or alias.",
                profile_id=profile_id,
            )

        for alias in profile.aliases:
            if alias in self.profiles or alias in self.alias_map:
                raise HardwareProfileConflictError(
                    f"Hardware profile alias '{alias}' conflicts with ID or alias.",
                    profile_id=profile_id,
                )

        if profile.total_memory_bytes <= 0:
            raise ProfileValidationError(
                f"Hardware profile '{profile_id}' must have total_memory > 0."
            )

        if not profile.evidence:
            raise ProfileValidationError(
                f"Hardware profile '{profile_id}' must contain evidence."
            )

        if profile.status == ProfileStatus.DEPRECATED and not profile.notes:
            raise ProfileValidationError(
                f"Deprecated hardware profile '{profile_id}' must provide notes."
            )

        if len(profile.supported_backend_ids) != len(
            set(profile.supported_backend_ids)
        ):
            raise ProfileValidationError(
                f"Hardware profile '{profile_id}' backend_ids contains duplicates."
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
    ) -> "HardwareRegistry":
        """Load hardware profiles from a local directory."""
        registry = cls()
        if directory.exists() and directory.is_dir():
            for path in sorted(directory.iterdir()):
                if path.suffix in {".json", ".yaml", ".yml"}:
                    raw = safe_load_file_content(path)
                    if isinstance(raw, list):
                        for item in raw:
                            prof = parse_hardware_profile(item, source_path=path)
                            registry.add(prof, allow_synthetic=allow_synthetic)
                    elif isinstance(raw, dict):
                        prof = parse_hardware_profile(raw, source_path=path)
                        registry.add(prof, allow_synthetic=allow_synthetic)
        return registry

    def get(self, identifier: str) -> HardwareProfile | None:
        """Retrieve a HardwareProfile by ID or alias."""
        target_id = self.alias_map.get(identifier)
        if not target_id:
            return None
        return self.profiles.get(target_id)

    def list_profiles(self) -> list[HardwareProfile]:
        """Return a sorted list of registered hardware profiles."""
        return sorted(self.profiles.values(), key=lambda p: p.profile_id)


_DEFAULT_HARDWARE_REGISTRY: HardwareRegistry | None = None


def get_default_hardware_registry() -> HardwareRegistry:
    """Get or lazily initialize the default built-in HardwareRegistry."""
    global _DEFAULT_HARDWARE_REGISTRY
    if _DEFAULT_HARDWARE_REGISTRY is None:
        _DEFAULT_HARDWARE_REGISTRY = HardwareRegistry.from_directory(
            DEFAULT_HARDWARE_PROFILES_DIR, allow_synthetic=False
        )
    return _DEFAULT_HARDWARE_REGISTRY
