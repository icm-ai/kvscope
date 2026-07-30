"""Hardware Memory Budget Engine for KVScope."""

from kvscope.domain.enums import MemoryTopology
from kvscope.domain.hardware import HardwareProfile
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.ranges import (
    ByteRange,
    add_byte_ranges,
    multiply_bytes_by_ratio_range,
)


def estimate_hardware_memory_budget(
    profile: HardwareProfile,
    *,
    total_memory_override_bytes: int | None = None,
    user_reserve_bytes: int = 0,
    additional_reserves: list[ByteRange] | None = None,
) -> HardwareMemoryBudget:
    """Calculate the hardware memory budget breakdown and allocatable memory ranges.

    This pure computation engine subtracts non-model reserves from physical memory
    and applies recommended headroom ratios to determine allocatable memory bounds.
    """
    if user_reserve_bytes < 0:
        raise ValueError("user_reserve_bytes must be non-negative")

    if total_memory_override_bytes is not None and total_memory_override_bytes <= 0:
        raise ValueError("total_memory_override_bytes must be strictly positive (> 0)")

    physical_total = (
        total_memory_override_bytes
        if total_memory_override_bytes is not None
        else profile.total_memory_bytes
    )

    assumptions: list[str] = []
    warnings: list[str] = list(profile.notes)

    if total_memory_override_bytes is not None:
        assumptions.append(
            f"Physical total memory overridden by user: "
            f"{total_memory_override_bytes} bytes."
        )

    os_res = profile.reserves.os_reserve
    disp_res = profile.reserves.display_reserve
    bg_res = profile.reserves.background_process_reserve
    dev_res = profile.reserves.device_specific_reserve
    usr_res = ByteRange.exact(user_reserve_bytes)

    if user_reserve_bytes > 0:
        assumptions.append(
            f"User explicit reserve of {user_reserve_bytes} bytes applied."
        )

    add_res_list = additional_reserves or []
    if add_res_list:
        assumptions.append(
            f"{len(add_res_list)} additional custom reserve ranges applied."
        )

    total_non_model_reserve = add_byte_ranges(
        os_res, disp_res, bg_res, dev_res, usr_res, *add_res_list
    )

    alloc_lower = max(0, physical_total - total_non_model_reserve.upper_bytes)
    alloc_expected = max(0, physical_total - total_non_model_reserve.expected_bytes)
    alloc_upper = max(0, physical_total - total_non_model_reserve.lower_bytes)

    allocatable_before_headroom = ByteRange(
        lower_bytes=alloc_lower,
        expected_bytes=alloc_expected,
        upper_bytes=alloc_upper,
    )

    recommended_headroom = multiply_bytes_by_ratio_range(
        allocatable_before_headroom, profile.recommended_headroom_ratio
    )

    rec_lower = max(
        0, allocatable_before_headroom.lower_bytes - recommended_headroom.upper_bytes
    )
    rec_expected = max(
        0,
        allocatable_before_headroom.expected_bytes
        - recommended_headroom.expected_bytes,
    )
    rec_upper = max(
        0, allocatable_before_headroom.upper_bytes - recommended_headroom.lower_bytes
    )

    recommended_allocatable = ByteRange(
        lower_bytes=rec_lower,
        expected_bytes=rec_expected,
        upper_bytes=rec_upper,
    )

    if profile.memory_topology == MemoryTopology.UNIFIED:
        warnings.append(
            "Unified memory is shared with the operating system and other processes. "
            "Actual allocatable memory can vary at runtime."
        )

    return HardwareMemoryBudget(
        physical_total_bytes=physical_total,
        os_reserve=os_res,
        display_reserve=disp_res,
        background_process_reserve=bg_res,
        device_specific_reserve=dev_res,
        user_reserve=usr_res,
        total_non_model_reserve=total_non_model_reserve,
        allocatable_before_headroom=allocatable_before_headroom,
        recommended_headroom=recommended_headroom,
        recommended_allocatable=recommended_allocatable,
        memory_topology=profile.memory_topology,
        confidence=profile.confidence,
        assumptions=assumptions,
        warnings=warnings,
    )
