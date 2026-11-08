"""End-to-end demo pipeline through the real HTTP API (TV5).

login -> hubs -> wallet top-up -> reserve -> pick up -> return -> operator sees state
-> What-if on a snapshot (real state untouched) -> demo reset.
Steps that belong to a module that is still a TODO are skipped, never faked.
"""
import pytest

from src.backend.core.database import persistence
from src.backend.core.enums import VehicleStatus
from src.backend.core.state_manager import network
from src.backend.modules.reservation import payment_gateway


def login(client, email):
    r = client.post("/api/auth/demo-login", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def sqlite_on(tmp_path):
    """Turn the global database ON for one test, like the real server does."""
    from src.backend.core.demo import register_persisted_stores
    register_persisted_stores()
    persistence.connect(str(tmp_path / "e2e.db"))
    persistence.flush()
    yield persistence
    persistence.close()


def test_student_pipeline_changes_wallet_and_is_saved_to_sqlite(client, sqlite_on):
    student = login(client, "an@hcmut.edu.vn")
    operator = login(client, "operator@hub.vn")

    hubs = client.get("/api/hubs").json()
    assert {h["hub_id"] for h in hubs} >= {"HUB-METRO", "HUB-KTX"}
    assert all(h["data_connection"] == "ok" for h in hubs)

    start_balance = client.get("/api/wallet", headers=student).json()["balance"]

    # top-up through the mock checkout (HMAC-signed callback, idempotent)
    order = client.post("/api/wallet/topup", headers=student, json={"amount": 50000}).json()
    order_id = order.get("order_id")
    sig = payment_gateway.compute_signature(order_id, 50000, "U-S01")
    cb = {"order_id": order_id, "amount": 50000, "user_id": "U-S01", "signature": sig, "success": True}
    assert client.post("/api/payments/callback", json=cb).status_code == 200
    client.post("/api/payments/callback", json=cb)                      # replay: must not credit twice
    assert client.get("/api/wallet", headers=student).json()["balance"] == start_balance + 50000
    assert client.post("/api/payments/callback", json={**cb, "signature": "bad"}).status_code == 400

    # reserve -> pick up -> return at another hub
    r = client.post("/api/reservation/vehicles/reserve", headers=student, json={"hub_id": "HUB-METRO"})
    assert r.status_code == 200, r.text
    reservation = r.json()
    rid = reservation.get("reservation_id")
    vid = reservation.get("vehicle_id") or reservation.get("resource_id")
    assert network.vehicles[vid].status == VehicleStatus.RESERVED
    assert client.get("/api/wallet", headers=student).json()["held_deposit"] > 0

    # a second student cannot take the same vehicle (409 / unavailable)
    other = login(client, "binh@hcmut.edu.vn")
    clash = client.post("/api/reservation/vehicles/reserve", headers=other,
                        json={"hub_id": "HUB-METRO", "vehicle_id": vid})
    assert clash.status_code in (409, 400)

    pick = client.post("/api/reservation/pickup", headers=student,
                       json={"reservation_id": rid, "vehicle_id": vid, "qr_code": reservation.get("qr_code", "")})
    assert pick.status_code == 200, pick.text
    trip_id = pick.json().get("trip_id")
    assert network.vehicles[vid].status == VehicleStatus.IN_USE

    done = client.post("/api/reservation/return", headers=student, json={"trip_id": trip_id, "hub_id": "HUB-KTX"})
    assert done.status_code == 200, done.text
    assert network.vehicles[vid].hub_id == "HUB-KTX"
    final = client.get("/api/wallet", headers=student).json()
    assert final["held_deposit"] == 0 and final["balance"] < start_balance + 50000   # trip fee charged
    assert client.get("/api/reservation/my-trips", headers=student).status_code == 200

    # operator side: dashboard data reflects the move
    status = client.get("/api/network/status", headers=operator).json()
    ktx = next(h for h in status["hubs"] if h["hub_id"] == "HUB-KTX")
    assert ktx["vehicles_total"] == 5          # 4 seeded + the returned one

    # everything above was written to SQLite by the request middleware
    counts = persistence.table_counts()
    assert counts["reservations"] >= 1 and counts["events"] >= 3
    assert counts["module_state"] >= 3                                 # wallet, ledger, trip
    row = persistence._conn.execute("SELECT hub_id,status FROM vehicles WHERE vehicle_id=?", (vid,)).fetchone()
    assert row["hub_id"] == "HUB-KTX"
    info = client.get("/api/demo/database", headers=operator).json()
    assert info["enabled"] and info["tables"]["vehicles"] == 34


def test_restart_restores_wallet_and_trips(client, sqlite_on, tmp_path):
    student = login(client, "an@hcmut.edu.vn")
    client.post("/api/reservation/vehicles/reserve", headers=student, json={"hub_id": "HUB-METRO"})
    held = client.get("/api/wallet", headers=student).json()
    assert held["held_deposit"] > 0
    path = persistence.path
    persistence.close()

    # "restart": wipe memory completely, then load the file
    payment_gateway.reset_ledger()
    network.reset()
    persistence.connect(path)
    assert persistence.load() is True
    again = client.get("/api/wallet", headers=login(client, "an@hcmut.edu.vn")).json()
    assert again["held_deposit"] == held["held_deposit"] and again["balance"] == held["balance"]
    assert any(r.user_id == "U-S01" for r in network.reservations.values())


def test_what_if_does_not_change_real_state(client):
    operator = login(client, "operator@hub.vn")
    templates = client.get("/api/simulation/templates", headers=operator)
    if templates.status_code == 501:
        pytest.skip("What-if (TV4) not implemented yet")
    before = ({v.vehicle_id: (v.battery_level, v.status, v.hub_id) for v in network.vehicles.values()},
              network.get_network_status()["totals"])
    items = templates.json()
    tid = (items[0].get("id") or items[0].get("template_id")) if items else None
    sc = client.post("/api/simulation/scenarios", headers=operator,
                     json={"kind": "metro_surge", "params": {}, "template_id": tid})
    if sc.status_code == 501:
        pytest.skip("What-if (TV4) not implemented yet")
    sid = sc.json().get("scenario_id")
    run = client.post(f"/api/simulation/scenarios/{sid}/run", headers=operator)
    if run.status_code == 501:
        pytest.skip("What-if run (TV4) not implemented yet")
    after = ({v.vehicle_id: (v.battery_level, v.status, v.hub_id) for v in network.vehicles.values()},
             network.get_network_status()["totals"])
    assert before == after


def test_demo_reset_restores_seed_data_and_wallets(client, sqlite_on):
    student = login(client, "an@hcmut.edu.vn")
    operator = login(client, "operator@hub.vn")
    client.post("/api/reservation/vehicles/reserve", headers=student, json={"hub_id": "HUB-METRO"})
    network.vehicles["V-005"].battery_level = 1
    assert client.post("/api/demo/reset", headers=student).status_code == 403
    r = client.post("/api/demo/reset", headers=operator)
    assert r.status_code == 200 and r.json()["vehicles"] == 34
    assert network.vehicles["V-005"].battery_level == 90 and not network.reservations
    assert client.get("/api/wallet", headers=student).json()["held_deposit"] == 0
    assert persistence.table_counts()["reservations"] == 0
    assert persistence.table_counts()["vehicles"] == 34


def test_operator_demo_switches_over_http(client):
    operator = login(client, "operator@hub.vn")
    r = client.post("/api/demo/telemetry", headers=operator, json={"target_type": "hub", "target_id": "HUB-LIB"})
    assert r.status_code == 200 and "HUB-LIB" in r.json()["cut_hubs"]
    assert client.get("/api/hubs/HUB-LIB").json()["data_connection"] == "lost"
    client.post("/api/demo/telemetry", headers=operator, json={"target_type": "hub", "target_id": "HUB-LIB", "cut": False})
    assert client.get("/api/hubs/HUB-LIB").json()["data_connection"] == "ok"
    assert client.post("/api/demo/telemetry", headers=operator,
                       json={"target_type": "vehicle", "target_id": "NOPE"}).status_code == 404
    cfg = client.post("/api/demo/simulator", headers=operator, json={"seed": 5, "fault_probability": 0.5}).json()
    assert cfg["seed"] == 5 and cfg["fault_probability"] == 0.5
    assert client.post("/api/demo/simulator", headers=operator, json={"fault_probability": 3}).status_code == 422
    assert client.post("/api/demo/simulator/tick", headers=operator).status_code == 200
