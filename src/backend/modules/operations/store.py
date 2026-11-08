"""Module-owned data of the operations module.   OWNER: Member 3

Alerts, incidents, maintenance tickets, relocation orders, notifications and
the operator audit log. Everything is a ``dict[str, dict]`` of JSON-friendly
values so ``core.database.persistence`` can save/restore it (module_state table).

Like the charging module, the store is bound to the *first hub object* of the
network: whenever the network is re-seeded (tests, demo reset) or reloaded from
SQLite the hub objects are new, so a fresh empty store is created automatically.
No change to shared reset code is needed.
"""
from __future__ import annotations

from ...core.database import persistence
from ...core.entities import new_id, utcnow
from ...core.state_manager import network


class OperationsStore:
    def __init__(self, anchor) -> None:
        self.anchor = anchor
        self.alerts: dict = {}
        self.incidents: dict = {}
        self.tickets: dict = {}
        self.orders: dict = {}
        self.notifications: dict = {}
        self.audit: dict = {}


_store: OperationsStore | None = None


def current() -> OperationsStore:
    global _store
    anchor = next(iter(network.hubs.values()), None)
    if _store is None or _store.anchor is not anchor:
        _store = OperationsStore(anchor)
    return _store


def now_iso() -> str:
    return utcnow().isoformat()


def log_audit(action: str, operator_id: str, **details) -> dict:
    """Who did what, when (UC-OP09 requires this for every override)."""
    entry = {"audit_id": new_id("AU"), "action": action, "operator_id": operator_id,
             "timestamp": now_iso(), **details}
    current().audit[entry["audit_id"]] = entry
    return entry


def notify(to: str, kind: str, **details) -> dict:
    """Mock notification channel (student App / field staff / maintenance team)."""
    entry = {"notification_id": new_id("ON"), "to": to, "kind": kind,
             "created_at": now_iso(), **details}
    current().notifications[entry["notification_id"]] = entry
    return entry


# Register with the database at import time. app.py imports operations.routes before
# the lifespan runs persistence.load(), so these stores are restored after a restart.
for _name in ("alerts", "incidents", "tickets", "orders", "notifications", "audit"):
    persistence.register_store(f"operations.{_name}", (lambda n=_name: getattr(current(), n)))
