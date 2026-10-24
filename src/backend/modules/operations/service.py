"""Operator monitoring + alerts.   OWNER: Member 3

  UC01 Monitor Network-wide Status (Dashboard)
  UC02 Manage System Alerts
(see Operator_Use_Case_Specification.docx)

``network.get_network_status()`` (core) already returns per-hub KPIs; extend it
here with alerts, charging-point info and trends rather than editing core.
"""
from __future__ import annotations

from typing import List, Optional

from ...core.entities import Event
from ...core.todo import todo

OWNER = "Member 3"


def get_dashboard() -> dict:
    """UC01: network KPIs + per-hub table + map markers + open alerts count."""
    todo(OWNER, "UC01", "start from network.get_network_status(); add alerts, charging points, markers")


def get_hub_detail(hub_id: str) -> dict:
    """UC01 step 4: drill-down for one hub (vehicles, parking spaces, charging points)."""
    todo(OWNER, "UC01", "vehicles + spaces + points of one hub")


def scan_for_alerts() -> List[dict]:
    """UC02: derive alerts - hub near capacity (hub.is_near_capacity), low battery fleet,
    charger out of service/offline. Call periodically or after state-changing events."""
    todo(OWNER, "UC02", "create Alert records, de-duplicate, emit ALERT_RAISED / HUB_NEAR_CAPACITY")


def list_alerts(status: Optional[str] = None) -> List[dict]:
    todo(OWNER, "UC02", "return alerts filtered by open/handled")


def acknowledge_alert(alert_id: str, operator_id: str) -> dict:
    """UC02: mark as handled (store who/when)."""
    todo(OWNER, "UC02", "mark alert handled")


def register_event_handlers() -> None:
    """Subscribe to bus events (called once from app startup if you want).
    e.g. bus.subscribe(EventType.ISSUE_REPORTED, incident_handler.on_issue_reported)."""
    todo(OWNER, "UC02/UC05", "bus.subscribe(...) for ISSUE_REPORTED, CHARGER_STATUS_CHANGED, ...")
