"""Member 2 tests in the 13-category order of Software Testing slides 30-51.

Run: python -m pytest src/backend/tests/test_charging.py -v
Use-case test specifications are in docs/testing/Charging Scheduling Use Case Testing.docx.

Categories describe purpose; unit/component/system describe test level. They
are independent dimensions. Black-box partition/boundary cases are in group 01;
failure injection / selected internal paths are in 04 and 12. No claim of 100%
statement, branch or path coverage is made without a coverage measurement.
Tests are independent; source order is for reading/default pytest collection.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from time import perf_counter

from fastapi import HTTPException
import pytest

from src.backend.core.entities import ChargingSession, EVehicle, Student, utcnow
from src.backend.core.enums import ChargingPointStatus as PS, ChargingSessionStatus as SS, EventType, ReservationStatus, VehicleStatus
from src.backend.core.event_bus import bus
from src.backend.core.state_manager import network
from src.backend.modules.charging import point_monitor, scheduler, service, telemetry
from src.backend.modules.charging.repository import repository
from src.backend.tests.conftest import OPERATOR, PRIVATE_EV_STUDENT, STUDENT

HUB = "HUB-KTX"
POINT = "HUB-KTX-C01"


@pytest.fixture(autouse=True)
def charging_state(fresh_state, monkeypatch):
    monkeypatch.setenv("CHARGING_SIMULATOR", "0")
    telemetry.stop_simulator()
    repository.store
    yield
    telemetry.stop_simulator()


def request(**kwargs):
    return service.submit_charging_request("U-S02", "PV-001", HUB, **kwargs)


def second_vehicle():
    network.register_user(Student("U-X", "Other student", "other@example.com", has_private_ev=True))
    network.register_vehicle(EVehicle("PV-X", battery_level=40, hub_id=HUB, owner_id="U-X"))
    telemetry.ingest_readings([{"kind": "vehicle", "id": "PV-X", "battery_level": 40}])


def window():
    start = repository.clock() + timedelta(hours=1)
    return start, start + timedelta(minutes=30)


# =============================================================================
# 01 Functionality Tests | slide 30
# =============================================================================


# Black-box functions and component workflows, including equivalence partitions
# and boundary values (slide 25). Setup, action and assertions are explicit per test.


def test_priority_is_higher_for_low_battery():
    now = utcnow()
    assert scheduler.calculate_priority(10, now + timedelta(hours=1), now) > scheduler.calculate_priority(80, now + timedelta(hours=1), now)


def test_priority_is_higher_when_needed_sooner():
    now = utcnow()
    assert scheduler.calculate_priority(30, now + timedelta(minutes=10), now) > scheduler.calculate_priority(30, now + timedelta(hours=4), now)


@pytest.mark.parametrize("battery", [0, 1, 50, 99, 100], ids=["min", "min+1", "representative", "max-1", "max"])
def test_battery_equivalence_partition_and_boundaries(battery):
    """Black-box: representative valid partition and both valid boundaries."""
    score = scheduler.calculate_priority(battery, None)
    assert 0 <= score <= 100


def test_freshness_boundary_uses_reception_not_device_time(monkeypatch):
    entry = repository.store.latest[("vehicle", "PV-001")]
    now = entry.reception_time + timedelta(seconds=120)
    monkeypatch.setattr(repository, "clock", lambda: now)
    entry.device_timestamp -= timedelta(days=1)
    assert not repository.freshness("vehicle", "PV-001")["outdated"]
    now += timedelta(microseconds=1)
    assert repository.freshness("vehicle", "PV-001")["outdated"]


def test_submit_request_main_flow_and_event():
    session = request(battery_level=90, target_level=80)
    assert session.status == SS.QUEUED and session.battery_level_used == 20
    assert bus.history[-1].event_type == EventType.CHARGING_REQUESTED
    assert bus.history[-1].payload["vehicle_id"] == "PV-001"


def test_stale_request_requires_confirmation_and_tracks_last_known_value():
    entry = repository.store.latest[("vehicle", "PV-001")]
    entry.reception_time -= timedelta(seconds=121)
    with pytest.raises(HTTPException) as exc:
        request()
    assert exc.value.detail["code"] == "outdated_data"
    assert not network.charging_sessions
    session = request(continue_outdated=True)
    assert session.battery_unconfirmed and session.battery_updated_at == entry.reception_time


def test_schedule_session_rejects_overlapping_window_on_same_point():
    second_vehicle()
    start, end = window()
    booking = service.schedule_charging_session("U-S02", HUB, "PV-001", POINT, start, end)
    assert booking.status == ReservationStatus.CONFIRMED
    with pytest.raises(HTTPException) as exc:
        service.schedule_charging_session("U-X", HUB, "PV-X", POINT, start, end)
    assert exc.value.status_code == 409
    assert len(network.reservations) == 1


def test_adjacent_windows_are_allowed():
    second_vehicle()
    start, end = window()
    service.schedule_charging_session("U-S02", HUB, "PV-001", POINT, start, end)
    service.schedule_charging_session("U-X", HUB, "PV-X", POINT, end, end + timedelta(minutes=20))
    assert len(network.reservations) == 2


def test_select_points_and_booking_validation():
    network.get_hub(HUB).charging_points[POINT].status = PS.OUT_OF_SERVICE
    assert POINT not in [p.point_id for p in service.list_available_points(HUB)]
    start, end = window()
    for a, b in [(end, start), (start, start + timedelta(days=8))]:
        with pytest.raises(HTTPException):
            service.schedule_charging_session("U-S02", HUB, "PV-001", None, a, b)


def test_proposal_does_not_mutate_and_discard_keeps_state():
    session = request()
    before = network.snapshot()
    result = scheduler.create_proposal(HUB, "U-OP1")
    assert result["assignments"]
    assert network.snapshot().charging_sessions == before.charging_sessions
    assert network.snapshot().hubs == before.hubs
    scheduler.discard_proposal(result["proposal_id"], "U-OP1")
    assert session.status == SS.QUEUED
    with pytest.raises(HTTPException):
        scheduler.approve_proposal(result["proposal_id"], "U-OP1")


def test_approval_assigns_and_notifies_once():
    session = request()
    result = scheduler.create_proposal(HUB, "U-OP1")
    scheduler.approve_proposal(result["proposal_id"], "U-OP1")
    assert session.status == SS.SCHEDULED and session.point_id
    assert repository.store.notifications[-1]["user_id"] == "U-S02"
    assert bus.history[-1].event_type == EventType.CHARGING_SCHEDULED
    with pytest.raises(HTTPException):
        scheduler.approve_proposal(result["proposal_id"], "U-OP1")


def test_capacity_horizon_lists_unserved():
    session = request()
    result = scheduler.create_proposal(HUB, "U-OP1", horizon_minutes=1)
    assert result["unserved"] == [session.session_id]
    scheduler.approve_proposal(result["proposal_id"], "U-OP1")
    assert session.status == SS.QUEUED


def test_empty_schedule():
    assert scheduler.create_proposal(HUB, "U-OP1")["status"] == "nothing_to_schedule"
    assert scheduler.run_prioritization(HUB) == []


def test_cancel_frees_point_and_promotes_queue():
    second_vehicle()
    first = request()
    scheduler.run_prioritization(HUB)
    point = repository.point(first.point_id)
    for p in network.get_hub(HUB).charging_points.values():
        if p != point:
            p.status = PS.OUT_OF_SERVICE
    second = service.submit_charging_request("U-X", "PV-X", HUB)
    service.cancel_charging_reservation("U-S02", first.session_id)
    assert first.status == SS.CANCELLED and second.point_id == point.point_id
    assert second.status == SS.SCHEDULED


def test_cancel_future_reservation_releases_slot():
    start, end = window()
    booking = service.schedule_charging_session("U-S02", HUB, "PV-001", POINT, start, end)
    service.cancel_charging_reservation("U-S02", booking.reservation_id)
    assert POINT in [p.point_id for p in service.list_available_points(HUB, start, end)]
    assert service.cancel_charging_reservation("U-S02", booking.reservation_id)["already_cancelled"]


def test_manual_status_preview_and_invalid_transition(client):
    body = {"status": "out_of_service", "reason": "Maintenance"}
    result = client.patch(f"/api/charging/points/{POINT}/status", headers=OPERATOR, json=body)
    assert result.json()["status"] == "awaiting_confirmation"
    assert repository.point(POINT).status == PS.AVAILABLE
    result = client.patch(f"/api/charging/points/{POINT}/status", headers=OPERATOR,
                          json={**body, "confirmed": True})
    assert result.status_code == 200 and repository.point(POINT).status == PS.OUT_OF_SERVICE
    with pytest.raises(HTTPException):
        point_monitor.update_point_status(POINT, PS.OCCUPIED, "U-OP1", "Bad")


def test_monitor_excludes_outdated_points_from_available_count():
    repository.store.latest[("charging_point", POINT)].reception_time -= timedelta(seconds=121)
    points = point_monitor.get_points_status(HUB)
    item = next(p for p in points if p["point_id"] == POINT)
    assert item["data_outdated"] and item["hub_free_points"] == 5


def test_my_status_is_read_only_and_private():
    session = request()
    before = deepcopy(asdict(session))
    result = service.get_my_charging_status("U-S02")
    assert result[0]["queue_position"] == 1 and result[0]["battery_level"] == 20
    assert not service.get_my_charging_status("U-S01")
    assert asdict(session) == before


def test_suggestions_return_top_three_and_create_nothing():
    result = service.get_smart_suggestion("U-S02", "PV-001")
    assert len(result["suggestions"]) == 3
    assert not network.charging_sessions and not network.reservations
    with pytest.raises(HTTPException):
        service.get_smart_suggestion("U-S01", "PV-001")


def test_telemetry_updates_battery_and_rejects_invalid_values():
    count = telemetry.ingest_readings([
        {"kind": "vehicle", "id": "PV-001", "battery_level": 42},
        {"kind": "vehicle", "id": "PV-001", "battery_level": 101},
        {"kind": "vehicle", "id": "missing", "battery_level": 30}])
    assert count == 1 and network.get_vehicle("PV-001").battery_level == 42
    assert [e.result.value for e in repository.store.log[-3:]] == ["Accepted", "Rejected", "Rejected"]


def test_simulator_completes_and_releases_resources():
    session = request(target_level=21)
    scheduler.run_prioritization(HUB)
    point_id = session.point_id
    telemetry.simulator_tick()
    assert session.status == SS.COMPLETED
    assert repository.point(point_id).current_session_id is None
    assert network.get_vehicle("PV-001").status == VehicleStatus.AVAILABLE


def test_override_requires_reason_and_is_audited():
    session = request()
    with pytest.raises(HTTPException):
        scheduler.apply_manual_override(HUB, session.session_id, "U-OP1")
    scheduler.apply_manual_override(HUB, session.session_id, "U-OP1", "Urgent departure")
    assert session.priority > 100 and session.point_id
    assert bus.history[-1].event_type == EventType.CHARGING_OVERRIDE
    assert repository.store.audit[-1]["reason"] == "Urgent departure"


# =============================================================================
# 02 GUI Testing | slides 31-32
# =============================================================================


# Automated checks below cover served HTML/assets and translation parity only.
# Browser rendering, keyboard usability and mobile layout require manual GUI checks.


@pytest.mark.parametrize("page,region", [
    ("student/charging-request.html", 'id="controls"'),
    ("operator/charging.html", 'id="run-form"'),
])
def test_gui_page_contract_is_served(client, page, region):
    """GUI support only: HTML/assets contract; not browser rendering or usability."""
    response = client.get('/app/' + page)
    assert response.status_code == 200
    assert region in response.text and 'id="nav"' in response.text
    for asset in ['/shared/i18n.js', '/shared/api-client.js', '/app/assets/js/main.js']:
        assert asset in response.text
        assert client.get(asset).status_code == 200


def test_gui_charging_translation_keys_match():
    """Static GUI support: the charging screens have matching EN/VI keys."""
    import re
    source = (Path(__file__).resolve().parents[2] / 'shared' / 'i18n.js').read_text(encoding='utf-8')
    en, vi = source.split('    vi: {', 1)
    keys = lambda text: set(re.findall(r"'(charging\.[^']+)'\s*:", text))
    assert keys(en) and keys(en) == keys(vi)


# =============================================================================
# 03 Interoperability Tests | slide 33
# =============================================================================


# Integration with the current shared core and JSON API; not OS/browser certification.


def test_class_diagram_methods_and_allocation_delegate():
    from src.backend.core.allocation_service import allocation_service
    session = allocation_service.schedule_charging("PV-001")
    assert isinstance(session, ChargingSession) and session.status == SS.SCHEDULED
    assert session.calculate_priority() >= 0
    session.schedule()
    telemetry.simulator_tick()
    session.complete()
    assert session.status == SS.COMPLETED


def test_scheduling_policy_is_replaceable():
    request()
    class FixedPolicy:
        def score(self, battery_level, needed_by, now, *, waiting_minutes=0):
            return 17
    proposal = scheduler.SchedulePlanner(policy=FixedPolicy()).build(
        HUB, "U-OP1", 240, False, ["battery_level", "needed_by"])
    assert proposal.ranking[0]["priority"] == 17


def test_telemetry_api_logs_invalid_payloads_and_source_registration(client):
    assert client.post("/api/charging/telemetry/sources", headers=OPERATOR, json={"source_id": "sensor-1"}).status_code == 200
    result = client.post("/api/charging/telemetry", json=[
        {"source_id": "sensor-1", "kind": "vehicle", "id": "PV-001", "battery_level": -1}])
    assert result.status_code == 200 and result.json()["accepted"] == 0
    assert result.json()["results"][0]["result"] == "Rejected"


# =============================================================================
# 04 Robustness Tests | slide 34
# =============================================================================


@pytest.mark.parametrize("battery", [-1, 101, True, 1.5])
def test_invalid_priority_input(battery):
    with pytest.raises(HTTPException):
        scheduler.calculate_priority(battery, None)


@pytest.mark.parametrize("kwargs", [{"target_level": 20}, {"needed_by": "bad"},
    {"needed_by": "2020-01-01T00:00:00Z"}, {"needed_by": "2030-01-01T12:00:00"}])
def test_request_invalid_values(kwargs):
    with pytest.raises(HTTPException):
        request(**kwargs)
    assert not network.charging_sessions


def test_request_duplicate_and_wrong_hub_rejected():
    with pytest.raises(HTTPException):
        service.submit_charging_request("U-S02", "PV-001", "HUB-METRO")
    request()
    with pytest.raises(HTTPException) as exc:
        request()
    assert exc.value.status_code == 409


def test_request_all_points_broken():
    for point in network.get_hub(HUB).charging_points.values():
        point.status = PS.OUT_OF_SERVICE
    with pytest.raises(HTTPException) as exc:
        request()
    assert exc.value.status_code == 409


def test_suggestion_no_capacity_and_stale_warning():
    for hub in network.hubs.values():
        for point in hub.charging_points.values():
            point.status = PS.OUT_OF_SERVICE
    assert service.get_smart_suggestion("U-S02", "PV-001")["status"] == "no_feasible_suggestion"
    repository.point(POINT).status = PS.AVAILABLE
    repository.store.latest[("vehicle", "PV-001")].reception_time -= timedelta(seconds=121)
    assert service.get_smart_suggestion("U-S02", "PV-001")["status"] == "awaiting_decision"


def test_duplicate_rejected_and_unknown_source_never_refresh_age():
    entry = repository.store.latest[("vehicle", "PV-001")]
    before = entry.reception_time
    assert telemetry.ingest_readings([{"kind": "vehicle", "id": "PV-001", "battery_level": 99,
        "device_timestamp": entry.device_timestamp.isoformat()}]) == 0
    assert repository.store.log[-1].result.value == "Ignored"
    assert telemetry.ingest_readings([{"kind": "vehicle", "id": "PV-001", "battery_level": 99,
        "source_id": "unknown"}]) == 0
    assert repository.store.latest[("vehicle", "PV-001")].reception_time == before
    assert network.get_vehicle("PV-001").battery_level == 20


def test_log_failure_is_fail_closed(monkeypatch):
    def fail(_):
        raise OSError("Disk unavailable")
    before = repository.store.latest[("vehicle", "PV-001")]
    monkeypatch.setattr(repository.store, "append_update", fail)
    with pytest.raises(HTTPException) as exc:
        telemetry.ingest_readings([{"kind": "vehicle", "id": "PV-001", "battery_level": 90}])
    assert exc.value.status_code == 503
    assert repository.store.latest[("vehicle", "PV-001")] is before
    assert network.get_vehicle("PV-001").battery_level == 20


def test_calculation_failure_keeps_previous_schedule(monkeypatch):
    session = request()
    before = deepcopy(asdict(session))
    def fail(*args, **kwargs):
        raise ArithmeticError("Calculation unavailable")
    monkeypatch.setattr(scheduler.SchedulePlanner, "build", fail)
    with pytest.raises(HTTPException) as exc:
        scheduler.create_proposal(HUB, "U-OP1")
    assert exc.value.status_code == 500 and asdict(session) == before


def test_invalid_hub_and_criteria_are_business_errors(client):
    response = client.post('/api/charging/prioritization/run', headers=OPERATOR, json={"hub_id": "missing"})
    assert response.status_code == 404
    response = client.post('/api/charging/prioritization/run', headers=OPERATOR, json={"hub_id": HUB, "criteria": []})
    assert response.status_code == 400


# =============================================================================
# 05 Performance Tests | slide 35
# =============================================================================


# Local CPU smoke budgets, not agreed production SLAs; timing is recorded via record_property.


@pytest.mark.parametrize("transactions", [100, 1000])
def test_priority_processing_performance_smoke(transactions, record_property):
    """Measure CPU-local scoring, not HTTP/network or a production performance SLA."""
    now = utcnow()
    started = perf_counter()
    scores = [scheduler.calculate_priority(i % 101, now + timedelta(minutes=i % 300), now)
              for i in range(transactions)]
    elapsed = perf_counter() - started
    record_property('transactions', transactions)
    record_property('elapsed_seconds', elapsed)
    record_property('transactions_per_second', transactions / max(elapsed, 1e-9))
    assert len(scores) == transactions and all(0 <= score <= 100 for score in scores)
    assert elapsed < 10, f'Local smoke budget exceeded: {elapsed:.3f}s'


# =============================================================================
# 06 Scalability Tests | slide 36
# =============================================================================


# Increasing in-memory demand up to the demo limit; not distributed-system capacity certification.


@pytest.mark.parametrize("requests_count", [10, 50, 100])
def test_planner_scales_to_demo_queue_limit(requests_count, record_property):
    """Bounded demo scalability: increasing requests, unchanged allocation invariants."""
    from src.backend.modules.charging.domain import ChargingRecord
    for i in range(requests_count):
        vid = f'SCALE-{i}'
        network.register_vehicle(EVehicle(vid, battery_level=20, hub_id=HUB))
        telemetry.ingest_readings([{'kind': 'vehicle', 'id': vid, 'battery_level': 20}])
        item = ChargingRecord(f'CS-SCALE-{i}', vid, hub_id=HUB)
        network.charging_sessions[item.session_id] = item
    started = perf_counter()
    result = scheduler.create_proposal(HUB, 'U-OP1', horizon_minutes=60)
    elapsed = perf_counter() - started
    record_property('requests_count', requests_count)
    record_property('elapsed_seconds', elapsed)
    assert len(result['ranking']) == requests_count
    assert len(result['assignments']) + len(result['unserved']) == requests_count
    for point_id in {a['point_id'] for a in result['assignments']}:
        slots = sorted((a['start_time'], a['end_time']) for a in result['assignments'] if a['point_id'] == point_id)
        assert all(left[1] <= right[0] for left, right in zip(slots, slots[1:]))
    assert elapsed < 10, f'Local smoke budget exceeded: {elapsed:.3f}s'


# =============================================================================
# 07 Stress Tests | slide 37
# =============================================================================


def test_two_threads_cannot_book_the_same_slot():
    second_vehicle()
    start, end = window()
    def reserve(pair):
        try:
            return service.schedule_charging_session(pair[0], HUB, pair[1], POINT, start, end).reservation_id
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, [("U-S02", "PV-001"), ("U-X", "PV-X")]))
    assert results.count(409) == 1 and len(network.reservations) == 1


def test_queue_overload_is_rejected_without_partial_write():
    """Stress: push beyond the explicit 100-request queue limit."""
    from src.backend.modules.charging.domain import ChargingRecord, QUEUE_LIMIT
    for i in range(QUEUE_LIMIT):
        item = ChargingRecord(f'CS-FULL-{i}', f'FLEET-{i}', hub_id=HUB)
        network.charging_sessions[item.session_id] = item
    with pytest.raises(HTTPException) as exc:
        request()
    assert exc.value.status_code == 409 and len(network.charging_sessions) == QUEUE_LIMIT
    assert 'queue is full' in exc.value.detail.lower()


def test_peak_concurrent_requests_create_exactly_one_session():
    """Stress: synchronize competing callers against one private vehicle."""
    callers = 12
    barrier = Barrier(callers)
    def submit(_):
        barrier.wait(timeout=10)
        try:
            return request().session_id
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=callers) as pool:
        results = list(pool.map(submit, range(callers)))
    assert results.count(409) == callers - 1
    assert len(network.charging_sessions) == 1


# =============================================================================
# 08 Load and Stability Tests | slides 38-39
# =============================================================================


# Repeated sequential demo workload; not a long-duration multi-user endurance benchmark.


def test_repeated_booking_cycles_leave_no_resource_leaks(record_property):
    """Load/stability smoke: repeat a fixed sequential workload on the same state."""
    cycles = 30
    started = perf_counter()
    for _ in range(cycles):
        session = request()
        scheduler.run_prioritization(HUB)
        assert session.status == SS.SCHEDULED
        service.cancel_charging_reservation('U-S02', session.session_id)
    record_property('cycles', cycles)
    record_property('elapsed_seconds', perf_counter() - started)
    assert len(network.charging_sessions) == cycles
    assert all(s.status == SS.CANCELLED for s in network.charging_sessions.values())
    assert not network.reservations
    assert all(p.current_session_id is None and p.status == PS.AVAILABLE
               for p in network.get_hub(HUB).charging_points.values())


# =============================================================================
# 09 Security Testing | slides 40-45
# =============================================================================


def test_submit_request_rejected_without_private_ev():
    with pytest.raises(HTTPException) as exc:
        service.submit_charging_request("U-S01", "PV-001", HUB, 20)
    assert exc.value.status_code == 403


def test_cancellation_checks_owner_running_and_idempotency():
    session = request()
    with pytest.raises(HTTPException) as exc:
        service.cancel_charging_reservation("U-S01", session.session_id)
    assert exc.value.status_code == 403
    scheduler.run_prioritization(HUB)
    telemetry.simulator_tick()
    assert session.status == SS.CHARGING
    with pytest.raises(HTTPException):
        service.cancel_charging_reservation("U-S02", session.session_id)


def test_api_authentication_and_role_separation(client):
    assert client.get('/api/charging/my-status').status_code == 401
    assert client.get('/api/charging/points', headers=STUDENT).status_code == 403
    assert client.post('/api/charging/prioritization/run', headers=STUDENT, json={'hub_id': HUB}).status_code == 403


def test_other_student_cannot_read_notifications_or_cancel_booking(client):
    session = request()
    repository.notify('U-S02', 'charging_scheduled', session_id=session.session_id)
    assert client.get('/api/charging/my-status', headers=STUDENT).json() == []
    assert client.get('/api/charging/notifications', headers=STUDENT).json() == []
    response = client.post(f'/api/charging/reservations/{session.session_id}/cancel', headers=STUDENT)
    assert response.status_code == 403 and session.status == SS.QUEUED


# =============================================================================
# 10 Regulatory Tests | slide 46
# =============================================================================


# NOT APPLICABLE / NOT EXECUTED: no applicable regulation or certification target
# has been specified for this academic simulator. Do not invent a passing test
# or infer GDPR/electrical compliance from the security and safety tests.


# =============================================================================
# 11 Safety Assurance | slide 47
# =============================================================================


# Software allocation invariants only. No physical charging/electrical safety certification.


def test_out_of_service_point_is_never_assigned():
    network.get_hub(HUB).charging_points[POINT].status = PS.OUT_OF_SERVICE
    session = request()
    scheduler.run_prioritization(HUB)
    assert session.status == SS.SCHEDULED and session.point_id != POINT


def test_unknown_reserved_and_occupied_points_are_not_stolen():
    points = list(network.get_hub(HUB).charging_points.values())
    for point in points:
        point.status = PS.RESERVED
    points[0].status = PS.OCCUPIED
    session = request()
    scheduler.run_prioritization(HUB)
    assert session.status == SS.QUEUED and session.point_id is None


def test_approval_rejects_changed_resource_atomically():
    session = request()
    result = scheduler.create_proposal(HUB, "U-OP1")
    repository.point(result["assignments"][0]["point_id"]).status = PS.OUT_OF_SERVICE
    with pytest.raises(HTTPException) as exc:
        scheduler.approve_proposal(result["proposal_id"], "U-OP1")
    assert exc.value.status_code == 409 and session.status == SS.QUEUED


def test_future_booking_is_preserved_and_not_overlapped():
    second_vehicle()
    start = repository.clock() + timedelta(minutes=5)
    end = start + timedelta(minutes=30)
    booking = service.schedule_charging_session("U-S02", HUB, "PV-001", POINT, start, end)
    for p in network.get_hub(HUB).charging_points.values():
        if p.point_id != POINT:
            p.status = PS.OUT_OF_SERVICE
    session = service.submit_charging_request("U-X", "PV-X", HUB)
    scheduler.run_prioritization(HUB)
    assert session.start_time >= end and booking.start_time == start


def test_update_point_status_requeues_running_session():
    session = request()
    scheduler.run_prioritization(HUB)
    telemetry.simulator_tick()
    point = repository.point(session.point_id)
    result = point_monitor.update_point_status(point.point_id, PS.OUT_OF_SERVICE, "U-OP1", "Broken")
    assert result["requeued_session_ids"] == [session.session_id]
    assert session.status == SS.QUEUED and session.point_id is None
    assert network.get_vehicle("PV-001").status == VehicleStatus.AVAILABLE
    assert bus.history[-1].event_type == EventType.CHARGER_STATUS_CHANGED


def test_telemetry_sensor_failure_requeues_session():
    session = request()
    scheduler.run_prioritization(HUB)
    point = session.point_id
    assert telemetry.ingest_readings([{"kind": "charging_point", "id": point, "status": "out_of_service"}]) == 1
    assert session.status == SS.QUEUED and session.point_id is None


# =============================================================================
# 12 Regression Tests | slides 48-50
# =============================================================================


# Previously working behaviour and concrete bug regressions; the full suite is also regression testing.


def test_heartbeat_does_not_invalidate_unchanged_proposal():
    request()
    result = scheduler.create_proposal(HUB, "U-OP1")
    telemetry.ingest_readings([{"kind": "vehicle", "id": "PV-001", "battery_level": 20}])
    assert scheduler.approve_proposal(result["proposal_id"], "U-OP1")["status"] == "applied"


def test_stale_proposal_and_mixed_fresh_flags():
    second_vehicle()
    fresh = request()
    fresh.battery_unconfirmed = True
    old = service.submit_charging_request("U-X", "PV-X", HUB)
    repository.store.latest[("vehicle", "PV-X")].reception_time -= timedelta(seconds=121)
    result = scheduler.create_proposal(HUB, "U-OP1")
    assert result["status"] == "awaiting_decision"
    assert old.status == SS.QUEUED
    result = scheduler.create_proposal(HUB, "U-OP1", continue_outdated=True)
    scheduler.approve_proposal(result["proposal_id"], "U-OP1")
    assert not fresh.battery_unconfirmed and old.battery_unconfirmed


def test_simulator_start_stop_are_idempotent():
    telemetry.start_simulator(30)
    first = telemetry._thread
    telemetry.start_simulator(30)
    assert telemetry._thread is first and first.is_alive()
    telemetry.stop_simulator()
    telemetry.stop_simulator()
    assert not first.is_alive()
    with pytest.raises(HTTPException):
        telemetry.start_simulator(31)


def test_module_store_resets_with_seed():
    from src.backend.data.seed_data import seed_network
    request()
    repository.notify("U-S02", "test")
    seed_network(fresh=True)
    assert not repository.store.notifications and not network.charging_sessions


def test_missing_timestamps_work_with_coarse_windows_clock(monkeypatch):
    now = repository.clock()
    monkeypatch.setattr(repository, "clock", lambda: now)
    for battery in [22, 23, 24]:
        assert telemetry.ingest_readings([{"kind": "vehicle", "id": "PV-001", "battery_level": battery}]) == 1
    assert network.get_vehicle("PV-001").battery_level == 24


def test_manual_override_survives_recalculation_when_waiting():
    second_vehicle()
    first = request()
    other = service.submit_charging_request("U-X", "PV-X", HUB)
    for point in network.get_hub(HUB).charging_points.values():
        point.status = PS.RESERVED
    scheduler.apply_manual_override(HUB, other.session_id, "U-OP1", "Urgent")
    repository.point(POINT).status = PS.AVAILABLE
    result = scheduler.create_proposal(HUB, "U-OP1")
    assert result["ranking"][0]["session_id"] == other.session_id
    scheduler.approve_proposal(result["proposal_id"], "U-OP1")
    assert other.start_time <= first.start_time


def test_future_reservation_requeues_and_relinks_after_point_failure():
    start, end = window()
    booking = service.schedule_charging_session("U-S02", HUB, "PV-001", POINT, start, end)
    point_monitor.update_point_status(POINT, PS.OUT_OF_SERVICE, "U-OP1", "Broken")
    session = network.charging_sessions[booking.session_id]
    assert booking.point_unavailable and session.status == SS.QUEUED
    scheduler.run_prioritization(HUB)
    assert booking.resource_id == session.point_id != POINT
    assert not booking.point_unavailable
    assert booking.start_time == start and booking.end_time == end


def test_simulator_logs_point_release_immediately():
    session = request(target_level=21)
    scheduler.run_prioritization(HUB)
    point_id = session.point_id
    telemetry.simulator_tick()
    assert repository.store.latest[("charging_point", point_id)].values["status"] == 'available'


# =============================================================================
# 13 Acceptance Testing | slide 51
# =============================================================================


# Automated acceptance candidate through the API; real user acceptance/UAT is not claimed.
# Human-executable scenarios and expected outputs are in the separate Word document.


def test_authenticated_api_workflow(client):
    assert client.get("/api/charging/my-status").status_code == 401
    assert client.get("/api/charging/points", headers=STUDENT).status_code == 403
    assert client.get("/api/charging/my-vehicles", headers=PRIVATE_EV_STUDENT).json()[0]["vehicle_id"] == "PV-001"
    result = client.post("/api/charging/requests", headers=PRIVATE_EV_STUDENT,
                         json={"vehicle_id": "PV-001", "hub_id": HUB})
    assert result.status_code == 200
    proposal = client.post("/api/charging/prioritization/run", headers=OPERATOR, json={"hub_id": HUB}).json()
    assert proposal["status"] == "proposed"
    assert client.post(f'/api/charging/proposals/{proposal["proposal_id"]}/approve', headers=OPERATOR).status_code == 200
    assert client.get("/api/charging/notifications", headers=PRIVATE_EV_STUDENT).json()
