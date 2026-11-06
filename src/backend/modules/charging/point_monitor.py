"""UC-CH-07/08 monitoring and manual status changes (not incident dispatch)."""
from __future__ import annotations

from typing import List, Optional
from fastapi import HTTPException

from ...core.enums import ChargingPointStatus, ChargingSessionStatus, EventType, VehicleStatus
from ...core.event_bus import bus
from .repository import repository


def requeue_affected(point):
    affected = []
    for session in repository.sessions(point.hub_id, active=True):
        if session.point_id != point.point_id:
            continue
        session.status = ChargingSessionStatus.QUEUED
        session.point_id = session.start_time = session.end_time = None
        if hasattr(session, "point_unavailable"):
            session.point_unavailable = True
        vehicle = repository.network.get_vehicle(session.vehicle_id)
        if vehicle.status == VehicleStatus.CHARGING:
            vehicle.status = VehicleStatus.AVAILABLE
        booking = repository.booking_for(session)
        if booking:
            booking.point_unavailable = True
        repository.notify(session.requested_by, "charging_point_unavailable", session_id=session.session_id)
        affected.append(session.session_id)
    point.current_session_id = None
    return affected


def get_points_status(hub_id: Optional[str] = None) -> List[dict]:
    from .service import session_view
    with repository.network.lock:
        hubs = [repository.network.get_hub(hub_id)] if hub_id else repository.network.list_hubs()
        result = []
        for hub in hubs:
            points = list(hub.charging_points.values())
            free = sum(p.status == ChargingPointStatus.AVAILABLE and
                       not repository.freshness("charging_point", p.point_id)["outdated"]
                       for p in points)
            queue = sum(s.status == ChargingSessionStatus.QUEUED for s in repository.sessions(hub.hub_id))
            utilization = sum(p.status in {ChargingPointStatus.RESERVED, ChargingPointStatus.OCCUPIED}
                              for p in points) / (len(points) or 1)
            for point in points:
                session = repository.network.charging_sessions.get(point.current_session_id)
                view = session_view(session) if session else None
                fresh = repository.freshness("charging_point", point.point_id)
                result.append({"point_id": point.point_id, "hub_id": hub.hub_id,
                    "status": point.status, "power_rating": point.power_rating,
                    "current_session_id": point.current_session_id,
                    "vehicle_id": session.vehicle_id if session else None,
                    "battery_level": view["battery_level"] if view else None,
                    "battery_data_outdated": view["battery_data_outdated"] if view else False,
                    "estimated_completion": view["estimated_completion"] if view else None,
                    "queue_length": queue, "hub_free_points": free,
                    "hub_utilization": round(utilization, 3), "hub_near_capacity": utilization >= .85,
                    "data_outdated": fresh["outdated"], "last_update": fresh["last_update"],
                    "age_seconds": fresh["age_seconds"]})
        return result


def preview_point_status(point_id, status):
    with repository.network.lock:
        point = repository.point(point_id)
        if status not in {ChargingPointStatus.AVAILABLE, ChargingPointStatus.OUT_OF_SERVICE}:
            raise HTTPException(400, "Manual changes only allow Available or Out of Service")
        if status == ChargingPointStatus.AVAILABLE and point.status == ChargingPointStatus.OCCUPIED:
            raise HTTPException(409, "Cannot mark an occupied point Available")
        affected = [s for s in repository.sessions(point.hub_id, active=True) if s.point_id == point_id]
        if status == ChargingPointStatus.AVAILABLE and point.current_session_id and affected:
            raise HTTPException(409, "Cancel or complete the current allocation before marking its point Available")
        return {"point_id": point_id, "old_status": point.status, "new_status": status,
                "affected_session_ids": [s.session_id for s in affected],
                "affected_reservations": sum(repository.booking_for(s) is not None for s in affected),
                "ongoing_sessions": sum(s.status == ChargingSessionStatus.CHARGING for s in affected)}


def update_point_status(point_id: str, status: ChargingPointStatus, operator_id: str, reason: str = "") -> dict:
    with repository.network.lock:
        repository.operator(operator_id)
        if not reason.strip():
            raise HTTPException(400, "A reason is required")
        try:
            status = ChargingPointStatus(status)
        except ValueError:
            raise HTTPException(400, "Unknown charging point status") from None
        impact = preview_point_status(point_id, status)
        point = repository.point(point_id)
        if point.status == status:
            return {**impact, "changed": False}
        old = point.status
        point.status = status
        affected = requeue_affected(point) if status == ChargingPointStatus.OUT_OF_SERVICE else []
        repository.audit("point_status_changed", operator_id, point_id=point_id,
                         old_status=old, new_status=status, reason=reason)
        # Manual overrides do not forge accepted sensor timestamps.
    bus.emit(EventType.CHARGER_STATUS_CHANGED, hub_id=point.hub_id, point_id=point_id,
             old_status=old.value, new_status=status.value, origin="charging.manual")
    return {**impact, "changed": True, "requeued_session_ids": affected}
