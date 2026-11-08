"""Operator monitoring + alerts.   OWNER: Member 3

  UC01 Monitor Network-wide Status (Dashboard)
  UC02 Manage System Alerts

``network.get_network_status()`` (core) already returns per-hub KPIs; this module
extends it with alerts, charging-point info and map markers instead of editing core.

Alerts are derived from live data by ``scan_for_alerts()`` which is idempotent:
one alert per (type, target) while the condition holds, and an alert whose
condition disappears is closed automatically (RESOLVED_BY_SYSTEM, UC02 alt 7a).
The scan runs after relevant bus events (see ``register_event_handlers``) and
also whenever the dashboard / alert list is read, so the UI is never stale even
if no event fired.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException

from ...core.entities import Event, new_id, utcnow
from ...core.enums import ChargingPointStatus, EventType, Severity, VehicleStatus
from ...core.event_bus import bus
from ...core.logger import get_logger
from ...core.state_manager import network
from . import store as ops_store
from .models import (AUTO_TYPES, LOW_BATTERY, LOW_BATTERY_MIN, LOW_BATTERY_SHARE, LOW_VEHICLES,
                     NEAR_CAPACITY, OPEN_ALERT, ORDER_ACK_MINUTES, AlertStatus, AlertType,
                     OrderStatus, battery_band)

OWNER = "Member 3"
log = get_logger("operations")
_SEVERITY_ORDER = {Severity.CRITICAL.value: 0, Severity.WARNING.value: 1, Severity.INFO.value: 2}


# --------------------------------------------------------------------------- #
# UC01 - dashboard                                                            #
# --------------------------------------------------------------------------- #
def _hub_tone(status: dict, open_alerts: int) -> str:
    """Marker colour: offline (grey) > busy (red) > low stock (amber) > ok."""
    if status["data_connection"] == "lost":
        return "offline"
    if status["free_spaces"] == 0 or status["near_capacity"]:
        return "busy"
    if status["vehicles_available"] <= 2:
        return "low"
    return "ok"


def get_dashboard() -> dict:
    """UC01: network KPIs + per-hub table + map markers + open alerts count."""
    scan_for_alerts()
    with network.lock:
        base = network.get_network_status()
        alerts = [a for a in ops_store.current().alerts.values() if a["status"] in OPEN_ALERT]
        unread = [a for a in alerts if a["status"] == AlertStatus.UNREAD.value]
        per_hub_alerts: dict = {}
        for a in unread:
            per_hub_alerts[a["hub_id"]] = per_hub_alerts.get(a["hub_id"], 0) + 1
        hubs, markers = [], []
        for status in base["hubs"]:
            hub = network.get_hub(status["hub_id"])
            points = list(hub.charging_points.values())
            row = {**status,
                   "occupancy_rate": status["utilization"],
                   "alerts_open": per_hub_alerts.get(hub.hub_id, 0),
                   "charging_points_in_use": sum(p.status in (ChargingPointStatus.OCCUPIED,
                                                              ChargingPointStatus.RESERVED) for p in points)}
            row["tone"] = _hub_tone(status, row["alerts_open"])
            if row["tone"] == "offline":
                row["offline_message"] = f"Data connection lost at Hub {hub.name}"
            hubs.append(row)
            markers.append({"hub_id": hub.hub_id, "name": hub.name, "lat": hub.location.get("lat"),
                            "lng": hub.location.get("lng"), "tone": row["tone"],
                            "vehicles_available": status["vehicles_available"],
                            "free_spaces": status["free_spaces"]})
        totals = {**base["totals"],
                  "alerts_open": len(unread),
                  "alerts_critical": sum(a["severity"] == Severity.CRITICAL.value for a in unread),
                  "incidents_open": sum(i["status"] != "resolved" for i in ops_store.current().incidents.values()),
                  "orders_active": sum(o["status"] in (OrderStatus.PENDING.value, OrderStatus.ASSIGNED.value)
                                       for o in ops_store.current().orders.values()),
                  "hubs_offline": sum(h["tone"] == "offline" for h in hubs)}
        return {"generated_at": base["generated_at"], "totals": totals, "hubs": hubs, "markers": markers,
                "alerts": _sorted(unread)[:5]}


def get_hub_detail(hub_id: str) -> dict:
    """UC01 step 4: drill-down for one hub (vehicles, parking spaces, charging points)."""
    with network.lock:
        hub = network.get_hub(hub_id)            # HubNotFound -> HTTP 404 (app.py handler)
        status = network.get_hub_status(hub_id)
        vehicles = sorted(network.vehicles_at(hub_id), key=lambda v: v.vehicle_id)
        sessions = {s.point_id: s for s in network.charging_sessions.values() if s.point_id}
        points = []
        for p in sorted(hub.charging_points.values(), key=lambda p: p.point_id):
            session = network.charging_sessions.get(p.current_session_id) or sessions.get(p.point_id)
            points.append({"point_id": p.point_id, "status": p.status.value, "power_rating": p.power_rating,
                           "current_session_id": p.current_session_id,
                           "vehicle_id": session.vehicle_id if session else None})
        by_band = {"low": 0, "medium": 0, "high": 0}
        for v in vehicles:
            by_band[battery_band(v.battery_level)] += 1
        return {
            **status,
            "occupancy_rate": status["utilization"],
            "tone": _hub_tone(status, 0),
            "vehicles": [{"vehicle_id": v.vehicle_id, "model": v.model, "vehicle_type": v.vehicle_type,
                          "battery_level": v.battery_level, "battery_band": battery_band(v.battery_level),
                          "status": v.status.value, "is_shared": v.is_shared} for v in vehicles],
            "battery_summary": by_band,
            "parking_spaces": [{"space_id": s.space_id, "zone": s.zone, "occupied": s.is_occupied,
                                "vehicle_id": s.vehicle_id, "reserved_by": s.reserved_by}
                               for s in sorted(hub.parking_spaces.values(), key=lambda s: s.space_id)],
            "charging_points": points,
            "alerts": _sorted([a for a in ops_store.current().alerts.values()
                               if a["hub_id"] == hub_id and a["status"] in OPEN_ALERT]),
        }


# --------------------------------------------------------------------------- #
# UC02 - alerts                                                               #
# --------------------------------------------------------------------------- #
def _sorted(alerts: List[dict]) -> List[dict]:
    """Red first, then yellow, then blue; newest first inside a priority."""
    return sorted(alerts, key=lambda a: (_SEVERITY_ORDER.get(a["severity"], 9), _neg(a["created_at"])))


def _neg(iso: str):
    return tuple(-ord(c) for c in iso)    # descending string order without a second sort pass


def _create_alert(key: str, type_: AlertType, severity: Severity, hub_id: Optional[str], message: str,
                  cause: str, actions: List[str], target_id: Optional[str] = None, **extra) -> dict:
    alert = {"alert_id": new_id("AL"), "dedupe_key": key, "type": type_.value, "severity": severity.value,
             "hub_id": hub_id, "target_id": target_id, "message": message, "cause": cause,
             "suggested_actions": actions, "status": AlertStatus.UNREAD.value,
             "created_at": ops_store.now_iso(), "updated_at": ops_store.now_iso(),
             "acknowledged_by": None, "acknowledged_at": None, "resolved_at": None, **extra}
    ops_store.current().alerts[alert["alert_id"]] = alert
    return alert


def raise_alert(key: str, type_: AlertType, severity: Severity, hub_id: Optional[str], message: str,
                cause: str = "", actions: Optional[List[str]] = None, target_id: Optional[str] = None,
                emit: bool = True) -> dict:
    """Create an alert unless an open one with the same key already exists (de-duplication)."""
    with network.lock:
        for a in ops_store.current().alerts.values():
            if a["dedupe_key"] == key and a["status"] in OPEN_ALERT:
                return a
        alert = _create_alert(key, type_, severity, hub_id, message, cause, actions or [], target_id)
    if emit:
        kind = EventType.HUB_NEAR_CAPACITY if type_ == AlertType.HUB_NEAR_CAPACITY else EventType.ALERT_RAISED
        bus.emit(kind, hub_id=hub_id, severity=severity, alert_id=alert["alert_id"], message=message)
    return alert


def _close(alert: dict, status: AlertStatus) -> None:
    alert["status"] = status.value
    alert["updated_at"] = alert["resolved_at"] = ops_store.now_iso()


def close_alerts_for(key: str, by: AlertStatus = AlertStatus.RESOLVED) -> None:
    with network.lock:
        for a in ops_store.current().alerts.values():
            if a["dedupe_key"] == key and a["status"] in OPEN_ALERT:
                _close(a, by)


def _conditions() -> dict:
    """Everything that is abnormal right now: {dedupe_key: kwargs for _create_alert}."""
    active: dict = {}
    now = utcnow()
    for hub in network.list_hubs():
        status = network.get_hub_status(hub.hub_id)
        vehicles = network.vehicles_at(hub.hub_id)
        if status["data_connection"] == "lost":
            active[f"{AlertType.HUB_CONNECTION_LOST.value}:{hub.hub_id}"] = dict(
                type_=AlertType.HUB_CONNECTION_LOST, severity=Severity.CRITICAL, hub_id=hub.hub_id,
                message=f"Data connection lost at Hub {hub.name}",
                cause="No telemetry received from this hub within the allowed time.",
                actions=["Check the hub gateway / network", "Treat the figures shown for this hub as stale"])
            continue      # the numbers of an offline hub are not trustworthy -> no other alerts for it
        if hub.is_near_capacity(NEAR_CAPACITY):
            full = status["free_spaces"] == 0
            active[f"{AlertType.HUB_NEAR_CAPACITY.value}:{hub.hub_id}"] = dict(
                type_=AlertType.HUB_NEAR_CAPACITY, severity=Severity.CRITICAL if full else Severity.WARNING,
                hub_id=hub.hub_id,
                message=(f"Hub {hub.name} is full" if full
                         else f"Hub {hub.name} has only {status['free_spaces']} free parking space(s) left"),
                cause=f"Occupancy {round(status['utilization'] * 100)}% (threshold {round(NEAR_CAPACITY * 100)}%).",
                actions=["Redistribute vehicles to a hub with free spaces"])
        if status["vehicles_available"] <= LOW_VEHICLES:
            none = status["vehicles_available"] == 0
            active[f"{AlertType.HUB_VEHICLES_LOW.value}:{hub.hub_id}"] = dict(
                type_=AlertType.HUB_VEHICLES_LOW, severity=Severity.CRITICAL if none else Severity.WARNING,
                hub_id=hub.hub_id,
                message=(f"Hub {hub.name} has no available vehicle" if none
                         else f"Hub {hub.name} has only {status['vehicles_available']} available vehicle"),
                cause="Students cannot reserve a vehicle here.",
                actions=["Redistribute vehicles from a hub with a surplus", "Check vehicles in maintenance"])
        shared = [v for v in vehicles if v.is_shared and v.status != VehicleStatus.MAINTENANCE]
        low = [v for v in shared if v.battery_level < LOW_BATTERY]
        if len(low) >= LOW_BATTERY_MIN and len(low) >= math.ceil(LOW_BATTERY_SHARE * len(shared)):
            active[f"{AlertType.HUB_LOW_BATTERY.value}:{hub.hub_id}"] = dict(
                type_=AlertType.HUB_LOW_BATTERY, severity=Severity.WARNING, hub_id=hub.hub_id,
                message=f"{len(low)} of {len(shared)} vehicles at Hub {hub.name} are below {LOW_BATTERY}% battery",
                cause="Most of the fleet at this hub is almost flat.",
                actions=["Check the charging queue", "Force-charge the most urgent vehicle"])
        for point in hub.charging_points.values():
            if point.status == ChargingPointStatus.OUT_OF_SERVICE:
                active[f"{AlertType.CHARGER_OUT_OF_SERVICE.value}:{point.point_id}"] = dict(
                    type_=AlertType.CHARGER_OUT_OF_SERVICE, severity=Severity.WARNING, hub_id=hub.hub_id,
                    target_id=point.point_id, message=f"Charging port {point.point_id} is out of service",
                    cause="The port reported a fault or was switched off.",
                    actions=["Open an incident for the port", "Re-run charging allocation for the hub"])
    for vid in sorted(network.cut_vehicles):
        v = network.vehicles.get(vid)
        active[f"{AlertType.VEHICLE_CONNECTION_LOST.value}:{vid}"] = dict(
            type_=AlertType.VEHICLE_CONNECTION_LOST, severity=Severity.INFO, hub_id=v.hub_id if v else None,
            target_id=vid, message=f"No telemetry from vehicle {vid}",
            cause="The battery level shown is the last known value.", actions=["Wait for the next report"])
    deadline = now - timedelta(minutes=ORDER_ACK_MINUTES)
    for order in ops_store.current().orders.values():
        if order["status"] == OrderStatus.PENDING.value and datetime.fromisoformat(order["created_at"]) < deadline:
            active[f"{AlertType.RELOCATION_UNASSIGNED.value}:{order['order_id']}"] = dict(
                type_=AlertType.RELOCATION_UNASSIGNED, severity=Severity.WARNING, hub_id=order["from_hub"],
                target_id=order["order_id"],
                message=f"Relocation order {order['order_id']} has not been accepted by field staff",
                cause=f"Pending for more than {ORDER_ACK_MINUTES} minutes.",
                actions=["Contact field staff", "Cancel and re-create the order"])
    return active


def scan_for_alerts() -> List[dict]:
    """UC02: derive alerts and auto-close the ones whose condition is gone. Returns open alerts."""
    created: List[dict] = []
    with network.lock:
        # repair incidents of devices that recovered on their own (imported lazily: no import cycle)
        from . import incident_handler
        incident_handler.auto_resolve_recovered()
        active = _conditions()
        alerts = ops_store.current().alerts
        open_by_key = {a["dedupe_key"]: a for a in alerts.values() if a["status"] in OPEN_ALERT}
        for key, spec in active.items():
            if key not in open_by_key:
                created.append(_create_alert(key, **spec))
        for key, alert in open_by_key.items():           # UC02 alt 7a: Auto-resolve
            if AlertType(alert["type"]) in AUTO_TYPES and key not in active:
                _close(alert, AlertStatus.RESOLVED_BY_SYSTEM)
    for alert in created:
        kind = EventType.HUB_NEAR_CAPACITY if alert["type"] == AlertType.HUB_NEAR_CAPACITY.value else EventType.ALERT_RAISED
        bus.emit(kind, hub_id=alert["hub_id"], severity=Severity(alert["severity"]),
                 alert_id=alert["alert_id"], message=alert["message"])
    return [a for a in ops_store.current().alerts.values() if a["status"] in OPEN_ALERT]


def list_alerts(status: Optional[str] = None) -> List[dict]:
    """status: None = all | 'open' = needs attention (UNREAD) | 'handled' = everything else
    | an exact AlertStatus value. Sorted red -> yellow -> blue, newest first."""
    scan_for_alerts()
    rows = list(ops_store.current().alerts.values())
    if status in (None, "", "all"):
        pass
    elif status == "open":
        rows = [a for a in rows if a["status"] == AlertStatus.UNREAD.value]
    elif status == "handled":
        rows = [a for a in rows if a["status"] != AlertStatus.UNREAD.value]
    elif status in {s.value for s in AlertStatus}:
        rows = [a for a in rows if a["status"] == status]
    else:
        raise HTTPException(400, f"Unknown alert status '{status}'")
    return _sorted(rows)


def get_alert(alert_id: str) -> dict:
    alert = ops_store.current().alerts.get(alert_id)
    if alert is None:
        raise HTTPException(404, f"Alert {alert_id} not found")
    return alert


def acknowledge_alert(alert_id: str, operator_id: str) -> dict:
    """UC02 step 7-8: UNREAD -> ACKNOWLEDGED (store who/when). Idempotent for the same state."""
    with network.lock:
        alert = get_alert(alert_id)
        if alert["status"] == AlertStatus.ACKNOWLEDGED.value:
            return alert
        if alert["status"] != AlertStatus.UNREAD.value:
            raise HTTPException(409, f"Alert is already {alert['status']}")
        alert.update(status=AlertStatus.ACKNOWLEDGED.value, acknowledged_by=operator_id,
                     acknowledged_at=ops_store.now_iso(), updated_at=ops_store.now_iso())
        ops_store.log_audit("alert_acknowledged", operator_id, alert_id=alert_id)
        return alert


def resolve_alert(alert_id: str, operator_id: str) -> dict:
    """Operator closes an alert (-> RESOLVED). Auto-derived alerts that are still true come back on the next scan."""
    with network.lock:
        alert = get_alert(alert_id)
        if alert["status"] in (AlertStatus.RESOLVED.value, AlertStatus.RESOLVED_BY_SYSTEM.value):
            raise HTTPException(409, f"Alert is already {alert['status']}")
        _close(alert, AlertStatus.RESOLVED)
        alert["acknowledged_by"] = alert["acknowledged_by"] or operator_id
        ops_store.log_audit("alert_resolved", operator_id, alert_id=alert_id)
        return alert


# --------------------------------------------------------------------------- #
# event wiring                                                                #
# --------------------------------------------------------------------------- #
# Events after which the abnormal-condition picture can have changed.
_RESCAN_ON = (EventType.CHARGER_STATUS_CHANGED, EventType.VEHICLE_PICKED_UP, EventType.VEHICLE_RETURNED,
              EventType.VEHICLE_RESERVED, EventType.PARKING_RESERVED, EventType.RESERVATION_CANCELLED,
              EventType.RELOCATION_ORDER_CREATED)


def _rescan(event: Event) -> None:
    scan_for_alerts()


def _on_charger_changed(event: Event) -> None:
    from . import incident_handler
    incident_handler.on_charger_status_changed(event)
    scan_for_alerts()


def register_event_handlers() -> None:
    """Subscribe to bus events (called once from app startup). Safe to call repeatedly."""
    from . import incident_handler

    def sub(event_type, handler):
        if handler not in bus._handlers[event_type]:        # idempotent
            bus.subscribe(event_type, handler)

    sub(EventType.ISSUE_REPORTED, incident_handler.on_issue_reported)
    sub(EventType.CHARGER_STATUS_CHANGED, _on_charger_changed)
    for et in _RESCAN_ON:
        if et != EventType.CHARGER_STATUS_CHANGED:
            sub(et, _rescan)
