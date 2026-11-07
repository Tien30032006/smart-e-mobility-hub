"""HubNetworkManager - the single in-memory source of truth. SHARED FILE.

All modules read/write shared state through the ``network`` singleton.

Concurrency rule: any read-modify-write on shared state (booking a slot,
changing a vehicle's hub, assigning a charging point) must run inside
``with network.lock:`` so two students cannot double-book the same resource.
``network.snapshot()`` returns a deep copy - the What-if engine works on that
copy only and must never touch live objects.
"""
from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from .entities import (
    ChargingSession, Event, EVehicle, MobilityHub, ParkingSpace, Reservation, User, utcnow,
)
from .enums import ChargingPointStatus, VehicleStatus
from .todo import todo


class HubNotFound(KeyError):
    pass


class VehicleNotFound(KeyError):
    pass


@dataclass
class NetworkSnapshot:
    """Read-only deep copy of the network at one instant (UC4 of What-if)."""
    taken_at: datetime
    hubs: Dict[str, MobilityHub]
    vehicles: Dict[str, EVehicle]
    reservations: Dict[str, Reservation]
    charging_sessions: Dict[str, ChargingSession]


class HubNetworkManager:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.hubs: Dict[str, MobilityHub] = {}
        self.vehicles: Dict[str, EVehicle] = {}
        self.users: Dict[str, User] = {}
        self.reservations: Dict[str, Reservation] = {}
        self.charging_sessions: Dict[str, ChargingSession] = {}
        # Demo switches (TV5): hubs / vehicles whose telemetry is cut ("Data connection lost").
        self.cut_hubs: set = set()
        self.cut_vehicles: set = set()
        # Extra per-module stores (alerts, incidents, relocation orders, ...)
        # can be added by modules in their own files - do not grow this class.

    # ---- registration -----------------------------------------------------
    def reset(self) -> None:
        with self.lock:
            self.hubs.clear()
            self.vehicles.clear()
            self.users.clear()
            self.reservations.clear()
            self.charging_sessions.clear()
            self.cut_hubs.clear()
            self.cut_vehicles.clear()

    def register_hub(self, hub: MobilityHub) -> None:
        with self.lock:
            self.hubs[hub.hub_id] = hub

    def register_vehicle(self, vehicle: EVehicle) -> None:
        """Add a vehicle; if it has a hub_id it occupies a free parking space there."""
        with self.lock:
            self.vehicles[vehicle.vehicle_id] = vehicle
            if vehicle.hub_id:
                hub = self.get_hub(vehicle.hub_id)
                hub.vehicle_ids.add(vehicle.vehicle_id)
                space = self._free_space(hub)
                if space is not None:
                    space.occupy(vehicle.vehicle_id)

    def register_user(self, user: User) -> None:
        with self.lock:
            self.users[user.user_id] = user

    # ---- lookups ----------------------------------------------------------
    def get_hub(self, hub_id: str) -> MobilityHub:
        try:
            return self.hubs[hub_id]
        except KeyError:
            raise HubNotFound(hub_id) from None

    def get_vehicle(self, vehicle_id: str) -> EVehicle:
        try:
            return self.vehicles[vehicle_id]
        except KeyError:
            raise VehicleNotFound(vehicle_id) from None

    def list_hubs(self) -> List[MobilityHub]:
        return list(self.hubs.values())

    def vehicles_at(self, hub_id: str) -> List[EVehicle]:
        hub = self.get_hub(hub_id)
        return [self.vehicles[v] for v in hub.vehicle_ids if v in self.vehicles]

    # ---- status views (UC01 dashboard / Student.viewHubStatus) ------------
    def get_hub_status(self, hub_id: str) -> dict:
        with self.lock:
            hub = self.get_hub(hub_id)
            vehicles = self.vehicles_at(hub_id)
            points = list(hub.charging_points.values())
            return {
                "hub_id": hub.hub_id,
                "name": hub.name,
                "location": hub.location,
                "capacity": hub.capacity,
                "free_spaces": hub.get_available_resources(),
                "utilization": hub.update_utilization(),
                "near_capacity": hub.is_near_capacity(),
                "vehicles_total": len(vehicles),
                "vehicles_available": sum(v.status == VehicleStatus.AVAILABLE for v in vehicles),
                "vehicles_charging": sum(v.status == VehicleStatus.CHARGING for v in vehicles),
                "charging_points_total": len(points),
                "charging_points_free": sum(p.status == ChargingPointStatus.AVAILABLE for p in points),
                "charging_points_out_of_service": sum(
                    p.status == ChargingPointStatus.OUT_OF_SERVICE for p in points),
                "data_connection": "lost" if hub_id in self.cut_hubs else "ok",
            }

    def get_network_status(self) -> dict:
        with self.lock:
            hubs = [self.get_hub_status(h) for h in self.hubs]
            return {
                "generated_at": utcnow().isoformat(),
                "hubs": hubs,
                "totals": {
                    "hubs": len(hubs),
                    "vehicles_available": sum(h["vehicles_available"] for h in hubs),
                    "vehicles_charging": sum(h["vehicles_charging"] for h in hubs),
                    "free_spaces": sum(h["free_spaces"] for h in hubs),
                    "charging_points_free": sum(h["charging_points_free"] for h in hubs),
                },
            }

    # ---- shared primitive: atomic vehicle move ----------------------------
    def move_vehicle(self, vehicle_id: str, to_hub_id: str) -> bool:
        """Atomically re-dock a vehicle at another hub.

        Returns False (state untouched) when the destination has no free space.
        Used by: Member 1 (return vehicle U6), Member 3 (relocation UC03).
        """
        with self.lock:
            vehicle = self.get_vehicle(vehicle_id)
            dest = self.get_hub(to_hub_id)
            if vehicle.hub_id == to_hub_id:
                return True
            space = self._free_space(dest)
            if space is None:
                return False
            if vehicle.hub_id:
                src = self.get_hub(vehicle.hub_id)
                src.vehicle_ids.discard(vehicle_id)
                for s in src.parking_spaces.values():
                    if s.vehicle_id == vehicle_id:
                        s.release()
            space.occupy(vehicle_id)
            dest.vehicle_ids.add(vehicle_id)
            vehicle.hub_id = to_hub_id
            return True

    @staticmethod
    def _free_space(hub: MobilityHub):
        return next((s for s in hub.parking_spaces.values() if s.is_available()), None)

    # ---- class-diagram method owned by a member ---------------------------
    def redistribute_vehicles(self, from_hub: str, to_hub: str) -> bool:
        todo("Member 3", "UC03", "delegate to modules/operations/redistribution.py; use move_vehicle()")

    # ---- snapshot for What-if ---------------------------------------------
    def snapshot(self) -> NetworkSnapshot:
        with self.lock:
            return NetworkSnapshot(
                taken_at=utcnow(),
                hubs=copy.deepcopy(self.hubs),
                vehicles=copy.deepcopy(self.vehicles),
                reservations=copy.deepcopy(self.reservations),
                charging_sessions=copy.deepcopy(self.charging_sessions),
            )


network = HubNetworkManager()
