"""Student-side charging use cases.   OWNER: Member 2

  UC-CH-01 Submit Charging Request      UC-CH-02 Schedule Charging Session
  UC-CH-03 Select Charging Point        UC-CH-04 Get Smart Charging Suggestion
  UC-CH-05 Cancel Charging Reservation  UC-CH-06 View My Charging Status
(see Charging__Scheduling.docx)

Notes
  * Sessions live in ``network.charging_sessions``; charging reservations in
    ``network.reservations`` with kind=ReservationKind.CHARGING.
  * Only students with has_private_ev (private EV) may request/schedule charging.
  * Always lock: ``with network.lock:`` around "check point free -> assign".
  * Emit CHARGING_REQUESTED / CHARGING_SCHEDULED so Member 3's dashboard reacts.
"""
from __future__ import annotations

from typing import List, Optional

from ...core.entities import ChargingPoint, ChargingSession, Reservation
from ...core.todo import todo

OWNER = "Member 2"


def submit_charging_request(user_id: str, vehicle_id: str, hub_id: str, battery_level: int,
                            needed_by: Optional[str] = None) -> ChargingSession:
    """UC-CH-01: create QUEUED session; priority is computed later by UC-CH-09."""
    todo(OWNER, "UC-CH-01", "validate private EV + hub, create QUEUED ChargingSession, emit CHARGING_REQUESTED")


def list_available_points(hub_id: str, start_time=None, end_time=None) -> List[ChargingPoint]:
    """UC-CH-03: operational, not reserved in the window."""
    todo(OWNER, "UC-CH-03", "filter hub.charging_points by status and overlapping reservations")


def schedule_charging_session(user_id: str, hub_id: str, vehicle_id: Optional[str] = None,
                              point_id: Optional[str] = None, start_time=None, end_time=None) -> Reservation:
    """UC-CH-02 (includes UC-CH-03). Atomic reservation of point + window."""
    todo(OWNER, "UC-CH-02", "lock -> check overlap -> create CHARGING Reservation + SCHEDULED session")


def get_smart_suggestion(user_id: str, vehicle_id: str, needed_by: Optional[str] = None) -> dict:
    """UC-CH-04: best {hub_id, point_id, start_time, end_time} using battery + predicted availability."""
    todo(OWNER, "UC-CH-04", "score candidate (hub, point, window) and return top suggestion(s)")


def cancel_charging_reservation(user_id: str, reservation_or_session_id: str) -> dict:
    """UC-CH-05: free point/time window/queue position."""
    todo(OWNER, "UC-CH-05", "cancel Reservation/Session, free point, re-run scheduler if queue waits")


def get_my_charging_status(user_id: str) -> List[dict]:
    """UC-CH-06: requests, reservations, live progress (point, queue position, battery, ETA)."""
    todo(OWNER, "UC-CH-06", "join sessions + vehicle battery + ETA = (100-battery)/power")
