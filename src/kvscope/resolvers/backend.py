"""Backend profile resolver for KVScope."""

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import Field, StrictStr

from kvscope.domain.backend import BackendProfile
from kvscope.domain.base import DomainModel
from kvscope.domain.enums import Confidence, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import HardwareProfile
from kvscope.errors import (
    BackendProfileAmbiguousError,
    BackendProfileNotFoundError,
    BackendVersionMismatchError,
)
from kvscope.registries.backends import get_default_backend_registry


class BackendProfileCandidate(DomainModel):
    """Evaluation record of a backend profile candidate during resolution."""

    profile_id: StrictStr
    matched_backend: bool
    matched_version: bool
    matched_hardware: bool
    selected: bool
    rejection_reason: StrictStr | None = None


class ResolvedBackendProfile(DomainModel):
    """The resolved BackendProfile along with resolution details and provenance."""

    profile: BackendProfile
    source_type: StrictStr = "built_in_registry"
    source_location: StrictStr | None = None
    resolver_id: StrictStr = "backend_profile_resolver"
    confidence: Confidence
    warnings: list[StrictStr] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    candidates: list[BackendProfileCandidate] = Field(default_factory=list)


def resolve_backend_profile(
    backend_id: str,
    *,
    version: str | None = None,
    hardware: HardwareProfile | None = None,
    allow_unverified: bool = True,
    allow_deprecated: bool = False,
) -> ResolvedBackendProfile:
    """Resolve a BackendProfile matching backend_id, version, and hardware constraints.

    Rules:
    1. backend_id or alias must match.
    2. If version is specified, version_specifier must match.
    3. If hardware is specified, topology/vendor/family filters must match.
    4. Evaluates specificity scoring and raises BackendProfileAmbiguousError on ties.
    """
    registry = get_default_backend_registry()
    all_profiles = registry.list_profiles()

    candidate_records: list[BackendProfileCandidate] = []
    eligible_candidates: list[tuple[int, BackendProfile]] = []
    warnings: list[str] = []

    has_backend_match = False
    has_version_mismatch = False

    for prof in all_profiles:
        matched_backend = (
            prof.backend_id == backend_id
            or backend_id in prof.aliases
            or prof.profile_id == backend_id
        )
        if not matched_backend:
            candidate_records.append(
                BackendProfileCandidate(
                    profile_id=prof.profile_id,
                    matched_backend=False,
                    matched_version=False,
                    matched_hardware=False,
                    selected=False,
                    rejection_reason="backend_id mismatch",
                )
            )
            continue

        has_backend_match = True
        matched_version = True
        rejection_reason: str | None = None

        if version is not None:
            if prof.version_specifier is not None:
                try:
                    parsed_v = Version(version)
                    spec_set = SpecifierSet(prof.version_specifier)
                    if parsed_v not in spec_set:
                        matched_version = False
                        has_version_mismatch = True
                        rejection_reason = (
                            f"version '{version}' does not satisfy specifier "
                            f"'{prof.version_specifier}'"
                        )
                except InvalidVersion:
                    matched_version = False
                    rejection_reason = f"invalid version string '{version}'"

        if not matched_version:
            candidate_records.append(
                BackendProfileCandidate(
                    profile_id=prof.profile_id,
                    matched_backend=True,
                    matched_version=False,
                    matched_hardware=False,
                    selected=False,
                    rejection_reason=rejection_reason,
                )
            )
            continue

        matched_hardware = True
        if hardware is not None:
            if (
                prof.supported_memory_topologies
                and hardware.memory_topology not in prof.supported_memory_topologies
            ):
                matched_hardware = False
                top_val = hardware.memory_topology.value
                rejection_reason = (
                    f"topology '{top_val}' not supported by backend profile"
                )
            elif (
                prof.supported_vendors and hardware.vendor not in prof.supported_vendors
            ):
                matched_hardware = False
                rejection_reason = (
                    f"vendor '{hardware.vendor}' not supported by backend profile"
                )
            elif (
                prof.supported_families
                and hardware.family
                and hardware.family not in prof.supported_families
            ):
                matched_hardware = False
                rejection_reason = (
                    f"family '{hardware.family}' not supported by backend profile"
                )

        if not matched_hardware:
            candidate_records.append(
                BackendProfileCandidate(
                    profile_id=prof.profile_id,
                    matched_backend=True,
                    matched_version=matched_version,
                    matched_hardware=False,
                    selected=False,
                    rejection_reason=rejection_reason,
                )
            )
            continue

        if prof.status == ProfileStatus.DEPRECATED and not allow_deprecated:
            candidate_records.append(
                BackendProfileCandidate(
                    profile_id=prof.profile_id,
                    matched_backend=True,
                    matched_version=matched_version,
                    matched_hardware=matched_hardware,
                    selected=False,
                    rejection_reason="deprecated profile not allowed",
                )
            )
            continue

        if prof.status == ProfileStatus.UNVERIFIED and not allow_unverified:
            candidate_records.append(
                BackendProfileCandidate(
                    profile_id=prof.profile_id,
                    matched_backend=True,
                    matched_version=matched_version,
                    matched_hardware=matched_hardware,
                    selected=False,
                    rejection_reason="unverified profile not allowed",
                )
            )
            continue

        score = 0
        if version is not None and prof.version_specifier is not None:
            score += 100
        elif prof.version_specifier is not None:
            score += 10

        if hardware is not None and (
            prof.supported_memory_topologies
            or prof.supported_vendors
            or prof.supported_families
        ):
            score += 50

        if prof.status == ProfileStatus.VERIFIED:
            score += 20

        eligible_candidates.append((score, prof))

    if not eligible_candidates:
        if not has_backend_match:
            raise BackendProfileNotFoundError(
                f"No backend profile found for backend_id '{backend_id}'.",
                backend_id=backend_id,
                version=version,
                suggestion="Specify a backend ID (e.g. 'vllm' or 'llama_cpp').",
            )
        elif has_version_mismatch:
            msg = (
                f"Backend profile for '{backend_id}' found, but requested "
                f"version '{version}' did not match version specifiers."
            )
            sug = (
                "Specify a supported backend version or omit version "
                "to match generic template."
            )
            raise BackendVersionMismatchError(
                msg,
                backend_id=backend_id,
                version=version,
                suggestion=sug,
            )
        else:
            msg = f"No backend profile matching '{backend_id}' found."
            raise BackendProfileNotFoundError(
                msg,
                backend_id=backend_id,
                version=version,
            )

    eligible_candidates.sort(key=lambda x: x[0], reverse=True)

    max_score = eligible_candidates[0][0]
    top_tier = [c for c in eligible_candidates if c[0] == max_score]

    if len(top_tier) > 1:
        tied_ids = [c[1].profile_id for c in top_tier]
        err = (
            f"Ambiguous backend profile selection for '{backend_id}': "
            f"multiple profiles tied with top score {max_score}: {tied_ids}"
        )
        raise BackendProfileAmbiguousError(
            err,
            backend_id=backend_id,
            version=version,
            suggestion="Specify exact profile ID or narrow version/hardware criteria.",
        )

    selected_profile = top_tier[0][1]

    final_candidates: list[BackendProfileCandidate] = []
    for cand in candidate_records:
        if cand.profile_id == selected_profile.profile_id:
            final_candidates.append(
                BackendProfileCandidate(
                    profile_id=cand.profile_id,
                    matched_backend=cand.matched_backend,
                    matched_version=cand.matched_version,
                    matched_hardware=cand.matched_hardware,
                    selected=True,
                    rejection_reason=None,
                )
            )
        else:
            final_candidates.append(cand)

    if not any(c.profile_id == selected_profile.profile_id for c in final_candidates):
        final_candidates.append(
            BackendProfileCandidate(
                profile_id=selected_profile.profile_id,
                matched_backend=True,
                matched_version=version is not None,
                matched_hardware=hardware is not None,
                selected=True,
                rejection_reason=None,
            )
        )

    confidence = selected_profile.confidence
    if version is None:
        warnings.append(
            f"No backend version specified when resolving '{backend_id}'. "
            f"Selected generic profile '{selected_profile.profile_id}'."
        )
        if confidence == Confidence.EXACT or confidence == Confidence.HIGH:
            confidence = Confidence.MEDIUM

    return ResolvedBackendProfile(
        profile=selected_profile,
        source_type="built_in_registry",
        source_location=f"registry:{selected_profile.profile_id}",
        resolver_id="backend_profile_resolver",
        confidence=confidence,
        warnings=warnings,
        evidence=list(selected_profile.evidence),
        candidates=final_candidates,
    )
