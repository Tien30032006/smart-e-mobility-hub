"""UC-CH-01..06 student workflows. Allocation checks and writes share one lock."""
from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from typing import List, Optional

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from ...core.entities import ChargingPoint, ChargingSession, Reservation, new_id
from ...core.enums import ChargingPointStatus, ChargingSessionStatus, EventType, ReservationKind, ReservationStatus, VehicleStatus
from ...core.event_bus import bus
from .domain import (ACTIVE_SESSIONS, BOOKING_DAYS, QUEUE_LIMIT, ChargingBooking, ChargingRecord,
                     charging_minutes, overlaps, percentage, timestamp)
from .repository import repository


def _assert_no_active(vehicle_id):
    if any(s.vehicle_id == vehicle_id and s.status in ACTIVE_SESSIONS
           for s in repository.network.charging_sessions.values()):
        raise HTTPException(409, "Vehicle already has an active charging request or reservation")


def submit_charging_request(user_id: str, vehicle_id: str, hub_id: str, battery_level: int = None,
                            needed_by: Optional[str] = None, *, target_level=100,
                            continue_outdated=False) -> ChargingSession:
    with repository.network.lock:
        vehicle = repository.student_vehicle(user_id, vehicle_id)
        hub = repository.network.get_hub(hub_id)
        if vehicle.hub_id != hub_id:
            raise HTTPException(400, "Vehicle must be parked at the selected hub")
        if vehicle.status in {VehicleStatus.IN_USE, VehicleStatus.MAINTENANCE, VehicleStatus.OFFLINE}:
            raise HTTPException(409, "Vehicle is unavailable for charging")
        _assert_no_active(vehicle_id)
        if battery_level is not None:
            percentage(battery_level)  # Legacy input is validated, never trusted as telemetry.
        percentage(target_level, "target_level")
        if target_level <= vehicle.battery_level:
            raise HTTPException(400, "Target level must exceed the current battery level")
        now = repository.clock()
        needed = timestamp(needed_by, "needed_by")
        if needed is not None and needed <= now:
            raise HTTPException(400, "needed_by must be in the future")
        if not any(p.is_operational() for p in hub.charging_points.values()):
            raise HTTPException(409, "No operational charging point; choose another hub")
        if sum(s.status == ChargingSessionStatus.QUEUED for s in repository.sessions(hub_id)) >= QUEUE_LIMIT:
            raise HTTPException(409, "Charging queue is full; choose another hub")
        fresh = repository.freshness("vehicle", vehicle_id, now)
        if fresh["outdated"] and not continue_outdated:
            raise HTTPException(409, jsonable_encoder({"code": "outdated_data", "items": [fresh],
                                      "message": "Confirm use of the last known battery level or cancel"}))
        session = ChargingRecord(new_id("CS"), vehicle_id, hub_id=hub_id, requested_by=user_id,
            needed_by=needed, created_at=now, target_level=target_level,
            battery_level_used=vehicle.battery_level, battery_updated_at=fresh["last_update"],
            battery_unconfirmed=fresh["outdated"])
        repository.network.charging_sessions[session.session_id] = session
    bus.emit(EventType.CHARGING_REQUESTED, hub_id=hub_id, session_id=session.session_id, vehicle_id=vehicle_id)
    return session


def list_available_points(hub_id: str, start_time=None, end_time=None) -> List[ChargingPoint]:
    with repository.network.lock:
        hub = repository.network.get_hub(hub_id)
        now = repository.clock()
        if (start_time is None) != (end_time is None):
            raise HTTPException(400, "Both start_time and end_time are required")
        start, end = timestamp(start_time) or now, timestamp(end_time) or now + timedelta(minutes=1)
        if start >= end:
            raise HTTPException(400, "End time must be after start time")
        return [p for p in hub.charging_points.values() if repository.can_book(p, start, end, now)]


def schedule_charging_session(user_id: str, hub_id: str, vehicle_id: Optional[str] = None,
                              point_id: Optional[str] = None, start_time=None, end_time=None,
                              *, target_level=100) -> Reservation:
    with repository.network.lock:
        vehicle = repository.student_vehicle(user_id, vehicle_id)
        repository.network.get_hub(hub_id)
        start, end, now = timestamp(start_time), timestamp(end_time), repository.clock()
        if start is None or end is None or start <= now or end <= start:
            raise HTTPException(400, "Choose a future start time and a later end time")
        if end > now + timedelta(days=BOOKING_DAYS):
            raise HTTPException(400, f"Reservations must end within {BOOKING_DAYS} days")
        percentage(target_level, "target_level")
        if target_level <= vehicle.battery_level:
            raise HTTPException(400, "Target level must exceed the current battery level")
        _assert_no_active(vehicle.vehicle_id)
        points = list_available_points(hub_id, start, end)
        if point_id is not None:
            point = repository.point(point_id)
            if point.hub_id != hub_id:
                raise HTTPException(400, "Point does not belong to the selected hub")
            points = [p for p in points if p.point_id == point_id]
        if not points:
            from .availability import nearby_windows
            raise HTTPException(409, jsonable_encoder({"code": "slot_conflict",
                "message": "Selected time window is unavailable; choose a nearby alternative",
                "alternatives": nearby_windows(hub_id, start, end)}))
        point = points[0]
        fresh = repository.freshness("vehicle", vehicle.vehicle_id)
        session = ChargingRecord(new_id("CS"), vehicle.vehicle_id, point_id=point.point_id,
            hub_id=hub_id, start_time=start, end_time=end, needed_by=end,
            status=ChargingSessionStatus.SCHEDULED, requested_by=user_id, created_at=now,
            target_level=target_level, battery_level_used=vehicle.battery_level,
            battery_updated_at=fresh["last_update"], battery_unconfirmed=fresh["outdated"])
        booking = ChargingBooking(new_id("CR"), ReservationKind.CHARGING, user_id, hub_id,
            point.point_id, start_time=start, end_time=end, status=ReservationStatus.CONFIRMED,
            session_id=session.session_id, vehicle_id=vehicle.vehicle_id)
        session.reservation_id = booking.reservation_id
        repository.network.charging_sessions[session.session_id] = session
        repository.network.reservations[booking.reservation_id] = booking
    bus.emit(EventType.CHARGING_SCHEDULED, hub_id=hub_id, session_id=session.session_id,
             vehicle_id=vehicle.vehicle_id)
    return booking


def get_smart_suggestion(user_id: str, vehicle_id: str, needed_by: Optional[str] = None,
                         *, continue_outdated=False) -> dict:
    with repository.network.lock:
        vehicle = repository.student_vehicle(user_id, vehicle_id)
        now = repository.clock()
        deadline = timestamp(needed_by, "needed_by") or now + timedelta(hours=4)
        if deadline <= now or deadline > now + timedelta(days=BOOKING_DAYS):
            raise HTTPException(400, "needed_by must be in the future and within the booking period")
        candidates = []
        for hub in repository.network.hubs.values():
            for point in hub.charging_points.values():
                if not point.is_operational():
                    continue
                duration = timedelta(minutes=charging_minutes(vehicle.battery_level, 100, point.power_rating))
                start = now + timedelta(minutes=1)
                for a, b in sorted(repository.intervals(point.point_id, now)):
                    if overlaps(start, start + duration, a, b):
                        start = b
                end = start + duration
                if end <= deadline and repository.can_book(point, start, end, now):
                    items = [repository.freshness("vehicle", vehicle_id),
                             repository.freshness("charging_point", point.point_id)]
                    candidates.append({"hub_id": hub.hub_id, "point_id": point.point_id,
                        "start_time": start, "end_time": end,
                        "waiting_minutes": round((start - now).total_seconds() / 60, 1),
                        "reason": "earliest_completion", "outdated_items": [i for i in items if i["outdated"]]})
        candidates.sort(key=lambda c: (c["end_time"], c["start_time"], c["point_id"]))
        suggestions = candidates[:3]
        outdated = [item for c in suggestions for item in c["outdated_items"]]
        if outdated and not continue_outdated:
            return {"status": "awaiting_decision", "outdated_items": outdated, "suggestions": []}
        return {"status": "suggested" if suggestions else "no_feasible_suggestion",
                "suggestions": suggestions, "outdated_items": outdated,
                **({k: v for k, v in suggestions[0].items()} if suggestions else {})}


def release_point(session):
    if not session.point_id:
        return
    point = repository.point(session.point_id)
    if point.current_session_id == session.session_id:
        point.current_session_id = None
        if point.status != ChargingPointStatus.OUT_OF_SERVICE:
            point.status = ChargingPointStatus.AVAILABLE


def promote_queue(hub_id):
    from .scheduler import run_prioritization
    if not repository.outdated_items(hub_id):
        run_prioritization(hub_id)


def cancel_charging_reservation(user_id: str, reservation_or_session_id: str) -> dict:
    with repository.network.lock:
        session = repository.network.charging_sessions.get(reservation_or_session_id)
        booking = repository.network.reservations.get(reservation_or_session_id)
        if booking and booking.kind != ReservationKind.CHARGING:
            raise HTTPException(404, "Charging booking not found")
        if session is None and booking:
            session = repository.network.charging_sessions.get(getattr(booking, "session_id", ""))
        if session is None:
            raise HTTPException(404, "Charging booking not found")
        if session.requested_by != user_id:
            raise HTTPException(403, "Booking belongs to another user")
        booking = repository.booking_for(session)
        if session.status == ChargingSessionStatus.CANCELLED:
            return {"status": "cancelled", "session_id": session.session_id, "already_cancelled": True}
        if session.status not in {ChargingSessionStatus.QUEUED, ChargingSessionStatus.SCHEDULED}:
            raise HTTPException(409, "Charging has already started or completed")
        release_point(session)
        session.status = ChargingSessionStatus.CANCELLED
        if booking:
            booking.status = ReservationStatus.CANCELLED
        if session.hub_id:
            promote_queue(session.hub_id)
        return {"status": "cancelled", "session_id": session.session_id}


def session_view(session):
    vehicle = repository.network.get_vehicle(session.vehicle_id)
    fresh = repository.freshness("vehicle", vehicle.vehicle_id)
    from .scheduler import get_queue
    queue = [s for s in get_queue(session.hub_id) if s.status == ChargingSessionStatus.QUEUED]
    point = repository.point(session.point_id) if session.point_id else None
    booking = repository.booking_for(session)
    minutes = charging_minutes(vehicle.battery_level, getattr(session, "target_level", 100),
                                point.power_rating if point else 3.3)
    now = repository.clock()
    battery_score = round(.6 * (100-vehicle.battery_level), 1)
    needed_minutes = (session.needed_by-now).total_seconds()/60 if session.needed_by else 240
    urgency_score = round(.4 * max(0, min(100, (240-needed_minutes)/210*100)), 1)
    live_priority = next((s.priority for s in get_queue(session.hub_id) if s.session_id == session.session_id), session.priority)
    return {**asdict(session), "priority": live_priority,
            "priority_breakdown": {"battery_points": battery_score, "urgency_points": urgency_score,
                "waiting_minutes": round(max(0, (now-getattr(session, "created_at", now)).total_seconds()/60), 1),
                "criteria": repository.store.hub_criteria.get(session.hub_id, ["battery_level", "needed_by"])},
            "reservation_id": booking.reservation_id if booking else None,
            "reservation_status": booking.status if booking else None,
            "battery_level": vehicle.battery_level, "battery_last_update": fresh["last_update"],
            "battery_data_outdated": fresh["outdated"], "battery_age_seconds": fresh["age_seconds"],
            "queue_position": next((i + 1 for i, s in enumerate(queue) if s.session_id == session.session_id), None),
            "estimated_minutes": minutes,
            "estimated_completion": (session.end_time if session.status == ChargingSessionStatus.SCHEDULED
                else repository.clock() + timedelta(minutes=minutes)
                if session.status == ChargingSessionStatus.CHARGING else None),
            "can_cancel": session.status in {ChargingSessionStatus.QUEUED, ChargingSessionStatus.SCHEDULED}}


def get_my_charging_status(user_id: str) -> List[dict]:
    with repository.network.lock:
        return [session_view(s) for s in sorted(repository.sessions(),
            key=lambda s: getattr(s, "created_at", repository.clock()), reverse=True) if s.requested_by == user_id]


def get_my_vehicles(user_id):
    with repository.network.lock:
        return [{**asdict(v), **repository.freshness("vehicle", v.vehicle_id)}
                for v in repository.network.vehicles.values() if v.owner_id == user_id]


def complete_session(session_id):
    with repository.network.lock:
        session = repository.network.charging_sessions.get(session_id)
        if session is None:
            raise HTTPException(404, "Charging session not found")
        if session.status == ChargingSessionStatus.COMPLETED:
            return session
        if session.status != ChargingSessionStatus.CHARGING:
            raise HTTPException(409, "Only a running charging session can complete")
        release_point(session)
        session.status = ChargingSessionStatus.COMPLETED
        session.end_time = repository.clock()
        vehicle = repository.network.get_vehicle(session.vehicle_id)
        if vehicle.status == VehicleStatus.CHARGING:
            vehicle.status = VehicleStatus.AVAILABLE
        booking = repository.booking_for(session)
        if booking:
            booking.status = ReservationStatus.COMPLETED
        repository.notify(session.requested_by, "charging_completed", session_id=session.session_id)
        promote_queue(session.hub_id)
    bus.emit(EventType.CHARGING_COMPLETED, hub_id=session.hub_id,
             session_id=session.session_id, vehicle_id=session.vehicle_id)
    return session
