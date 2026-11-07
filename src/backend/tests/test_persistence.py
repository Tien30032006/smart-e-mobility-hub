"""SQLite persistence (TV5): state survives a 'restart'."""
import sqlite3

import pytest

from src.backend.core.database import Persistence
from src.backend.core.entities import Reservation, new_id
from src.backend.core.enums import ReservationKind, ReservationStatus, VehicleStatus
from src.backend.core.event_bus import EventBus
from src.backend.core.enums import EventType
from src.backend.core.state_manager import HubNetworkManager
from src.backend.data.seed_data import seed_network


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "hub.db")


def fresh_world(db_path, stores=None):
    """A brand-new 'process': empty network + Persistence bound to the same file."""
    net = HubNetworkManager()
    p = Persistence(net)
    for ns, d in (stores or {}).items():
        p.register_store(ns, lambda d=d: d)
    p.connect(db_path)
    return net, p


def test_schema_has_real_tables(db_path):
    _, p = fresh_world(db_path)
    names = {r[0] for r in sqlite3.connect(db_path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "hubs", "parking_spaces", "charging_points", "vehicles", "reservations",
            "charging_sessions", "events", "module_state"} <= names


def test_seed_save_and_restore_roundtrip(db_path):
    net, p = fresh_world(db_path)
    seed_network(net)
    p.flush()
    counts = p.table_counts()
    assert counts["hubs"] == 4 and counts["vehicles"] == 10 and counts["users"] == 3
    assert counts["parking_spaces"] == 12 + 20 + 16 + 8 and counts["charging_points"] == 16
    p.close()

    net2, p2 = fresh_world(db_path)                     # "restart"
    assert p2.load() is True
    assert set(net2.hubs) == set(net.hubs) and set(net2.vehicles) == set(net.vehicles)
    for hub_id in net.hubs:
        assert net2.get_hub_status(hub_id) == net.get_hub_status(hub_id)
    assert net2.hubs["HUB-METRO"].vehicle_ids == net.hubs["HUB-METRO"].vehicle_ids
    assert net2.users["U-S02"].has_private_ev and net2.users["U-OP1"].user_role.value == "operator"


def test_changes_are_persisted_and_unchanged_rows_are_not_rewritten(db_path):
    net, p = fresh_world(db_path)
    seed_network(net)
    p.flush()
    assert p.flush() == 0                                # nothing changed -> nothing written
    net.vehicles["V-001"].battery_level = 33
    net.vehicles["V-001"].status = VehicleStatus.IN_USE
    assert p.flush() == 1
    assert net.move_vehicle("V-002", "HUB-LIB")
    p.flush()
    p.close()
    net2, p2 = fresh_world(db_path)
    p2.load()
    assert net2.vehicles["V-001"].battery_level == 33 and net2.vehicles["V-001"].status == VehicleStatus.IN_USE
    assert net2.vehicles["V-002"].hub_id == "HUB-LIB" and "V-002" in net2.hubs["HUB-LIB"].vehicle_ids
    assert "V-002" not in net2.hubs["HUB-METRO"].vehicle_ids
    assert net2.hubs["HUB-LIB"].get_available_resources() == net.hubs["HUB-LIB"].get_available_resources()


def test_reservations_and_deleted_rows(db_path):
    net, p = fresh_world(db_path)
    seed_network(net)
    r = Reservation(new_id("R"), ReservationKind.VEHICLE, "U-S01", "HUB-METRO", "V-001",
                    status=ReservationStatus.CONFIRMED, deposit_amount=20000)
    net.reservations[r.reservation_id] = r
    p.flush()
    p.close()
    net2, p2 = fresh_world(db_path)
    p2.load()
    back = net2.reservations[r.reservation_id]
    assert back.status == ReservationStatus.CONFIRMED and back.deposit_amount == 20000
    assert back.start_time == r.start_time and back.kind == ReservationKind.VEHICLE
    del net2.reservations[r.reservation_id]
    p2.flush()
    assert p2.table_counts()["reservations"] == 0


def test_module_stores_wallet_survive_restart(db_path):
    wallets = {"U-S01": {"user_id": "U-S01", "balance": 150000.0, "held_deposit": 20000.0, "updated_at": "t"}}
    net, p = fresh_world(db_path, {"wallet.wallets": wallets})
    seed_network(net)
    p.flush()
    wallets["U-S01"]["balance"] = 99000.0
    p.flush()
    p.close()
    restored = {}
    net2, p2 = fresh_world(db_path, {"wallet.wallets": restored})
    p2.load()
    assert restored["U-S01"]["balance"] == 99000.0 and restored["U-S01"]["held_deposit"] == 20000.0


def test_event_audit_log(db_path):
    net, p = fresh_world(db_path)
    bus = EventBus()
    p.attach_bus(bus)
    seed_network(net)
    bus.emit(EventType.ALERT_RAISED, hub_id="HUB-METRO", alert_id="A1", message="Metro full")
    p.flush()
    p.flush()                                            # idempotent
    events = p.recent_events()
    assert len(events) == 1 and events[0]["event_type"] == "alert_raised"
    assert events[0]["payload"]["message"] == "Metro full"


def test_new_users_and_profile_persist(db_path):
    from src.backend.core.entities import Student
    net, p = fresh_world(db_path)
    seed_network(net)
    u = Student("U-S-new", "Lan", "lan@hcmut.edu.vn", student_code="2311111")
    u._db = {"google_sub": "g-1", "phone": "0909", "onboarded": False, "picture": "", "created_at": "2026-11-06"}
    net.register_user(u)
    p.flush()
    p.close()
    net2, p2 = fresh_world(db_path)
    p2.load()
    got = net2.users["U-S-new"]
    assert got.student_code == "2311111" and got._db["google_sub"] == "g-1" and got._db["onboarded"] is False


def test_empty_database_reports_no_data(db_path):
    _, p = fresh_world(db_path)
    assert p.has_data() is False and p.load() is False
