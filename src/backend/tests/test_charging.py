"""TV2: 4 selected categories x 4 cases, in lecture order (30, 34, 35, 40).

IDs F01..F04, R01..R04, P01..P04, S01..S04 map one-to-one to the Word test plan.
Independent cases; source order is for readability, not a state dependency.
The previous extended suite is charging_regression_archive.py (explicit run only).
Performance thresholds are local smoke budgets, not a production SLA.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
from time import perf_counter

from fastapi import HTTPException
import pytest

from src.backend.core.entities import EVehicle, Student, utcnow
from src.backend.core.enums import ChargingSessionStatus as SS, EventType
from src.backend.core.event_bus import bus
from src.backend.core.state_manager import network
from src.backend.modules.charging import scheduler, service, telemetry
from src.backend.modules.charging.domain import ChargingRecord
from src.backend.modules.charging.repository import repository
from src.backend.tests.conftest import OPERATOR, PRIVATE_EV_STUDENT, STUDENT

HUB, POINT = 'HUB-KTX', 'HUB-KTX-C01'


@pytest.fixture(autouse=True)
def isolated_charging(fresh_state, monkeypatch):
    monkeypatch.setenv('CHARGING_SIMULATOR', '0')
    telemetry.stop_simulator()
    repository.store
    yield
    telemetry.stop_simulator()


def queue_request(**kwargs):
    return service.submit_charging_request('U-S02', 'PV-001', HUB, **kwargs)


def other_student():
    user = Student('U-X', 'Student X', 'x@example.test', has_private_ev=True)
    network.register_user(user)
    network.register_vehicle(EVehicle('PV-X', battery_level=40, hub_id=HUB, owner_id='U-X'))
    telemetry.ingest_readings([{'kind':'vehicle','id':'PV-X','battery_level':40}])
    from src.backend.core.auth import issue_token  # tokens are signed JWTs now (TV5)
    return {'Authorization': f'Bearer {issue_token(user)}'}


def booking_window():
    start = repository.clock() + timedelta(hours=1)
    return start, start + timedelta(minutes=30)


def measure(record_property, name, workload, operation):
    started = perf_counter()
    result = operation()
    elapsed = perf_counter() - started
    record_property('case_id', name)
    record_property('workload', workload)
    record_property('elapsed_seconds', round(elapsed, 6))
    record_property('throughput_per_second', round(workload / max(elapsed, 1e-9), 2))
    assert elapsed < 10, f'{name}: local 10-second smoke budget exceeded ({elapsed:.3f}s)'
    return result


def seed_demand(count):
    for i in range(count):
        vid = f'LOAD-{i}'
        network.register_vehicle(EVehicle(vid, battery_level=20, hub_id=HUB))
        telemetry.ingest_readings([{'kind':'vehicle','id':vid,'battery_level':20}])
        record = ChargingRecord(f'CS-LOAD-{i}', vid, hub_id=HUB)
        network.charging_sessions[record.session_id] = record


# =============================================================================
# 1. Functionality Tests - TV2 main workflows
# =============================================================================
def test_F01_register_private_vehicle_then_submit_request(client):
    """F01: TV2 onboarding -> accepted telemetry -> owned charging request."""
    result = client.post('/api/me/vehicles', headers=STUDENT, json={
        'model':'Demo private e-bike','vehicle_type':'e-bike','battery_level':30,'hub_id':HUB})
    assert result.status_code == 201
    vehicle = result.json()
    assert vehicle['owner_id'] == 'U-S01' and network.users['U-S01'].has_private_ev
    assert vehicle['outdated']  # User estimate is not an accepted sensor reading.
    telemetry.ingest_readings([{'kind':'vehicle','id':vehicle['vehicle_id'],'battery_level':30}])
    result = client.post('/api/charging/requests', headers=STUDENT, json={
        'vehicle_id':vehicle['vehicle_id'],'hub_id':HUB,'target_level':80,
        'needed_by':(repository.clock()+timedelta(hours=4)).isoformat()})
    assert result.status_code == 200 and result.json()['status'] == 'queued'
    mine = client.get('/api/me/vehicles',headers=STUDENT).json()
    assert [v['vehicle_id'] for v in mine] == [vehicle['vehicle_id']]
    assert bus.history[-1].event_type == EventType.CHARGING_REQUESTED


def test_F02_book_slot_updates_availability(client):
    """F02: a free time window becomes reserved and links reservation/session."""
    start,end = booking_window()
    url=f'/api/charging/hubs/{HUB}/slots'
    params={'start_time':start.isoformat(),'count':1,'slot_minutes':30}
    before=client.get(url,params=params,headers=PRIVATE_EV_STUDENT).json()
    assert next(p for p in before['windows'][0]['points'] if p['point_id']==POINT)['available']
    booking=service.schedule_charging_session('U-S02',HUB,'PV-001',POINT,start,end)
    after=client.get(url,params=params,headers=PRIVATE_EV_STUDENT).json()
    assert not next(p for p in after['windows'][0]['points'] if p['point_id']==POINT)['available']
    assert network.charging_sessions[booking.session_id].reservation_id == booking.reservation_id
    assert network.charging_sessions[booking.session_id].status == SS.SCHEDULED


def test_F03_queue_changes_after_simulator_battery_and_needed_time(client):
    """F03: TV5 event adapter and needed-by edit change ranking without allocating."""
    other_student()
    first=queue_request(needed_by=(repository.clock()+timedelta(hours=4)).isoformat())
    second=service.submit_charging_request('U-X','PV-X',HUB,
        needed_by=(repository.clock()+timedelta(hours=4)).isoformat())
    telemetry.register_simulator_handlers()
    assert scheduler.get_queue(HUB)[0].session_id == first.session_id
    event=bus.emit(EventType.BATTERY_UPDATED,hub_id=HUB,vehicle_id='PV-X',battery_level=5,
                   device_timestamp=(repository.clock()+timedelta(seconds=1)).isoformat(),origin='core.simulator')
    assert repository.store.latest[('vehicle','PV-X')].values['battery_level'] == 5
    assert scheduler.get_queue(HUB)[0].session_id == second.session_id
    count=len(repository.store.log)
    bus.publish(event)
    assert len(repository.store.log)==count  # Duplicate delivery does not echo indefinitely.
    response=client.patch(f'/api/charging/requests/{first.session_id}',headers=PRIVATE_EV_STUDENT,
        json={'needed_by':(repository.clock()+timedelta(minutes=10)).isoformat()})
    assert response.status_code == 200
    assert scheduler.get_queue(HUB)[0].session_id == first.session_id
    assert first.status == second.status == SS.QUEUED


def test_F04_approve_charge_complete_and_cancel_new_request(client):
    """F04: proposal approval -> charging completion -> cancellation frees a new request."""
    session=queue_request(target_level=21)
    proposal=scheduler.create_proposal(HUB,'U-OP1')
    assert session.status == SS.QUEUED
    scheduler.approve_proposal(proposal['proposal_id'],'U-OP1')
    assert session.status == SS.SCHEDULED and session.point_id
    telemetry.simulator_tick()
    assert session.status == SS.COMPLETED
    events=[e.event_type for e in bus.history]
    assert events.index(EventType.CHARGING_STARTED) < events.index(EventType.CHARGING_COMPLETED)
    new=queue_request(target_level=80)
    service.cancel_charging_reservation('U-S02',new.session_id)
    assert new.status == SS.CANCELLED
    assert client.get('/api/charging/notifications',headers=PRIVATE_EV_STUDENT).json()


# =============================================================================
# 2. Robustness Tests - validation, collisions, stale data and failures
# =============================================================================
def test_R01_invalid_telemetry_does_not_overwrite_accepted_data():
    """R01: boundary violation 101% is logged Rejected, never applied."""
    before=deepcopy(repository.store.latest[('vehicle','PV-001')])
    assert telemetry.ingest_readings([{'kind':'vehicle','id':'PV-001','battery_level':101}]) == 0
    assert network.get_vehicle('PV-001').battery_level == 20
    assert repository.store.latest[('vehicle','PV-001')] == before
    assert repository.store.log[-1].result.value == 'Rejected'


def test_R02_conflicting_slot_returns_alternatives_without_double_booking(client):
    """R02: a taken slot returns 409 and nearest feasible windows."""
    headers=other_student()
    start,end=booking_window()
    existing=service.schedule_charging_session('U-S02',HUB,'PV-001',POINT,start,end)
    response=client.post('/api/charging/reservations',headers=headers,json={
        'hub_id':HUB,'vehicle_id':'PV-X','point_id':POINT,
        'start_time':start.isoformat(),'end_time':end.isoformat()})
    assert response.status_code == 409
    assert response.json()['detail']['code']=='slot_conflict'
    assert response.json()['detail']['alternatives']
    assert list(network.reservations) == [existing.reservation_id]


def test_R03_stale_battery_requires_decision_and_flag(monkeypatch):
    """R03: <=120 seconds is fresh; >120 requires explicit continue."""
    entry=repository.store.latest[('vehicle','PV-001')]
    now=entry.reception_time+timedelta(seconds=120)
    monkeypatch.setattr(repository,'clock',lambda:now)
    assert not repository.freshness('vehicle','PV-001')['outdated']
    now+=timedelta(seconds=1)
    with pytest.raises(HTTPException) as exc:
        queue_request()
    assert exc.value.status_code==409 and exc.value.detail['code']=='outdated_data'
    assert not network.charging_sessions  # Cancel/no retry leaves no request.
    session=queue_request(continue_outdated=True)
    assert session.battery_unconfirmed and session.battery_level_used==20


def test_R04_planner_failure_keeps_previous_state(monkeypatch):
    """R04: failed calculation is reported and the previous state is retained."""
    session=queue_request()
    before=deepcopy(asdict(session))
    def fail(*args,**kwargs):
        raise ArithmeticError('Injected calculation failure')
    monkeypatch.setattr(scheduler.SchedulePlanner,'build',fail)
    with pytest.raises(HTTPException) as exc:
        scheduler.create_proposal(HUB,'U-OP1')
    assert exc.value.status_code==500
    assert asdict(session)==before and not repository.store.notifications


# =============================================================================
# 3. Performance Tests - explicit local workloads; setup excluded from timing
# =============================================================================
def test_P01_priority_100_calculations(record_property):
    now=utcnow()
    scores=measure(record_property,'P01',100,lambda:[scheduler.calculate_priority(i%101,now+timedelta(minutes=i%300),now) for i in range(100)])
    assert len(scores)==100 and all(0<=score<=100 for score in scores)


def test_P02_priority_1000_calculations(record_property):
    now=utcnow()
    scores=measure(record_property,'P02',1000,lambda:[scheduler.calculate_priority(i%101,now+timedelta(minutes=i%300),now) for i in range(1000)])
    assert len(scores)==1000 and all(0<=score<=100 for score in scores)


def test_P03_plan_10_requests(record_property):
    seed_demand(10)
    result=measure(record_property,'P03',10,lambda:scheduler.create_proposal(HUB,'U-OP1',horizon_minutes=60))
    assert len(result['ranking'])==10
    assert len(result['assignments'])+len(result['unserved'])==10
    assert all(s.status==SS.QUEUED for s in network.charging_sessions.values())


def test_P04_plan_100_requests(record_property):
    seed_demand(100)
    result=measure(record_property,'P04',100,lambda:scheduler.create_proposal(HUB,'U-OP1',horizon_minutes=60))
    assert len(result['ranking'])==100
    assert len(result['assignments'])+len(result['unserved'])==100
    for point in {a['point_id'] for a in result['assignments']}:
        slots=sorted((a['start_time'],a['end_time']) for a in result['assignments'] if a['point_id']==point)
        assert all(a[1]<=b[0] for a,b in zip(slots,slots[1:]))


# =============================================================================
# 4. Security Tests - existing auth boundary, role checks and ownership
# =============================================================================
def test_S01_anonymous_student_data_is_denied(client):
    assert client.get('/api/me/vehicles').status_code==401
    assert client.get('/api/charging/my-status').status_code==401


def test_S02_student_cannot_run_operator_schedule(client):
    response=client.post('/api/charging/prioritization/run',headers=STUDENT,json={'hub_id':HUB})
    assert response.status_code==403
    assert client.get('/api/charging/points',headers=STUDENT).status_code==403


def test_S03_cannot_spoof_owner_or_charge_another_students_vehicle(client):
    headers=other_student()
    spoof=client.post('/api/me/vehicles',headers=headers,json={
        'model':'Spoof','hub_id':HUB,'owner_id':'U-S02'})
    assert spoof.status_code==422
    response=client.post('/api/charging/requests',headers=headers,json={
        'vehicle_id':'PV-001','hub_id':HUB,'target_level':80})
    assert response.status_code==403 and not network.charging_sessions
    assert [v['vehicle_id'] for v in client.get('/api/me/vehicles',headers=headers).json()]==['PV-X']


def test_S04_other_student_cannot_cancel_edit_or_read_private_booking(client):
    session=queue_request()
    repository.notify('U-S02','charging_scheduled',session_id=session.session_id)
    response=client.post(f'/api/charging/reservations/{session.session_id}/cancel',headers=STUDENT)
    assert response.status_code==403
    response=client.patch(f'/api/charging/requests/{session.session_id}',headers=STUDENT,
        json={'needed_by':(repository.clock()+timedelta(minutes=10)).isoformat()})
    assert response.status_code==403 and session.status==SS.QUEUED
    assert client.get('/api/charging/my-status',headers=STUDENT).json()==[]
    assert client.get('/api/charging/notifications',headers=STUDENT).json()==[]
