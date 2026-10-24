"""Smart charging prioritization algorithm.   OWNER: Member 2   (UC-CH-09)

THE core algorithm of the charging subsystem. Member 3's UC-OP08 (supervise) and
UC-OP09 (manual override) CALL these functions - keep signatures stable and
tell him before changing them.

Suggested priority (tune + justify in the report):
    priority = round(0.6 * (100 - battery_level) + 0.4 * urgency)
    urgency  = 100 if needed_by within 30 min, scaling down to 0 beyond ~4 h.
Tie-break: earlier request time first. Must never assign a point that is
OUT_OF_SERVICE, reserved or occupied.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ...core.entities import ChargingSession
from ...core.todo import todo

OWNER = "Member 2"


def calculate_priority(battery_level: int, needed_by: Optional[datetime], now: Optional[datetime] = None) -> int:
    """Pure function -> easy to unit test (tests/test_charging.py)."""
    todo(OWNER, "UC-CH-09", "implement the priority formula")


def run_prioritization(hub_id: str) -> List[ChargingSession]:
    """Rank QUEUED/SCHEDULED sessions of one hub and assign free points. Returns the new ordering."""
    todo(OWNER, "UC-CH-09", "sort by priority desc, assign to free operational points, emit CHARGING_SCHEDULED")


def get_queue(hub_id: str) -> List[ChargingSession]:
    """Current ordered queue (used by Member 3's operator charging view, UC-OP08)."""
    todo(OWNER, "UC-CH-09", "return sessions ordered by priority")


def apply_manual_override(hub_id: str, session_id: str, operator_id: str, reason: str = "") -> ChargingSession:
    """Called by Member 3 (UC-OP09): force this session to the front/next free point, log who/why."""
    todo(OWNER, "UC-CH-09 / UC-OP09", "bypass ranking for one session; emit CHARGING_OVERRIDE")
