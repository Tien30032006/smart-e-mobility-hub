"""What-if simulation engine.   OWNER: Member 4

  UC3 Run Scenario Simulation (includes UC4 + UC5)
  UC4 Fetch Operational State Snapshot
  UC5 Evaluate Service Impact & Overload Risk
(see what_if_template.docx)

HARD RULE: work ONLY on ``network.snapshot()`` (deep copy). Never call a
mutating method of the live ``network`` and never import service functions that
change live state. A unit test must prove live state is unchanged after a run.

Suggested model: discrete time steps (e.g. 5 min). Each step applies the
scenario to the snapshot (extra arrivals, failed points, ...) and updates
free spaces / free chargers / waiting users. Deterministic (seed) for repeatable demos.
"""
from __future__ import annotations

from ...core.state_manager import NetworkSnapshot
from ...core.todo import todo
from .models import SimulationResult, SimulationScenario

OWNER = "Member 4"


def fetch_snapshot() -> NetworkSnapshot:
    """UC4. Thin wrapper over network.snapshot(); add 'stale data' warning if you want."""
    todo(OWNER, "UC4", "return network.snapshot()")


def run(scenario: SimulationScenario) -> SimulationResult:
    """UC3: snapshot -> step loop -> evaluate_impact -> (if risk) recommender.generate -> bus SIMULATION_COMPLETED."""
    todo(OWNER, "UC3", "step loop on the snapshot copy")


def evaluate_impact(start: NetworkSnapshot, end: NetworkSnapshot, scenario: SimulationScenario) -> SimulationResult:
    """UC5: per hub - served vs unserved demand, peak utilization, charger queue length, first time hub is full.
    Classify impact_level."""
    todo(OWNER, "UC5", "compute metrics + overload risk per hub")
