"""UC6 Generate Rebalancing Recommendations (extends UC5).   OWNER: Member 4

Produce a list of recommendations. Three kinds required by the assignment:
  {"type": "redistribute",   "from_hub", "to_hub", "vehicle_ids", "reason"}   <- SAME shape as Member 3's relocation plan
  {"type": "reschedule_charging", "hub_id", "details", "reason"}               <- relates to Member 2's scheduler
  {"type": "redirect_users", "from_hub", "to_hub", "reason"}
Recommendations are ADVICE ONLY; applying them is done by the operator via
Member 3's endpoints (redistribution orders / charging override).
"""
from __future__ import annotations

from typing import List

from ...core.todo import todo
from .models import SimulationResult

OWNER = "Member 4"


def generate(result: SimulationResult) -> List[dict]:
    todo(OWNER, "UC6", "rules over result.metrics: overloaded hub -> neighbour with free capacity, etc.")
