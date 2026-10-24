"""SimulationScenario / SimulationResult (class diagram).   OWNER: Member 4"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ...core.entities import new_id
from ...core.todo import todo

OWNER = "Member 4"


@dataclass
class SimulationResult:
    result_id: str = field(default_factory=lambda: new_id("SR"))
    scenario_id: str = ""
    impact_level: str = "low"               # low | medium | high | critical
    summary: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)       # per-hub timeline, service rate, ...
    recommendations: List[dict] = field(default_factory=list)   # UC6, plan format in operations/redistribution.py

    def get_recommendations(self) -> List[dict]:
        return self.recommendations

    def compare_with_current(self) -> str:
        todo(OWNER, "UC5", "text/table comparing simulated end state vs the snapshot taken at start")


@dataclass
class SimulationScenario:
    scenario_id: str = field(default_factory=lambda: new_id("SC"))
    description: str = ""
    kind: str = ""                          # demand_surge | hub_full | charging_fault | vehicle_concentration
    params: Dict[str, Any] = field(default_factory=dict)
    is_applied: bool = False                # always False: What-if NEVER changes live state

    def configure(self, params: Dict[str, Any]) -> None:
        todo(OWNER, "UC1", "validate + store parameters (hub_id, surge_factor, failed_points, duration...)")

    def run_simulation(self) -> SimulationResult:
        todo(OWNER, "UC3", "delegate to engine.run(scenario)")
