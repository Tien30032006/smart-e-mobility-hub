"""UC-CH-09: pure scoring, read-only proposals and atomic approval.

Integration signatures stay stable. run_prioritization is the one-step command
for Member 3; the UI uses create_proposal / approve_proposal / discard_proposal.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException

from ...core.entities import ChargingSession, new_id, utcnow
from ...core.enums import ChargingPointStatus, ChargingSessionStatus, EventType, ReservationStatus, VehicleStatus
from ...core.event_bus import bus
from ...core.logger import get_logger
from .domain import (PriorityPolicy, Proposal, SelectedCriteriaPolicy, WeightedPriorityPolicy,
                     charging_minutes, overlaps, timestamp)
from .repository import repository

log = get_logger("charging.scheduler")


def calculate_priority(battery_level: int, needed_by: Optional[datetime], now: Optional[datetime] = None) -> int:
    return WeightedPriorityPolicy().score(battery_level, timestamp(needed_by), timestamp(now) or utcnow())


class SchedulePlanner:
    """Planning depends on a repository and a replaceable scoring policy."""
    def __init__(self, repo=repository, policy: Optional[PriorityPolicy] = None):
        self.repo = repo
        self.policy = policy or WeightedPriorityPolicy()

    def build(self, hub_id, operator_id, horizon_minutes, continue_outdated, criteria):
        now = self.repo.clock()
        hub = self.repo.network.get_hub(hub_id)
        sessions = [s for s in self.repo.sessions(hub_id, active=True)
                    if s.status != ChargingSessionStatus.CHARGING]
        outdated = self.repo.outdated_items(hub_id, now)
        if outdated and not continue_outdated and sessions:
            return {"status": "awaiting_decision", "outdated_items": outdated}
        end = now + timedelta(minutes=horizon_minutes)
        ranking = []
        for session in sessions:
            vehicle = self.repo.network.get_vehicle(session.vehicle_id)
            waiting = (now - getattr(session, "created_at", now)).total_seconds() / 60
            score = self.policy.score(vehicle.battery_level, session.needed_by, now, waiting_minutes=waiting)
            score = self.repo.store.manual_overrides.get(session.session_id, score)
            ranking.append({"session_id": session.session_id, "vehicle_id": session.vehicle_id,
                "priority": score, "requested_at": getattr(session, "created_at", now),
                "battery_unconfirmed": self.repo.freshness("vehicle", session.vehicle_id, now)["outdated"]})
        ranking.sort(key=lambda r: (-r["priority"], r["requested_at"], r["session_id"]))
        blocked = {p.point_id: self.repo.intervals(p.point_id, now) for p in hub.charging_points.values()}
        assignments, unserved = [], []
        for row in ranking:
            session = self.repo.network.charging_sessions[row["session_id"]]
            if session.point_id and session.status == ChargingSessionStatus.SCHEDULED:
                continue  # Keep confirmed bookings and existing allocations.
            vehicle = self.repo.network.get_vehicle(session.vehicle_id)
            if vehicle.hub_id != hub_id or vehicle.status in {
                    VehicleStatus.MAINTENANCE, VehicleStatus.OFFLINE, VehicleStatus.IN_USE}:
                unserved.append(session.session_id)
                continue
            choices = []
            booking = self.repo.booking_for(session)
            earliest = max(now, booking.start_time) if booking else now
            latest = min(end, booking.end_time) if booking and booking.end_time else end
            for point in hub.charging_points.values():
                if point.status == ChargingPointStatus.OUT_OF_SERVICE:
                    continue
                if point.status != ChargingPointStatus.AVAILABLE and not blocked[point.point_id]:
                    continue
                if point.current_session_id and point.current_session_id not in self.repo.network.charging_sessions:
                    continue
                duration = (latest - earliest if booking else
                    timedelta(minutes=charging_minutes(vehicle.battery_level,
                        getattr(session, "target_level", 100), point.power_rating)))
                if duration <= timedelta(0):
                    continue
                start = earliest
                for a, b in sorted(blocked[point.point_id]):
                    if overlaps(start, start + duration, a, b):
                        start = b
                if start + duration <= latest:
                    choices.append((start, start + duration, point.point_id))
            if not choices:
                unserved.append(session.session_id)
                continue
            start, finish, pid = min(choices)
            blocked[pid].append((start, finish))
            assignments.append({"session_id": session.session_id, "point_id": pid,
                                "start_time": start, "end_time": finish})
        proposal = Proposal(new_id("CP"), hub_id, operator_id, now, end, self.repo.fingerprint(hub_id),
                            ranking, assignments, unserved, outdated, continue_outdated)
        proposal.criteria = list(criteria)
        return proposal


def create_proposal(hub_id, operator_id, horizon_minutes=240, continue_outdated=False, criteria=None):
    criteria = ["battery_level", "needed_by"] if criteria is None else criteria
    if not isinstance(horizon_minutes, int) or not 1 <= horizon_minutes <= 10080:
        raise HTTPException(400, "Planning horizon must be between 1 and 10080 minutes")
    if not criteria or len(set(criteria)) != len(criteria) or set(criteria) - {"battery_level", "needed_by", "waiting_time"}:
        raise HTTPException(400, "Unknown or duplicate prioritization criteria")
    with repository.network.lock:
        if operator_id != "system":
            repository.operator(operator_id)
        repository.network.get_hub(hub_id)
        try:
            policy = (WeightedPriorityPolicy() if criteria == ["battery_level", "needed_by"]
                      else SelectedCriteriaPolicy(criteria))
            proposal = SchedulePlanner(policy=policy).build(hub_id, operator_id, horizon_minutes, continue_outdated, criteria)
        except HTTPException:
            raise
        except Exception:
            log.exception("Scheduling calculation failed for %s", hub_id)
            raise HTTPException(500, "Calculation failed; previous schedule is unchanged") from None
        if isinstance(proposal, dict):
            return proposal
        if not proposal.ranking:
            return {"status": "nothing_to_schedule", "outdated_items": []}
        repository.store.proposals = {k: p for k, p in repository.store.proposals.items()
                                      if p.expires_at >= repository.clock() and p.state == "proposed"}
        repository.store.proposals[proposal.proposal_id] = proposal
        return {"status": "proposed", **asdict(proposal)}


def _owned_proposal(proposal_id, operator_id):
    proposal = repository.store.proposals.get(proposal_id)
    if proposal is None:
        raise HTTPException(404, "Proposal not found")
    if proposal.operator_id != operator_id:
        raise HTTPException(403, "Proposal belongs to another operator")
    if proposal.state != "proposed":
        raise HTTPException(409, "Proposal was already approved or discarded")
    return proposal


def approve_proposal(proposal_id, operator_id):
    events = []
    with repository.network.lock:
        proposal = _owned_proposal(proposal_id, operator_id)
        if proposal.expires_at < repository.clock():
            raise HTTPException(409, "Proposal expired; generate a new proposal")
        if proposal.fingerprint != repository.fingerprint(proposal.hub_id):
            raise HTTPException(409, "Scheduling data changed; generate a new proposal")
        if not proposal.continue_outdated and repository.outdated_items(proposal.hub_id):
            raise HTTPException(409, "Data is now outdated; generate a new proposal")
        if any(a["end_time"] <= repository.clock() for a in proposal.assignments):
            raise HTTPException(409, "Proposed time slots expired; generate a new proposal")
        for row in proposal.ranking:
            session = repository.network.charging_sessions[row["session_id"]]
            session.priority = row["priority"]
            if hasattr(session, "battery_unconfirmed"):
                session.battery_unconfirmed = row["battery_unconfirmed"]
                session.battery_level_used = repository.network.get_vehicle(session.vehicle_id).battery_level
                session.battery_updated_at = repository.freshness("vehicle", session.vehicle_id)["last_update"]
        for assignment in proposal.assignments:
            session = repository.network.charging_sessions[assignment["session_id"]]
            session.point_id = assignment["point_id"]
            session.start_time = assignment["start_time"]
            session.end_time = assignment["end_time"]
            session.status = ChargingSessionStatus.SCHEDULED
            repository.store.manual_overrides.pop(session.session_id, None)
            booking = repository.booking_for(session)
            if booking:
                booking.resource_id = session.point_id
                booking.start_time, booking.end_time = session.start_time, session.end_time
                booking.point_unavailable = False
                booking.status = ReservationStatus.CONFIRMED
            if hasattr(session, "point_unavailable"):
                session.point_unavailable = False
            point = repository.point(session.point_id)
            if session.start_time <= repository.clock() and point.status == ChargingPointStatus.AVAILABLE:
                point.status = ChargingPointStatus.RESERVED
                point.current_session_id = session.session_id
            repository.notify(session.requested_by, "charging_scheduled", session_id=session.session_id)
            events.append((session.hub_id, session.session_id, session.vehicle_id))
        proposal.state = "applied"
        repository.store.hub_criteria[proposal.hub_id] = proposal.criteria
        repository.audit("schedule_applied", operator_id, proposal_id=proposal_id, hub_id=proposal.hub_id)
        result = {"status": "applied", "proposal_id": proposal_id,
                  "assignments": proposal.assignments, "unserved": proposal.unserved}
    for hub_id, sid, vid in events:
        bus.emit(EventType.CHARGING_SCHEDULED, hub_id=hub_id, session_id=sid, vehicle_id=vid)
    return result


def discard_proposal(proposal_id, operator_id):
    with repository.network.lock:
        proposal = _owned_proposal(proposal_id, operator_id)
        proposal.state = "discarded"
    return {"status": "discarded", "changes_applied": False}


def run_prioritization(hub_id: str) -> List[ChargingSession]:
    """Compatibility command: rank + apply; stale data still needs confirmation."""
    with repository.network.lock:
        result = create_proposal(hub_id, "system")
        if result["status"] == "awaiting_decision":
            raise HTTPException(409, "Outdated data requires operator confirmation via the proposal API")
        if result["status"] == "proposed":
            approve_proposal(result["proposal_id"], "system")
        return get_queue(hub_id)


def get_queue(hub_id: str) -> List[ChargingSession]:
    from dataclasses import replace
    with repository.network.lock:
        repository.network.get_hub(hub_id)
        now = repository.clock()
        criteria = repository.store.hub_criteria.get(hub_id, ["battery_level", "needed_by"])
        policy = WeightedPriorityPolicy() if criteria == ["battery_level", "needed_by"] else SelectedCriteriaPolicy(criteria)
        rows = []
        for session in repository.sessions(hub_id, active=True):
            vehicle = repository.network.get_vehicle(session.vehicle_id)
            score = policy.score(vehicle.battery_level, session.needed_by, now,
                waiting_minutes=(now-getattr(session, "created_at", now)).total_seconds()/60)
            score = repository.store.manual_overrides.get(session.session_id, score)
            rows.append(replace(session, priority=score))
        return sorted(rows,
                      key=lambda s: (-s.priority, getattr(s, "created_at", utcnow()), s.session_id))


def apply_manual_override(hub_id: str, session_id: str, operator_id: str, reason: str = "") -> ChargingSession:
    with repository.network.lock:
        repository.operator(operator_id)
        repository.network.get_hub(hub_id)
        if not reason.strip():
            raise HTTPException(400, "An override reason is required")
        session = repository.network.charging_sessions.get(session_id)
        if session is None or session.hub_id != hub_id:
            raise HTTPException(404, "Charging session not found at this hub")
        if session.status != ChargingSessionStatus.QUEUED:
            raise HTTPException(409, "Only a queued request can be overridden")
        vehicle = repository.network.get_vehicle(session.vehicle_id)
        if vehicle.status in {VehicleStatus.IN_USE, VehicleStatus.OFFLINE, VehicleStatus.MAINTENANCE}:
            raise HTTPException(409, "Vehicle is not available for charging")
        if repository.outdated_items(hub_id):
            raise HTTPException(409, "Refresh outdated data before a manual override")
        session.priority = max([s.priority for s in get_queue(hub_id)] + [100]) + 1
        repository.store.manual_overrides[session_id] = session.priority
        now = repository.clock()
        for point in repository.network.get_hub(hub_id).charging_points.values():
            end = now + timedelta(minutes=charging_minutes(vehicle.battery_level,
                getattr(session, "target_level", 100), point.power_rating))
            if point.status == ChargingPointStatus.AVAILABLE and repository.can_book(point, now, end, now):
                session.point_id, session.start_time, session.end_time = point.point_id, now, end
                session.status = ChargingSessionStatus.SCHEDULED
                point.status, point.current_session_id = ChargingPointStatus.RESERVED, session.session_id
                repository.store.manual_overrides.pop(session_id, None)
                repository.notify(session.requested_by, "charging_scheduled", session_id=session_id)
                break
        repository.audit("manual_override", operator_id, session_id=session_id, hub_id=hub_id, reason=reason)
    bus.emit(EventType.CHARGING_OVERRIDE, hub_id=hub_id, session_id=session_id,
             operator_id=operator_id, reason=reason)
    return session
