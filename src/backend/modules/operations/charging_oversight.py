"""Operator side of smart charging.   OWNER: Member 3

  UC-OP08 Smart Charging Scheduling and Allocation (supervise)
  UC-OP09 Override Charging Priority (manual override)

THE ALGORITHM IS NOT HERE - it is Member 2's UC-CH-09 in modules/charging/scheduler.py.
This module is the operator workflow around it: view queue + priority scores,
trigger a run, override, show the audit trail. Do not duplicate the scoring logic.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException

from ...core.entities import utcnow
from ...core.enums import ChargingSessionStatus as SS
from ...core.state_manager import network
from . import store as ops_store
from .models import SAFE_BATTERY

OWNER = "Member 3"


def _reason(rank: int, row, vehicle, overridden: bool, free_points: int, ahead: int) -> dict:
    """Transparent 'why is this vehicle charging / waiting' (UC-OP08 step 7). Returned as a code + params so
    the UI can translate it."""
    if overridden:
        return {"code": "override", "params": {}}
    if row.status == SS.CHARGING:
        return {"code": "charging", "params": {"rank": rank, "score": row.priority}}
    if row.status == SS.SCHEDULED:
        return {"code": "scheduled", "params": {"rank": rank, "score": row.priority, "point": row.point_id}}
    if vehicle is not None and vehicle.battery_level >= SAFE_BATTERY and row.needed_by is None:
        return {"code": "battery_full", "params": {"battery": vehicle.battery_level}}
    if free_points == 0:
        return {"code": "no_point", "params": {"ahead": ahead}}
    return {"code": "lower_priority", "params": {"ahead": ahead, "score": row.priority}}


def view_charging_allocation(hub_id: str) -> dict:
    """UC-OP08: queue with priority scores + which point each vehicle got.
    Uses charging.scheduler.get_queue(hub_id)."""
    from ..charging import scheduler
    from ..charging.repository import repository
    with network.lock:
        hub = network.get_hub(hub_id)
        queue = scheduler.get_queue(hub_id)
        manual = repository.store.manual_overrides
        points = list(hub.charging_points.values())
        free_points = sum(p.status.value == "available" for p in points)
        rows: List[dict] = []
        for rank, s in enumerate(queue, start=1):
            vehicle = network.vehicles.get(s.vehicle_id)
            rows.append({
                "rank": rank, "session_id": s.session_id, "vehicle_id": s.vehicle_id,
                "battery_level": vehicle.battery_level if vehicle else None,
                "above_safe_threshold": bool(vehicle and vehicle.battery_level >= SAFE_BATTERY),
                "priority": s.priority, "status": s.status.value, "point_id": s.point_id,
                "needed_by": s.needed_by.isoformat() if s.needed_by else None,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "manual_override": s.session_id in manual,
                "can_override": s.status == SS.QUEUED,
                "reason": _reason(rank, s, vehicle, s.session_id in manual, free_points, rank - 1)})
        return {"hub_id": hub_id, "hub_name": hub.name, "generated_at": utcnow().isoformat(),
                "points_total": len(points), "points_free": free_points,
                "points_out_of_service": sum(p.status.value == "out_of_service" for p in points),
                "queue": rows, "overrides": list_override_audit(hub_id)[:10]}


def run_allocation(hub_id: str, operator_id: str) -> dict:
    """UC-OP08: trigger charging.scheduler.run_prioritization(hub_id).
    If sensor data is outdated Member 2's rule applies (HTTP 409): the Operator must use the proposal flow
    on the Charging Stations page to decide whether to continue."""
    from ..charging import scheduler
    with network.lock:
        network.get_hub(hub_id)
        queue = scheduler.run_prioritization(hub_id)
        ops_store.log_audit("run_allocation", operator_id, hub_id=hub_id, queue_size=len(queue))
    view = view_charging_allocation(hub_id)
    return {"hub_id": hub_id, "ran_at": utcnow().isoformat(), "queue_size": len(queue),
            "scheduled": sum(r["status"] in ("scheduled", "charging") for r in view["queue"]),
            "waiting": sum(r["status"] == "queued" for r in view["queue"]), **view}


def override_priority(hub_id: str, session_id: str, operator_id: str, reason: str) -> dict:
    """UC-OP09: require a reason, call charging.scheduler.apply_manual_override, keep audit log."""
    from ..charging import scheduler
    if not isinstance(reason, str) or not reason.strip():
        raise HTTPException(400, "An override reason is required")
    with network.lock:
        before = next((s for s in scheduler.get_queue(hub_id) if s.session_id == session_id), None)
        session = scheduler.apply_manual_override(hub_id, session_id, operator_id, reason.strip())
        entry = ops_store.log_audit("charging_override", operator_id, hub_id=hub_id, session_id=session_id,
                                    vehicle_id=session.vehicle_id, reason=reason.strip(),
                                    priority_before=before.priority if before else None,
                                    priority_after=session.priority, point_id=session.point_id,
                                    status_after=session.status.value)
        return {"session_id": session_id, "vehicle_id": session.vehicle_id, "status": session.status.value,
                "priority": session.priority, "point_id": session.point_id, "audit_id": entry["audit_id"]}


def list_override_audit(hub_id: Optional[str] = None) -> List[dict]:
    """The operator audit trail (newest first). Overrides + runs + incident / relocation actions."""
    rows = [a for a in ops_store.current().audit.values() if hub_id is None or a.get("hub_id") == hub_id]
    if hub_id is not None:
        rows = [a for a in rows if a["action"] in ("charging_override", "run_allocation")]
    return sorted(rows, key=lambda a: a["timestamp"], reverse=True)
