"""Vehicle redistribution.   OWNER: Member 3

  UC03    Redistribute Vehicles
  UC-OP04 Create Relocation Order (included by UC03)

Member 4's What-if recommendations (UC6) produce *plans* in the SAME format as
``propose_redistribution`` so the operator can apply a simulated suggestion
directly via ``create_relocation_order``:

    plan = {"from_hub": str, "to_hub": str, "vehicle_ids": [str, ...], "reason": str}

Use ``network.move_vehicle`` (atomic, core) to move a vehicle only when the
field staff confirm the order (or immediately for the MVP demo).
"""
from __future__ import annotations

from typing import List

from ...core.todo import todo

OWNER = "Member 3"


def propose_redistribution() -> List[dict]:
    """UC03: find surplus hubs (utilization high) and shortage hubs (few available vehicles);
    return a list of plans (format above). Never propose vehicles that are reserved/in use/maintenance."""
    todo(OWNER, "UC03", "surplus -> shortage matching, pick vehicles with enough battery")


def create_relocation_order(plan: dict, operator_id: str) -> dict:
    """UC-OP04: validate plan, store order (status PENDING/ASSIGNED/DONE), notify field staff
    (mock), emit RELOCATION_ORDER_CREATED. Alternate flow: staff reject/timeout -> alert operator."""
    todo(OWNER, "UC-OP04", "persist order + mock notify staff")


def complete_relocation_order(order_id: str) -> dict:
    todo(OWNER, "UC-OP04", "move vehicles with network.move_vehicle, mark DONE")


def list_orders() -> List[dict]:
    todo(OWNER, "UC-OP04", "list relocation orders")
