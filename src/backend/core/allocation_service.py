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
        from fastapi import HTTPException
        from ..modules.charging import scheduler, service
        from ..modules.charging.domain import ACTIVE_SESSIONS
        from .state_manager import network
        with network.lock:
            vehicle = network.get_vehicle(vehicle_id)
            if not vehicle.hub_id or not vehicle.owner_id:
                raise HTTPException(400, "A private vehicle parked at a hub is required")
            session = next((s for s in network.charging_sessions.values()
                            if s.vehicle_id == vehicle_id and s.status in ACTIVE_SESSIONS), None)
            if session is None:
                session = service.submit_charging_request(vehicle.owner_id, vehicle_id, vehicle.hub_id)
            scheduler.run_prioritization(vehicle.hub_id)
            return session


allocation_service = AllocationService()
