"""Scenario configuration and templates.   OWNER: Member 4

  UC1 Configure Simulation Scenario     UC2 Load Scenario Template
"""
from __future__ import annotations

import json
import os
import uuid
from typing import List

from ...core.state_manager import network
from .models import SimulationScenario

# Database in-memory lưu các kịch bản đang soạn thảo
SCENARIOS_DB = {}

def get_config_path() -> str:
    """Lấy đường dẫn tuyệt đối tới file configs/simulation-scenarios.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    return os.path.join(base_dir, "configs", "simulation-scenarios.json")

def list_templates() -> List[dict]:
    """UC2: Load danh sách template từ file JSON."""
    try:
        with open(get_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("scenarios", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def create_scenario(kind: str, params: dict, description: str = "") -> SimulationScenario:
    """UC1: Validate tham số đầu vào và tạo kịch bản mới."""
    target_hub_id = params.get("hub_id")
    
    # 1. Validate: Hub phải tồn tại
    if target_hub_id:
        try:
            hub = network.get_hub(target_hub_id)
        except Exception:
            raise ValueError(f"Hub {target_hub_id} không tồn tại trong hệ thống.")
            
        # 2. Validate: Số lượng cổng hỏng không được vượt quá số cổng thật của Hub
        if kind == "charging_fault":
            failed_points = params.get("failed_points", 0)
            total_points = len(hub.charging_points)
            if failed_points > total_points:
                raise ValueError(f"Số cổng sạc hỏng ({failed_points}) vượt quá tổng số cổng hiện có ({total_points}) tại {target_hub_id}.")
                
    # 3. Validate: Các hệ số phải hợp lệ
    if kind == "demand_surge":
        surge = params.get("surge_factor", 1.0)
        if surge < 0:
            raise ValueError("Hệ số gia tăng (surge_factor) không được mang giá trị âm.")

    scenario_id = f"SCN-{uuid.uuid4().hex[:8]}"
    scenario = SimulationScenario(
        scenario_id=scenario_id,
        kind=kind,
        params=params,
        description=description
    )
    
    SCENARIOS_DB[scenario_id] = scenario
    return scenario

def create_from_template(template_id: str, overrides: dict | None = None) -> SimulationScenario:
    """UC2: Load kịch bản từ template và áp dụng các thông số chỉnh sửa (nếu có)."""
    templates = list_templates()
    template = next((t for t in templates if t["id"] == template_id), None)
    
    if not template:
        raise ValueError(f"Không tìm thấy template với id: {template_id}")
        
    kind = template.get("type", "unknown")
    params = template.copy()
    
    # Xóa các key định danh của template để dùng làm params
    params.pop("id", None)
    params.pop("name", None)
    params.pop("type", None)
    
    # Ghi đè bằng tham số người dùng nhập (nếu có)
    if overrides:
        params.update(overrides)
        
    description = f"Tạo từ template: {template.get('name')}"
    return create_scenario(kind, params, description)

def get_scenario(scenario_id: str) -> SimulationScenario:
    """UC1: Lấy kịch bản theo ID."""
    if scenario_id not in SCENARIOS_DB:
        raise KeyError(f"Không tìm thấy kịch bản {scenario_id}")
    return SCENARIOS_DB[scenario_id]