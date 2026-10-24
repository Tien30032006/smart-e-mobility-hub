"""AllocationService (class diagram) - shared entry point, split by owner.

The diagram has one AllocationService with three methods. To avoid merge
conflicts each method simply delegates to the module that owns the logic.
Keep this file thin; real logic stays in the modules.
"""
from __future__ import annotations

from typing import Optional

from .entities import ChargingSession, ParkingSpace, Reservation
from .todo import todo


class AllocationService:
    def __init__(self, strategy: str = "nearest_available") -> None:
        self.strategy = strategy

    def allocate_vehicle(self, user_id: str, hub_id: str, vehicle_type: Optional[str] = None) -> Reservation:
        # Owner: Member 1 (U2). Pick a vehicle by battery level + availability.
        todo("Member 1", "U2", "choose best shared vehicle at hub (battery, availability)")

    def allocate_parking_space(self, hub_id: str, user_id: Optional[str] = None) -> ParkingSpace:
        # Owner: Member 1 (U3). Must be atomic: use `with network.lock:`.
        todo("Member 1", "U3", "pick a free ParkingSpace and mark reserved_by atomically")

    def schedule_charging(self, vehicle_id: str) -> ChargingSession:
        # Owner: Member 2 (UC-CH-02/09). Delegates to charging.scheduler.
        todo("Member 2", "UC-CH-09", "delegate to modules/charging/scheduler.py")


allocation_service = AllocationService()
