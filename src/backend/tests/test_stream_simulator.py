"""Simulator + SSE hub (TV5)."""
import asyncio

import pytest

from src.backend.core.enums import ChargingPointStatus, EventType, VehicleStatus
from src.backend.core.event_bus import bus
from src.backend.core.simulator import Simulator
from src.backend.core.state_manager import network
from src.backend.core.stream import StreamHub, format_sse
from src.backend.core.enums import UserRole


def snapshot_state():
    return ({v.vehicle_id: (v.battery_level, v.status.value, v.hub_id) for v in network.vehicles.values()},
            {p.point_id: p.status.value for h in network.hubs.values() for p in h.charging_points.values()})


def run_ticks(seed, n=30):
    from src.backend.data.seed_data import seed_network
    seed_network(fresh=True)
    network.vehicles["V-001"].status = VehicleStatus.IN_USE
    network.vehicles["V-004"].status = VehicleStatus.CHARGING
    sim = Simulator(seed=seed)
    sim.rush_hour, sim.fault_probability = "on", 0.3
    for _ in range(n):
        sim.tick()
    return snapshot_state()


def test_same_seed_gives_same_run_and_other_seed_differs():
    assert run_ticks(7) == run_ticks(7)
    assert run_ticks(7) != run_ticks(8)


def test_battery_drains_when_riding_and_fills_when_charging():
    network.vehicles["V-001"].status = VehicleStatus.IN_USE
    network.vehicles["V-004"].status = VehicleStatus.CHARGING
    sim = Simulator(seed=1)
    sim.fault_probability = 0
    b1, b4 = network.vehicles["V-001"].battery_level, network.vehicles["V-004"].battery_level
    sim.tick()
    assert network.vehicles["V-001"].battery_level < b1
    assert network.vehicles["V-004"].battery_level > b4
    assert any(e.event_type == EventType.BATTERY_UPDATED for e in bus.history)


def test_full_battery_frees_the_vehicle():
    v = network.vehicles["V-004"]
    v.status, v.battery_level = VehicleStatus.CHARGING, 99
    sim = Simulator(seed=1)
    sim.tick()
    assert v.battery_level == 100 and v.status == VehicleStatus.AVAILABLE


def test_cut_telemetry_freezes_vehicle_and_marks_hub_connection_lost():
    network.vehicles["V-004"].status = VehicleStatus.CHARGING
    sim = Simulator(seed=1)
    sim.fault_probability = 0
    sim.cut_telemetry("vehicle", "V-004", True)
    before = network.vehicles["V-004"].battery_level
    for _ in range(5):
        sim.tick()
    assert network.vehicles["V-004"].battery_level == before
    assert not [e for e in bus.history if e.payload.get("vehicle_id") == "V-004"
                and e.event_type == EventType.BATTERY_UPDATED]
    sim.cut_telemetry("hub", "HUB-LIB", True)
    assert network.get_hub_status("HUB-LIB")["data_connection"] == "lost"
    sim.cut_telemetry("hub", "HUB-LIB", False)
    assert network.get_hub_status("HUB-LIB")["data_connection"] == "ok"
    with pytest.raises(ValueError):
        sim.cut_telemetry("planet", "x", True)


def test_charger_faults_emit_events_and_get_repaired():
    sim = Simulator(seed=3)
    sim.fault_probability = 1.0
    sim.tick()
    broken = [p for h in network.hubs.values() for p in h.charging_points.values()
              if p.status == ChargingPointStatus.OUT_OF_SERVICE]
    assert len(broken) == 1
    assert any(e.event_type == EventType.CHARGER_STATUS_CHANGED and e.payload["new_status"] == "out_of_service"
               for e in bus.history)
    sim.fault_probability = 0
    for _ in range(7):
        sim.tick()
    assert broken[0].status == ChargingPointStatus.AVAILABLE


def test_ambient_traffic_never_breaks_capacity():
    sim = Simulator(seed=11)
    sim.rush_hour, sim.fault_probability = "on", 0
    for _ in range(200):
        sim.tick()
    for hub in network.hubs.values():
        occupied = sum(1 for s in hub.parking_spaces.values() if s.is_occupied)
        assert occupied <= hub.capacity
        assert occupied == len([v for v in network.vehicles.values() if v.hub_id == hub.hub_id])


def test_simulator_never_touches_snapshots():
    snap = network.snapshot()
    before = {v.vehicle_id: (v.battery_level, v.hub_id) for v in snap.vehicles.values()}
    network.vehicles["V-001"].status = VehicleStatus.IN_USE
    sim = Simulator(seed=5)
    sim.rush_hour = "on"
    for _ in range(20):
        sim.tick()
    assert {v.vehicle_id: (v.battery_level, v.hub_id) for v in snap.vehicles.values()} == before


async def _drain(sub, n, timeout=1.0):
    return [await asyncio.wait_for(sub.queue.get(), timeout) for _ in range(n)]


def test_stream_hub_routes_messages_by_user_and_role():
    async def scenario():
        hub = StreamHub()
        hub.bind_loop(asyncio.get_running_loop())
        student = hub.subscribe("U-S01", UserRole.STUDENT)
        other = hub.subscribe("U-S02", UserRole.STUDENT)
        op = hub.subscribe("U-OP1", UserRole.OPERATOR)
        hub.publish("hub_updated", {"hub_id": "HUB-METRO"})
        hub.publish("payment_updated", {"x": 1}, user_id="U-S01")
        hub.publish("alert_created", {"a": 1}, operator_only=True)
        got_student = await _drain(student, 2)
        got_other = await _drain(other, 1)
        got_op = await _drain(op, 2)
        assert [m[0] for m in got_student] == ["hub_updated", "payment_updated"]
        assert [m[0] for m in got_other] == ["hub_updated"] and other.queue.empty()
        assert [m[0] for m in got_op] == ["hub_updated", "alert_created"]
        hub.unsubscribe(student)
        assert hub.subscriber_count == 2
    asyncio.run(scenario())


def test_stream_hub_is_thread_safe_and_bridges_bus_events():
    async def scenario():
        hub = StreamHub()
        loop = asyncio.get_running_loop()
        hub.bind_loop(loop)
        hub.attach()
        sub = hub.subscribe("U-OP1", UserRole.OPERATOR)
        await loop.run_in_executor(None, lambda: bus.emit(EventType.ALERT_RAISED, hub_id="HUB-METRO", alert_id="A9",
                                                           message="Metro almost full"))
        name, data = await asyncio.wait_for(sub.queue.get(), 1)
        assert name == "alert_created" and data["alert_id"] == "A9" and data["hub_id"] == "HUB-METRO"
    asyncio.run(scenario())


def test_stream_hub_drops_oldest_when_client_is_slow():
    async def scenario():
        hub = StreamHub()
        hub.bind_loop(asyncio.get_running_loop())
        sub = hub.subscribe("U", UserRole.STUDENT)
        for i in range(300):
            hub.publish("hub_updated", {"i": i})
        await asyncio.sleep(0)
        assert sub.queue.qsize() == 200
        assert (await sub.queue.get())[1]["i"] == 100
    asyncio.run(scenario())


def test_format_sse_wire_format():
    text = format_sse("hub_updated", {"seq": 7, "hub_id": "H"})
    assert text.startswith("event: hub_updated\nid: 7\ndata: ") and text.endswith("\n\n")


def test_stream_endpoint_requires_valid_token(client):
    assert client.get("/api/stream?token=garbage").status_code == 401
    assert client.get("/api/stream").status_code == 422
