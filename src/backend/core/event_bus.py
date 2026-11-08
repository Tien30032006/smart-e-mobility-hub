"""In-process publish/subscribe bus. SHARED FILE.

Modules talk to each other through events instead of importing each other
wherever possible, e.g.
    Member 1   : bus.emit(EventType.ISSUE_REPORTED, hub_id=..., issue=...)
    Member 3  : bus.subscribe(EventType.ISSUE_REPORTED, on_issue_reported)
A failing handler never breaks the publisher.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from .entities import Event
from .enums import EventType, Severity
from .logger import get_logger

log = get_logger("event_bus")
Handler = Callable[[Event], None]


class EventBus:
    MAX_HISTORY = 1000

    def __init__(self) -> None:
        self._handlers: Dict[Optional[EventType], List[Handler]] = defaultdict(list)
        self._lock = threading.RLock()
        self.history: List[Event] = []
        self.generation = 0

    def subscribe(self, event_type: Optional[EventType], handler: Handler) -> None:
        """event_type=None subscribes to every event."""
        with self._lock:
            self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> Event:
        with self._lock:
            self.history.append(event)
            del self.history[: -self.MAX_HISTORY]
            handlers = list(self._handlers[event.event_type]) + list(self._handlers[None])
        for handler in handlers:
            try:
                handler(event)
            except Exception:  # noqa: BLE001 - isolate subscribers
                log.exception("handler %s failed for %s", handler, event.event_type)
        return event

    def emit(self, event_type: EventType, hub_id: Optional[str] = None,
             severity: Severity = Severity.INFO, **payload) -> Event:
        return self.publish(Event(event_type=event_type, hub_id=hub_id,
                                  severity=severity, payload=payload))

    def clear(self) -> None:
        """Test helper: drop handlers and history."""
        with self._lock:
            self._handlers.clear()
            self.history.clear()
            self.generation += 1


bus = EventBus()
