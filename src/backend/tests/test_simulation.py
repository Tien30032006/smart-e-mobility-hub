import pytest
import copy
from src.backend.core.state_manager import network
from src.backend.modules.simulation import scenarios, engine

def test_simulation_does_not_mutate_live_state():
    """Kiểm tra: Chạy What-if Simulation không được làm thay đổi trạng thái mạng lưới thật."""
    
    # 1. Lấy trạng thái thật ban đầu (deep copy để so sánh)
    with network.lock:
        live_state_before = copy.deepcopy(network.snapshot())
        
    # 2. Tạo và chạy kịch bản mô phỏng
    scenario = scenarios.create_scenario(
        kind="demand_surge", 
        params={"hub_id": "HUB-METRO", "surge_factor": 3.0}
    )
    result = engine.run(scenario)
    
    # 3. Lấy trạng thái thật sau khi mô phỏng
    with network.lock:
        live_state_after = network.snapshot()
        
    # 4. Assert (Khẳng định) dữ liệu không bị thay đổi
    assert result.impact_level in ["LOW", "MEDIUM", "HIGH"]
    
    # Kiểm tra số lượng Hub và Xe phải y nguyên
    assert len(live_state_before.hubs) == len(live_state_after.hubs)
    assert len(live_state_before.vehicles) == len(live_state_after.vehicles)
    
    # Kiểm tra số lượng chỗ trống tại HUB-METRO ở mạng lưới thật không bị lấp đầy bởi mô phỏng
    if "HUB-METRO" in live_state_before.hubs:
        free_before = live_state_before.hubs["HUB-METRO"].get_available_resources()
        free_after = live_state_after.hubs["HUB-METRO"].get_available_resources()
        assert free_before == free_after