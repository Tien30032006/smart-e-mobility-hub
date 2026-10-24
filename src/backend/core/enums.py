"""Shared enumerations. SHARED FILE - do not change without telling the whole team.

Every module must use these values (never raw strings) so that statuses
written by one module are understood by the others.
"""
from enum import Enum


class UserRole(str, Enum):
    STUDENT = "student"
    OPERATOR = "operator"


class VehicleStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    IN_USE = "in_use"
    CHARGING = "charging"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class ChargingPointStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"
    OUT_OF_SERVICE = "out_of_service"


class ReservationKind(str, Enum):
    VEHICLE = "vehicle"      # U2  - shared vehicle hold
    PARKING = "parking"      # U3  - parking slot / return dock hold
    CHARGING = "charging"    # UC-CH-02 - charging slot hold


class ReservationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ACTIVE = "active"        # picked up / in use
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ChargingSessionStatus(str, Enum):
    QUEUED = "queued"        # request submitted, waiting for a point
    SCHEDULED = "scheduled"  # point + time window assigned
    CHARGING = "charging"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EventType(str, Enum):
    """Cross-module events. Publish with core.event_bus.bus.emit(...)."""
    # reservation module (Member 1)
    VEHICLE_RESERVED = "vehicle_reserved"
    PARKING_RESERVED = "parking_reserved"
    RESERVATION_CANCELLED = "reservation_cancelled"
    VEHICLE_PICKED_UP = "vehicle_picked_up"
    VEHICLE_RETURNED = "vehicle_returned"
    ISSUE_REPORTED = "issue_reported"            # consumed by operations (UC05)
    # charging module (Member 2)
    CHARGING_REQUESTED = "charging_requested"
    CHARGING_SCHEDULED = "charging_scheduled"
    CHARGING_STARTED = "charging_started"
    CHARGING_COMPLETED = "charging_completed"
    CHARGER_STATUS_CHANGED = "charger_status_changed"
    BATTERY_UPDATED = "battery_updated"
    # operations module (Member 3)
    HUB_NEAR_CAPACITY = "hub_near_capacity"
    ALERT_RAISED = "alert_raised"
    INCIDENT_OPENED = "incident_opened"
    RELOCATION_ORDER_CREATED = "relocation_order_created"
    CHARGING_OVERRIDE = "charging_override"
    # simulation module (Member 4)
    SIMULATION_COMPLETED = "simulation_completed"


# Event types that Event.is_incident() treats as incidents.
INCIDENT_EVENT_TYPES = {EventType.ISSUE_REPORTED, EventType.INCIDENT_OPENED}
