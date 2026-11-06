"""Member 2 HTTP boundary: authentication, validated inputs and workflow commands."""
from contextlib import asynccontextmanager
from dataclasses import asdict
import os
import importlib.util
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictInt

from ...core.auth import require_operator, require_student
from ...core.entities import Operator, Student
from ...core.enums import ChargingPointStatus
from . import availability, point_monitor, private_vehicles, scheduler, service, telemetry
from .repository import repository


@asynccontextmanager
async def lifespan(_):
    with repository.network.lock:
        repository.store
    telemetry.register_simulator_handlers()
    central_available = importlib.util.find_spec("src.backend.core.simulator") is not None
    enabled = os.getenv("CHARGING_SIMULATOR", "0" if central_available else "1") != "0"
    if enabled:
        telemetry.start_simulator()
    try:
        yield
    finally:
        if enabled:
            telemetry.stop_simulator()


router = APIRouter(prefix="/api/charging", tags=["Charging - Member 2"], lifespan=lifespan)


class ChargingRequestIn(BaseModel):
    vehicle_id: str
    hub_id: str
    battery_level: Optional[StrictInt] = Field(default=None, ge=0, le=100)
    needed_by: Optional[str] = None
    target_level: StrictInt = Field(default=100, ge=1, le=100)
    continue_outdated: bool = False


class ScheduleIn(BaseModel):
    hub_id: str
    vehicle_id: Optional[str] = None
    point_id: Optional[str] = None
    start_time: str
    end_time: str
    target_level: StrictInt = Field(default=100, ge=1, le=100)


class PointStatusIn(BaseModel):
    status: ChargingPointStatus
    reason: str = ""
    confirmed: bool = False


class PrioritizeIn(BaseModel):
    hub_id: str
    horizon_minutes: int = Field(default=240, ge=1, le=10080)
    continue_outdated: bool = False
    criteria: List[str] = Field(default_factory=lambda: ["battery_level", "needed_by"])


class OverrideIn(BaseModel):
    hub_id: str
    session_id: str
    reason: str


class SourceIn(BaseModel):
    source_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")


class PrivateVehicleIn(BaseModel):
    model: str = Field(min_length=1, max_length=80)
    vehicle_type: str = "e-bike"
    battery_level: StrictInt = Field(default=20, ge=0, le=100)
    hub_id: Optional[str] = None
    model_config = {"extra": "forbid"}


class RequestUpdateIn(BaseModel):
    needed_by: str


@router.get("/my-vehicles")
def my_vehicles(user: Student = Depends(require_student)):
    return service.get_my_vehicles(user.user_id)


@router.get("/hubs/{hub_id}/availability")
def hub_capacity(hub_id: str, user: Student = Depends(require_student)):
    return availability.hub_availability(hub_id)


@router.get("/hubs/{hub_id}/slots")
def charging_slots(hub_id: str, start_time: Optional[str] = None, slot_minutes: int = 30,
                   count: int = 8, user: Student = Depends(require_student)):
    return availability.slot_grid(hub_id, start_time, slot_minutes, count)


@router.post("/requests")
def submit_request(body: ChargingRequestIn, user: Student = Depends(require_student)):
    return service.submit_charging_request(user.user_id, **body.model_dump())


@router.patch("/requests/{session_id}")
def update_request(session_id: str, body: RequestUpdateIn, user: Student = Depends(require_student)):
    from ...core.enums import ChargingSessionStatus, EventType
    from ...core.event_bus import bus
    from .domain import timestamp
    with repository.network.lock:
        session = repository.network.charging_sessions.get(session_id)
        if not session:
            raise HTTPException(404, "Charging request not found")
        if session.requested_by != user.user_id:
            raise HTTPException(403, "Request belongs to another student")
        if session.status != ChargingSessionStatus.QUEUED:
            raise HTTPException(409, "Only a queued request can be edited")
        needed = timestamp(body.needed_by, "needed_by")
        if not needed or needed <= repository.clock():
            raise HTTPException(400, "needed_by must be in the future")
        session.needed_by = needed
        result = service.session_view(session)
    bus.emit(EventType.CHARGING_REQUESTED, hub_id=session.hub_id, session_id=session_id,
             vehicle_id=session.vehicle_id, action="updated")
    return result


@router.get("/hubs/{hub_id}/points")
def available_points(hub_id: str, start_time: Optional[str] = None, end_time: Optional[str] = None,
                     user: Student = Depends(require_student)):
    with repository.network.lock:
        return [{**asdict(p), **repository.freshness("charging_point", p.point_id)}
                for p in service.list_available_points(hub_id, start_time, end_time)]


@router.post("/reservations")
def schedule(body: ScheduleIn, user: Student = Depends(require_student)):
    return service.schedule_charging_session(user.user_id, **body.model_dump())


@router.get("/suggestion")
def suggestion(vehicle_id: str, needed_by: Optional[str] = None, continue_outdated: bool = False,
               user: Student = Depends(require_student)):
    return service.get_smart_suggestion(user.user_id, vehicle_id, needed_by, continue_outdated=continue_outdated)


@router.post("/reservations/{item_id}/cancel")
def cancel(item_id: str, user: Student = Depends(require_student)):
    return service.cancel_charging_reservation(user.user_id, item_id)


@router.get("/my-status")
def my_status(user: Student = Depends(require_student)):
    return service.get_my_charging_status(user.user_id)


@router.get("/notifications")
def notifications(user: Student = Depends(require_student)):
    with repository.network.lock:
        return [n.copy() for n in repository.store.notifications if n["user_id"] == user.user_id]


@router.get("/points")
def points_status(hub_id: Optional[str] = None, op: Operator = Depends(require_operator)):
    return point_monitor.get_points_status(hub_id)


@router.patch("/points/{point_id}/status")
def update_point(point_id: str, body: PointStatusIn, op: Operator = Depends(require_operator)):
    if not body.confirmed:
        return {"status": "awaiting_confirmation", **point_monitor.preview_point_status(point_id, body.status)}
    return point_monitor.update_point_status(point_id, body.status, op.user_id, body.reason)


@router.post("/prioritization/run")
def run_prioritization(body: PrioritizeIn, op: Operator = Depends(require_operator)):
    return scheduler.create_proposal(body.hub_id, op.user_id, body.horizon_minutes,
                                     body.continue_outdated, body.criteria)


@router.post("/proposals/{proposal_id}/approve")
def approve(proposal_id: str, op: Operator = Depends(require_operator)):
    return scheduler.approve_proposal(proposal_id, op.user_id)


@router.post("/proposals/{proposal_id}/discard")
def discard(proposal_id: str, op: Operator = Depends(require_operator)):
    return scheduler.discard_proposal(proposal_id, op.user_id)


@router.get("/queue/{hub_id}")
def queue(hub_id: str, op: Operator = Depends(require_operator)):
    with repository.network.lock:
        return [service.session_view(s) for s in scheduler.get_queue(hub_id)]


@router.post("/prioritization/override")
def override(body: OverrideIn, op: Operator = Depends(require_operator)):
    return scheduler.apply_manual_override(body.hub_id, body.session_id, op.user_id, body.reason)


@router.get("/audit")
def audit(op: Operator = Depends(require_operator)):
    with repository.network.lock:
        return list(repository.store.audit)


@router.post("/telemetry")
def report(readings: List[dict]):
    # Raw readings reach ingestion so even invalid values get a Rejected log.
    with repository.network.lock:
        offset = len(repository.store.log)
        count = telemetry.ingest_readings(readings)
        entries = repository.store.log[offset:]
        return {"accepted": count, "results": [asdict(e) for e in entries]}


@router.get("/telemetry/log")
def update_log(op: Operator = Depends(require_operator)):
    with repository.network.lock:
        return [asdict(e) for e in repository.store.log[-200:]]


@router.post("/telemetry/sources")
def register_source(body: SourceIn, op: Operator = Depends(require_operator)):
    if body.source_id == "seed":
        raise HTTPException(400, "Reserved source ID")
    with repository.network.lock:
        repository.store.sources.add(body.source_id)
    return {"source_id": body.source_id, "registered": True}


@router.post("/simulator/start")
def simulator_start(op: Operator = Depends(require_operator)):
    telemetry.start_simulator()
    return {"running": True}


@router.post("/simulator/stop")
def simulator_stop(op: Operator = Depends(require_operator)):
    telemetry.stop_simulator()
    return {"running": False}


# Aggregate TV2 routers here so app.py does not need a shared-file edit.
charging_router = router
vehicles_router = APIRouter(prefix="/api/me", tags=["Private vehicles - TV2"])


@vehicles_router.get("/vehicles")
def list_private_vehicles(user: Student = Depends(require_student)):
    return service.get_my_vehicles(user.user_id)


@vehicles_router.post("/vehicles", status_code=201)
def register_private_vehicle(body: PrivateVehicleIn, user: Student = Depends(require_student)):
    return private_vehicles.register_vehicle(user.user_id, **body.model_dump())


router = APIRouter()
router.include_router(charging_router)
router.include_router(vehicles_router)
