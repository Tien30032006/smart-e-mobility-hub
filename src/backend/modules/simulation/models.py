"""Data models for What-if Simulation.   OWNER: Member 4"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List

@dataclass
class SimulationScenario:
    scenario_id: str
    kind: str  # VD: "demand_surge", "hub_full", "charging_fault"
    params: Dict[str, Any]
    description: str = ""

@dataclass
class SimulationResult:
    result_id: str
    scenario_id: str
    impact_level: str  # "LOW", "MEDIUM", "HIGH"
    metrics: Dict[str, dict]  # Lưu các chỉ số KPIs theo từng hub_id
    generated_at: datetime
    recommendations: List[dict] = field(default_factory=list)