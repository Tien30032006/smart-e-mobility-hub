"""UC6 Generate Rebalancing Recommendations (extends UC5).   OWNER: Member 4"""
from __future__ import annotations

from typing import List

from ...core.state_manager import network
from ...core.enums import VehicleStatus
from .models import SimulationResult


def generate(result: SimulationResult) -> List[dict]:
    recommendations = []
    
    # Nếu hệ thống an toàn (LOW risk), không cần sinh đề xuất
    if result.impact_level == "LOW":
        return recommendations
        
    for hub_id, metrics in result.metrics.items():
        # Phát hiện Hub đang bị quá tải hoặc có khách hàng không được phục vụ
        if metrics["peak_utilization"] >= 0.85 or metrics["unserved_demand_count"] > 0:
            
            # Tìm Hub lân cận đang trống (Utilization < 60%)
            available_hubs = []
            with network.lock:
                for h in network.list_hubs():
                    if h.hub_id != hub_id and h.update_utilization() < 0.6:
                        available_hubs.append(h)
                        
            if available_hubs:
                target_hub = available_hubs[0]
                
                # Loại 1: Điều chuyển xe (Redistribute) - Chuẩn format của Member 3
                vehicles_to_move = []
                with network.lock:
                    v_list = network.vehicles_at(hub_id)
                    for v in v_list:
                        if v.status == VehicleStatus.AVAILABLE:
                            vehicles_to_move.append(v.vehicle_id)
                            if len(vehicles_to_move) >= 3:  # Giới hạn điều 3 xe nhàn rỗi đi
                                break
                                
                if vehicles_to_move:
                    recommendations.append({
                        "type": "redistribute",
                        "from_hub": hub_id,
                        "to_hub": target_hub.hub_id,
                        "vehicle_ids": vehicles_to_move,
                        "reason": f"Quá tải tại {hub_id} (Peak {metrics['peak_utilization']*100}%). Điều chuyển xe nhàn rỗi sang {target_hub.name}."
                    })
                    
                # Loại 2: Điều hướng người dùng (Redirect)
                recommendations.append({
                    "type": "redirect_users",
                    "from_hub": hub_id,
                    "to_hub": target_hub.hub_id,
                    "reason": f"Khuyến khích sinh viên trả xe tại {target_hub.name} đang còn nhiều chỗ trống."
                })
                
            # Loại 3: Can thiệp lịch sạc (Reschedule)
            recommendations.append({
                "type": "reschedule_charging",
                "hub_id": hub_id,
                "details": "Tạm dừng sạc các xe đã đạt >80% pin để nhường cổng sạc.",
                "reason": "Nhu cầu sạc tăng đột biến, cần giải phóng cổng sạc khẩn cấp."
            })
            
    return recommendations