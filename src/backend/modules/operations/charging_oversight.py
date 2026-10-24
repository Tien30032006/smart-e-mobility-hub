"""Operator side of smart charging.   OWNER: Member 3

  UC-OP08 Smart Charging Scheduling and Allocation (supervise)
  UC-OP09 Override Charging Priority (manual override)

THE ALGORITHM IS NOT HERE - it is Member 2's UC-CH-09 in modules/charging/scheduler.py.
This module is the operator workflow around it: view queue + priority scores,
trigger a run, override, show the audit trail. Do not duplicate the scoring logic.
"""
from __future__ import annotations

from ...core.todo import todo

OWNER = "Member 3"


def view_charging_allocation(hub_id: str) -> dict:
    """UC-OP08: queue with priority scores + which point each vehicle got.
    Uses charging.scheduler.get_queue(hub_id)."""
    todo(OWNER, "UC-OP08", "call Member 2's scheduler.get_queue and shape it for the UI")


def run_allocation(hub_id: str, operator_id: str) -> dict:
    """UC-OP08: trigger charging.scheduler.run_prioritization(hub_id)."""
    todo(OWNER, "UC-OP08", "call Member 2's scheduler.run_prioritization and return result summary")


def override_priority(hub_id: str, session_id: str, operator_id: str, reason: str) -> dict:
    """UC-OP09: require a reason, call charging.scheduler.apply_manual_override, keep audit log."""
    todo(OWNER, "UC-OP09", "validate reason, call Member 2's apply_manual_override, store audit entry")
