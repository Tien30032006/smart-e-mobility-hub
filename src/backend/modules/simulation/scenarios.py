"""Scenario configuration and templates.   OWNER: Member 4

  UC1 Configure Simulation Scenario     UC2 Load Scenario Template

Templates come from configs/simulation-scenarios.json (already has 4 samples;
add 'vehicle_concentration' to cover the 5th scenario in the assignment).
"""
from __future__ import annotations

from typing import List

from ...core.todo import todo
from .models import SimulationScenario

OWNER = "Member 4"


def list_templates() -> List[dict]:
    """UC2: read configs via data.loader.load_json('simulation-scenarios.json')."""
    todo(OWNER, "UC2", "return templates")


def create_scenario(kind: str, params: dict, description: str = "") -> SimulationScenario:
    """UC1: validate (hub exists, factors in range, failed_points <= hub points) and store."""
    todo(OWNER, "UC1", "validate + store scenario in a module-level dict")


def create_from_template(template_id: str, overrides: dict | None = None) -> SimulationScenario:
    """UC2: template + operator overrides (extends UC1)."""
    todo(OWNER, "UC2", "load template, apply overrides, call create_scenario")


def get_scenario(scenario_id: str) -> SimulationScenario:
    todo(OWNER, "UC1", "lookup")
