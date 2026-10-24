"""Incident handling.   OWNER: Member 3

  UC05    Handle Device Incident
  UC-OP06 Create Maintenance Ticket (included by UC05)
  UC-OP07 Cancel Reservation (extends UC05) -> reuses Member 1's U4

Flow: student report (Member 1 U7) emits ISSUE_REPORTED -> on_issue_reported() ->
open incident -> operator calls handle_incident() -> device goes to maintenance
-> ticket created -> affected reservations cancelled (+ replacement suggestion).

ISSUE_REPORTED payload (agreed with Member 1):
  {issue_id, target_type: 'vehicle'|'charging_point'|'parking_space', target_id, category, description}
"""
from __future__ import annotations

from ...core.entities import Event
from ...core.todo import todo

OWNER = "Member 3"


def on_issue_reported(event: Event) -> None:
    """Event subscriber: create an Incident (status OPEN), emit INCIDENT_OPENED."""
    todo(OWNER, "UC05", "create incident from ISSUE_REPORTED payload")


def handle_incident(incident_id: str, operator_id: str) -> bool:
    """UC05 (also used by Operator.handle_incident in core entities).
    vehicle -> VehicleStatus.MAINTENANCE ; charging_point -> ChargingPointStatus.OUT_OF_SERVICE
    (if a charging session is running on it, ask Member 2's point_monitor.update_point_status to requeue)."""
    todo(OWNER, "UC05", "move device to maintenance, create ticket, cancel affected reservations")


def create_maintenance_ticket(incident_id: str) -> dict:
    """UC-OP06: ticket for the maintenance team (mock notification)."""
    todo(OWNER, "UC-OP06", "persist ticket {ticket_id, device, priority, status}")


def cancel_affected_reservations(vehicle_id: str, reason: str = "vehicle_maintenance") -> list:
    """UC-OP07: for each live reservation of the vehicle call
    modules.reservation.service.cancel_reservation(rid, reason=reason, by_system=True)
    then notify the student with a replacement vehicle suggestion (same hub, similar battery)."""
    todo(OWNER, "UC-OP07", "call Member 1's cancel_reservation(by_system=True); suggest replacement")


def list_incidents(status: str | None = None) -> list:
    todo(OWNER, "UC05", "list incidents")
