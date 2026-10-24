"""U9 Control Smart Lock - MOCK of the IoT lock actuator.   OWNER: Member 1"""
from ...core.todo import todo

OWNER = "Member 1"


def unlock(vehicle_id: str) -> bool:
    """Send unlock command; mock may randomly fail to demo the exception flow."""
    todo(OWNER, "U9", "mock unlock + sensor confirmation")


def lock(vehicle_id: str) -> bool:
    todo(OWNER, "U9", "mock lock + verify docked sensor state")
