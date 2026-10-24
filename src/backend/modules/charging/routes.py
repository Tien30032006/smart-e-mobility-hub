"""HTTP API of the charging module.   OWNER: Member 2

Base path: /api/charging
  student endpoints  -> require_student      operator endpoints -> require_operator
  /telemetry         -> open (sensor/simulator source, no login)
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...core.auth import require_operator, require_student
from ...core.entities import Operator, Student
from ...core.enums import ChargingPointStatus
from . import point_monitor, scheduler, service, telemetry

router = APIRouter(prefix="/api/charging", tags=["Charging - Member 2"])


class ChargingRequestIn(BaseModel):
    vehicle_id: str
    hub_id: str
    battery_level: int
    needed_by: Optional[str] = None


class ScheduleIn(BaseModel):
    hub_id: str
    vehicle_id: Optional[str] = None
    point_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class PointStatusIn(BaseModel):
    status: ChargingPointStatus
    reason: str = ""


class PrioritizeIn(BaseModel):
    hub_id: str


class Reading(BaseModel):
    kind: str
    id: str
    battery_level: Optional[int] = None
    status: Optional[str] = None


# ---- student --------------------------------------------------------------
@router.post("/requests")                                  # UC-CH-01
def submit_request(body: ChargingRequestIn, user: Student = Depends(require_student)):
    return service.submit_charging_request(user.user_id, **body.model_dump())


@router.get("/hubs/{hub_id}/points")                       # UC-CH-03
def available_points(hub_id: str, start_time: Optional[str] = None, end_time: Optional[str] = None):
    return service.list_available_points(hub_id, start_time, end_time)


@router.post("/reservations")                              # UC-CH-02
def schedule(body: ScheduleIn, user: Student = Depends(require_student)):
    return service.schedule_charging_session(user.user_id, **body.model_dump())


@router.get("/suggestion")                                 # UC-CH-04
def suggestion(vehicle_id: str, needed_by: Optional[str] = None, user: Student = Depends(require_student)):
    return service.get_smart_suggestion(user.user_id, vehicle_id, needed_by)


@router.post("/reservations/{item_id}/cancel")             # UC-CH-05
def cancel(item_id: str, user: Student = Depends(require_student)):
    return service.cancel_charging_reservation(user.user_id, item_id)


@router.get("/my-status")                                  # UC-CH-06
def my_status(user: Student = Depends(require_student)):
    return service.get_my_charging_status(user.user_id)


# ---- operator -------------------------------------------------------------
@router.get("/points")                                     # UC-CH-07
def points_status(hub_id: Optional[str] = None, op: Operator = Depends(require_operator)):
    return point_monitor.get_points_status(hub_id)


@router.patch("/points/{point_id}/status")                 # UC-CH-08
def update_point(point_id: str, body: PointStatusIn, op: Operator = Depends(require_operator)):
    return point_monitor.update_point_status(point_id, body.status, op.user_id, body.reason)


@router.post("/prioritization/run")                        # UC-CH-09
def run_prioritization(body: PrioritizeIn, op: Operator = Depends(require_operator)):
    return scheduler.run_prioritization(body.hub_id)


# ---- sensor / simulator ---------------------------------------------------
@router.post("/telemetry")                                 # UC-CH-10
def report(readings: List[Reading]):
    return {"accepted": telemetry.ingest_readings([r.model_dump() for r in readings])}
