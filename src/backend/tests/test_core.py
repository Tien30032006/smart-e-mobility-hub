"""Tests of the SHARED layer. They must stay green - if one breaks, someone changed a shared file."""
from src.backend.core.entities import Event, Operator, Student
from src.backend.core.enums import EventType, Severity, VehicleStatus
from src.backend.core.event_bus import bus
from src.backend.core.state_manager import network
from src.backend.tests.conftest import OPERATOR, STUDENT


def test_seed_loaded():
    assert len(network.hubs) == 4 and len(network.vehicles) == 10
    assert isinstance(network.users["U-S01"], Student)
    assert isinstance(network.users["U-OP1"], Operator)


def test_vehicles_occupy_parking_spaces():
    hub = network.get_hub("HUB-METRO")
    assert hub.capacity == 12
    assert hub.get_available_resources() == 12 - 3


def test_move_vehicle_is_atomic_and_updates_spaces():
    assert network.move_vehicle("V-001", "HUB-LIB") is True
    assert network.get_vehicle("V-001").hub_id == "HUB-LIB"
    assert "V-001" not in network.get_hub("HUB-METRO").vehicle_ids
    assert network.get_hub("HUB-METRO").get_available_resources() == 12 - 2


def test_move_vehicle_refuses_full_hub():
    lib = network.get_hub("HUB-LIB")
    for s in lib.parking_spaces.values():
        if s.is_available():
            s.occupy("dummy")
    assert network.move_vehicle("V-001", "HUB-LIB") is False
    assert network.get_vehicle("V-001").hub_id == "HUB-METRO"


def test_snapshot_is_isolated_from_live_state():
    snap = network.snapshot()
    snap.vehicles["V-001"].battery_level = 1
    snap.hubs["HUB-METRO"].parking_spaces.clear()
    assert network.get_vehicle("V-001").battery_level == 85
    assert len(network.get_hub("HUB-METRO").parking_spaces) == 12


def test_event_bus_delivers_and_isolates_failures():
    got = []
    bus.subscribe(EventType.ISSUE_REPORTED, lambda e: 1 / 0)       # broken subscriber
    bus.subscribe(EventType.ISSUE_REPORTED, got.append)
    ev = bus.emit(EventType.ISSUE_REPORTED, hub_id="HUB-KTX", severity=Severity.WARNING, target_id="V-004")
    assert got == [ev] and ev.is_incident()


def test_reservation_entity_state_rules():
    from src.backend.core.entities import Reservation
    from src.backend.core.enums import ReservationKind, ReservationStatus
    r = Reservation("R1", ReservationKind.VEHICLE, "U-S01", "HUB-METRO", "V-001")
    assert r.confirm() and r.status == ReservationStatus.CONFIRMED
    assert r.cancel() and not r.cancel()


def test_login_and_roles(client):
    assert client.post("/api/auth/login", json={"email": "an@hcmut.edu.vn"}).json()["role"] == "student"
    assert client.post("/api/auth/login", json={"email": "x@y.z"}).status_code == 401
    assert client.get("/api/operator/dashboard").status_code == 401           # no token
    assert client.get("/api/operator/dashboard", headers=STUDENT).status_code == 403
    assert client.get("/api/reservation/my-trips", headers=OPERATOR).status_code == 403


def test_shared_hub_endpoints(client):
    assert client.get("/api/health").json()["hubs"] == 4
    assert len(client.get("/api/hubs").json()) == 4
    assert client.get("/api/hubs/HUB-NOPE").status_code == 404
    assert client.get("/api/network/status").json()["totals"]["hubs"] == 4


def test_unfinished_endpoint_reports_owner(client):
    r = client.get("/api/operator/dashboard", headers=OPERATOR)
    assert r.status_code == 501 and r.json()["owner"] == "Member 3"
