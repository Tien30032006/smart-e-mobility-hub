"""What-if simulation engine.   OWNER: Member 4

  UC3 Run Scenario Simulation (includes UC4 + UC5)
  UC4 Fetch Operational State Snapshot
  UC5 Evaluate Service Impact & Overload Risk
"""
from __future__ import annotations

import copy
import random
from datetime import timedelta
from typing import Dict, Any

from ...core.state_manager import NetworkSnapshot, network
from ...core.enums import ChargingPointStatus, VehicleStatus, EventType, Severity
from ...core.event_bus import bus
from .models import SimulationResult, SimulationScenario

def fetch_snapshot() -> NetworkSnapshot:
    """UC4: Fetch Operational State Snapshot."""
    # Lấy deep copy từ network manager để đảm bảo tính an toàn dữ liệu
    return network.snapshot()

def run(scenario: SimulationScenario, seed: int = 42) -> SimulationResult:
    """UC3: Run Scenario Simulation."""
    # 1. Fetch snapshot
    snapshot = fetch_snapshot()
    initial_snapshot = copy.deepcopy(snapshot) # Giữ lại bản gốc để so sánh (UC5)
    
    # 2. Thiết lập Sandbox mô phỏng
    random.seed(seed)
    time_step_minutes = 5
    total_duration_minutes = scenario.params.get("duration_minutes", 60)
    current_time = snapshot.taken_at
    end_time = current_time + timedelta(minutes=total_duration_minutes)
    
    target_hub_id = scenario.params.get("hub_id")
    
    # Tracking metrics trong quá trình chạy
    unserved_demand_count = 0
    served_demand_count = 0
    max_utilization_recorded = 0.0

    # 3. Áp dụng các thay đổi ngay từ đầu (Ví dụ: hỏng trạm sạc)
    if scenario.kind == "charging_fault" and target_hub_id in snapshot.hubs:
        hub = snapshot.hubs[target_hub_id]
        failed_count = min(
            scenario.params.get("failed_points", 1), 
            len(hub.charging_points)
        )
        
        # Mô phỏng hỏng trạm sạc
        points = list(hub.charging_points.values())
        for i in range(failed_count):
            if points[i].status != ChargingPointStatus.OUT_OF_SERVICE:
                points[i].status = ChargingPointStatus.OUT_OF_SERVICE

    # 4. Vòng lặp mô phỏng Discrete-event (Time-step Loop)
    while current_time < end_time:
        if target_hub_id in snapshot.hubs:
            hub = snapshot.hubs[target_hub_id]
            
            # Mô phỏng Nhu cầu (Demand Surge)
            surge_factor = scenario.params.get("surge_factor", 1.0)
            base_arrivals = random.randint(0, 2)
            arrivals = int(base_arrivals * surge_factor)
            
            for _ in range(arrivals):
                if hub.get_available_resources() > 0:
                    served_demand_count += 1
                    # Giả lập lấp đầy 1 chỗ đỗ bằng cách tạo 1 xe ảo
                    vehicle_id = f"SIM-V-{random.randint(1000, 9999)}"
                    # Tìm chỗ trống đầu tiên và chiếm chỗ (chỉ thay đổi trên snapshot)
                    free_space = next((s for s in hub.parking_spaces.values() if s.is_available()), None)
                    if free_space:
                        free_space.is_occupied = True
                        free_space.vehicle_id = vehicle_id
                else:
                    unserved_demand_count += 1
                    
            # Cập nhật Utilization
            current_util = hub.update_utilization()
            max_utilization_recorded = max(max_utilization_recorded, current_util)

        current_time += timedelta(minutes=time_step_minutes)

    # Đóng gói dữ liệu tracking tạm thời để truyền sang evaluate_impact
    tracking_data = {
        "served_demand": served_demand_count,
        "unserved_demand": unserved_demand_count,
        "peak_utilization": max_utilization_recorded
    }

    # 5. Đánh giá Tác động (UC5)
    result = evaluate_impact(initial_snapshot, snapshot, scenario, tracking_data)
    
    # 6. Kích hoạt cảnh báo hệ thống báo mô phỏng hoàn tất
    bus.emit(
        EventType.SIMULATION_COMPLETED,
        hub_id=target_hub_id,
        severity=Severity.INFO,
        result_id=result.result_id,
        impact_level=result.impact_level
    )

    return result

def evaluate_impact(
    start: NetworkSnapshot, 
    end: NetworkSnapshot, 
    scenario: SimulationScenario,
    tracking_data: Dict[str, Any]
) -> SimulationResult:
    """UC5: Evaluate Service Impact & Overload Risk."""
    target_hub_id = scenario.params.get("hub_id")
    
    metrics = {}
    impact_level = "LOW"
    
    if target_hub_id in end.hubs:
        hub_end = end.hubs[target_hub_id]
        
        served = tracking_data["served_demand"]
        unserved = tracking_data["unserved_demand"]
        peak_util = tracking_data["peak_utilization"]
        
        fulfillment_rate = (served / (served + unserved)) * 100 if (served + unserved) > 0 else 100.0
        
        # Xếp loại rủi ro (Overload Risk Score)
        if peak_util >= 0.9 or fulfillment_rate < 50:
            impact_level = "HIGH"
        elif peak_util >= 0.75 or fulfillment_rate < 80:
            impact_level = "MEDIUM"

        metrics[target_hub_id] = {
            "fulfillment_rate_percent": round(fulfillment_rate, 2),
            "unserved_demand_count": unserved,
            "peak_utilization": peak_util,
            "final_utilization": hub_end.utilization
        }

    return SimulationResult(
        result_id=f"RES-{scenario.scenario_id}",
        scenario_id=scenario.scenario_id,
        impact_level=impact_level,
        metrics=metrics,
        generated_at=end.taken_at
    )