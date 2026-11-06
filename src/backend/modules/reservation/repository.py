"""Reservation storage helpers (in-memory, inside network.reservations).   OWNER: Member 1

Small ready-made helpers; extend as needed. Charging reservations (Member 2) use the
same store, so keep these generic and filter by ``kind``.
"""
from __future__ import annotations

from typing import List, Optional

from ...core.entities import Reservation
from ...core.enums import ReservationKind, ReservationStatus
from ...core.state_manager import network


def add(reservation: Reservation) -> Reservation:
    with network.lock:
        network.reservations[reservation.reservation_id] = reservation
    return reservation


def get(reservation_id: str) -> Optional[Reservation]:
    return network.reservations.get(reservation_id)


def list_by_user(user_id: str, kind: Optional[ReservationKind] = None) -> List[Reservation]:
    return [r for r in network.reservations.values()
            if r.user_id == user_id and (kind is None or r.kind == kind)]


def list_active(hub_id: Optional[str] = None) -> List[Reservation]:
    live = (ReservationStatus.PENDING, ReservationStatus.CONFIRMED, ReservationStatus.ACTIVE)
    return [r for r in network.reservations.values()
            if r.status in live and (hub_id is None or r.hub_id == hub_id)]


def get_active_by_user(user_id: str, kind: Optional[ReservationKind] = None) -> Optional[Reservation]:
    live = (ReservationStatus.PENDING, ReservationStatus.CONFIRMED, ReservationStatus.ACTIVE)
    for r in network.reservations.values():
        if r.user_id == user_id and r.status in live and (kind is None or r.kind == kind):
            return r
    return None


def get_active_by_resource(resource_id: str) -> Optional[Reservation]:
    live = (ReservationStatus.PENDING, ReservationStatus.CONFIRMED, ReservationStatus.ACTIVE)
    for r in network.reservations.values():
        if r.resource_id == resource_id and r.status in live:
            return r
    return None
