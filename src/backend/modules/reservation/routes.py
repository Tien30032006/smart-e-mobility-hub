"""HTTP API of the reservation module.   OWNER: Member 1

Base path: /api/reservation  (students only; see core.auth.require_student)
Refine request/response schemas as you implement; keep the paths stable because
frontend pages (student/*.html) call them through src/shared/api-client.js.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...core.auth import require_student
from ...core.entities import Student
from . import service

router = APIRouter(prefix="/api/reservation", tags=["Reservation - Member 1"])


class ReserveVehicleIn(BaseModel):
    hub_id: str
    vehicle_id: Optional[str] = None
    vehicle_type: Optional[str] = None


class ReserveParkingIn(BaseModel):
    hub_id: str
    mode: str = "shared_return"       # shared_return | private
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class PickUpIn(BaseModel):
    reservation_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    qr_code: str = ""


class ReturnIn(BaseModel):
    trip_id: str
    hub_id: str


class IssueIn(BaseModel):
    target_type: str                  # vehicle | charging_point | parking_space
    target_id: str
    category: str
    description: str = ""
    photo_urls: List[str] = []


@router.get("/search")                                    # U1
def search(from_hub: Optional[str] = None, to_hub: Optional[str] = None,
           vehicle_type: Optional[str] = None, min_battery: int = 0):
    return service.search_hubs_and_vehicles(from_hub, to_hub, vehicle_type, min_battery)


@router.get("/vehicles/{vehicle_id}")                     # U1 detail
def vehicle_detail(vehicle_id: str):
    return service.get_vehicle_detail(vehicle_id)


@router.post("/vehicles/reserve")                         # U2
def reserve_vehicle(body: ReserveVehicleIn, user: Student = Depends(require_student)):
    return service.reserve_vehicle(user.user_id, **body.model_dump())


@router.post("/parking/reserve")                          # U3
def reserve_parking(body: ReserveParkingIn, user: Student = Depends(require_student)):
    return service.reserve_parking_slot(user.user_id, body.hub_id, body.start_time, body.end_time, body.mode)


@router.post("/reservations/{reservation_id}/cancel")     # U4
def cancel(reservation_id: str, user: Student = Depends(require_student)):
    return service.cancel_reservation(reservation_id, user_id=user.user_id)


@router.post("/pickup")                                   # U5
def pick_up(body: PickUpIn, user: Student = Depends(require_student)):
    return service.pick_up_vehicle(user.user_id, **body.model_dump())


@router.post("/return")                                   # U6
def return_vehicle(body: ReturnIn, user: Student = Depends(require_student)):
    return service.return_vehicle(user.user_id, body.trip_id, body.hub_id)


@router.post("/issues")                                   # U7
def report_issue(body: IssueIn, user: Student = Depends(require_student)):
    return service.report_issue(user.user_id, **body.model_dump())


@router.get("/my-trips")                                  # my-trips page
def my_trips(user: Student = Depends(require_student)):
    return service.list_my_trips(user.user_id)
