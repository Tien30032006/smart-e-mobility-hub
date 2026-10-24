# Hợp đồng chung giữa các module

Nếu muốn đổi bất kỳ mục nào dưới đây → báo cả nhóm và ghi vào biên bản họp.

## 1. Class diagram → code

| Class diagram | Code | Người code phần nghiệp vụ |
|---|---|---|
| `User` (abstract), `Student`, `Operator` | `core/entities.py` | chung (đã xong) |
| `MobilityHub`, `ParkingSpace`, `ChargingPoint`, `EVehicle` | `core/entities.py` | chung (đã xong) |
| `Reservation` | `core/entities.py` + `reservation/repository.py` | Member 1 |
| `ChargingSession` | `core/entities.py` (`schedule/complete/calculate_priority` = todo) | Member 2 |
| `Event` | `core/entities.py` | chung (đã xong) |
| `HubNetworkManager` | `core/state_manager.py` (`redistribute_vehicles` = todo) | chung / Member 3 |
| `AllocationService` | `core/allocation_service.py` | Member 1 (vehicle, parking), Member 2 (charging) |
| `SimulationScenario`, `SimulationResult` | `modules/simulation/models.py` | Member 4 |

Quy ước tên: camelCase trong diagram → snake_case trong Python (`getAvailableResources` → `get_available_resources`).
Khi nộp tài liệu #3, mô tả method theo **đúng class diagram**; nếu code lệch diagram thì cập nhật diagram.

## 2. Trạng thái (enum trong `core/enums.py`)

* `VehicleStatus`: available, reserved, in_use, charging, maintenance, offline
* `ChargingPointStatus`: available, reserved, occupied, out_of_service
* `ReservationKind`: vehicle, parking, charging — `ReservationStatus`: pending, confirmed, active, completed, cancelled, expired
* `ChargingSessionStatus`: queued, scheduled, charging, completed, cancelled

Xe dùng chung: `EVehicle.owner_id is None`. Xe cá nhân: `owner_id = user_id` của sinh viên.

## 3. Sự kiện (`bus.emit(EventType.X, hub_id=..., **payload)`)

| Sự kiện | Người phát | Người nghe | Payload bắt buộc |
|---|---|---|---|
| `ISSUE_REPORTED` | Member 1 (U7) | Member 3 (UC05) | `issue_id, target_type ('vehicle'/'charging_point'/'parking_space'), target_id, category, description` |
| `RESERVATION_CANCELLED` | Member 1 (U4) | Member 3 (dashboard) | `reservation_id, reason, by_system` |
| `VEHICLE_PICKED_UP` / `VEHICLE_RETURNED` | Member 1 | Member 3, Member 2 | `vehicle_id, user_id` |
| `CHARGING_REQUESTED` / `CHARGING_SCHEDULED` | Member 2 | Member 3 | `session_id, vehicle_id` |
| `CHARGER_STATUS_CHANGED` | Member 2 (CH-08, CH-10) | Member 3 (UC02 cảnh báo) | `point_id, old_status, new_status` |
| `BATTERY_UPDATED` | Member 2 (CH-10) | — | `vehicle_id, battery_level` |
| `HUB_NEAR_CAPACITY`, `ALERT_RAISED` | Member 3 (UC02) | — | `alert_id, message` |
| `INCIDENT_OPENED` | Member 3 (UC05) | — | `incident_id, target_id` |
| `RELOCATION_ORDER_CREATED` | Member 3 (UC-OP04) | — | `order_id` |
| `CHARGING_OVERRIDE` | Member 2 (khi Member 3 gọi override) | — | `session_id, operator_id, reason` |
| `SIMULATION_COMPLETED` | Member 4 | — | `result_id, impact_level` |

## 4. Hàm các module gọi lẫn nhau (giữ nguyên chữ ký)

| Hàm | Chủ sở hữu | Người gọi |
|---|---|---|
| `reservation.service.cancel_reservation(reservation_id, user_id=None, reason, by_system=False)` | Member 1 | Member 3 UC-OP07 |
| `charging.scheduler.run_prioritization(hub_id)` | Member 2 | Member 3 UC-OP08 |
| `charging.scheduler.get_queue(hub_id)` | Member 2 | Member 3 UC-OP08 |
| `charging.scheduler.apply_manual_override(hub_id, session_id, operator_id, reason)` | Member 2 | Member 3 UC-OP09 |
| `charging.point_monitor.update_point_status(point_id, status, operator_id, reason)` | Member 2 | Member 3 UC05 |
| `network.move_vehicle(vehicle_id, to_hub_id)` → bool | Core | Member 1 U6, Member 3 UC-OP04 |
| `network.snapshot()` → `NetworkSnapshot` (deep copy) | Core | Member 4 UC4 |

## 5. Định dạng kế hoạch điều chuyển xe (Member 3 định nghĩa, Member 4 sinh ra ở UC6)

```json
{ "from_hub": "HUB-METRO", "to_hub": "HUB-KTX", "vehicle_ids": ["V-001", "V-003"], "reason": "Metro 92% full" }
```

## 6. Quy ước API

* Tiền tố: `/api/reservation` (Member 1), `/api/charging` (Member 2), `/api/operator` (Member 3), `/api/simulation` (Member 4); API chung `/api/auth`, `/api/hubs`, `/api/network`.
* Đăng nhập: `POST /api/auth/login {email}` → token = `user_id`; gửi `Authorization: Bearer <user_id>`.
* Lỗi nghiệp vụ: `HTTPException(400/404/409, detail="…")` (409 = tài nguyên vừa bị người khác giữ). Chưa làm: HTTP 501 tự động.
* Thời gian: ISO-8601 UTC (`datetime.now(timezone.utc)`).

## 7. Tài khoản demo

| Email | Vai trò | user_id |
|---|---|---|
| an@hcmut.edu.vn | Sinh viên, xe dùng chung | U-S01 |
| binh@hcmut.edu.vn | Sinh viên, có xe điện cá nhân `PV-001` | U-S02 |
| operator@hub.vn | Operator | U-OP1 |

## 8. Dữ liệu demo (`configs/hubs-data.json`)

Hub nhỏ có chủ đích (Metro 12 chỗ, Thư viện 8 chỗ…) để dễ tạo tình huống đầy/quá tải khi demo. Muốn thêm dữ liệu: sửa JSON này, không sửa trong code của module.
