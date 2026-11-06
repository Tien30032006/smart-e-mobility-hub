"""Charging-specific records and policies; shared entity contracts stay unchanged."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import ceil
from typing import Optional, Protocol

from fastapi import HTTPException

from ...core.entities import ChargingSession, Reservation, utcnow
from ...core.enums import ChargingSessionStatus, ReservationStatus

FRESH_SECONDS = 120
BOOKING_DAYS = 7
QUEUE_LIMIT = 100
# Demo assumption: entities do not yet expose vehicle battery capacity.
BATTERY_CAPACITY_KWH = 3.3
ACTIVE_SESSIONS = {ChargingSessionStatus.QUEUED, ChargingSessionStatus.SCHEDULED,
                   ChargingSessionStatus.CHARGING}
ACTIVE_RESERVATIONS = {ReservationStatus.PENDING, ReservationStatus.CONFIRMED,
                       ReservationStatus.ACTIVE}


def timestamp(value, name="time") -> Optional[datetime]:
    if value is None:
        return None
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("Timezone required")
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, f"{name} must be an ISO-8601 timestamp with timezone") from None


def percentage(value, name="battery_level") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise HTTPException(400, f"{name} must be an integer between 0 and 100")
    return value


def overlaps(start, end, other_start, other_end) -> bool:
    return start < other_end and other_start < end


def charging_minutes(battery, target, power) -> int:
    if power <= 0:
        raise HTTPException(400, "Charging point must have positive power")
    return max(1, ceil(max(0, target - battery) / 100 * BATTERY_CAPACITY_KWH / power * 60))


@dataclass
class ChargingRecord(ChargingSession):
    created_at: datetime = field(default_factory=utcnow)
    target_level: int = 100
    battery_level_used: int = 0
    battery_updated_at: Optional[datetime] = None
    battery_unconfirmed: bool = False
    reservation_id: Optional[str] = None
    point_unavailable: bool = False


@dataclass
class ChargingBooking(Reservation):
    session_id: str = ""
    vehicle_id: str = ""
    point_unavailable: bool = False


class LogResult(str, Enum):
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    IGNORED = "Ignored"


@dataclass
class UpdateLogEntry:
    source_id: str
    kind: str
    item_id: str
    values: dict
    device_timestamp: Optional[datetime]
    reception_time: datetime
    result: LogResult
    reason: str = ""


class PriorityPolicy(Protocol):
    """A scheduler can receive any scoring policy with this small interface."""
    def score(self, battery_level: int, needed_by: Optional[datetime], now: datetime,
              *, waiting_minutes: float = 0) -> int: ...


class WeightedPriorityPolicy:
    def score(self, battery_level, needed_by, now, *, waiting_minutes=0):
        percentage(battery_level)
        minutes = (needed_by - now).total_seconds() / 60 if needed_by else 240
        urgency = max(0, min(100, (240 - minutes) / 210 * 100))
        return round(0.6 * (100 - battery_level) + 0.4 * urgency)


class SelectedCriteriaPolicy:
    """Equal weights for an explicitly selected subset of criteria."""
    def __init__(self, criteria):
        self.criteria = tuple(criteria)

    def score(self, battery_level, needed_by, now, *, waiting_minutes=0):
        percentage(battery_level)
        minutes = (needed_by - now).total_seconds() / 60 if needed_by else 240
        values = {"battery_level": 100 - battery_level,
                  "needed_by": max(0, min(100, (240 - minutes) / 210 * 100)),
                  "waiting_time": min(100, max(0, waiting_minutes))}
        return round(sum(values[k] for k in self.criteria) / len(self.criteria))


@dataclass
class Proposal:
    proposal_id: str
    hub_id: str
    operator_id: str
    generated_at: datetime
    horizon_end: datetime
    fingerprint: str
    ranking: list[dict]
    assignments: list[dict]
    unserved: list[str]
    outdated_items: list[dict]
    continue_outdated: bool
    state: str = "proposed"
    criteria: list[str] = field(default_factory=lambda: ["battery_level", "needed_by"])

    @property
    def expires_at(self):
        return self.generated_at + timedelta(minutes=10)
