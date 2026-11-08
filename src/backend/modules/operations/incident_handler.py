"""Incident handling.   OWNER: Member 3

  UC05    Handle Device Incident
  UC-OP06 Create Maintenance Ticket (included by UC05)
  UC-OP07 Cancel Reservation (extends UC05) -> reuses Member 1's U4

Flow: student report (Member 1 U7) emits ISSUE_REPORTED -> on_issue_reported() ->
open incident -> operator calls handle_incident() -> device goes to maintenance
-> ticket created -> affected reservations cancelled (+ replacement suggestion).
A charger that reports OUT_OF_SERVICE by itself (device signal) opens an incident too.

ISSUE_REPORTED payload (agreed with Member 1):
  {issue_id, target_type: 'vehicle'|'charging_point'|'parking_space', target_id, category, description}
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException

from ...core.entities import Event, new_id
from ...core.enums import (ChargingPointStatus, EventType, ReservationKind, ReservationStatus,
                           Severity, VehicleStatus)
from ...core.event_bus import bus
from ...core.logger import get_logger
from ...core.state_manager import HubNotFound, VehicleNotFound, network
from . import service, store as ops_store
from .models import PRIORITIES, AlertType, IncidentStatus, TicketStatus

OWNER = "Member 3"
log = get_logger("operations.incidents")
TARGET_TYPES = ("vehicle", "charging_point", "parking_space")
_CANCELLABLE = (ReservationStatus.PENDING, ReservationStatus.CONFIRMED)


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def _locate(target_type: str, target_id: str) -> Optional[str]:
    """hub_id of the device, or None if the device does not exist."""
    if target_type == "vehicle":
        v = network.vehicles.get(target_id)
        return (v.hub_id or "") if v else None
    for hub in network.list_hubs():
        if target_type == "charging_point" and target_id in hub.charging_points:
            return hub.hub_id
        if target_type == "parking_space" and target_id in hub.parking_spaces:
            return hub.hub_id
    return None


def _active_for(target_type: str, target_id: str) -> Optional[dict]:
    return next((i for i in ops_store.current().incidents.values()
                 if i["target_type"] == target_type and i["target_id"] == target_id
                 and i["status"] != IncidentStatus.RESOLVED.value), None)


def get_incident(incident_id: str) -> dict:
    incident = ops_store.current().incidents.get(incident_id)
    if incident is None:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return incident


def _open_incident(source: str, target_type: str, target_id: str, hub_id: Optional[str], category: str,
                   description: str, issue_id: Optional[str] = None,
                   severity: Severity = Severity.WARNING) -> Optional[dict]:
    """Create an OPEN incident (or attach the report to the one already open for the device)."""
    with network.lock:
        existing = _active_for(target_type, target_id)
        if existing:
            if issue_id and issue_id not in existing["issue_ids"]:
                existing["issue_ids"].append(issue_id)
                existing["report_count"] += 1
            return None
        incident = {"incident_id": new_id("INC"), "source": source, "issue_ids": [issue_id] if issue_id else [],
                    "report_count": 1, "hub_id": hub_id, "target_type": target_type, "target_id": target_id,
                    "category": category or "other", "description": description or "",
                    "status": IncidentStatus.OPEN.value, "priority": "medium", "note": "",
                    "severity": severity.value, "created_at": ops_store.now_iso(), "handled_by": None,
                    "handled_at": None, "resolved_at": None, "ticket_id": None, "previous_status": None,
                    "cancelled_reservations": []}
        ops_store.current().incidents[incident["incident_id"]] = incident
        service.raise_alert(f"{AlertType.INCIDENT.value}:{incident['incident_id']}", AlertType.INCIDENT, severity,
                            hub_id, f"{target_type.replace('_', ' ').title()} {target_id}: {category or 'fault'} reported",
                            description or "A fault was reported for this device.",
                            ["Open the incident and move the device to maintenance"], target_id, emit=False)
    bus.emit(EventType.INCIDENT_OPENED, hub_id=hub_id, severity=severity, incident_id=incident["incident_id"],
             target_type=target_type, target_id=target_id, message=f"Incident on {target_id}")
    return incident


def seed_demo_incidents() -> None:
    """Seed repeatable demo incidents using the current operations store schema."""
    if ops_store.current().incidents:
        return
    examples = [
        ("vehicle", "V-002", "brake_failure", Severity.CRITICAL, "brake"),
        ("vehicle", "V-007", "battery_danger", Severity.WARNING, "lowBattery"),
        ("vehicle", "V-014", "flat_tire", Severity.INFO, "flatTire"),
    ]
    for target_type, target_id, category, severity, demo_case in examples:
        hub_id = _locate(target_type, target_id)
        if not hub_id:
            continue
        incident = _open_incident("demo", target_type, target_id, hub_id, category,
                                  "", severity=severity)
        if incident:
            incident["demo"] = True
            incident["demo_case"] = demo_case


# --------------------------------------------------------------------------- #
# event subscribers                                                           #
# --------------------------------------------------------------------------- #
def on_issue_reported(event: Event) -> None:
    """Event subscriber: create an Incident (status OPEN), emit INCIDENT_OPENED."""
    p = event.payload or {}
    target_type, target_id = p.get("target_type"), p.get("target_id")
    if target_type not in TARGET_TYPES or not target_id:
        log.warning("ISSUE_REPORTED ignored: bad payload %s", p)
        return
    hub_id = _locate(target_type, target_id)
    if hub_id is None:
        log.warning("ISSUE_REPORTED ignored: unknown %s %s", target_type, target_id)
        return
    _open_incident("student_report", target_type, target_id, hub_id or event.hub_id, p.get("category", ""),
                   p.get("description", ""), issue_id=p.get("issue_id"))


def on_charger_status_changed(event: Event) -> None:
    """A charger that went OUT_OF_SERVICE by itself is a device signal (UC05 precondition)."""
    p = event.payload or {}
    if p.get("new_status") != ChargingPointStatus.OUT_OF_SERVICE.value:
        return
    point_id = p.get("point_id")
    if not point_id or _locate("charging_point", point_id) is None:
        return
    _open_incident("device_signal", "charging_point", point_id, event.hub_id, "charger_fault",
                   "The charging port reported a fault.")


def auto_resolve_recovered() -> None:
    """Device-signal incidents close by themselves when the charger recovers before anyone handled it."""
    with network.lock:
        for inc in ops_store.current().incidents.values():
            if (inc["status"] == IncidentStatus.OPEN.value and inc["source"] == "device_signal"
                    and inc["target_type"] == "charging_point"):
                hub = network.hubs.get(inc["hub_id"])
                point = hub.charging_points.get(inc["target_id"]) if hub else None
                if point is not None and point.status != ChargingPointStatus.OUT_OF_SERVICE:
                    _finish(inc, "system", "Device recovered on its own")


def _finish(incident: dict, operator_id: str, note: str) -> None:
    incident.update(status=IncidentStatus.RESOLVED.value, resolved_at=ops_store.now_iso())
    if note:
        incident["note"] = (incident["note"] + " | " if incident["note"] else "") + note
    service.close_alerts_for(f"{AlertType.INCIDENT.value}:{incident['incident_id']}")
    ops_store.log_audit("incident_resolved", operator_id, incident_id=incident["incident_id"])


# --------------------------------------------------------------------------- #
# UC05 / UC-OP06 / UC-OP07                                                    #
# --------------------------------------------------------------------------- #
def _live_reservations(vehicle_id: str) -> list:
    return [r for r in network.reservations.values()
            if r.kind == ReservationKind.VEHICLE and r.resource_id == vehicle_id and r.status in _CANCELLABLE]


def get_incident_impact(incident_id: str) -> dict:
    """UC05 alt 5a: what moving this device to maintenance would disturb (shown before the Operator confirms)."""
    with network.lock:
        inc = get_incident(incident_id)
        impact = {"incident_id": incident_id, "target_type": inc["target_type"], "target_id": inc["target_id"],
                  "device_status": None, "affected_reservations": [], "blocked_reason": None,
                  "requires_confirmation": False}
        if inc["target_type"] == "vehicle":
            v = network.vehicles.get(inc["target_id"])
            if v is None:
                raise HTTPException(404, f"Vehicle {inc['target_id']} not found")
            impact["device_status"] = v.status.value
            if v.status == VehicleStatus.IN_USE:
                impact["blocked_reason"] = "Vehicle is in use by a student; wait until it is returned."
            impact["affected_reservations"] = [{"reservation_id": r.reservation_id, "user_id": r.user_id}
                                               for r in _live_reservations(v.vehicle_id)]
        elif inc["target_type"] == "charging_point":
            hub = network.hubs.get(inc["hub_id"])
            point = hub.charging_points.get(inc["target_id"]) if hub else None
            if point is None:
                raise HTTPException(404, f"Charging point {inc['target_id']} not found")
            impact["device_status"] = point.status.value
        impact["requires_confirmation"] = bool(impact["affected_reservations"])
        return impact


def create_maintenance_ticket(incident_id: str, priority: Optional[str] = None, note: Optional[str] = None) -> dict:
    """UC-OP06: ticket for the maintenance team (mock notification). Idempotent per incident."""
    with network.lock:
        inc = get_incident(incident_id)
        if inc["ticket_id"]:
            return ops_store.current().tickets[inc["ticket_id"]]
        ticket = {"ticket_id": new_id("TK"), "incident_id": incident_id, "device_type": inc["target_type"],
                  "device": inc["target_id"], "hub_id": inc["hub_id"], "category": inc["category"],
                  "priority": priority or inc["priority"], "note": note if note is not None else inc["note"],
                  "status": TicketStatus.OPEN.value, "team": "hardware", "created_at": ops_store.now_iso()}
        ops_store.current().tickets[ticket["ticket_id"]] = ticket
        inc["ticket_id"] = ticket["ticket_id"]
        ops_store.notify("maintenance_team", "ticket_created", ticket_id=ticket["ticket_id"],
                         device=ticket["device"], priority=ticket["priority"])
        return ticket


def _suggest_replacement(vehicle) -> Optional[dict]:
    """Same hub, shared, AVAILABLE, same type first, closest battery level."""
    pool = [v for v in network.vehicles_at(vehicle.hub_id) if v.vehicle_id != vehicle.vehicle_id
            and v.is_shared and v.status == VehicleStatus.AVAILABLE and v.battery_level >= 20]
    if not pool:
        return None
    best = min(pool, key=lambda v: (v.vehicle_type != vehicle.vehicle_type,
                                    abs(v.battery_level - vehicle.battery_level), v.vehicle_id))
    return {"vehicle_id": best.vehicle_id, "model": best.model, "vehicle_type": best.vehicle_type,
            "battery_level": best.battery_level, "hub_id": best.hub_id}


def cancel_affected_reservations(vehicle_id: str, reason: str = "vehicle_maintenance") -> list:
    """UC-OP07: for each live reservation of the vehicle call
    modules.reservation.service.cancel_reservation(rid, reason=reason, by_system=True)
    then notify the student with a replacement vehicle suggestion (same hub, similar battery)."""
    from ..reservation import service as reservation_service
    results = []
    with network.lock:
        vehicle = network.get_vehicle(vehicle_id)
        for res in _live_reservations(vehicle_id):
            reservation_service.cancel_reservation(res.reservation_id, reason=reason, by_system=True)
            replacement = _suggest_replacement(vehicle)
            message = (f"Sorry - vehicle {vehicle_id} needs maintenance and your reservation was cancelled "
                       f"(deposit refunded)." + (f" Suggested replacement: {replacement['vehicle_id']} "
                                                 f"({replacement['battery_level']}%)." if replacement else ""))
            ops_store.notify(res.user_id, "reservation_cancelled_by_system", reservation_id=res.reservation_id,
                             vehicle_id=vehicle_id, replacement=replacement, message=message)
            try:                                      # also reach the student through the existing notification feed
                from ..charging.repository import repository as charging_repo
                charging_repo.notify(res.user_id, "reservation_cancelled_by_system",
                                     reservation_id=res.reservation_id, replacement=replacement)
            except Exception:  # noqa: BLE001 - never block maintenance because of a notification
                log.exception("could not push student notification")
            results.append({"reservation_id": res.reservation_id, "user_id": res.user_id,
                            "replacement": replacement})
    return results


def handle_incident_detailed(incident_id: str, operator_id: str, note: str = "", priority: str = "medium",
                             confirm_cancel: bool = False) -> dict:
    """UC05 main flow + alt 5a. Returns {handled, incident, ticket, cancelled_reservations}."""
    if priority not in PRIORITIES:
        raise HTTPException(400, f"priority must be one of {', '.join(PRIORITIES)}")
    with network.lock:
        inc = get_incident(incident_id)
        if inc["status"] != IncidentStatus.OPEN.value:
            raise HTTPException(409, f"Incident is already {inc['status']}")
        impact = get_incident_impact(incident_id)
        if impact["blocked_reason"]:
            raise HTTPException(409, impact["blocked_reason"])
        if impact["requires_confirmation"] and not confirm_cancel:
            raise HTTPException(409, "Vehicle is reserved. Moving it to maintenance will cancel the trip - "
                                     "confirm to continue.")
        reason = note.strip() or f"Incident {incident_id}: {inc['category']}"
        cancelled: list = []
        if inc["target_type"] == "vehicle":
            vehicle = network.get_vehicle(inc["target_id"])
            inc["previous_status"] = vehicle.status.value
            cancelled = cancel_affected_reservations(vehicle.vehicle_id)
            vehicle.update_status(VehicleStatus.MAINTENANCE)
        elif inc["target_type"] == "charging_point":
            from ..charging import point_monitor
            point = network.hubs[inc["hub_id"]].charging_points[inc["target_id"]]
            inc["previous_status"] = point.status.value
            inc["status"] = IncidentStatus.IN_MAINTENANCE.value   # set first: de-duplicates the CHARGER event
            try:
                point_monitor.update_point_status(point.point_id, ChargingPointStatus.OUT_OF_SERVICE, operator_id, reason)
            except Exception:
                inc["status"] = IncidentStatus.OPEN.value          # nothing changed -> stay open
                raise
        # parking_space: the entity has no status field -> only the ticket is created (cordon it off physically)
        inc.update(status=IncidentStatus.IN_MAINTENANCE.value, priority=priority, note=note.strip(),
                   handled_by=operator_id, handled_at=ops_store.now_iso(),
                   cancelled_reservations=[c["reservation_id"] for c in cancelled])
        ticket = create_maintenance_ticket(incident_id, priority, note.strip())
        service.close_alerts_for(f"{AlertType.INCIDENT.value}:{incident_id}")
        ops_store.log_audit("incident_handled", operator_id, incident_id=incident_id, ticket_id=ticket["ticket_id"],
                            device=inc["target_id"], cancelled=len(cancelled))
    service.scan_for_alerts()
    return {"handled": True, "incident": inc, "ticket": ticket, "cancelled_reservations": cancelled}


def handle_incident(incident_id: str, operator_id: str) -> bool:
    """UC05 (also used by Operator.handle_incident in core entities).
    vehicle -> VehicleStatus.MAINTENANCE ; charging_point -> ChargingPointStatus.OUT_OF_SERVICE
    (if a charging session is running on it, Member 2's point_monitor.update_point_status requeues it)."""
    return handle_incident_detailed(incident_id, operator_id)["handled"]


def resolve_incident(incident_id: str, operator_id: str) -> dict:
    """Repair finished: device back in service, ticket closed (state machine: MAINTENANCE -> AVAILABLE)."""
    with network.lock:
        inc = get_incident(incident_id)
        if inc["status"] != IncidentStatus.IN_MAINTENANCE.value:
            raise HTTPException(409, "Only an incident that is in maintenance can be resolved")
        if inc["target_type"] == "vehicle":
            v = network.get_vehicle(inc["target_id"])
            if v.status == VehicleStatus.MAINTENANCE:
                v.update_status(VehicleStatus.AVAILABLE)
        elif inc["target_type"] == "charging_point":
            from ..charging import point_monitor
            point_monitor.update_point_status(inc["target_id"], ChargingPointStatus.AVAILABLE, operator_id,
                                              f"Repair completed ({incident_id})")
        ticket = ops_store.current().tickets.get(inc["ticket_id"] or "")
        if ticket:
            ticket["status"] = TicketStatus.CLOSED.value
        _finish(inc, operator_id, "")
    service.scan_for_alerts()
    return inc


def list_incidents(status: Optional[str] = None) -> list:
    """status: None/'all' | 'active' (not resolved) | open | in_maintenance | resolved."""
    if status not in (None, "", "all", "active") and status not in IncidentStatus._value2member_map_:
        raise HTTPException(400, f"Unknown incident status '{status}'")
    rows = list(ops_store.current().incidents.values())
    if status == "active":
        rows = [i for i in rows if i["status"] != IncidentStatus.RESOLVED.value]
    elif status in IncidentStatus._value2member_map_:
        rows = [i for i in rows if i["status"] == status]
    tickets = ops_store.current().tickets
    out = [{**i, "ticket": tickets.get(i["ticket_id"] or "")} for i in rows]
    return sorted(out, key=lambda i: i["created_at"], reverse=True)


def list_tickets() -> list:
    return sorted(ops_store.current().tickets.values(), key=lambda t: t["created_at"], reverse=True)
