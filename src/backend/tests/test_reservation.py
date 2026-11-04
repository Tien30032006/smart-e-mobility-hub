"""Tests for Member 1 (U1-U9). Comprehensive test suite verifying business logic,
concurrency, payment processing, smart lock actuation, and event emission.
"""
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from src.backend.data.seed_data import seed_network
from src.backend.core.entities import utcnow
from src.backend.core.enums import EventType, ReservationKind, ReservationStatus, VehicleStatus
from src.backend.core.event_bus import bus
from src.backend.core.state_manager import network
from src.backend.modules.reservation import payment_gateway, repository, service, smart_lock


@pytest.fixture(autouse=True)
def setup_network():
    """Reset network and modules before each test."""
    bus.clear()
    seed_network()
    service.reset_module_state()
    yield


def test_search_returns_hubs_with_available_vehicles():
    """U1: Search hubs and filter by vehicle type and battery level."""
    # Unfiltered search
    hubs = service.search_hubs_and_vehicles()
    assert len(hubs) > 0
    metro = next(h for h in hubs if h["hub_id"] == "HUB-METRO")
    assert metro["free_spaces"] > 0
    assert metro["vehicles_available"] >= 3

    # Filter with minimum battery
    filtered = service.search_hubs_and_vehicles(min_battery=80)
    for h in filtered:
        for v in h["vehicles"]:
            assert v["battery_level"] >= 80

    # Filter by vehicle type
    bikes_only = service.search_hubs_and_vehicles(vehicle_type="e-bike")
    for h in bikes_only:
        for v in h["vehicles"]:
            assert v["type"] == "e-bike"

    # Detail lookup
    detail = service.get_vehicle_detail("V-001")
    assert detail["vehicle_id"] == "V-001"
    assert detail["status"] == "available"
    assert detail["estimated_range_km"] > 0


def test_reserve_vehicle_marks_vehicle_reserved_and_holds_deposit():
    """U2: Reserve a vehicle, hold deposit, and emit VEHICLE_RESERVED."""
    events = []
    bus.subscribe(EventType.VEHICLE_RESERVED, lambda ev: events.append(ev))

    res = service.reserve_vehicle("U-S01", "HUB-METRO", vehicle_id="V-001")
    assert res.status == ReservationStatus.CONFIRMED
    assert res.deposit_amount == 50000.0
    assert res.resource_id == "V-001"

    # Verify vehicle is now RESERVED
    veh = network.get_vehicle("V-001")
    assert veh.status == VehicleStatus.RESERVED

    # Verify deposit in ledger
    tx_id = res.notes.split("deposit_tx:")[1].split()[0]
    tx = payment_gateway.get_transaction(tx_id)
    assert tx is not None
    assert tx["status"] == "authorized"
    assert tx["amount"] == 50000.0

    # Verify event emitted
    assert len(events) == 1
    assert events[0].payload["vehicle_id"] == "V-001"


def test_two_students_cannot_reserve_the_same_vehicle():
    """U2 (concurrency): Two students reserving the exact same vehicle -> only one succeeds."""
    results = []
    errors = []

    def try_reserve(user_id: str):
        try:
            r = service.reserve_vehicle(user_id, "HUB-METRO", vehicle_id="V-001")
            results.append(r)
        except HTTPException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=try_reserve, args=("U-S01",))
    t2 = threading.Thread(target=try_reserve, args=("U-S02",))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one succeeded
    assert len(results) == 1
    assert len(errors) == 1
    assert errors[0].status_code == 409


def test_reserve_parking_slot_blocks_the_slot_for_others():
    """U3: Reserve parking space and verify capacity is decremented."""
    events = []
    bus.subscribe(EventType.PARKING_RESERVED, lambda ev: events.append(ev))

    metro = network.get_hub("HUB-METRO")
    initial_free = metro.get_available_resources()

    res = service.reserve_parking_slot("U-S01", "HUB-METRO", mode="shared_return")
    assert res.kind == ReservationKind.PARKING
    assert res.status == ReservationStatus.CONFIRMED

    # Slot should be reserved
    space = metro.parking_spaces[res.resource_id]
    assert space.reserved_by == res.reservation_id
    assert metro.get_available_resources() == initial_free - 1

    # Event emitted
    assert len(events) == 1
    assert events[0].payload["space_id"] == space.space_id


def test_cancel_reservation_releases_resource_and_refunds():
    """U4: Cancel reservation -> vehicle returned to AVAILABLE and deposit refunded."""
    events = []
    bus.subscribe(EventType.RESERVATION_CANCELLED, lambda ev: events.append(ev))

    res = service.reserve_vehicle("U-S01", "HUB-METRO", vehicle_id="V-001")
    tx_id = res.notes.split("deposit_tx:")[1].split()[0]

    cancelled = service.cancel_reservation(res.reservation_id, user_id="U-S01", reason="changed_mind")
    assert cancelled.status == ReservationStatus.CANCELLED

    # Vehicle released
    veh = network.get_vehicle("V-001")
    assert veh.status == VehicleStatus.AVAILABLE

    # Deposit refunded
    tx = payment_gateway.get_transaction(tx_id)
    assert tx["status"] == "refunded"
    assert tx["refunded_amount"] == 50000.0

    # Event emitted
    assert len(events) == 1
    assert events[0].payload["reservation_id"] == res.reservation_id
    assert events[0].payload["reason"] == "changed_mind"


def test_pickup_requires_valid_reservation_and_unlocks():
    """U5: Valid reservation unlock vs invalid QR rejection."""
    events = []
    bus.subscribe(EventType.VEHICLE_PICKED_UP, lambda ev: events.append(ev))

    res = service.reserve_vehicle("U-S01", "HUB-METRO", vehicle_id="V-001")

    # Mismatched QR code should fail
    with pytest.raises(HTTPException) as exc:
        service.pick_up_vehicle("U-S01", reservation_id=res.reservation_id, qr_code="QR-WRONG")
    assert exc.value.status_code == 400

    # Valid pickup
    trip = service.pick_up_vehicle("U-S01", reservation_id=res.reservation_id, qr_code="QR-V-001")
    assert trip["status"] == "active"
    assert trip["vehicle_id"] == "V-001"

    # Vehicle in use and lock unlocked
    veh = network.get_vehicle("V-001")
    assert veh.status == VehicleStatus.IN_USE
    assert smart_lock.get_lock_status("V-001") == "unlocked"

    # Event emitted
    assert len(events) == 1
    assert events[0].payload["vehicle_id"] == "V-001"


def test_return_vehicle_to_full_hub_is_rejected():
    """U6: Returning vehicle to a 100% full hub is rejected with 409 unless slot was reserved."""
    # U-S01 picks up vehicle V-001 from METRO
    res = service.reserve_vehicle("U-S01", "HUB-METRO", vehicle_id="V-001")
    trip = service.pick_up_vehicle("U-S01", reservation_id=res.reservation_id, qr_code="V-001")

    # Fill HUB-LIB completely (capacity 8)
    lib = network.get_hub("HUB-LIB")
    for space in lib.parking_spaces.values():
        space.occupy("DUMMY")

    assert lib.get_available_resources() == 0

    # Attempting to return to full HUB-LIB without reserved dock raises 409
    with pytest.raises(HTTPException) as exc:
        service.return_vehicle("U-S01", trip_id=trip["trip_id"], hub_id="HUB-LIB")
    assert exc.value.status_code == 409
    assert "100% full" in exc.value.detail

    # Returning to HUB-KTX (has free space) succeeds
    receipt = service.return_vehicle("U-S01", trip_id=trip["trip_id"], hub_id="HUB-KTX")
    assert receipt["status"] == "completed"
    assert receipt["rental_fee"] >= 10000.0
    assert receipt["deposit_refunded"] <= 40000.0
    assert smart_lock.get_lock_status("V-001") == "locked"


def test_report_issue_emits_issue_reported_event():
    """U7: Reporting severe issue flags vehicle as MAINTENANCE and emits ISSUE_REPORTED."""
    events = []
    bus.subscribe(EventType.ISSUE_REPORTED, lambda ev: events.append(ev))

    issue = service.report_issue(
        user_id="U-S01",
        target_type="vehicle",
        target_id="V-001",
        category="brake_failure",
        description="Front brake is unresponsive",
    )

    assert issue["issue_id"].startswith("ISSUE-")
    assert issue["status"] == "open"

    # Safety action: vehicle marked MAINTENANCE
    veh = network.get_vehicle("V-001")
    assert veh.status == VehicleStatus.MAINTENANCE

    # Event emitted with exact contract payload for Member 3
    assert len(events) == 1
    assert events[0].payload["issue_id"] == issue["issue_id"]
    assert events[0].payload["target_type"] == "vehicle"
    assert events[0].payload["target_id"] == "V-001"
    assert events[0].payload["category"] == "brake_failure"


def test_walk_up_pickup_without_reservation():
    """U5 (walk-up): Student directly rents an available vehicle without prior reservation."""
    trip = service.pick_up_vehicle(user_id="U-S01", vehicle_id="V-002", qr_code="QR-V-002")
    assert trip["status"] == "active"
    assert trip["vehicle_id"] == "V-002"

    veh = network.get_vehicle("V-002")
    assert veh.status == VehicleStatus.IN_USE

    # Settle trip
    receipt = service.return_vehicle(user_id="U-S01", trip_id=trip["trip_id"], hub_id="HUB-METRO")
    assert receipt["status"] == "completed"


def test_reservation_expiry_frees_vehicle():
    """Reservation expiration: 15-minute timeout automatically expires hold and refunds deposit."""
    res = service.reserve_vehicle("U-S01", "HUB-METRO", vehicle_id="V-001")
    assert network.get_vehicle("V-001").status == VehicleStatus.RESERVED

    # Fast-forward 16 minutes
    future_time = utcnow() + timedelta(minutes=16)
    expired = service.check_expired_reservations(now=future_time)

    assert res.reservation_id in expired
    assert network.get_vehicle("V-001").status == VehicleStatus.AVAILABLE


def test_api_reservation_endpoints(client):
    """Test reservation API routes end-to-end via FastAPI TestClient."""
    from src.backend.tests.conftest import STUDENT

    # GET /api/reservation/search
    res = client.get("/api/reservation/search")
    assert res.status_code == 200
    hubs = res.json()
    assert len(hubs) > 0

    # GET /api/reservation/vehicles/V-001
    res = client.get("/api/reservation/vehicles/V-001")
    assert res.status_code == 200
    assert res.json()["vehicle_id"] == "V-001"

    # POST /api/reservation/vehicles/reserve
    res = client.post(
        "/api/reservation/vehicles/reserve",
        json={"hub_id": "HUB-METRO", "vehicle_id": "V-001"},
        headers=STUDENT,
    )
    assert res.status_code == 200
    res_data = res.json()
    res_id = res_data["reservation_id"]
    assert res_data["deposit_amount"] == 50000.0

    # POST /api/reservation/pickup
    res = client.post(
        "/api/reservation/pickup",
        json={"reservation_id": res_id, "qr_code": "QR-V-001"},
        headers=STUDENT,
    )
    assert res.status_code == 200
    trip = res.json()
    trip_id = trip["trip_id"]

    # POST /api/reservation/return
    res = client.post(
        "/api/reservation/return",
        json={"trip_id": trip_id, "hub_id": "HUB-METRO"},
        headers=STUDENT,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "completed"

    # GET /api/reservation/my-trips
    res = client.get("/api/reservation/my-trips", headers=STUDENT)
    assert res.status_code == 200
    my_data = res.json()
    assert len(my_data["history"]) >= 1

    # POST /api/reservation/issues
    res = client.post(
        "/api/reservation/issues",
        json={
            "target_type": "vehicle",
            "target_id": "V-001",
            "category": "battery_danger",
            "description": "Battery overheating",
            "photo_urls": [],
        },
        headers=STUDENT,
    )
    assert res.status_code == 200
    assert res.json()["issue_id"].startswith("ISSUE-")


def test_student_wallet_topup_and_callback(client):
    """Test wallet balance, top-up order generation, HMAC verification & idempotent callback."""
    from src.backend.tests.conftest import STUDENT

    # GET /api/wallet (initial balance: 200,000 VND)
    res = client.get("/api/wallet", headers=STUDENT)
    assert res.status_code == 200
    w = res.json()
    assert w["balance"] == 200000.0
    assert w["available_balance"] == 200000.0

    # POST /api/wallet/topup (create 100,000 VND top-up)
    res = client.post("/api/wallet/topup", json={"amount": 100000}, headers=STUDENT)
    assert res.status_code == 200
    order = res.json()
    assert order["order_id"].startswith("ORD-")
    assert order["amount"] == 100000
    assert "signature" in order
    assert "mock-checkout.html" in order["pay_url"]

    # Invalid HMAC signature should be rejected with 400
    fake_callback = {
        "order_id": order["order_id"],
        "amount": 100000,
        "user_id": "U-S01",
        "signature": "fake-bad-signature",
        "success": True,
    }
    res = client.post("/api/payments/callback", json=fake_callback)
    assert res.status_code == 400

    # Valid callback should credit wallet
    valid_callback = {
        "order_id": order["order_id"],
        "amount": 100000,
        "user_id": "U-S01",
        "signature": order["signature"],
        "success": True,
    }
    res = client.post("/api/payments/callback", json=valid_callback)
    assert res.status_code == 200
    cb_data = res.json()
    assert cb_data["status"] == "completed"
    assert cb_data["new_balance"] == 300000.0
    assert cb_data["idempotent"] is False

    # Idempotent call: duplicate callback does not credit twice
    res = client.post("/api/payments/callback", json=valid_callback)
    assert res.status_code == 200
    assert res.json()["idempotent"] is True

    # Verify wallet has exactly 300,000 VND
    res = client.get("/api/wallet", headers=STUDENT)
    assert res.json()["balance"] == 300000.0

    # GET /api/wallet/transactions
    res = client.get("/api/wallet/transactions", headers=STUDENT)
    assert res.status_code == 200
    txs = res.json()
    assert any(t["type"] == "topup" for t in txs)


