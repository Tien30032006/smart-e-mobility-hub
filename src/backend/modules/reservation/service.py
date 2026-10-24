"""Student Discovery & Reservation - business logic.   OWNER: Member 1

Use cases (see Student_Discovery__Reservation_Specification.docx):
  U1 Search Hub and Vehicle detail   U2 Reserve Vehicle     U3 Reserve Parking Slot
  U4 Cancel Reservation              U5 Pick Up Vehicle     U6 Return Vehicle
  U7 Report Issue                    U8 Process Payment  -> payment_gateway.py
  U9 Control Smart Lock              -> smart_lock.py

Implementation notes
  * Wrap every "check free -> mark taken" in ``with network.lock:`` (no double booking).
  * Store reservations through repository.py; kind=ReservationKind.VEHICLE / PARKING.
  * Emit events with ``bus.emit(EventType.X, hub_id=..., ...)`` (see core/enums.py).
  * Vehicle hold lasts 15 minutes (spec U2) -> expire via Reservation.is_expired().
"""
from __future__ import annotations

from typing import List, Optional

from ...core.entities import Reservation
from ...core.todo import todo

OWNER = "Member 1"


# ---- U1 -------------------------------------------------------------------
def search_hubs_and_vehicles(from_hub: Optional[str] = None, to_hub: Optional[str] = None,
                             vehicle_type: Optional[str] = None, min_battery: int = 0) -> List[dict]:
    """Hubs with free vehicles (shared) and free parking slots (private EV)."""
    todo(OWNER, "U1", "filter network.hubs/vehicles; return battery %, free slots; sort by suitability")


def get_vehicle_detail(vehicle_id: str) -> dict:
    todo(OWNER, "U1", "single vehicle: battery, status, hub, estimated range")


# ---- U2 / U3 --------------------------------------------------------------
def reserve_vehicle(user_id: str, hub_id: str, vehicle_id: Optional[str] = None,
                    vehicle_type: Optional[str] = None) -> Reservation:
    """Hold a shared vehicle 15 min. Calls payment_gateway.authorize_deposit (U8)."""
    todo(OWNER, "U2", "lock -> pick vehicle (allocation_service.allocate_vehicle) -> deposit -> RESERVED")


def reserve_parking_slot(user_id: str, hub_id: str, start_time=None, end_time=None,
                         mode: str = "shared_return") -> Reservation:
    """mode: 'shared_return' (return dock for rented vehicle) | 'private' (own EV)."""
    todo(OWNER, "U3", "lock -> allocation_service.allocate_parking_space -> ParkingSpace.reserved_by")


# ---- U4 -------------------------------------------------------------------
def cancel_reservation(reservation_id: str, user_id: Optional[str] = None,
                       reason: str = "user_cancelled", by_system: bool = False) -> Reservation:
    """Release the resource + refund deposit.
    ALSO CALLED BY Member 3 (UC-OP07) with by_system=True when a reserved vehicle breaks down."""
    todo(OWNER, "U4", "Reservation.cancel(); free vehicle/space; refund via payment_gateway; emit RESERVATION_CANCELLED")


# ---- U5 / U6 --------------------------------------------------------------
def pick_up_vehicle(user_id: str, reservation_id: Optional[str] = None, vehicle_id: Optional[str] = None,
                    qr_code: str = "") -> dict:
    """Verify QR, smart_lock.unlock, status -> IN_USE, start trip. Supports walk-up (no reservation)."""
    todo(OWNER, "U5", "validate -> unlock -> vehicle IN_USE -> create trip record -> VEHICLE_PICKED_UP")


def return_vehicle(user_id: str, trip_id: str, hub_id: str) -> dict:
    """Dock via network.move_vehicle(), lock, charge fee (U8), close trip."""
    todo(OWNER, "U6", "network.move_vehicle() -> smart_lock.lock -> payment fee -> VEHICLE_RETURNED")


def list_my_trips(user_id: str) -> List[dict]:
    todo(OWNER, "U5/U6", "reservations + trips of the user for the my-trips page")


# ---- U7 -------------------------------------------------------------------
def report_issue(user_id: str, target_type: str, target_id: str, category: str,
                 description: str = "", photo_urls: Optional[List[str]] = None) -> dict:
    """Validate target, store issue, then bus.emit(EventType.ISSUE_REPORTED, ...).
    Member 3's incident handler (UC05) subscribes to that event - keep the payload keys stable:
    {issue_id, target_type ('vehicle'|'charging_point'|'parking_space'), target_id, category, description}"""
    todo(OWNER, "U7", "store issue + emit ISSUE_REPORTED")
