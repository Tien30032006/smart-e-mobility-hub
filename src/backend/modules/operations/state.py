"""In-memory stores for operator-owned workflows."""
from __future__ import annotations

from typing import Dict

alerts: Dict[str, dict] = {}
incidents: Dict[str, dict] = {}
tickets: Dict[str, dict] = {}
relocation_orders: Dict[str, dict] = {}
charging_overrides: Dict[str, dict] = {}


def reset() -> None:
    alerts.clear()
    incidents.clear()
    tickets.clear()
    relocation_orders.clear()
    charging_overrides.clear()
