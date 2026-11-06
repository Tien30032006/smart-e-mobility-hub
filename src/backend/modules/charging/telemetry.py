"""UC-CH-10: log-before-write ingestion and a stoppable demo simulator."""
from __future__ import annotations

from datetime import timedelta
import math
import threading
from typing import List

from fastapi import HTTPException

from ...core.enums import ChargingPointStatus, ChargingSessionStatus, EventType, ReservationStatus, VehicleStatus
from ...core.event_bus import bus
from ...core.logger import get_logger
from .domain import BATTERY_CAPACITY_KWH, LogResult, UpdateLogEntry, percentage, timestamp
from .repository import repository

log = get_logger("charging.telemetry")
_thread = None
_stop = threading.Event()
_thread_lock = threading.Lock()


def on_simulator_event(event):
    """TV5 adapter: accept BATTERY_UPDATED / CHARGER_STATUS_CHANGED without echo loops.

    Sensor events should carry device_timestamp. The existing simulator's legacy
    timestamp-free payload is supported by the ingestion monotonic clock adapter.
    """
    payload = event.payload
    if str(payload.get("origin", "")).startswith("charging."):
        return
    with repository.network.lock:
        if event.event_id in repository.store.received_events:
            return
        if event.event_type == EventType.BATTERY_UPDATED:
            reading = {"kind": "vehicle", "id": payload.get("vehicle_id"),
                       "battery_level": payload.get("battery_level")}
        elif event.event_type == EventType.CHARGER_STATUS_CHANGED:
            reading = {"kind": "charging_point", "id": payload.get("point_id"),
                       "status": payload.get("new_status", payload.get("status"))}
        else:
            return
        reading["source_id"] = "simulator"
        if payload.get("device_timestamp"):
            reading["device_timestamp"] = payload["device_timestamp"]
        ingest_readings([reading])
        if len(repository.store.received_events) >= 1000:
            repository.store.received_events.clear()
        repository.store.received_events.add(event.event_id)


def register_simulator_handlers():
    """Call at application lifespan start; event IDs deduplicate repeated delivery."""
    bus.subscribe(EventType.BATTERY_UPDATED, on_simulator_event)
    bus.subscribe(EventType.CHARGER_STATUS_CHANGED, on_simulator_event)


def ingest_readings(readings: List[dict]) -> int:
    accepted, events = 0, []
    with repository.network.lock:
        store = repository.store
        for reading in readings:
            now = repository.clock()
            source = reading.get("source_id", "simulator")
            kind, item_id = reading.get("kind", ""), reading.get("id", "")
            device_time, entity, value = None, None, None
            result, reason = LogResult.ACCEPTED, ""
            try:
                if source not in store.sources or source == "seed":
                    raise HTTPException(400, "Unknown sensor source")
                device_time = timestamp(reading.get("device_timestamp"), "device_timestamp") or now
                if device_time > now + timedelta(minutes=5):
                    raise HTTPException(400, "Device timestamp is too far in the future")
                if kind == "vehicle":
                    entity = repository.network.vehicles.get(item_id)
                    if entity is None:
                        raise HTTPException(400, "Unknown vehicle")
                    value = percentage(reading.get("battery_level"))
                elif kind == "charging_point":
                    entity = repository.point(item_id)
                    value = ChargingPointStatus(reading.get("status"))
                    if value in {ChargingPointStatus.AVAILABLE, ChargingPointStatus.RESERVED}:
                        session = repository.network.charging_sessions.get(entity.current_session_id)
                        if session and (session.status == ChargingSessionStatus.CHARGING or
                                        (value == ChargingPointStatus.AVAILABLE and session.status == ChargingSessionStatus.SCHEDULED)):
                            raise HTTPException(409, "Complete active session before freeing its point")
                else:
                    raise HTTPException(400, "kind must be vehicle or charging_point")
                previous = store.latest.get((kind, item_id))
                # Legacy/simulator readings omit a device timestamp. Generate a
                # monotonic one even on Windows clocks with coarse resolution.
                if previous and reading.get("device_timestamp") is None and device_time <= previous.device_timestamp:
                    device_time = previous.device_timestamp + timedelta(microseconds=1)
                if previous and device_time <= previous.device_timestamp:
                    result, reason = LogResult.IGNORED, "Duplicate or older device timestamp"
            except (HTTPException, ValueError, TypeError) as exc:
                result, reason = LogResult.REJECTED, str(getattr(exc, "detail", exc))
            values = {k: reading[k] for k in ("battery_level", "status") if k in reading}
            entry = UpdateLogEntry(source, kind, item_id, values, device_time, now, result, reason)
            try:
                store.append_update(entry)
            except Exception:
                log.exception("Data Update Log unavailable; reading not applied")
                raise HTTPException(503, "Data Update Log unavailable; update was not applied") from None
            if result != LogResult.ACCEPTED:
                continue
            accepted += 1
            if kind == "vehicle":
                entity.battery_level = value
                events.append((EventType.BATTERY_UPDATED, entity.hub_id,
                               {"vehicle_id": item_id, "battery_level": value}))
            else:
                old = entity.status
                entity.status = value
                if value == ChargingPointStatus.OUT_OF_SERVICE:
                    from .point_monitor import requeue_affected
                    requeue_affected(entity)
                if value != old:
                    events.append((EventType.CHARGER_STATUS_CHANGED, entity.hub_id,
                                   {"point_id": item_id, "old_status": old.value, "new_status": value.value}))
        # Completion is driven by accepted battery data, never by rejected readings.
        from .service import complete_session
        for session in list(repository.sessions(active=True)):
            vehicle = repository.network.get_vehicle(session.vehicle_id)
            if session.status == ChargingSessionStatus.CHARGING and vehicle.battery_level >= getattr(session, "target_level", 100):
                complete_session(session.session_id)
    for event, hub_id, payload in events:
        bus.emit(event, hub_id=hub_id, origin="charging.telemetry", **payload)
    return accepted


def simulator_tick(elapsed_seconds=5):
    """One deterministic tick; tests can call it without starting a background thread."""
    from .service import complete_session
    with repository.network.lock:
        now = repository.clock()
        started = []
        for session in repository.sessions(active=True):
            if session.status != ChargingSessionStatus.SCHEDULED or not session.point_id:
                continue
            vehicle = repository.network.get_vehicle(session.vehicle_id)
            point = repository.point(session.point_id)
            if session.end_time and session.end_time <= now:
                session.status = ChargingSessionStatus.CANCELLED
                booking = repository.booking_for(session)
                if booking:
                    booking.status = ReservationStatus.EXPIRED
                from .service import release_point
                release_point(session)
                repository.notify(session.requested_by, "charging_window_expired", session_id=session.session_id)
                continue
            if (session.start_time and session.start_time <= now and vehicle.hub_id == session.hub_id
                    and vehicle.status not in {VehicleStatus.IN_USE, VehicleStatus.MAINTENANCE, VehicleStatus.OFFLINE}
                    and point.is_operational() and point.current_session_id in {None, session.session_id}
                    and point.status in {ChargingPointStatus.AVAILABLE, ChargingPointStatus.RESERVED}):
                session.status = ChargingSessionStatus.CHARGING
                point.status, point.current_session_id = ChargingPointStatus.OCCUPIED, session.session_id
                vehicle.status = VehicleStatus.CHARGING
                booking = repository.booking_for(session)
                if booking:
                    booking.status = ReservationStatus.ACTIVE
                started.append(session)
        for session in started:
            bus.emit(EventType.CHARGING_STARTED, hub_id=session.hub_id,
                     session_id=session.session_id, vehicle_id=session.vehicle_id)
        readings = []
        for vehicle in repository.network.vehicles.values():
            battery = vehicle.battery_level
            running = next((s for s in repository.sessions(active=True)
                            if s.vehicle_id == vehicle.vehicle_id and s.status == ChargingSessionStatus.CHARGING), None)
            if running:
                point = repository.point(running.point_id)
                battery = min(getattr(running, "target_level", 100), battery + max(1,
                    round(point.power_rating / BATTERY_CAPACITY_KWH * elapsed_seconds / 3600 * 100)))
            elif vehicle.status == VehicleStatus.IN_USE:
                battery = max(0, battery - 1)
            readings.append({"kind": "vehicle", "id": vehicle.vehicle_id, "battery_level": battery})
        for hub in repository.network.hubs.values():
            readings += [{"kind": "charging_point", "id": p.point_id, "status": p.status.value}
                         for p in hub.charging_points.values()]
        ingest_readings(readings)
        for session in list(repository.sessions(active=True)):
            if session.status == ChargingSessionStatus.CHARGING and session.end_time and session.end_time <= now:
                complete_session(session.session_id)
        changed_points = [{"kind": "charging_point", "id": point.point_id, "status": point.status.value}
            for hub in repository.network.hubs.values() for point in hub.charging_points.values()
            if repository.store.latest[("charging_point", point.point_id)].values.get("status") != point.status.value]
        if changed_points:
            ingest_readings(changed_points)  # Immediate report after completion/reallocation.


def start_simulator(interval_seconds: int = 5) -> None:
    global _thread
    if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, (int, float)) or not math.isfinite(interval_seconds) or not 0 < interval_seconds <= 30:
        raise HTTPException(400, "Simulator interval must be > 0 and <= 30 seconds")
    with _thread_lock:
        if _thread is not None and _thread.is_alive():
            return
        with repository.network.lock:
            repository.store  # Bootstrap before the first sensor tick.
        _stop.clear()
        def run():
            while not _stop.wait(interval_seconds):
                try:
                    simulator_tick(interval_seconds)
                except Exception:
                    log.exception("Simulator tick failed")
        _thread = threading.Thread(target=run, name="charging-simulator", daemon=True)
        _thread.start()


def stop_simulator() -> None:
    global _thread
    with _thread_lock:
        _stop.set()
        if _thread is not None:
            _thread.join(timeout=5)
            if not _thread.is_alive():
                _thread = None
