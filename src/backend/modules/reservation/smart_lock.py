"""U9 Control Smart Lock - MOCK of the IoT lock actuator.   OWNER: Member 1

Simulates IoT actuator communication to unlock and lock vehicles at docks,
with state tracking and simulated hardware jams / communication errors.
"""
from __future__ import annotations

from typing import Dict


class SmartLockError(Exception):
    """Raised when hardware actuator fails to engage or disengage."""
    pass


_lock_states: Dict[str, str] = {}  # vehicle_id -> "locked" | "unlocked"
_failed_vehicles: set[str] = {"FAIL_LOCK", "vehicle_fail_lock"}
_force_failure: bool = False


def reset_locks() -> None:
    """Helper for testing: reset lock status and failure flags."""
    global _force_failure
    _lock_states.clear()
    _force_failure = False


def set_force_failure(enable: bool) -> None:
    """Toggle simulated smart lock failure for exception flow demo."""
    global _force_failure
    _force_failure = enable


def get_lock_status(vehicle_id: str) -> str:
    return _lock_states.get(vehicle_id, "locked")


def unlock(vehicle_id: str) -> bool:
    """Send unlock command; mock may fail to demo the exception flow."""
    if _force_failure or vehicle_id in _failed_vehicles or vehicle_id.endswith("_fail_lock"):
        return False

    _lock_states[vehicle_id] = "unlocked"
    return True


def lock(vehicle_id: str) -> bool:
    """Mock lock + verify docked sensor state."""
    if _force_failure or vehicle_id in _failed_vehicles or vehicle_id.endswith("_fail_lock"):
        return False

    _lock_states[vehicle_id] = "locked"
    return True
