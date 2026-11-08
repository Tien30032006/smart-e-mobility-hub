"""Operations-module constants, enums and small helpers.   OWNER: Member 3

Statuses owned by this module live here (not in core/enums.py) so that the
shared enum file stays untouched. Values are plain lowercase strings so they
serialise to JSON and SQLite without any conversion.
"""
from __future__ import annotations

from enum import Enum


class AlertStatus(str, Enum):
    UNREAD = "unread"                         # raised, nobody looked at it yet
    ACKNOWLEDGED = "acknowledged"             # an operator is handling it (UC02 step 7)
    RESOLVED = "resolved"                     # operator closed it
    RESOLVED_BY_SYSTEM = "resolved_by_system" # condition disappeared (UC02 alt 7a)


class AlertType(str, Enum):
    HUB_NEAR_CAPACITY = "hub_near_capacity"
    HUB_VEHICLES_LOW = "hub_vehicles_low"
    HUB_LOW_BATTERY = "hub_low_battery"
    HUB_CONNECTION_LOST = "hub_connection_lost"
    VEHICLE_CONNECTION_LOST = "vehicle_connection_lost"
    CHARGER_OUT_OF_SERVICE = "charger_out_of_service"
    RELOCATION_UNASSIGNED = "relocation_unassigned"
    RELOCATION_REJECTED = "relocation_rejected"
    INCIDENT = "incident"


# Alert types derived from live data: scan_for_alerts() raises AND auto-resolves them.
# INCIDENT / RELOCATION_REJECTED alerts are closed explicitly by the code that owns them.
AUTO_TYPES = {
    AlertType.HUB_NEAR_CAPACITY, AlertType.HUB_VEHICLES_LOW, AlertType.HUB_LOW_BATTERY,
    AlertType.HUB_CONNECTION_LOST, AlertType.VEHICLE_CONNECTION_LOST,
    AlertType.CHARGER_OUT_OF_SERVICE, AlertType.RELOCATION_UNASSIGNED,
}

OPEN_ALERT = {AlertStatus.UNREAD.value, AlertStatus.ACKNOWLEDGED.value}


class IncidentStatus(str, Enum):
    OPEN = "open"                      # reported, device still in service
    IN_MAINTENANCE = "in_maintenance"  # device blocked + ticket created
    RESOLVED = "resolved"              # repaired / dismissed


class TicketStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    CLOSED = "closed"


class OrderStatus(str, Enum):
    PENDING = "pending"        # created, waiting for field staff
    ASSIGNED = "assigned"      # a staff member accepted
    DONE = "done"              # vehicles moved
    CANCELLED = "cancelled"    # operator cancelled, vehicles + slots released


ACTIVE_ORDER = {OrderStatus.PENDING.value, OrderStatus.ASSIGNED.value}
PRIORITIES = ("low", "medium", "high", "critical")

# ---- thresholds (tune here, not in the logic) -------------------------------
NEAR_CAPACITY = 0.85          # == MobilityHub.is_near_capacity default
LOW_VEHICLES = 1              # a hub with <= this many AVAILABLE vehicles is "running out"
LOW_BATTERY = 20              # percent
LOW_BATTERY_SHARE = 0.5       # >= 50% of the fleet below LOW_BATTERY ...
LOW_BATTERY_MIN = 2           # ... and at least this many vehicles
MIN_RELOCATION_BATTERY = 30   # never move a nearly flat vehicle
TARGET_UTILIZATION = 0.70     # redistribution tries to bring a full hub down to this
TARGET_STOCK = 3              # redistribution tries to bring a short hub up to this
SHORTAGE_VEHICLES = 2         # hub with <= this many AVAILABLE vehicles is short
ORDER_ACK_MINUTES = 15        # PENDING longer than this -> operator alert
SAFE_BATTERY = 85             # charging stops being useful above this (UC-OP08 alt 5a)


def battery_band(level: int) -> str:
    """UC01 step 5: vehicles are grouped by battery level."""
    return "low" if level < LOW_BATTERY else "medium" if level < 60 else "high"
