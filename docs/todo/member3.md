# TODO cá nhân – Member 3 (Operator Monitoring & Incident Lead)

* Tài liệu spec của bạn: **Operator_Use_Case_Specification.docx**
* Thư mục code: `src/backend/modules/operations/`
* Trang giao diện: `operator/dashboard.html`, `operator/incidents.html` và (cùng Member 2) `operator/charging.html`
* Test của bạn: `src/backend/tests/test_operations.py` (bỏ `@SKIP` khi làm xong từng UC)
* Đọc trước: `TEAM_TODO.md`, `docs/shared-contract.md`, `core/entities.py`, `core/state_manager.py`

Mỗi chỗ cần làm trong code đã có hàm stub gọi `todo(...)` kèm docstring hướng dẫn – tìm bằng `grep -rn "todo(" src/backend/modules/operations/`. Gọi endpoint chưa làm sẽ nhận HTTP 501 ghi tên bạn.

## A. Code (làm theo thứ tự P0 → P1 → P2)

### P0 – làm trước, người khác đang phụ thuộc / nền tảng

- [ ] **UC01 dashboard** — `service.get_dashboard`, `get_hub_detail`
  - Bắt đầu từ `network.get_network_status()` (đã có KPI từng Hub); thêm cảnh báo, cổng sạc, marker bản đồ.
- [ ] **UC02 cảnh báo** — `service.scan_for_alerts`, `list_alerts`, `acknowledge_alert`
  - Hub gần đầy (`hub.is_near_capacity()`), pin thấp hàng loạt, cổng mất kết nối; khử trùng lặp; phát `ALERT_RAISED`/`HUB_NEAR_CAPACITY`.
- [ ] **UC03 + UC-OP04 điều phối xe** — `redistribution.py`, `HubNetworkManager.redistribute_vehicles`
  - `propose_redistribution` → `create_relocation_order` → hoàn tất bằng `network.move_vehicle`. Định nghĩa **format `plan`** (Member 4 dùng lại).

### P1 – chức năng chính để demo

- [ ] **UC05 + UC-OP06 xử lý sự cố** — `incident_handler.on_issue_reported`, `handle_incident`, `create_maintenance_ticket`
  - Nghe `ISSUE_REPORTED` (Member 1 phát); xe → MAINTENANCE, cổng → OUT_OF_SERVICE (gọi hàm của Member 2 nếu đang sạc); tạo ticket.
- [ ] **UC-OP07 hủy đặt chỗ do sự cố** — `cancel_affected_reservations`
  - Gọi `reservation.service.cancel_reservation(by_system=True)` của Member 1 + gợi ý xe thay thế.
- [ ] **UC-OP08 + OP09 giám sát/ghi đè sạc** — `charging_oversight.py`
  - **Không viết lại thuật toán** – gọi `scheduler` của Member 2; lưu nhật ký ghi đè (ai, lý do, lúc nào).

### P2 – hoàn thiện

- [ ] **`register_event_handlers`** — đăng ký `bus.subscribe` lúc khởi động (gọi từ `app.py` – báo cả nhóm khi sửa)
- [ ] **Giao diện** — dashboard (bảng + thanh độ đầy), trang sự cố, phần ưu tiên sạc trên `operator/charging.html`
- [ ] **Danh sách lệnh điều chuyển** — `list_orders` + trạng thái PENDING/ASSIGNED/DONE

## B. Tài liệu cá nhân (đề bài: mỗi người làm cho UC của mình)

| Use case | Sequence diagram (#2) | Activity diagram (#2) | UC detail (#1) |
|---|---|---|---|
| UC01 Monitor Network-wide Status | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC02 Manage System Alerts | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC03 Redistribute Vehicles | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-OP04 Create Relocation Order | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC05 Handle Device Incident | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-OP06 Create Maintenance Ticket | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-OP07 Cancel Reservation | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-OP08 Smart Charging Scheduling and Allocation | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-OP09 Override Charging Priority | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |

- [ ] **Hạn #3 – Class & method description** cho: `Operator` (monitorNetwork, handleIncident), `MobilityHub` (getAvailableResources, updateUtilization, isNearCapacity), `HubNetworkManager`, `Event` (mô tả *mọi* method trong class diagram của lớp mình; nếu code lệch diagram thì báo nhóm để sửa diagram).
- [ ] (Bonus) State-chart diagram cho đối tượng có vòng đời: xe, cổng sạc, reservation, charging session, incident, simulation.
- [ ] (Bonus) Test case: dùng danh sách ở mục D làm gốc.

## C. Phụ thuộc với người khác

- **Người khác cần bạn:** Member 4: khuyến nghị điều chuyển dùng đúng format `plan`.
- **Bạn cần người khác:** Member 1: `cancel_reservation`, sự kiện `ISSUE_REPORTED`. Member 2: `run_prioritization`, `get_queue`, `apply_manual_override`, `update_point_status`.
- Đổi chữ ký hàm / payload sự kiện đã ghi trong `docs/shared-contract.md` → nhắn cả nhóm trước.

## D. Test tối thiểu cần có

- [ ] Dashboard: tổng KPI khớp `network.get_network_status()`
- [ ] Hub vượt 85% tạo đúng 1 cảnh báo (không trùng)
- [ ] Điều chuyển không chọn xe đang được đặt/đang chạy/bảo trì
- [ ] Xử lý sự cố: xe → MAINTENANCE + đặt chỗ liên quan bị hủy

## E. Phần chung cả nhóm (bạn cùng làm)

- [ ] Use-case diagram toàn hệ thống (#1) · Mô tả bối cảnh/stakeholder/phạm vi (#1) · NFR chung (#1)
- [ ] UI mockup (#2) – phần màn hình của bạn: `operator/dashboard.html`, `operator/incidents.html` và (cùng Member 2) `operator/charging.html`
- [ ] Deployment view + Development view (#3)
- [ ] Slide demo + luyện demo – phần của bạn: Kịch bản 3 và 4 trong TEAM_TODO.md (xử lý sự cố; Hub Metro sắp đầy → áp dụng điều chuyển).
- [ ] Đánh giá chéo thành viên cuối kỳ

## F. Definition of Done cho mỗi use case

- [ ] Hàm trong `service` chạy đúng luồng chính **và** luồng ngoại lệ trong spec
- [ ] Endpoint trả đúng mã lỗi (400/404/409), không còn 501
- [ ] Có ≥ 1 test cho luồng chính, 1 cho luồng lỗi; `pytest` xanh
- [ ] Trang giao diện dùng được (không còn khung TODO màu vàng)
- [ ] Sequence + activity diagram khớp với code thật
