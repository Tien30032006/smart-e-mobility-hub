"""Read models for the mobile hub choice, slot grid and collision alternatives."""
from datetime import timedelta
from math import hypot

from fastapi import HTTPException

from ...core.enums import ChargingPointStatus, ChargingSessionStatus
from .domain import BOOKING_DAYS, charging_minutes, overlaps, timestamp
from .repository import repository


def _hub_summary(hub, now):
    points = list(hub.charging_points.values())
    sessions = repository.sessions(hub.hub_id, active=True)
    queue = [s for s in sessions if s.status == ChargingSessionStatus.QUEUED]
    free = sum(p.status == ChargingPointStatus.AVAILABLE
               and not repository.freshness("charging_point", p.point_id, now)["outdated"]
               and repository.can_book(p, now, now + timedelta(minutes=1), now) for p in points)
    operational = [p for p in points if p.status != ChargingPointStatus.OUT_OF_SERVICE]
    releases = [max(0, (b - now).total_seconds() / 60)
                for p in operational for a, b in repository.intervals(p.point_id, now)
                if a <= now < b]
    waiting = 0 if free else round(min(releases), 1) if releases else None
    if waiting is not None and queue:
        waiting += round(sum(charging_minutes(repository.network.get_vehicle(s.vehicle_id).battery_level,
            getattr(s, "target_level", 100), 3.3) for s in queue) / max(1, len(operational)), 1)
    return {"hub_id": hub.hub_id, "name": hub.name, "free_points": free,
            "operational_points": len(operational), "queue_length": len(queue),
            "estimated_wait_minutes": waiting,
            "data_outdated": any(repository.freshness("charging_point", p.point_id, now)["outdated"] for p in points)}


def hub_availability(hub_id):
    with repository.network.lock:
        hub = repository.network.get_hub(hub_id)
        now = repository.clock()
        nearby = [other for other in repository.network.hubs.values() if other.hub_id != hub_id]
        nearby.sort(key=lambda other: hypot(other.location["lat"]-hub.location["lat"],
                                            other.location["lng"]-hub.location["lng"]))
        alternatives = [_hub_summary(other, now) for other in nearby]
        return {**_hub_summary(hub, now),
                "alternatives": [other for other in alternatives if other["operational_points"]][:3]}


def slot_grid(hub_id, start_time=None, slot_minutes=30, count=8):
    with repository.network.lock:
        if not 5 <= slot_minutes <= 120 or not 1 <= count <= 48:
            raise HTTPException(400, "Invalid slot duration or slot count")
        hub = repository.network.get_hub(hub_id)
        now = repository.clock()
        start = timestamp(start_time) or now + timedelta(minutes=1)
        if start < now - timedelta(minutes=1) or start + timedelta(minutes=count*slot_minutes) > now + timedelta(days=BOOKING_DAYS):
            raise HTTPException(400, "Slot grid must be within the booking period")
        windows = []
        for i in range(count):
            a = start + timedelta(minutes=i * slot_minutes)
            b = a + timedelta(minutes=slot_minutes)
            windows.append({"start_time": a, "end_time": b, "points": [
                {"point_id": p.point_id, "available": repository.can_book(p, a, b, now),
                 "outdated": repository.freshness("charging_point", p.point_id, now)["outdated"]}
                for p in hub.charging_points.values()]})
        return {"hub_id": hub_id, "point_ids": list(hub.charging_points), "windows": windows}


def nearby_windows(hub_id, start, end):
    """Find up to three nearby alternatives of the requested duration at this hub."""
    now = repository.clock()
    duration = end - start
    choices = []
    for point in repository.network.get_hub(hub_id).charging_points.values():
        if point.status == ChargingPointStatus.OUT_OF_SERVICE:
            continue
        candidate = max(start, now + timedelta(minutes=1))
        for a, b in sorted(repository.intervals(point.point_id, now)):
            if overlaps(candidate, candidate + duration, a, b):
                candidate = b
        if candidate + duration <= now + timedelta(days=BOOKING_DAYS) and repository.can_book(point, candidate, candidate+duration, now):
            choices.append({"hub_id": hub_id, "point_id": point.point_id,
                            "start_time": candidate, "end_time": candidate+duration})
    return sorted(choices, key=lambda c: (c["start_time"], c["point_id"]))[:3]
