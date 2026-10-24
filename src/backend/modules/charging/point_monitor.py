"""Operator-side charging point monitoring.   OWNER: Member 2

  UC-CH-07 Monitor Charging Point Status
  UC-CH-08 Update Charging Point Status (manual Out-of-Service / Available)

Boundary with Member 3: broken-device INCIDENTS and maintenance dispatch are
Member 3's UC05/UC-OP06. Here the operator only flips a point's status.
"""
from __future__ import annotations

from typing import List, Optional

from ...core.enums import ChargingPointStatus
from ...core.todo import todo

OWNER = "Member 2"


def get_points_status(hub_id: Optional[str] = None) -> List[dict]:
    """Per point: status, vehicle, battery, ETA, queue length; flag hubs near charging capacity."""
    todo(OWNER, "UC-CH-07", "iterate hub.charging_points; join current session + vehicle")


def update_point_status(point_id: str, status: ChargingPointStatus, operator_id: str, reason: str = "") -> dict:
    """If a session is running on a point set OUT_OF_SERVICE -> requeue it (re-run scheduler).
    Emit CHARGER_STATUS_CHANGED."""
    todo(OWNER, "UC-CH-08", "validate transition, update point, requeue affected session, emit event")
