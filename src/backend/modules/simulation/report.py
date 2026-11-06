"""UC7 Export Simulation Report.   OWNER: Member 4"""
import io
import openpyxl
from typing import Tuple

from .models import SimulationResult


def export_report(result: SimulationResult, fmt: str = "xlsx") -> Tuple[bytes, str, str]:
    if fmt != "xlsx":
        raise ValueError("Hệ thống hiện tại chỉ hỗ trợ xuất báo cáo định dạng Excel (.xlsx)")
        
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "What-if Simulation Report"
    
    # Header & Thông tin chung
    ws.append(["BÁO CÁO KẾT QUẢ MÔ PHỎNG WHAT-IF"])
    ws.append([])
    ws.append(["Mã kết quả (Result ID):", result.result_id])
    ws.append(["Mã kịch bản (Scenario ID):", result.scenario_id])
    ws.append(["Mức độ rủi ro (Impact Level):", result.impact_level])
    ws.append(["Thời gian xuất báo cáo:", result.generated_at.strftime("%Y-%m-%d %H:%M:%S")])
    ws.append([])
    
    # Bảng số liệu KPIs
    headers = ["Mã Hub", "Tỷ lệ phục vụ (%)", "Lượt khách bỏ lỡ", "Mức sử dụng tối đa", "Mức sử dụng cuối cùng"]
    ws.append(headers)
    
    for hub_id, metrics in result.metrics.items():
        ws.append([
            hub_id,
            metrics.get("fulfillment_rate_percent", 100.0),
            metrics.get("unserved_demand_count", 0),
            metrics.get("peak_utilization", 0.0),
            metrics.get("final_utilization", 0.0)
        ])
        
    # Ghi ra stream bytes (không cần tạo file rác trên ổ cứng server)
    stream = io.BytesIO()
    wb.save(stream)
    content = stream.getvalue()
    
    filename = f"WhatIf_Report_{result.result_id}.xlsx"
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return content, media_type, filename