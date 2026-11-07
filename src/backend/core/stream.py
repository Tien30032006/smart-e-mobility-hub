"""Server-Sent Events hub. SHARED FILE (owner: TV5).

Bridges the in-process ``bus`` (sync, called from worker threads) to browsers:

    GET /api/stream?token=<jwt>   ->  text/event-stream

Event names sent to clients (see shared/stream.js):
    hub_updated, vehicle_updated, alert_created, reservation_changed, payment_updated

Every message carries ``{"hub_id":..., "ts":..., ...}``. Clients that cannot use
SSE fall back to polling (``Stream.on`` does that automatically).
"""
from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from typing import Dict, Optional, Set

from .entities import Event
from .enums import EventType, UserRole
from .event_bus import bus
from .logger import get_logger

log = get_logger("stream")

STREAM_EVENTS = ("hub_updated", "vehicle_updated", "alert_created", "reservation_changed", "payment_updated")

# bus event -> list of SSE event names
_MAP: Dict[EventType, tuple] = {
    EventType.VEHICLE_RESERVED: ("reservation_changed", "hub_updated", "vehicle_updated"),
    EventType.PARKING_RESERVED: ("reservation_changed", "hub_updated"),
    EventType.RESERVATION_CANCELLED: ("reservation_changed", "hub_updated", "vehicle_updated"),
    EventType.VEHICLE_PICKED_UP: ("reservation_changed", "hub_updated", "vehicle_updated"),
    EventType.VEHICLE_RETURNED: ("reservation_changed", "hub_updated", "vehicle_updated"),
    EventType.ISSUE_REPORTED: ("alert_created",),
    EventType.CHARGING_REQUESTED: ("hub_updated",),
    EventType.CHARGING_SCHEDULED: ("hub_updated",),
    EventType.CHARGING_STARTED: ("hub_updated", "vehicle_updated"),
    EventType.CHARGING_COMPLETED: ("hub_updated", "vehicle_updated"),
    EventType.CHARGER_STATUS_CHANGED: ("hub_updated",),
    EventType.BATTERY_UPDATED: ("vehicle_updated",),
    EventType.HUB_NEAR_CAPACITY: ("hub_updated", "alert_created"),
    EventType.ALERT_RAISED: ("alert_created",),
    EventType.INCIDENT_OPENED: ("alert_created",),
    EventType.RELOCATION_ORDER_CREATED: ("hub_updated", "vehicle_updated"),
    EventType.CHARGING_OVERRIDE: ("hub_updated",),
}


@dataclass(eq=False)
class Subscriber:
    queue: "asyncio.Queue[tuple]"
    user_id: str
    role: UserRole


class StreamHub:
    def __init__(self) -> None:
        self._subs: Set[Subscriber] = set()
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.seq = 0

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)

    def subscribe(self, user_id: str, role: UserRole) -> Subscriber:
        sub = Subscriber(asyncio.Queue(maxsize=200), user_id, role)
        with self._lock:
            self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            self._subs.discard(sub)

    def publish(self, name: str, data: Optional[dict] = None, user_id: Optional[str] = None,
                operator_only: bool = False) -> None:
        """Thread-safe. ``user_id`` restricts delivery to one user (+ operators never see it)."""
        self.seq += 1
        message = (name, {"seq": self.seq, **(data or {})})
        with self._lock:
            targets = list(self._subs)
        for sub in targets:
            if user_id is not None and sub.user_id != user_id:
                continue
            if operator_only and sub.role != UserRole.OPERATOR:
                continue
            self._put(sub, message)

    def _put(self, sub: Subscriber, message: tuple) -> None:
        def put():
            try:
                sub.queue.put_nowait(message)
            except asyncio.QueueFull:    # slow client: drop oldest, keep newest
                try:
                    sub.queue.get_nowait()
                    sub.queue.put_nowait(message)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            put()
        else:
            loop.call_soon_threadsafe(put)

    # ---- bus bridge ------------------------------------------------------------
    def on_bus_event(self, event: Event) -> None:
        names = _MAP.get(event.event_type)
        if not names:
            return
        if (event.payload or {}).get("origin") == "core.simulator" and "reservation_changed" in names:
            names = tuple(n for n in names if n != "reservation_changed")   # ambient traffic is not a booking
        base = {"hub_id": event.hub_id, "event_type": event.event_type.value,
                "severity": event.severity.value, "ts": event.timestamp.isoformat()}
        payload = event.payload or {}
        for key in ("vehicle_id", "reservation_id", "point_id", "battery_level", "alert_id", "message",
                    "order_id", "session_id", "new_status"):
            if key in payload:
                base[key] = payload[key]
        for name in names:
            if name == "alert_created":
                self.publish(name, base, operator_only=True)
            elif name == "reservation_changed" and payload.get("user_id"):
                self.publish(name, base, user_id=payload["user_id"])
                self.publish(name, base, operator_only=True)
            else:
                self.publish(name, base)

    def attach(self) -> None:
        bus.subscribe(None, self.on_bus_event)


def format_sse(name: str, data: dict) -> str:
    return f"event: {name}\nid: {data.get('seq', 0)}\ndata: {json.dumps(data, default=str)}\n\n"


stream_hub = StreamHub()
