"""Shared domain entities - 1:1 with the team's Class Diagram. SHARED FILE.

Python naming: the diagram's camelCase becomes snake_case
(``getAvailableResources`` -> ``get_available_resources``).

Rules
-----
* Do NOT rename fields/methods or add required fields here without agreement
  from all four members - every module depends on this file.
* Methods marked ``todo(...)`` belong to the named member. Replace the body,
  keep the signature.
* Mutating shared state must happen inside ``with network.lock:``.
* SimulationScenario / SimulationResult live in modules/simulation/models.py
  (owned by Member 4); AllocationService lives in core/allocation_service.py.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .enums import (
    INCIDENT_EVENT_TYPES,
    ChargingPointStatus,
    ChargingSessionStatus,
    EventType,
    ReservationKind,
    ReservationStatus,
    Severity,
    UserRole,
    VehicleStatus,
)
from .todo import todo


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------- #
# Users                                                                       #
# --------------------------------------------------------------------------- #
@dataclass
class User(ABC):
    """<<abstract>> User"""
    user_id: str
    full_name: str
    email: str

    @property
    @abstractmethod
    def user_role(self) -> UserRole: ...

    def login(self) -> bool:
        """Real credential check lives in core.auth.login(); entity-level always True."""
        return True

    def view_hub_status(self, hub_id: str) -> List[dict]:
        from .state_manager import network
        return [network.get_hub_status(hub_id)]


@dataclass
class Student(User):
    student_code: str = ""
    has_private_ev: bool = False

    @property
    def user_role(self) -> UserRole:
        return UserRole.STUDENT

    def find_vehicle(self, from_hub: str, to_hub: str) -> List[dict]:
        # Delegates to reservation module - implemented by Member 1 (U1).
        from ..modules.reservation import service
        return service.search_hubs_and_vehicles(from_hub=from_hub, to_hub=to_hub)

    def reserve_resource(self, kind: ReservationKind, hub_id: str, **kwargs) -> "Reservation":
        # Delegates by kind: VEHICLE/PARKING -> Member 1, CHARGING -> Member 2.
        if kind == ReservationKind.VEHICLE:
            from ..modules.reservation import service
            return service.reserve_vehicle(self.user_id, hub_id=hub_id, **kwargs)
        if kind == ReservationKind.PARKING:
            from ..modules.reservation import service
            return service.reserve_parking_slot(self.user_id, hub_id=hub_id, **kwargs)
        from ..modules.charging import service as charging_service
        return charging_service.schedule_charging_session(self.user_id, hub_id=hub_id, **kwargs)


@dataclass
class Operator(User):
    operator_id: str = ""
    role: str = "Hub Operator"

    @property
    def user_role(self) -> UserRole:
        return UserRole.OPERATOR

    def monitor_network(self) -> dict:
        from .state_manager import network
        return network.get_network_status()

    def handle_incident(self, incident_id: str) -> bool:
        # Implemented by Member 3 (UC05).
        from ..modules.operations import incident_handler
        return incident_handler.handle_incident(incident_id, self.user_id)


# --------------------------------------------------------------------------- #
# Physical resources                                                          #
# --------------------------------------------------------------------------- #
@dataclass
class ParkingSpace:
    space_id: str
    hub_id: str
    zone: str = "A"
    is_occupied: bool = False
    vehicle_id: Optional[str] = None      # who is parked here
    reserved_by: Optional[str] = None     # reservation_id holding this slot (U3)

    def is_available(self) -> bool:
        return not self.is_occupied and self.reserved_by is None

    def occupy(self, vehicle_id: Optional[str] = None) -> None:
        self.is_occupied = True
        self.vehicle_id = vehicle_id
        self.reserved_by = None

    def release(self) -> None:
        self.is_occupied = False
        self.vehicle_id = None


@dataclass
class ChargingPoint:
    point_id: str
    hub_id: str
    power_rating: float = 3.3             # kW
    status: ChargingPointStatus = ChargingPointStatus.AVAILABLE
    current_session_id: Optional[str] = None

    def is_operational(self) -> bool:
        return self.status != ChargingPointStatus.OUT_OF_SERVICE

    def start_session(self, vehicle_id: str) -> "ChargingSession":
        """Minimal start (point -> OCCUPIED). Member 2 may extend with queue/ETA logic."""
        if not self.is_operational():
            raise ValueError(f"{self.point_id} is out of service")
        if self.status == ChargingPointStatus.OCCUPIED:
            raise ValueError(f"{self.point_id} is already occupied")
        session = ChargingSession(
            session_id=new_id("CS"), vehicle_id=vehicle_id,
            point_id=self.point_id, hub_id=self.hub_id,
            start_time=utcnow(), status=ChargingSessionStatus.CHARGING,
        )
        self.status = ChargingPointStatus.OCCUPIED
        self.current_session_id = session.session_id
        return session


@dataclass
class EVehicle:
    vehicle_id: str
    model: str = ""
    vehicle_type: str = "e-bike"          # e-bike | e-motorcycle | e-scooter
    battery_level: int = 100              # percent 0..100
    status: VehicleStatus = VehicleStatus.AVAILABLE
    hub_id: Optional[str] = None
    owner_id: Optional[str] = None        # set for a student's private EV; None = shared fleet

    @property
    def is_shared(self) -> bool:
        return self.owner_id is None

    def get_battery_level(self) -> int:
        return self.battery_level

    def update_status(self, status: VehicleStatus) -> None:
        self.status = VehicleStatus(status)

    def assign_to_hub(self, hub_id: str) -> None:
        from .state_manager import network
        network.move_vehicle(self.vehicle_id, hub_id)


@dataclass
class MobilityHub:
    hub_id: str
    name: str
    location: Dict[str, float]            # {"lat": .., "lng": ..}
    capacity: int                         # == number of parking spaces
    parking_spaces: Dict[str, ParkingSpace] = field(default_factory=dict)
    charging_points: Dict[str, ChargingPoint] = field(default_factory=dict)
    vehicle_ids: Set[str] = field(default_factory=set)
    utilization: float = 0.0

    def get_available_resources(self) -> int:
        """Free parking spaces (not occupied, not reserved)."""
        return sum(1 for s in self.parking_spaces.values() if s.is_available())

    def update_utilization(self) -> float:
        total = len(self.parking_spaces) or 1
        used = sum(1 for s in self.parking_spaces.values() if not s.is_available())
        self.utilization = round(used / total, 3)
        return self.utilization

    def is_near_capacity(self, threshold: float = 0.85) -> bool:
        return self.update_utilization() >= threshold


# --------------------------------------------------------------------------- #
# Business records                                                            #
# --------------------------------------------------------------------------- #
@dataclass
class Reservation:
    reservation_id: str
    kind: ReservationKind
    user_id: str
    hub_id: str
    resource_id: str                      # vehicle_id | space_id | point_id
    start_time: datetime = field(default_factory=utcnow)
    end_time: Optional[datetime] = None
    status: ReservationStatus = ReservationStatus.PENDING
    deposit_amount: float = 0.0
    notes: str = ""

    def confirm(self) -> bool:
        if self.status == ReservationStatus.PENDING:
            self.status = ReservationStatus.CONFIRMED
            return True
        return False

    def cancel(self) -> bool:
        if self.status in (ReservationStatus.PENDING, ReservationStatus.CONFIRMED):
            self.status = ReservationStatus.CANCELLED
            return True
        return False

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or utcnow()
        return (
            self.end_time is not None
            and self.end_time < now
            and self.status in (ReservationStatus.PENDING, ReservationStatus.CONFIRMED)
        )


@dataclass
class ChargingSession:
    session_id: str
    vehicle_id: str
    point_id: Optional[str] = None
    hub_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    needed_by: Optional[datetime] = None  # when the owner needs the vehicle again
    priority: int = 0                     # higher = charged first
    status: ChargingSessionStatus = ChargingSessionStatus.QUEUED
    requested_by: Optional[str] = None    # user_id

    def schedule(self) -> None:
        todo("Member 2", "UC-CH-02", "assign point + time window, status=SCHEDULED")

    def complete(self) -> None:
        todo("Member 2", "UC-CH-06", "set end_time, status=COMPLETED, free the charging point")

    def calculate_priority(self) -> int:
        todo("Member 2", "UC-CH-09", "priority from battery level + urgency (needed_by)")


@dataclass
class Event:
    event_type: EventType
    hub_id: Optional[str] = None
    severity: Severity = Severity.INFO
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: new_id("EV"))
    timestamp: datetime = field(default_factory=utcnow)

    def is_incident(self) -> bool:
        return self.event_type in INCIDENT_EVENT_TYPES

    def describe(self) -> str:
        where = f" @ {self.hub_id}" if self.hub_id else ""
        return f"[{self.severity.value}] {self.event_type.value}{where} {self.payload}"
