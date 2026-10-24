"""UC-CH-10 Report Real-time Charging & Battery Data.   OWNER: Member 2

Ingest interface for the Sensor / Simulation System plus a simple built-in
simulator that drifts battery levels (so the demo looks "live" without IoT).

Spec reminder: every source reports each item at least every 30 s and
immediately on a state change.
"""
from __future__ import annotations

from typing import List

from ...core.todo import todo

OWNER = "Member 2"


def ingest_readings(readings: List[dict]) -> int:
    """Each reading: {'kind': 'vehicle'|'charging_point', 'id': str, 'battery_level'?: int, 'status'?: str}.
    Validate, update the entity under network.lock, emit BATTERY_UPDATED / CHARGER_STATUS_CHANGED.
    Return the number accepted."""
    todo(OWNER, "UC-CH-10", "validate + apply readings; reject unknown ids/invalid values")


def start_simulator(interval_seconds: int = 5) -> None:
    """Background thread: +battery for CHARGING vehicles, -battery for IN_USE, complete sessions at 100%."""
    todo(OWNER, "UC-CH-10", "thread that calls ingest_readings(...) every interval")


def stop_simulator() -> None:
    todo(OWNER, "UC-CH-10", "stop the thread")
