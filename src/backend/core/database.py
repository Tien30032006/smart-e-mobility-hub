"""SQLite persistence for the whole network. SHARED FILE (owner: TV5).

Design
------
* ``network`` (core/state_manager.py) stays the in-memory source of truth - every
  module keeps working with plain Python objects and ``network.lock``.
* This file mirrors that state into SQLite with *proper relational tables*
  (users, hubs, parking_spaces, charging_points, vehicles, reservations,
  charging_sessions, events) plus a generic ``module_state`` table for the
  module-owned stores (wallet, ledger, trips, issues ...).
* ``Persistence.flush()`` writes only rows whose content changed (hash cache) in
  ONE transaction. It is called after every mutating HTTP request, on a timer
  and on shutdown. ``Persistence.load()`` rebuilds ``network`` at startup.

Modules that own extra stores register them with ``persistence.register_store``.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from .entities import (
    ChargingPoint, ChargingSession, Event, EVehicle, MobilityHub, Operator, ParkingSpace,
    Reservation, Student, User,
)
from .enums import (
    ChargingPointStatus, ChargingSessionStatus, EventType, ReservationKind, ReservationStatus,
    Severity, UserRole, VehicleStatus,
)
from .logger import get_logger
from .state_manager import HubNetworkManager, network as default_network

log = get_logger("database")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY, role TEXT NOT NULL, full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE, student_code TEXT DEFAULT '', operator_id TEXT DEFAULT '',
    phone TEXT DEFAULT '', has_private_ev INTEGER DEFAULT 0, google_sub TEXT, picture TEXT DEFAULT '',
    onboarded INTEGER DEFAULT 0, created_at TEXT
);
CREATE TABLE IF NOT EXISTS hubs (
    hub_id TEXT PRIMARY KEY, name TEXT NOT NULL, lat REAL, lng REAL, capacity INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS parking_spaces (
    space_id TEXT PRIMARY KEY, hub_id TEXT NOT NULL REFERENCES hubs(hub_id) ON DELETE CASCADE,
    zone TEXT, is_occupied INTEGER, vehicle_id TEXT, reserved_by TEXT
);
CREATE TABLE IF NOT EXISTS charging_points (
    point_id TEXT PRIMARY KEY, hub_id TEXT NOT NULL REFERENCES hubs(hub_id) ON DELETE CASCADE,
    power_rating REAL, status TEXT NOT NULL, current_session_id TEXT
);
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id TEXT PRIMARY KEY, model TEXT, vehicle_type TEXT, battery_level INTEGER,
    status TEXT NOT NULL, hub_id TEXT, owner_id TEXT
);
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY, kind TEXT NOT NULL, user_id TEXT NOT NULL, hub_id TEXT NOT NULL,
    resource_id TEXT NOT NULL, start_time TEXT, end_time TEXT, status TEXT NOT NULL,
    deposit_amount REAL DEFAULT 0, notes TEXT DEFAULT '', extra TEXT
);
CREATE TABLE IF NOT EXISTS charging_sessions (
    session_id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL, point_id TEXT, hub_id TEXT,
    start_time TEXT, end_time TEXT, needed_by TEXT, priority INTEGER DEFAULT 0,
    status TEXT NOT NULL, requested_by TEXT, extra TEXT
);
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, hub_id TEXT, severity TEXT,
    payload TEXT, timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_res_user ON reservations(user_id);
CREATE TABLE IF NOT EXISTS module_state (
    namespace TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

# Extra (non-dataclass) attributes some modules attach to entities, kept in a JSON column.
_RESERVATION_FIELDS = {"reservation_id", "kind", "user_id", "hub_id", "resource_id", "start_time",
                       "end_time", "status", "deposit_amount", "notes"}
_SESSION_FIELDS = {"session_id", "vehicle_id", "point_id", "hub_id", "start_time", "end_time",
                   "needed_by", "priority", "status", "requested_by"}


def _dt(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _json(value: Any) -> str:
    def default(o):
        if isinstance(o, datetime):
            return {"__dt__": o.isoformat()}
        if isinstance(o, (set, frozenset)):
            return {"__set__": sorted(o, key=str)}
        if hasattr(o, "value"):
            return o.value
        return str(o)
    return json.dumps(value, default=default, sort_keys=True, ensure_ascii=False)


def _unjson(text: Optional[str]) -> Any:
    def hook(d):
        if "__dt__" in d:
            return datetime.fromisoformat(d["__dt__"])
        if "__set__" in d:
            return set(d["__set__"])
        return d
    return json.loads(text, object_hook=hook) if text else None


class Persistence:
    """Mirror of ``network`` + registered module stores in a SQLite file."""

    def __init__(self, state: HubNetworkManager = default_network) -> None:
        self.network = state
        self.path: Optional[str] = None
        self._conn: Optional[sqlite3.Connection] = None
        self._io_lock = threading.RLock()
        self._hashes: Dict[tuple, str] = {}
        self._stores: Dict[str, Callable[[], dict]] = {}
        self._known_events: set = set()   # event ids already written
        self._bound_bus = None

    # ---- lifecycle ---------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self._conn is not None

    def connect(self, path: str) -> None:
        with self._io_lock:
            self.close()
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.path = path
            self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys=OFF")
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
            self._hashes.clear()
            self._known_events = set()

    def close(self) -> None:
        with self._io_lock:
            if self._conn is not None:
                self._conn.close()
            self._conn = None

    def register_store(self, namespace: str, getter: Callable[[], dict]) -> None:
        """Persist a module-owned ``dict`` (JSON-serialisable values) under ``namespace``."""
        self._stores[namespace] = getter

    def has_data(self) -> bool:
        if not self.enabled:
            return False
        with self._io_lock:
            return self._conn.execute("SELECT COUNT(*) FROM hubs").fetchone()[0] > 0

    # ---- flush (memory -> disk) -------------------------------------------
    def flush(self, include_events: bool = True) -> int:
        """Write every changed row. Returns the number of rows written/deleted."""
        if not self.enabled:
            return 0
        with self.network.lock:                      # consistent view of memory
            rows = self._collect_rows()
            module_rows = self._collect_module_rows()
        written = 0
        with self._io_lock:
            c = self._conn
            c.execute("BEGIN")
            try:
                for table, pk, items in rows:
                    written += self._sync_table(c, table, pk, items)
                written += self._sync_module_state(c, module_rows)
                if include_events:
                    written += self._flush_events(c)
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return written

    def _collect_rows(self):
        n = self.network
        users, hubs, spaces, points, vehicles, reservations, sessions = [], [], [], [], [], [], []
        for u in n.users.values():
            extra = getattr(u, "_db", {}) or {}
            users.append({
                "user_id": u.user_id, "role": u.user_role.value, "full_name": u.full_name, "email": u.email,
                "student_code": getattr(u, "student_code", ""), "operator_id": getattr(u, "operator_id", ""),
                "phone": extra.get("phone", ""), "has_private_ev": int(getattr(u, "has_private_ev", False)),
                "google_sub": extra.get("google_sub"), "picture": extra.get("picture", ""),
                "onboarded": int(extra.get("onboarded", True)), "created_at": extra.get("created_at"),
            })
        for h in n.hubs.values():
            hubs.append({"hub_id": h.hub_id, "name": h.name, "lat": h.location.get("lat"),
                         "lng": h.location.get("lng"), "capacity": h.capacity})
            for s in h.parking_spaces.values():
                spaces.append({"space_id": s.space_id, "hub_id": s.hub_id, "zone": s.zone,
                               "is_occupied": int(s.is_occupied), "vehicle_id": s.vehicle_id,
                               "reserved_by": s.reserved_by})
            for p in h.charging_points.values():
                points.append({"point_id": p.point_id, "hub_id": p.hub_id, "power_rating": p.power_rating,
                               "status": ChargingPointStatus(p.status).value,
                               "current_session_id": p.current_session_id})
        for v in n.vehicles.values():
            vehicles.append({"vehicle_id": v.vehicle_id, "model": v.model, "vehicle_type": v.vehicle_type,
                             "battery_level": v.battery_level, "status": VehicleStatus(v.status).value,
                             "hub_id": v.hub_id, "owner_id": v.owner_id})
        for r in n.reservations.values():
            extra = {k: val for k, val in vars(r).items() if k not in _RESERVATION_FIELDS}
            reservations.append({
                "reservation_id": r.reservation_id, "kind": ReservationKind(r.kind).value, "user_id": r.user_id,
                "hub_id": r.hub_id, "resource_id": r.resource_id, "start_time": _dt(r.start_time),
                "end_time": _dt(r.end_time), "status": ReservationStatus(r.status).value,
                "deposit_amount": r.deposit_amount, "notes": r.notes, "extra": _json(extra) if extra else None})
        for s in n.charging_sessions.values():
            extra = {k: val for k, val in vars(s).items() if k not in _SESSION_FIELDS}
            sessions.append({
                "session_id": s.session_id, "vehicle_id": s.vehicle_id, "point_id": s.point_id,
                "hub_id": s.hub_id, "start_time": _dt(s.start_time), "end_time": _dt(s.end_time),
                "needed_by": _dt(s.needed_by), "priority": s.priority,
                "status": ChargingSessionStatus(s.status).value, "requested_by": s.requested_by,
                "extra": _json(extra) if extra else None})
        return [("users", "user_id", users), ("hubs", "hub_id", hubs),
                ("parking_spaces", "space_id", spaces), ("charging_points", "point_id", points),
                ("vehicles", "vehicle_id", vehicles), ("reservations", "reservation_id", reservations),
                ("charging_sessions", "session_id", sessions)]

    def _collect_module_rows(self) -> Dict[str, Dict[str, str]]:
        out: Dict[str, Dict[str, str]] = {}
        for namespace, getter in self._stores.items():
            try:
                out[namespace] = {str(k): _json(v) for k, v in dict(getter()).items()}
            except Exception:  # noqa: BLE001 - a broken store must not stop persistence
                log.exception("cannot serialise store %s", namespace)
        return out

    def _sync_table(self, c, table: str, pk: str, items: List[dict]) -> int:
        written = 0
        seen = set()
        for row in items:
            key = (table, row[pk])
            seen.add(row[pk])
            digest = hashlib.sha1(_json(row).encode()).hexdigest()
            if self._hashes.get(key) == digest:
                continue
            cols = list(row)
            c.execute(f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                      [row[k] for k in cols])
            self._hashes[key] = digest
            written += 1
        stale = [k for k in self._hashes if k[0] == table and k[1] not in seen]
        for k in stale:
            c.execute(f"DELETE FROM {table} WHERE {pk}=?", (k[1],))
            del self._hashes[k]
            written += 1
        return written

    def _sync_module_state(self, c, module_rows: Dict[str, Dict[str, str]]) -> int:
        written = 0
        for namespace, rows in module_rows.items():
            for key, data in rows.items():
                hk = ("module_state", namespace, key)
                if self._hashes.get(hk) == data:
                    continue
                c.execute("INSERT OR REPLACE INTO module_state(namespace,key,data) VALUES (?,?,?)",
                          (namespace, key, data))
                self._hashes[hk] = data
                written += 1
            gone = [k for k in self._hashes if k[0] == "module_state" and k[1] == namespace and k[2] not in rows]
            for k in gone:
                c.execute("DELETE FROM module_state WHERE namespace=? AND key=?", (namespace, k[2]))
                del self._hashes[k]
                written += 1
        return written

    def attach_bus(self, bus) -> None:
        """Append-only audit log of every event published on the bus."""
        self._bound_bus = bus

    def _flush_events(self, c) -> int:
        bus = self._bound_bus
        if bus is None:
            return 0
        with bus._lock:
            history = list(bus.history)
        written = 0
        for ev in history:
            if ev.event_id in self._known_events:
                continue
            c.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)",
                      (ev.event_id, EventType(ev.event_type).value, ev.hub_id, Severity(ev.severity).value,
                       _json(ev.payload), ev.timestamp.isoformat()))
            self._known_events.add(ev.event_id)
            written += 1
        if len(self._known_events) > 5000:
            self._known_events = {e.event_id for e in history}
        return written

    # ---- load (disk -> memory) ----------------------------------------------
    def load(self) -> bool:
        """Rebuild ``network`` from the database. Returns False if the DB is empty."""
        if not self.has_data():
            return False
        n = self.network
        with self._io_lock, n.lock:
            c = self._conn
            n.reset()
            for r in c.execute("SELECT * FROM hubs"):
                n.hubs[r["hub_id"]] = MobilityHub(hub_id=r["hub_id"], name=r["name"],
                                                  location={"lat": r["lat"], "lng": r["lng"]}, capacity=r["capacity"])
            for r in c.execute("SELECT * FROM parking_spaces ORDER BY space_id"):
                hub = n.hubs.get(r["hub_id"])
                if hub:
                    hub.parking_spaces[r["space_id"]] = ParkingSpace(
                        space_id=r["space_id"], hub_id=r["hub_id"], zone=r["zone"] or "A",
                        is_occupied=bool(r["is_occupied"]), vehicle_id=r["vehicle_id"], reserved_by=r["reserved_by"])
            for r in c.execute("SELECT * FROM charging_points ORDER BY point_id"):
                hub = n.hubs.get(r["hub_id"])
                if hub:
                    hub.charging_points[r["point_id"]] = ChargingPoint(
                        point_id=r["point_id"], hub_id=r["hub_id"], power_rating=r["power_rating"],
                        status=ChargingPointStatus(r["status"]), current_session_id=r["current_session_id"])
            for r in c.execute("SELECT * FROM vehicles ORDER BY vehicle_id"):
                n.vehicles[r["vehicle_id"]] = EVehicle(
                    vehicle_id=r["vehicle_id"], model=r["model"] or "", vehicle_type=r["vehicle_type"] or "e-bike",
                    battery_level=r["battery_level"], status=VehicleStatus(r["status"]),
                    hub_id=r["hub_id"], owner_id=r["owner_id"])
                if r["hub_id"] in n.hubs:
                    n.hubs[r["hub_id"]].vehicle_ids.add(r["vehicle_id"])
            for r in c.execute("SELECT * FROM users"):
                n.users[r["user_id"]] = self._user_from_row(r)
            for r in c.execute("SELECT * FROM reservations"):
                res = Reservation(
                    reservation_id=r["reservation_id"], kind=ReservationKind(r["kind"]), user_id=r["user_id"],
                    hub_id=r["hub_id"], resource_id=r["resource_id"], start_time=_parse_dt(r["start_time"]),
                    end_time=_parse_dt(r["end_time"]), status=ReservationStatus(r["status"]),
                    deposit_amount=r["deposit_amount"], notes=r["notes"] or "")
                for k, v in (_unjson(r["extra"]) or {}).items():
                    setattr(res, k, v)
                n.reservations[res.reservation_id] = res
            for r in c.execute("SELECT * FROM charging_sessions"):
                s = ChargingSession(
                    session_id=r["session_id"], vehicle_id=r["vehicle_id"], point_id=r["point_id"], hub_id=r["hub_id"],
                    start_time=_parse_dt(r["start_time"]), end_time=_parse_dt(r["end_time"]),
                    needed_by=_parse_dt(r["needed_by"]), priority=r["priority"],
                    status=ChargingSessionStatus(r["status"]), requested_by=r["requested_by"])
                for k, v in (_unjson(r["extra"]) or {}).items():
                    setattr(s, k, v)
                n.charging_sessions[s.session_id] = s
            for namespace, getter in self._stores.items():
                target = getter()
                target.clear()
                for r in c.execute("SELECT key,data FROM module_state WHERE namespace=?", (namespace,)):
                    target[r["key"]] = _unjson(r["data"])
        self._hashes.clear()
        self.flush(include_events=False)       # prime the hash cache (writes nothing new)
        return True

    @staticmethod
    def _user_from_row(r) -> User:
        if r["role"] == UserRole.OPERATOR.value:
            user: User = Operator(user_id=r["user_id"], full_name=r["full_name"], email=r["email"],
                                  operator_id=r["operator_id"] or "")
        else:
            user = Student(user_id=r["user_id"], full_name=r["full_name"], email=r["email"],
                           student_code=r["student_code"] or "", has_private_ev=bool(r["has_private_ev"]))
        user._db = {"phone": r["phone"] or "", "google_sub": r["google_sub"], "picture": r["picture"] or "",
                    "onboarded": bool(r["onboarded"]), "created_at": r["created_at"]}
        return user

    # ---- maintenance ---------------------------------------------------------
    def wipe(self) -> None:
        """Delete every row (used by demo reset)."""
        if not self.enabled:
            return
        with self._io_lock:
            for t in ("users", "hubs", "parking_spaces", "charging_points", "vehicles", "reservations",
                      "charging_sessions", "events", "module_state"):
                self._conn.execute(f"DELETE FROM {t}")
            self._hashes.clear()
            self._known_events = set()

    def recent_events(self, limit: int = 100) -> List[dict]:
        if not self.enabled:
            return []
        with self._io_lock:
            rows = self._conn.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(r), "payload": _unjson(r["payload"])} for r in rows]

    def table_counts(self) -> Dict[str, int]:
        if not self.enabled:
            return {}
        with self._io_lock:
            return {t: self._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("users", "hubs", "parking_spaces", "charging_points", "vehicles",
                              "reservations", "charging_sessions", "events", "module_state")}


persistence = Persistence()
