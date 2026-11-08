"""Tests for Member 3 (UC01-UC-OP09).

Most tests call the module functions directly (fast, no HTTP); the last block checks the
HTTP layer (auth, status codes, payload shape). Every test starts from the seeded network
(``fresh_state`` fixture in conftest) with the operations event handlers registered.
"""
from datetime import timedelta

import pytest
from fastapi import HTTPException

from src.backend.core.entities import EVehicle, Reservation, new_id, utcnow
from src.backend.core.enums import (ChargingPointStatus, EventType, ReservationKind, ReservationStatus,
                                    VehicleStatus)
from src.backend.core.event_bus import bus
from src.backend.core.state_manager import HubNotFound, network
from src.backend.modules.charging.repository import repository as charging_repo
from src.backend.modules.charging.service import submit_charging_request
from src.backend.modules.operations import (charging_oversight, incident_handler, redistribution, service,
                                            store as ops_store)
from src.backend.tests.conftest import OPERATOR, STUDENT


@pytest.fixture(autouse=True)
def ops(fresh_state):
    service.register_event_handlers()          # conftest clears the bus before every test
    charging_repo.store                        # bind the charging store to the fresh network
    yield


def crowd(hub_id, n, battery=80, prefix="X"):
    for i in range(n):
        network.register_vehicle(EVehicle(f"{prefix}{i}", battery_level=battery, hub_id=hub_id))


def report(vehicle_id, issue_id="IS-1", category="brake"):
    bus.emit(EventType.ISSUE_REPORTED, hub_id=network.get_vehicle(vehicle_id).hub_id, issue_id=issue_id,
             target_type="vehicle", target_id=vehicle_id, category=category, description="reported")
    return next(i for i in incident_handler.list_incidents("open") if i["target_id"] == vehicle_id)


def reserve(vehicle_id, user_id="U-S01"):
    r = Reservation(new_id("R"), ReservationKind.VEHICLE, user_id, network.get_vehicle(vehicle_id).hub_id,
                    vehicle_id, status=ReservationStatus.CONFIRMED)
    network.reservations[r.reservation_id] = r
    network.get_vehicle(vehicle_id).status = VehicleStatus.RESERVED
    return r


# ----------------------------------------------------------------------------- UC01
def test_dashboard_totals_match_network_status():
    """UC01"""
    dash, status = service.get_dashboard(), network.get_network_status()
    for key in ("vehicles_available", "vehicles_charging", "free_spaces", "charging_points_free"):
        assert dash["totals"][key] == status["totals"][key]
    assert len(dash["hubs"]) == len(dash["markers"]) == len(network.hubs)
    assert "alerts_open" in dash["totals"]


def test_hub_detail_lists_vehicles_spaces_and_ports():
    detail = service.get_hub_detail("HUB-KTX")
    assert {v["vehicle_id"] for v in detail["vehicles"]} == {v.vehicle_id for v in network.vehicles_at("HUB-KTX")}
    assert detail["charging_points"] and detail["parking_spaces"]
    assert set(detail["battery_summary"]) == {"low", "medium", "high"}
    with pytest.raises(HubNotFound):
        service.get_hub_detail("HUB-NOPE")


def test_offline_hub_is_grey_with_message():
    """UC01 alt 5a"""
    network.cut_hubs.add("HUB-LIB")
    lib = next(h for h in service.get_dashboard()["hubs"] if h["hub_id"] == "HUB-LIB")
    assert lib["tone"] == "offline" and lib["offline_message"] == "Data connection lost at Hub Central Library"


# ----------------------------------------------------------------------------- UC02
def test_alert_raised_when_hub_near_capacity():
    """UC02"""
    crowd("HUB-LIB", 6)
    seen = []
    bus.subscribe(EventType.HUB_NEAR_CAPACITY, seen.append)
    first = [a for a in service.list_alerts() if a["type"] == "hub_near_capacity"]
    again = [a for a in service.list_alerts() if a["type"] == "hub_near_capacity"]
    assert len(first) == len(again) == 1 and len(seen) == 1          # de-duplicated, one event
    assert first[0]["status"] == "unread" and first[0]["suggested_actions"]


def test_acknowledge_alert_marks_handled():
    """UC02"""
    crowd("HUB-LIB", 6)
    alert = next(a for a in service.list_alerts("open") if a["type"] == "hub_near_capacity")
    done = service.acknowledge_alert(alert["alert_id"], "U-OP1")
    assert done["status"] == "acknowledged" and done["acknowledged_by"] == "U-OP1" and done["acknowledged_at"]
    assert alert["alert_id"] not in {a["alert_id"] for a in service.list_alerts("open")}
    with pytest.raises(HTTPException) as err:
        service.acknowledge_alert("AL-missing", "U-OP1")
    assert err.value.status_code == 404


def test_alert_auto_resolves_when_condition_disappears():
    """UC02 alt 7a"""
    crowd("HUB-LIB", 6)
    alert = next(a for a in service.list_alerts() if a["type"] == "hub_near_capacity")
    for i in range(4):
        network.move_vehicle(f"X{i}", "HUB-METRO")
    assert next(a for a in service.list_alerts("handled") if a["alert_id"] == alert["alert_id"])["status"] == \
        "resolved_by_system"


def test_alerts_sorted_critical_first_and_filter_validated():
    network.cut_hubs.add("HUB-KTX")                                   # critical
    network.get_hub("HUB-KTX")                                        # (offline hub raises no other alert)
    severities = [a["severity"] for a in service.list_alerts()]
    assert severities == sorted(severities, key={"critical": 0, "warning": 1, "info": 2}.get)
    with pytest.raises(HTTPException) as err:
        service.list_alerts("bogus")
    assert err.value.status_code == 400


# ----------------------------------------------------------------------------- UC03 / UC-OP04
def test_proposal_moves_from_surplus_to_shortage_hub():
    """UC03"""
    crowd("HUB-METRO", 10, battery=60, prefix="M")                    # Metro nearly full, Library has no vehicle
    plans = redistribution.propose_redistribution()
    assert plans and all(set(p) == {"from_hub", "to_hub", "vehicle_ids", "reason"} for p in plans)
    plan = plans[0]
    assert plan["from_hub"] == "HUB-METRO" and plan["to_hub"] in ("HUB-LIB", "HUB-CAMPUS")
    for vid in plan["vehicle_ids"]:
        vehicle = network.get_vehicle(vid)
        assert vehicle.status == VehicleStatus.AVAILABLE and vehicle.is_shared and vehicle.battery_level >= 30


def test_proposal_never_picks_reserved_or_maintenance_vehicles():
    crowd("HUB-METRO", 10, battery=60, prefix="M")
    network.get_vehicle("M0").status = VehicleStatus.RESERVED
    network.get_vehicle("M1").status = VehicleStatus.MAINTENANCE
    picked = {vid for p in redistribution.propose_redistribution() for vid in p["vehicle_ids"]}
    assert not picked & {"M0", "M1"}


def test_relocation_order_moves_vehicles_on_completion():
    """UC-OP04"""
    crowd("HUB-METRO", 10, battery=60, prefix="M")
    plan = redistribution.propose_redistribution()[0]
    free_before = network.get_hub(plan["to_hub"]).get_available_resources()
    order = redistribution.create_relocation_order(plan, "U-OP1")
    assert order["status"] == "pending"
    assert all(network.get_vehicle(v).status == VehicleStatus.RELOCATING for v in plan["vehicle_ids"])
    assert network.get_hub(plan["to_hub"]).get_available_resources() == free_before - len(plan["vehicle_ids"])
    done = redistribution.complete_relocation_order(order["order_id"])
    assert done["status"] == "done"
    for vid in plan["vehicle_ids"]:
        vehicle = network.get_vehicle(vid)
        assert vehicle.hub_id == plan["to_hub"] and vehicle.status == VehicleStatus.AVAILABLE
    assert not any(s.reserved_by for s in network.get_hub(plan["to_hub"]).parking_spaces.values())


def test_relocation_order_rejects_bad_requests():
    """UC03 alt 4a / 5a"""
    def attempt(**plan):
        with pytest.raises(HTTPException) as err:
            redistribution.create_relocation_order(plan, "U-OP1")
        return err.value
    base = {"from_hub": "HUB-METRO", "to_hub": "HUB-LIB", "vehicle_ids": ["V-001"]}
    assert attempt(**{**base, "to_hub": "HUB-METRO"}).status_code == 400
    assert attempt(**{**base, "vehicle_ids": []}).status_code == 400
    network.get_vehicle("V-002").status = VehicleStatus.RESERVED         # race: a student just reserved it
    err = attempt(**{**base, "vehicle_ids": ["V-001", "V-002"]})
    assert err.status_code == 409 and "V-002" in err.detail
    assert network.get_vehicle("V-001").status == VehicleStatus.AVAILABLE   # nothing half-applied
    crowd("HUB-LIB", 7)                                                  # destination full
    assert "capacity" in attempt(**base).detail


def test_cancel_order_releases_vehicles_and_spaces():
    order = redistribution.create_relocation_order(
        {"from_hub": "HUB-METRO", "to_hub": "HUB-CAMPUS", "vehicle_ids": ["V-001"]}, "U-OP1")
    redistribution.cancel_relocation_order(order["order_id"], "U-OP1")
    assert network.get_vehicle("V-001").status == VehicleStatus.AVAILABLE
    assert not any(s.reserved_by for s in network.get_hub("HUB-CAMPUS").parking_spaces.values())
    with pytest.raises(HTTPException):
        redistribution.complete_relocation_order(order["order_id"])


def test_staff_rejection_and_timeout_alert_the_operator():
    order = redistribution.create_relocation_order(
        {"from_hub": "HUB-METRO", "to_hub": "HUB-CAMPUS", "vehicle_ids": ["V-001"]}, "U-OP1")
    redistribution.reject_relocation_order(order["order_id"], "s1", "no truck")
    assert any(a["type"] == "relocation_rejected" for a in service.list_alerts())
    ops_store.current().orders[order["order_id"]]["created_at"] = (utcnow() - timedelta(minutes=30)).isoformat()
    assert any(a["type"] == "relocation_unassigned" for a in service.list_alerts())
    redistribution.assign_relocation_order(order["order_id"])
    assert not [a for a in service.list_alerts("open") if a["type"] == "relocation_unassigned"]


def test_network_redistribute_vehicles_delegates_to_operations():
    crowd("HUB-METRO", 8, battery=70, prefix="M")
    assert network.redistribute_vehicles("HUB-METRO", "HUB-LIB") is True
    assert network.redistribute_vehicles("HUB-LIB", "HUB-LIB") is False


# ----------------------------------------------------------------------------- UC05 / UC-OP06 / UC-OP07
def test_issue_report_opens_incident_and_alert():
    incident = report("V-001")
    assert incident["status"] == "open" and incident["hub_id"] == "HUB-METRO"
    assert any(a["type"] == "incident" for a in service.list_alerts())
    report("V-001", issue_id="IS-2")                                     # same device -> same incident
    assert len(incident_handler.list_incidents("open")) == 1
    assert incident_handler.list_incidents("open")[0]["report_count"] == 2


def test_bad_issue_payloads_are_ignored():
    bus.emit(EventType.ISSUE_REPORTED, issue_id="I", target_type="vehicle", target_id="GHOST", category="x")
    bus.emit(EventType.ISSUE_REPORTED, issue_id="I", target_type="spaceship", target_id="V-001", category="x")
    assert incident_handler.list_incidents() == []


def test_handle_incident_puts_vehicle_in_maintenance_and_opens_ticket():
    """UC05/UC-OP06"""
    incident = report("V-002")
    assert incident_handler.handle_incident(incident["incident_id"], "U-OP1") is True
    assert network.get_vehicle("V-002").status == VehicleStatus.MAINTENANCE
    handled = incident_handler.list_incidents("in_maintenance")[0]
    ticket = handled["ticket"]
    assert ticket["device"] == "V-002" and ticket["status"] == "open"
    assert not [a for a in service.list_alerts("open") if a["type"] == "incident"]   # alert closed
    with pytest.raises(HTTPException) as err:                                        # not twice
        incident_handler.handle_incident(incident["incident_id"], "U-OP1")
    assert err.value.status_code == 409


def test_incident_cancels_affected_reservation():
    """UC-OP07 (UC05 alt 5a)"""
    res = reserve("V-001")
    incident = report("V-001")
    impact = incident_handler.get_incident_impact(incident["incident_id"])
    assert impact["requires_confirmation"] and len(impact["affected_reservations"]) == 1
    with pytest.raises(HTTPException) as err:                            # needs the Operator's confirmation
        incident_handler.handle_incident_detailed(incident["incident_id"], "U-OP1")
    assert err.value.status_code == 409 and res.status == ReservationStatus.CONFIRMED
    out = incident_handler.handle_incident_detailed(incident["incident_id"], "U-OP1", note="cable",
                                                    priority="high", confirm_cancel=True)
    assert res.status == ReservationStatus.CANCELLED
    assert network.get_vehicle("V-001").status == VehicleStatus.MAINTENANCE
    assert out["ticket"]["priority"] == "high"
    assert out["cancelled_reservations"][0]["replacement"]               # suggestion for the student
    assert [n for n in ops_store.current().notifications.values() if n["to"] == "U-S01"]


def test_vehicle_in_use_cannot_go_to_maintenance():
    network.get_vehicle("V-003").status = VehicleStatus.IN_USE
    incident = report("V-003")
    with pytest.raises(HTTPException) as err:
        incident_handler.handle_incident(incident["incident_id"], "U-OP1")
    assert err.value.status_code == 409 and network.get_vehicle("V-003").status == VehicleStatus.IN_USE


def test_charger_fault_opens_incident_and_handling_blocks_the_port():
    point = network.get_hub("HUB-KTX").charging_points["HUB-KTX-C01"]
    point.status = ChargingPointStatus.OUT_OF_SERVICE
    bus.emit(EventType.CHARGER_STATUS_CHANGED, hub_id="HUB-KTX", point_id=point.point_id,
             new_status="out_of_service", origin="core.simulator")
    incident = incident_handler.list_incidents("open")[0]
    assert incident["source"] == "device_signal"
    incident_handler.handle_incident(incident["incident_id"], "U-OP1")
    assert len(incident_handler.list_incidents()) == 1                   # the port event did not open a duplicate
    incident_handler.resolve_incident(incident["incident_id"], "U-OP1")
    assert point.status == ChargingPointStatus.AVAILABLE


def test_resolve_incident_returns_vehicle_to_service_and_closes_ticket():
    incident = report("V-002")
    ticket = incident_handler.handle_incident_detailed(incident["incident_id"], "U-OP1")["ticket"]
    incident_handler.resolve_incident(incident["incident_id"], "U-OP1")
    assert network.get_vehicle("V-002").status == VehicleStatus.AVAILABLE
    assert ops_store.current().tickets[ticket["ticket_id"]]["status"] == "closed"


# ----------------------------------------------------------------------------- UC-OP08 / UC-OP09
def test_charging_view_explains_every_row():
    """UC-OP08"""
    submit_charging_request("U-S02", "PV-001", "HUB-KTX")
    view = charging_oversight.view_charging_allocation("HUB-KTX")
    assert view["queue"] and all(r["reason"]["code"] and "priority" in r for r in view["queue"])


def test_manual_override_requires_reason_and_is_audited():
    """UC-OP09"""
    session = submit_charging_request("U-S02", "PV-001", "HUB-KTX")
    for blank in ("", "   "):
        with pytest.raises(HTTPException) as err:
            charging_oversight.override_priority("HUB-KTX", session.session_id, "U-OP1", blank)
        assert err.value.status_code == 400
    assert not ops_store.current().audit                                  # a refused override leaves no trace
    result = charging_oversight.override_priority("HUB-KTX", session.session_id, "U-OP1", "exam today")
    entry = charging_oversight.list_override_audit("HUB-KTX")[0]
    assert entry["audit_id"] == result["audit_id"] and entry["reason"] == "exam today"
    assert entry["operator_id"] == "U-OP1" and entry["session_id"] == session.session_id


# ----------------------------------------------------------------------------- HTTP layer
def test_http_requires_an_operator(client):
    assert client.get("/api/operator/dashboard").status_code == 401
    assert client.get("/api/operator/dashboard", headers=STUDENT).status_code == 403
    assert client.get("/api/operator/dashboard", headers=OPERATOR).status_code == 200


def test_http_alert_flow(client):
    crowd("HUB-LIB", 6)
    alerts = client.get("/api/operator/alerts?status=open", headers=OPERATOR).json()
    alert = next(a for a in alerts if a["type"] == "hub_near_capacity")
    r = client.post(f"/api/operator/alerts/{alert['alert_id']}/acknowledge", headers=OPERATOR)
    assert r.status_code == 200 and r.json()["status"] == "acknowledged"
    assert client.get("/api/operator/hubs/HUB-NOPE", headers=OPERATOR).status_code == 404
    assert client.get("/api/operator/alerts?status=bogus", headers=OPERATOR).status_code == 400


def test_http_incident_and_relocation_flow(client):
    incident = report("V-001")
    res = reserve("V-001")
    url = f"/api/operator/incidents/{incident['incident_id']}"
    assert client.get(url + "/impact", headers=OPERATOR).json()["requires_confirmation"] is True
    assert client.post(url + "/handle", json={}, headers=OPERATOR).status_code == 409
    done = client.post(url + "/handle", json={"note": "brake", "priority": "high", "confirm_cancel": True},
                       headers=OPERATOR)
    assert done.status_code == 200 and done.json()["ticket"]["priority"] == "high"
    assert res.status == ReservationStatus.CANCELLED
    plan = {"from_hub": "HUB-METRO", "to_hub": "HUB-CAMPUS", "vehicle_ids": ["V-002"], "reason": "balance"}
    order = client.post("/api/operator/redistribution/orders", json=plan, headers=OPERATOR)
    assert order.status_code == 200
    oid = order.json()["order_id"]
    assert client.post(f"/api/operator/redistribution/orders/{oid}/complete", headers=OPERATOR).json()["status"] == "done"
    assert client.get("/api/operator/redistribution/orders", headers=OPERATOR).json()[0]["order_id"] == oid


def test_http_charging_override_needs_reason(client):
    session = submit_charging_request("U-S02", "PV-001", "HUB-KTX")
    body = {"hub_id": "HUB-KTX", "session_id": session.session_id, "reason": ""}
    assert client.post("/api/operator/charging/override", json=body, headers=OPERATOR).status_code == 400
    body["reason"] = "exam today"
    assert client.post("/api/operator/charging/override", json=body, headers=OPERATOR).status_code == 200
    assert client.get("/api/operator/charging/audit?hub_id=HUB-KTX", headers=OPERATOR).json()[0]["reason"] == "exam today"
