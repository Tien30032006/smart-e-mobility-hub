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

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from ...core.allocation_service import allocation_service
from ...core.entities import MobilityHub, ParkingSpace, Reservation, new_id, utcnow
from ...core.enums import EventType, ReservationKind, ReservationStatus, VehicleStatus
from ...core.event_bus import bus
from ...core.state_manager import HubNotFound, VehicleNotFound, network
from . import payment_gateway, repository, smart_lock

OWNER = "Member 1"

# In-memory stores for trips and reported issues
_trips: Dict[str, dict] = {}
_issues: Dict[str, dict] = {}


def reset_module_state() -> None:
    """Helper for unit tests: reset trips, issues, payments, and locks."""
    _trips.clear()
    _issues.clear()
    payment_gateway.reset_ledger()
    smart_lock.reset_locks()


def calculate_rental_fee(duration_minutes: float) -> float:
    """Trip rental rate plan (spec U6 / U8):
    10,000 VND for first 30 minutes, 5,000 VND for each subsequent 15-minute block.
    Minimum charge: 10,000 VND.
    """
    if duration_minutes <= 30.0:
        return 10000.0
    extra = duration_minutes - 30.0
    extra_blocks = math.ceil(extra / 15.0)
    return 10000.0 + (extra_blocks * 5000.0)


# ---- Expiry Job ------------------------------------------------------------
def check_expired_reservations(now: Optional[datetime] = None) -> List[str]:
    """Scan and expire reservations that have exceeded their hold window (15m for vehicles).
    Releases the held resource and refunds the security deposit.
    """
    now = now or utcnow()
    expired_ids: List[str] = []

    with network.lock:
        active_reservations = repository.list_active()
        for res in active_reservations:
            if res.is_expired(now):
                if res.kind == ReservationKind.VEHICLE:
                    try:
                        veh = network.get_vehicle(res.resource_id)
                        if veh.status == VehicleStatus.RESERVED:
                            veh.status = VehicleStatus.AVAILABLE
                    except VehicleNotFound:
                        pass

                    if "deposit_tx:" in res.notes:
                        tx_id = res.notes.split("deposit_tx:")[1].split()[0]
                        payment_gateway.refund(tx_id)

                elif res.kind == ReservationKind.PARKING:
                    try:
                        hub = network.get_hub(res.hub_id)
                        for space in hub.parking_spaces.values():
                            if space.reserved_by == res.reservation_id:
                                space.reserved_by = None
                    except HubNotFound:
                        pass

                res.status = ReservationStatus.EXPIRED
                expired_ids.append(res.reservation_id)

                bus.emit(
                    EventType.RESERVATION_CANCELLED,
                    hub_id=res.hub_id,
                    reservation_id=res.reservation_id,
                    reason="hold_expired",
                    by_system=True,
                )

    return expired_ids


# ---- U1 -------------------------------------------------------------------
def search_hubs_and_vehicles(from_hub: Optional[str] = None, to_hub: Optional[str] = None,
                             vehicle_type: Optional[str] = None, min_battery: int = 0) -> List[dict]:
    """Hubs with free vehicles (shared) and free parking slots (private EV)."""
    check_expired_reservations()

    with network.lock:
        hubs = network.list_hubs()
        if from_hub:
            hubs = [h for h in hubs if h.hub_id == from_hub]

        results = []
        for hub in hubs:
            status = network.get_hub_status(hub.hub_id)
            all_vehicles = network.vehicles_at(hub.hub_id)

            available_vehicles = []
            for v in all_vehicles:
                if (
                    v.is_shared
                    and v.status == VehicleStatus.AVAILABLE
                    and v.battery_level >= min_battery
                    and (vehicle_type is None or v.vehicle_type == vehicle_type)
                ):
                    available_vehicles.append({
                        "vehicle_id": v.vehicle_id,
                        "model": v.model,
                        "type": v.vehicle_type,
                        "battery_level": v.battery_level,
                        "status": v.status.value,
                        "estimated_range_km": round(v.battery_level * 0.8, 1),
                    })

            # Sort vehicles by battery level descending
            available_vehicles.sort(key=lambda item: item["battery_level"], reverse=True)

            hub_info = {
                "hub_id": hub.hub_id,
                "name": hub.name,
                "location": hub.location,
                "capacity": hub.capacity,
                "free_spaces": status["free_spaces"],
                "utilization": status["utilization"],
                "near_capacity": status["near_capacity"],
                "vehicles_available": len(available_vehicles),
                "charging_points_free": status["charging_points_free"],
                "vehicles": available_vehicles,
            }
            results.append(hub_info)

        # Sort hubs by available vehicles descending, then free spaces
        results.sort(key=lambda h: (h["vehicles_available"], h["free_spaces"]), reverse=True)
        return results


def get_vehicle_detail(vehicle_id: str) -> dict:
    """Get single vehicle details including battery, status, hub, and estimated range."""
    check_expired_reservations()
    v = network.get_vehicle(vehicle_id)  # raises VehicleNotFound if not found
    hub_name = None
    if v.hub_id:
        try:
            hub_name = network.get_hub(v.hub_id).name
        except HubNotFound:
            pass

    return {
        "vehicle_id": v.vehicle_id,
        "model": v.model,
        "type": v.vehicle_type,
        "battery_level": v.battery_level,
        "status": v.status.value,
        "hub_id": v.hub_id,
        "hub_name": hub_name,
        "is_shared": v.is_shared,
        "owner_id": v.owner_id,
        "estimated_range_km": round(v.battery_level * 0.8, 1),
    }


# ---- U2 / U3 --------------------------------------------------------------
def reserve_vehicle(user_id: str, hub_id: str, vehicle_id: Optional[str] = None,
                    vehicle_type: Optional[str] = None) -> Reservation:
    """Hold a shared vehicle for 15 min. Calls payment_gateway.authorize_deposit (U8).
    Prevents concurrent race conditions via network.lock and returns 409 if unavailable.
    """
    check_expired_reservations()

    # Precondition: Student cannot have another active trip or active vehicle reservation
    active_user_trip = next((t for t in _trips.values() if t["user_id"] == user_id and t["status"] == "active"), None)
    if active_user_trip:
        raise HTTPException(status_code=400, detail="Student already has an active ongoing trip")

    active_user_res = repository.get_active_by_user(user_id, kind=ReservationKind.VEHICLE)
    if active_user_res:
        raise HTTPException(status_code=400, detail="Student already has an active vehicle reservation")

    with network.lock:
        hub = network.get_hub(hub_id)  # raises HubNotFound if not found

        target_vehicle = None
        if vehicle_id:
            try:
                v = network.get_vehicle(vehicle_id)
            except VehicleNotFound:
                raise HTTPException(status_code=404, detail=f"Vehicle {vehicle_id} not found")

            if v.hub_id != hub_id:
                raise HTTPException(status_code=400, detail=f"Vehicle {vehicle_id} is not at hub {hub_id}")
            if not v.is_shared:
                raise HTTPException(status_code=400, detail=f"Vehicle {vehicle_id} is a private vehicle")
            if v.status != VehicleStatus.AVAILABLE:
                raise HTTPException(status_code=409, detail=f"Vehicle {vehicle_id} is no longer available (status: {v.status.value})")
            if v.battery_level < 30:
                raise HTTPException(status_code=400, detail=f"Vehicle battery too low ({v.battery_level}% < 30%)")
            target_vehicle = v
        else:
            candidates = [
                v for v in network.vehicles_at(hub_id)
                if v.is_shared and v.status == VehicleStatus.AVAILABLE and v.battery_level >= 30
                and (vehicle_type is None or v.vehicle_type == vehicle_type)
            ]
            if not candidates:
                raise HTTPException(status_code=409, detail=f"No available shared vehicles matching criteria at hub {hub_id}")
            candidates.sort(key=lambda item: item.battery_level, reverse=True)
            target_vehicle = candidates[0]

        # Authorize security deposit via U8 Payment System
        try:
            tx = payment_gateway.authorize_deposit(user_id, amount=50000.0)
        except payment_gateway.PaymentDeclined as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Transition vehicle state to RESERVED
        target_vehicle.status = VehicleStatus.RESERVED

        # Create Reservation record
        start_time = utcnow()
        end_time = start_time + timedelta(minutes=15)
        res = Reservation(
            reservation_id=new_id("RES-VEH"),
            kind=ReservationKind.VEHICLE,
            user_id=user_id,
            hub_id=hub_id,
            resource_id=target_vehicle.vehicle_id,
            start_time=start_time,
            end_time=end_time,
            status=ReservationStatus.CONFIRMED,
            deposit_amount=50000.0,
            notes=f"deposit_tx:{tx['transaction_id']}",
        )
        repository.add(res)

        # Emit cross-module event
        bus.emit(
            EventType.VEHICLE_RESERVED,
            hub_id=hub_id,
            reservation_id=res.reservation_id,
            vehicle_id=target_vehicle.vehicle_id,
            user_id=user_id,
        )

        return res


def reserve_parking_slot(user_id: str, hub_id: str, start_time: Optional[str] = None,
                         end_time: Optional[str] = None, mode: str = "shared_return") -> Reservation:
    """mode: 'shared_return' (return dock for rented vehicle) | 'private' (own EV)."""
    check_expired_reservations()

    with network.lock:
        hub = network.get_hub(hub_id)  # raises HubNotFound if not found

        try:
            space = allocation_service.allocate_parking_space(hub_id, user_id)
        except ValueError:
            raise HTTPException(status_code=409, detail=f"Hub {hub_id} has no available parking slots")

        start_dt = utcnow()
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
            except Exception:
                pass

        if mode == "shared_return":
            end_dt = start_dt + timedelta(minutes=20)
        else:
            if end_time:
                try:
                    end_dt = datetime.fromisoformat(end_time)
                except Exception:
                    end_dt = start_dt + timedelta(hours=3)
            else:
                end_dt = start_dt + timedelta(hours=3)

        res = Reservation(
            reservation_id=new_id("RES-PARK"),
            kind=ReservationKind.PARKING,
            user_id=user_id,
            hub_id=hub_id,
            resource_id=space.space_id,
            start_time=start_dt,
            end_time=end_dt,
            status=ReservationStatus.CONFIRMED,
            deposit_amount=0.0,
            notes=f"mode:{mode}",
        )

        space.reserved_by = res.reservation_id
        repository.add(res)

        bus.emit(
            EventType.PARKING_RESERVED,
            hub_id=hub_id,
            reservation_id=res.reservation_id,
            space_id=space.space_id,
            user_id=user_id,
        )

        return res


# ---- U4 -------------------------------------------------------------------
def cancel_reservation(reservation_id: str, user_id: Optional[str] = None,
                       reason: str = "user_cancelled", by_system: bool = False) -> Reservation:
    """Release the resource + refund deposit.
    ALSO CALLED BY Member 3 (UC-OP07) with by_system=True when a reserved vehicle breaks down.
    """
    res = repository.get(reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Reservation {reservation_id} not found")

    if user_id and not by_system and res.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this reservation")

    if res.status not in (ReservationStatus.PENDING, ReservationStatus.CONFIRMED):
        raise HTTPException(status_code=400, detail=f"Cannot cancel reservation in status '{res.status.value}'")

    with network.lock:
        if res.kind == ReservationKind.VEHICLE:
            try:
                veh = network.get_vehicle(res.resource_id)
                if veh.status == VehicleStatus.RESERVED:
                    veh.status = VehicleStatus.AVAILABLE
            except VehicleNotFound:
                pass

            if "deposit_tx:" in res.notes:
                tx_id = res.notes.split("deposit_tx:")[1].split()[0]
                payment_gateway.refund(tx_id)

        elif res.kind == ReservationKind.PARKING:
            try:
                hub = network.get_hub(res.hub_id)
                for space in hub.parking_spaces.values():
                    if space.reserved_by == res.reservation_id:
                        space.reserved_by = None
            except HubNotFound:
                pass

        res.status = ReservationStatus.CANCELLED

        bus.emit(
            EventType.RESERVATION_CANCELLED,
            hub_id=res.hub_id,
            reservation_id=res.reservation_id,
            reason=reason,
            by_system=by_system,
        )

        return res


# ---- U5 / U6 --------------------------------------------------------------
def pick_up_vehicle(user_id: str, reservation_id: Optional[str] = None, vehicle_id: Optional[str] = None,
                    qr_code: str = "") -> dict:
    """Verify QR, smart_lock.unlock, status -> IN_USE, start trip. Supports walk-up (no reservation)."""
    check_expired_reservations()

    # Precondition: Student cannot have another active trip
    active_user_trip = next((t for t in _trips.values() if t["user_id"] == user_id and t["status"] == "active"), None)
    if active_user_trip:
        raise HTTPException(status_code=400, detail="Student already has an active ongoing trip")

    with network.lock:
        res = None
        deposit_tx_id = None
        from_hub_id = None

        if reservation_id:
            res = repository.get(reservation_id)
            if not res:
                raise HTTPException(status_code=404, detail=f"Reservation {reservation_id} not found")
            if res.user_id != user_id:
                raise HTTPException(status_code=403, detail="Reservation belongs to another user")
            if res.status != ReservationStatus.CONFIRMED:
                raise HTTPException(status_code=400, detail=f"Reservation is not active (status: {res.status.value})")

            target_vehicle_id = res.resource_id
            if qr_code and qr_code not in (target_vehicle_id, f"QR-{target_vehicle_id}"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Scanned QR '{qr_code}' does not match your reserved vehicle '{target_vehicle_id}'",
                )

            target_vehicle = network.get_vehicle(target_vehicle_id)
            from_hub_id = res.hub_id
            if "deposit_tx:" in res.notes:
                deposit_tx_id = res.notes.split("deposit_tx:")[1].split()[0]

        else:
            # Walk-up rental flow
            target_vehicle_id = vehicle_id or (qr_code[3:] if qr_code.startswith("QR-") else qr_code)
            if not target_vehicle_id:
                raise HTTPException(status_code=400, detail="Vehicle ID or valid QR code is required for pickup")

            try:
                target_vehicle = network.get_vehicle(target_vehicle_id)
            except VehicleNotFound:
                raise HTTPException(status_code=404, detail=f"Vehicle {target_vehicle_id} not found")

            if not target_vehicle.is_shared:
                raise HTTPException(status_code=400, detail="Cannot rent a private vehicle")

            if target_vehicle.status != VehicleStatus.AVAILABLE:
                raise HTTPException(
                    status_code=409,
                    detail=f"Vehicle {target_vehicle_id} is not available (status: {target_vehicle.status.value})",
                )

            if target_vehicle.battery_level < 30:
                raise HTTPException(
                    status_code=400,
                    detail=f"Vehicle battery too low ({target_vehicle.battery_level}% < 30%)",
                )

            from_hub_id = target_vehicle.hub_id or "HUB-METRO"

            # Authorize deposit on-the-spot for walk-up
            try:
                tx = payment_gateway.authorize_deposit(user_id, amount=50000.0)
                deposit_tx_id = tx["transaction_id"]
            except payment_gateway.PaymentDeclined as e:
                raise HTTPException(status_code=400, detail=str(e))

        # Invoke U9 Smart Lock actuator
        unlocked = smart_lock.unlock(target_vehicle.vehicle_id)
        if not unlocked:
            if deposit_tx_id:
                payment_gateway.refund(deposit_tx_id)
            if res:
                res.cancel()
                target_vehicle.status = VehicleStatus.AVAILABLE
            raise HTTPException(
                status_code=500,
                detail="Smart lock hardware actuator failed to unlock. Deposit refunded.",
            )

        # Transition vehicle state to IN_USE
        target_vehicle.status = VehicleStatus.IN_USE

        # Release parking space at source Hub
        if from_hub_id:
            try:
                src_hub = network.get_hub(from_hub_id)
                src_hub.vehicle_ids.discard(target_vehicle.vehicle_id)
                for space in src_hub.parking_spaces.values():
                    if space.vehicle_id == target_vehicle.vehicle_id:
                        space.release()
                target_vehicle.hub_id = None
            except HubNotFound:
                pass

        if res:
            res.status = ReservationStatus.ACTIVE

        # Create active Trip record
        trip_id = new_id("TRIP")
        start_time_iso = utcnow().isoformat()
        trip_record = {
            "trip_id": trip_id,
            "user_id": user_id,
            "vehicle_id": target_vehicle.vehicle_id,
            "vehicle_model": target_vehicle.model,
            "vehicle_type": target_vehicle.vehicle_type,
            "from_hub": from_hub_id,
            "to_hub": None,
            "start_time": start_time_iso,
            "end_time": None,
            "duration_minutes": 0,
            "deposit_tx_id": deposit_tx_id,
            "deposit_amount": 50000.0,
            "rental_fee": 0.0,
            "refund_amount": 0.0,
            "status": "active",
            "reservation_id": res.reservation_id if res else None,
        }
        _trips[trip_id] = trip_record

        # Emit cross-module event
        bus.emit(
            EventType.VEHICLE_PICKED_UP,
            hub_id=from_hub_id,
            vehicle_id=target_vehicle.vehicle_id,
            user_id=user_id,
        )

        return trip_record


def return_vehicle(user_id: str, trip_id: str, hub_id: str) -> dict:
    """Dock via network.move_vehicle(), lock, charge fee (U8), close trip.
    If destination Hub is full and student has not reserved a return dock, returns 409
    with suggested alternative Hubs.
    """
    trip = _trips.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail=f"Trip {trip_id} not found")
    if trip["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Trip belongs to another user")
    if trip["status"] != "active":
        raise HTTPException(status_code=400, detail=f"Trip is not active (status: {trip['status']})")

    with network.lock:
        dest_hub = network.get_hub(hub_id)  # raises HubNotFound if not found
        vehicle = network.get_vehicle(trip["vehicle_id"])

        # Check if student held a return dock at destination Hub via U3
        held_space = None
        for space in dest_hub.parking_spaces.values():
            if space.reserved_by:
                park_res = repository.get(space.reserved_by)
                if park_res and park_res.user_id == user_id and park_res.status in (
                    ReservationStatus.PENDING, ReservationStatus.CONFIRMED, ReservationStatus.ACTIVE
                ):
                    held_space = space
                    park_res.status = ReservationStatus.COMPLETED
                    break

        if held_space is not None:
            allocated_space = held_space
        else:
            if dest_hub.get_available_resources() <= 0:
                # Hub is full! Suggest alternative Hubs with available docks
                alternatives = [
                    h.hub_id for h in network.list_hubs()
                    if h.hub_id != hub_id and h.get_available_resources() > 0
                ]
                alt_str = ", ".join(alternatives) if alternatives else "None"
                raise HTTPException(
                    status_code=409,
                    detail=f"Hub {hub_id} is 100% full. Suggested alternative hubs with free slots: {alt_str}",
                )
            allocated_space = next(s for s in dest_hub.parking_spaces.values() if s.is_available())

        # Dock vehicle into destination space
        allocated_space.occupy(vehicle.vehicle_id)
        dest_hub.vehicle_ids.add(vehicle.vehicle_id)
        vehicle.hub_id = hub_id

        # Engage U9 Smart Lock
        smart_lock.lock(vehicle.vehicle_id)

        # Stop trip timer and compute duration & rental fee
        end_dt = utcnow()
        start_dt = datetime.fromisoformat(trip["start_time"])
        duration_minutes = max(1.0, round((end_dt - start_dt).total_seconds() / 60.0, 1))
        rental_fee = calculate_rental_fee(duration_minutes)

        # Settle payment with deposit via U8
        settlement = payment_gateway.charge_trip_fee(
            user_id=user_id,
            transaction_id=trip.get("deposit_tx_id"),
            amount=rental_fee,
        )

        # Update vehicle status (flag charging if low battery)
        if vehicle.battery_level < 30:
            vehicle.status = VehicleStatus.CHARGING
        else:
            vehicle.status = VehicleStatus.AVAILABLE

        # Close associated vehicle reservation if any
        if trip.get("reservation_id"):
            veh_res = repository.get(trip["reservation_id"])
            if veh_res and veh_res.status == ReservationStatus.ACTIVE:
                veh_res.status = ReservationStatus.COMPLETED

        trip["to_hub"] = hub_id
        trip["end_time"] = end_dt.isoformat()
        trip["duration_minutes"] = duration_minutes
        trip["rental_fee"] = rental_fee
        trip["refund_amount"] = settlement.get("deposit_refunded", 0.0)
        trip["status"] = "completed"

        # Emit cross-module event
        bus.emit(
            EventType.VEHICLE_RETURNED,
            hub_id=hub_id,
            vehicle_id=vehicle.vehicle_id,
            user_id=user_id,
        )

        return {
            "trip_id": trip_id,
            "vehicle_id": vehicle.vehicle_id,
            "from_hub": trip["from_hub"],
            "to_hub": hub_id,
            "start_time": trip["start_time"],
            "end_time": trip["end_time"],
            "duration_minutes": duration_minutes,
            "rental_fee": rental_fee,
            "deposit_refunded": trip["refund_amount"],
            "status": "completed",
        }


def list_my_trips(user_id: str) -> dict:
    """Reservations + active trip + history of the user for the my-trips page."""
    check_expired_reservations()

    user_reservations = []
    for r in repository.list_by_user(user_id):
        user_reservations.append({
            "reservation_id": r.reservation_id,
            "kind": r.kind.value,
            "hub_id": r.hub_id,
            "resource_id": r.resource_id,
            "start_time": r.start_time.isoformat(),
            "end_time": r.end_time.isoformat() if r.end_time else None,
            "status": r.status.value,
            "deposit_amount": r.deposit_amount,
            "notes": r.notes,
        })

    active_trip = next((t for t in _trips.values() if t["user_id"] == user_id and t["status"] == "active"), None)
    history = [t for t in _trips.values() if t["user_id"] == user_id and t["status"] == "completed"]
    history.sort(key=lambda item: item.get("end_time") or "", reverse=True)

    return {
        "user_id": user_id,
        "active_trip": active_trip,
        "reservations": user_reservations,
        "history": history,
    }


# ---- U7 -------------------------------------------------------------------
def report_issue(user_id: str, target_type: str, target_id: str, category: str,
                 description: str = "", photo_urls: Optional[List[str]] = None) -> dict:
    """Validate target, store issue, then bus.emit(EventType.ISSUE_REPORTED, ...).
    Member 3's incident handler (UC05) subscribes to that event - keep the payload keys stable:
    {issue_id, target_type ('vehicle'|'charging_point'|'parking_space'), target_id, category, description}
    """
    if target_type not in ("vehicle", "charging_point", "parking_space"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target_type '{target_type}'. Must be vehicle, charging_point, or parking_space",
        )

    hub_id: Optional[str] = None
    with network.lock:
        if target_type == "vehicle":
            try:
                v = network.get_vehicle(target_id)
                hub_id = v.hub_id
                # Safety action: Automatically quarantine vehicle if severe issue
                if category.lower() in ("brake_failure", "battery_danger", "flat_tire", "severe_damage"):
                    v.status = VehicleStatus.MAINTENANCE
            except VehicleNotFound:
                raise HTTPException(status_code=404, detail=f"Vehicle {target_id} not found")

        elif target_type == "charging_point":
            found = False
            for h in network.list_hubs():
                if target_id in h.charging_points:
                    hub_id = h.hub_id
                    found = True
                    break
            if not found:
                raise HTTPException(status_code=404, detail=f"Charging point {target_id} not found")

        elif target_type == "parking_space":
            found = False
            for h in network.list_hubs():
                if target_id in h.parking_spaces:
                    hub_id = h.hub_id
                    found = True
                    break
            if not found:
                raise HTTPException(status_code=404, detail=f"Parking space {target_id} not found")

        issue_id = new_id("ISSUE")
        issue_record = {
            "issue_id": issue_id,
            "user_id": user_id,
            "target_type": target_type,
            "target_id": target_id,
            "category": category,
            "description": description,
            "photo_urls": photo_urls or [],
            "status": "open",
            "created_at": utcnow().isoformat(),
        }
        _issues[issue_id] = issue_record

        # Contract payload required by Member 3 (UC05)
        bus.emit(
            EventType.ISSUE_REPORTED,
            hub_id=hub_id,
            issue_id=issue_id,
            target_type=target_type,
            target_id=target_id,
            category=category,
            description=description,
        )

        return issue_record
