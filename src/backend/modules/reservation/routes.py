"""HTTP API of the reservation & student wallet module.   OWNER: Member 1

Endpoints:
- /api/reservation/*: Discovery, reservation, pickup, return, cancellation, issue reporting.
- /api/wallet, /api/wallet/transactions, /api/wallet/topup: Student digital wallet.
- /api/payments/callback: Idempotent payment callback from checkout gateway.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from ...core.auth import require_student
from ...core.entities import Student
from ...core.state_manager import network
from . import geo, payment_gateway, service

router = APIRouter(tags=["Reservation & Wallet - Member 1"])


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


class TopUpIn(BaseModel):
    amount: int
    method: str = "demo"


class PaymentCallbackIn(BaseModel):
    order_id: str
    amount: int
    user_id: str
    signature: str
    success: bool = True


# ---- U1 Search -------------------------------------------------------------
@router.get("/api/reservation/search")
def search(from_hub: Optional[str] = None, to_hub: Optional[str] = None,
           vehicle_type: Optional[str] = None, min_battery: int = 0):
    return service.search_hubs_and_vehicles(from_hub, to_hub, vehicle_type, min_battery)


@router.get("/api/reservation/hubs/nearby")
def hubs_nearby(lat: float = Query(..., ge=-90, le=90), lng: float = Query(..., ge=-180, le=180),
                limit: int = Query(0, ge=0, le=50)):
    """U1: hubs sorted by straight-line distance from a GPS fix or a point picked on the map."""
    return geo.rank_by_distance((network.get_hub_status(h) for h in list(network.hubs)), lat, lng, limit)


@router.get("/api/reservation/vehicles/{vehicle_id}")
def vehicle_detail(vehicle_id: str):
    return service.get_vehicle_detail(vehicle_id)


# ---- U2 / U3 Reservation ---------------------------------------------------
@router.post("/api/reservation/vehicles/reserve")
def reserve_vehicle(body: ReserveVehicleIn, user: Student = Depends(require_student)):
    return service.reserve_vehicle(user.user_id, **body.model_dump())


@router.post("/api/reservation/parking/reserve")
def reserve_parking(body: ReserveParkingIn, user: Student = Depends(require_student)):
    return service.reserve_parking_slot(user.user_id, body.hub_id, body.start_time, body.end_time, body.mode)


# ---- U4 Cancellation -------------------------------------------------------
@router.post("/api/reservation/reservations/{reservation_id}/cancel")
def cancel(reservation_id: str, user: Student = Depends(require_student)):
    return service.cancel_reservation(reservation_id, user_id=user.user_id)


# ---- U5 / U6 Pickup & Return -----------------------------------------------
@router.post("/api/reservation/pickup")
def pick_up(body: PickUpIn, user: Student = Depends(require_student)):
    return service.pick_up_vehicle(user.user_id, **body.model_dump())


@router.post("/api/reservation/return")
def return_vehicle(body: ReturnIn, user: Student = Depends(require_student)):
    return service.return_vehicle(user.user_id, body.trip_id, body.hub_id)


# ---- U7 Issue Reporting ---------------------------------------------------
@router.post("/api/reservation/issues")
def report_issue(body: IssueIn, user: Student = Depends(require_student)):
    return service.report_issue(user.user_id, **body.model_dump())


# ---- My Trips Page ---------------------------------------------------------
@router.get("/api/reservation/my-trips")
def my_trips(user: Student = Depends(require_student)):
    return service.list_my_trips(user.user_id)


# ---- Student Wallet & Payment Integration (Pipeline Extension) ------------
@router.get("/api/wallet")
def get_student_wallet(user: Student = Depends(require_student)):
    """GET /api/wallet: Return current student wallet balance and held deposit."""
    return payment_gateway.get_wallet(user.user_id)


@router.get("/api/wallet/transactions")
def get_wallet_transactions(user: Student = Depends(require_student)):
    """GET /api/wallet/transactions: Return audit ledger transactions for student."""
    return payment_gateway.list_transactions_by_user(user.user_id)


@router.post("/api/wallet/topup")
def topup_wallet(body: TopUpIn, user: Student = Depends(require_student)):
    """Create a demo, VietQR, or MoMo top-up order using server-side provider config."""
    try:
        return payment_gateway.create_topup_order(user.user_id, body.amount, body.method)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except payment_gateway.PaymentError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/api/wallet/payment-methods")
def wallet_payment_methods(user: Student = Depends(require_student)):
    return payment_gateway.available_payment_methods()


@router.get("/api/wallet/topup/{order_id}")
def topup_status(order_id: str, user: Student = Depends(require_student)):
    try:
        return payment_gateway.get_order_status(user.user_id, order_id)
    except payment_gateway.PaymentError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/payments/callback")
def payment_callback(body: PaymentCallbackIn):
    """POST /api/payments/callback: Process checkout payment callback with HMAC verification & idempotency."""
    try:
        return payment_gateway.process_payment_callback(
            order_id=body.order_id,
            amount=body.amount,
            user_id=body.user_id,
            signature=body.signature,
            success=body.success,
        )
    except payment_gateway.PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/payments/momo/ipn", status_code=204)
async def momo_payment_ipn(request: Request):
    """MoMo's server-to-server callback; never accept a browser-generated success signal."""
    try:
        payment_gateway.process_momo_ipn(await request.json())
    except payment_gateway.PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(status_code=204)
