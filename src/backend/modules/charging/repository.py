"""In-memory adapter: queries, telemetry freshness, notifications and audit records.

Call mutating methods under network.lock. Extra stores are module-owned and are
reset when seed_network replaces the first hub (without patching shared reset).
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
import hashlib
import json

from fastapi import HTTPException

from ...core.entities import Operator, Student, new_id, utcnow
from ...core.enums import ChargingPointStatus, ChargingSessionStatus, ReservationKind, VehicleStatus
from ...core.state_manager import network
from .domain import ACTIVE_RESERVATIONS, ACTIVE_SESSIONS, FRESH_SECONDS, LogResult, UpdateLogEntry, overlaps


class ChargingStore:
    def __init__(self, anchor):
        self.anchor = anchor
        self.log: list[UpdateLogEntry] = []
        self.latest: dict[tuple, UpdateLogEntry] = {}
        self.sources = {"simulator", "demo-sensor", "seed"}
        self.proposals = {}
        self.notifications: list[dict] = []
        self.audit: list[dict] = []
        self.manual_overrides: dict[str, int] = {}
        self.hub_criteria: dict[str, list[str]] = {}
        self.received_events: set[str] = set()

    def append_update(self, entry):
        # Append first: if writing fails, no current value/freshness is changed.
        self.log.append(entry)
        if entry.result == LogResult.ACCEPTED:
            self.latest[(entry.kind, entry.item_id)] = entry


class ChargingRepository:
    def __init__(self, state=network, clock=utcnow):
        self.network = state
        self.clock = clock
        self._store = None

    @property
    def store(self):
        anchor = next(iter(self.network.hubs.values()), None)
        if self._store is None or self._store.anchor is not anchor:
            self._store = ChargingStore(anchor)
            now = self.clock()
            # Seed rows simulate one accepted initial sensor report for the demo.
            for vehicle in self.network.vehicles.values():
                self._store.append_update(UpdateLogEntry("seed", "vehicle", vehicle.vehicle_id,
                    {"battery_level": vehicle.battery_level}, now, now, LogResult.ACCEPTED))
            for hub in self.network.hubs.values():
                for point in hub.charging_points.values():
                    self._store.append_update(UpdateLogEntry("seed", "charging_point", point.point_id,
                        {"status": point.status.value}, now, now, LogResult.ACCEPTED))
        return self._store

    def student_vehicle(self, user_id, vehicle_id=None):
        user = self.network.users.get(user_id)
        if not isinstance(user, Student) or not user.has_private_ev:
            raise HTTPException(403, "A student with a private EV is required")
        vehicles = [v for v in self.network.vehicles.values() if v.owner_id == user_id]
        if vehicle_id is None:
            if not vehicles:
                raise HTTPException(404, "No registered private vehicle")
            return vehicles[0]
        vehicle = self.network.get_vehicle(vehicle_id)
        if vehicle.owner_id != user_id:
            raise HTTPException(403, "Vehicle belongs to another user")
        return vehicle

    def operator(self, user_id):
        if not isinstance(self.network.users.get(user_id), Operator):
            raise HTTPException(403, "Operator only")

    def point(self, point_id):
        for hub in self.network.hubs.values():
            if point_id in hub.charging_points:
                return hub.charging_points[point_id]
        raise HTTPException(404, "Charging point not found")

    def sessions(self, hub_id=None, active=False):
        return [s for s in self.network.charging_sessions.values()
                if (hub_id is None or s.hub_id == hub_id) and (not active or s.status in ACTIVE_SESSIONS)]

    def booking_for(self, session):
        rid = getattr(session, "reservation_id", None)
        return self.network.reservations.get(rid) if rid else None

    def freshness(self, kind, item_id, now=None):
        now = now or self.clock()
        record = self.store.latest.get((kind, item_id))
        age = max(0, (now - record.reception_time).total_seconds()) if record else None
        return {"kind": kind, "id": item_id, "last_update": record.reception_time if record else None,
                "age_seconds": age, "outdated": age is None or age > FRESH_SECONDS,
                "last_known_values": record.values.copy() if record else {}}

    def outdated_items(self, hub_id, now=None):
        hub = self.network.get_hub(hub_id)
        ids = {s.vehicle_id for s in self.sessions(hub_id, active=True)}
        items = [self.freshness("vehicle", vid, now) for vid in sorted(ids)]
        items += [self.freshness("charging_point", p.point_id, now) for p in hub.charging_points.values()]
        return [i for i in items if i["outdated"]]

    def intervals(self, point_id, now, exclude_session=None):
        """Half-open intervals; future reservations do not block unrelated slots."""
        result = []
        for reservation in self.network.reservations.values():
            if (reservation.kind == ReservationKind.CHARGING and reservation.resource_id == point_id
                    and reservation.status in ACTIVE_RESERVATIONS):
                result.append((reservation.start_time, reservation.end_time or now + timedelta(days=365)))
        for session in self.sessions(active=True):
            if session.point_id == point_id and session.session_id != exclude_session:
                if session.status in {ChargingSessionStatus.SCHEDULED, ChargingSessionStatus.CHARGING}:
                    result.append((session.start_time or now, session.end_time or now + timedelta(days=365)))
        return result

    def can_book(self, point, start, end, now=None):
        now = now or self.clock()
        if point.status == ChargingPointStatus.OUT_OF_SERVICE:
            return False
        if point.current_session_id and point.current_session_id not in self.network.charging_sessions:
            return False
        if point.status in {ChargingPointStatus.RESERVED, ChargingPointStatus.OCCUPIED}:
            if not self.intervals(point.point_id, now):
                return False  # Unknown external allocation: never steal the point.
        return not any(overlaps(start, end, a, b) for a, b in self.intervals(point.point_id, now))

    def fingerprint(self, hub_id):
        hub = self.network.get_hub(hub_id)
        payload = {"hub": asdict(hub), "sessions": [asdict(s) for s in self.sessions(hub_id)],
                   "vehicles": [asdict(v) for v in self.network.vehicles.values() if v.hub_id == hub_id],
                   "reservations": [asdict(r) for r in self.network.reservations.values() if r.hub_id == hub_id],
                   "readings": [{"kind": e.kind, "id": e.item_id, "values": e.values,
                                 "outdated": self.freshness(e.kind, e.item_id)["outdated"]}
                                for e in self.store.latest.values()
                                if (e.kind == "vehicle" and e.item_id in hub.vehicle_ids)
                                or (e.kind == "charging_point" and e.item_id in hub.charging_points)]}
        raw = json.dumps(payload, sort_keys=True, default=lambda x: sorted(x) if isinstance(x, set) else str(x))
        return hashlib.sha256(raw.encode()).hexdigest()

    def notify(self, user_id, message, **details):
        if user_id:
            self.store.notifications.append({"notification_id": new_id("CN"), "user_id": user_id,
                "message": message, "created_at": self.clock(), **details})

    def audit(self, action, operator_id, **details):
        self.store.audit.append({"action": action, "operator_id": operator_id,
                                 "timestamp": self.clock(), **details})


repository = ChargingRepository()
