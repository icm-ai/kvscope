"""Hardware profile resolver for KVScope."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import Field, StrictStr

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import Confidence, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import HardwareProfile
from kvscope.errors import HardwareProfileError, HardwareProfileNotFoundError
from kvscope.registries.hardware import get_default_hardware_registry
from kvscope.registries.loader import parse_hardware_profile, safe_load_file_content


class ResolvedHardwareProfile(DomainModel):
    """The resolved HardwareProfile along with provenance information."""

    profile: HardwareProfile
    source_type: StrictStr
    source_location: StrictStr | None = None
    resolver_id: StrictStr = "hardware_profile_resolver"
    confidence: Confidence
    warnings: list[StrictStr] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


def resolve_hardware_profile(
    source: str | Path | Mapping[str, Any] | HardwareProfile,
    *,
    allow_deprecated: bool = False,
) -> ResolvedHardwareProfile:
    """Resolve a HardwareProfile from instance, dict mapping, file, ID, or alias.

    Resolver priority:
    1. HardwareProfile instance
    2. Explicit dict mapping
    3. Local file path
    4. Built-in Registry ID
    5. Built-in Registry alias
    """
    warnings: list[str] = []
    source_type = "unknown"
    source_location: str | None = None
    resolved_profile: HardwareProfile | None = None

    if isinstance(source, HardwareProfile):
        source_type = "instance"
        resolved_profile = source

    elif isinstance(source, Mapping):
        source_type = "mapping"
        dict_data = dict(source)
        resolved_profile = parse_hardware_profile(dict_data)

    elif isinstance(source, (str, Path)):
        path_candidate = Path(source)
        if path_candidate.exists() and path_candidate.is_file():
            source_type = "file"
            source_location = str(path_candidate.resolve())
            raw_data = safe_load_file_content(path_candidate)
            resolved_profile = parse_hardware_profile(
                raw_data, source_path=path_candidate
            )
        elif isinstance(source, str):
            registry = get_default_hardware_registry()
            matched = registry.get(source)
            if matched is not None:
                if matched.profile_id == source:
                    source_type = "built_in_registry_id"
                else:
                    source_type = "built_in_registry_alias"
                source_location = f"registry:{matched.profile_id}"
                resolved_profile = matched

    if resolved_profile is None:
        sug = (
            "Specify a valid hardware profile ID (e.g. 'generic-discrete-16gib'), "
            "file path, or HardwareProfile object."
        )
        raise HardwareProfileNotFoundError(
            f"Hardware profile source '{source}' could not be resolved.",
            profile_id=str(source) if isinstance(source, str) else None,
            suggestion=sug,
        )

    if resolved_profile.status == ProfileStatus.DEPRECATED:
        if not allow_deprecated:
            err = (
                f"Hardware profile '{resolved_profile.profile_id}' is deprecated. "
                "Set allow_deprecated=True to allow."
            )
            raise HardwareProfileError(
                err,
                profile_id=resolved_profile.profile_id,
            )
        warnings.append(
            f"Hardware profile '{resolved_profile.profile_id}' is deprecated."
        )

    confidence = resolved_profile.confidence
    evidence = list(resolved_profile.evidence)

    return ResolvedHardwareProfile(
        profile=resolved_profile,
        source_type=source_type,
        source_location=source_location,
        resolver_id="hardware_profile_resolver",
        confidence=confidence,
        warnings=warnings,
        evidence=evidence,
    )
