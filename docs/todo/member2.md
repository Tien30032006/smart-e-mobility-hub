# TODO cá nhân – Member 2 (Charging & Scheduling Lead)

* Tài liệu spec của bạn: **Charging__Scheduling.docx**
* Thư mục code: `src/backend/modules/charging/`
* Trang giao diện: `student/charging-request.html` và (cùng Member 3) `operator/charging.html`
* Test của bạn: `src/backend/tests/test_charging.py` (bỏ `@SKIP` khi làm xong từng UC)
* Đọc trước: `TEAM_TODO.md`, `docs/shared-contract.md`, `core/entities.py`, `core/state_manager.py`

Mỗi chỗ cần làm trong code đã có hàm stub gọi `todo(...)` kèm docstring hướng dẫn – tìm bằng `grep -rn "todo(" src/backend/modules/charging/`. Gọi endpoint chưa làm sẽ nhận HTTP 501 ghi tên bạn.

## A. Code (làm theo thứ tự P0 → P1 → P2)

### P0 – làm trước, người khác đang phụ thuộc / nền tảng

- [ ] **UC-CH-09 thuật toán ưu tiên** — `scheduler.calculate_priority` (hàm thuần), `run_prioritization`, `get_queue`
  - Công thức gợi ý trong docstring; xe pin thấp / sắp dùng được sạc trước; không bao giờ gán cổng hỏng/đã đặt. **Member 3 và Member 4 phụ thuộc** – làm đầu tiên.
- [ ] **UC-CH-01 gửi yêu cầu sạc** — `service.submit_charging_request`
  - Chỉ xe điện cá nhân; tạo session QUEUED; phát `CHARGING_REQUESTED`.
- [ ] **UC-CH-10 dữ liệu cảm biến** — `telemetry.ingest_readings`, `start_simulator`
  - Dữ liệu pin/cổng sạc cập nhật gần thời gian thực → làm demo "sống" cho cả nhóm.

### P1 – chức năng chính để demo

- [ ] **UC-CH-02 + 03 đặt lịch + chọn cổng** — `schedule_charging_session`, `list_available_points`
  - Chống trùng khung giờ trên cùng cổng (trong `network.lock`); tạo `Reservation(kind=CHARGING)`.
- [ ] **UC-CH-05 hủy** — `cancel_charging_reservation`
  - Nhả cổng/khung giờ và đẩy hàng đợi lên.
- [ ] **UC-CH-07 + 08 giám sát/đổi trạng thái cổng** — `point_monitor.py`
  - Cổng bị đặt OUT_OF_SERVICE khi đang sạc → đưa session về hàng đợi. Phát `CHARGER_STATUS_CHANGED`.
- [ ] **UC-CH-06 xem trạng thái sạc** — `get_my_charging_status`
  - Vị trí hàng đợi, cổng được gán, pin hiện tại, ETA = (100−pin)/công suất.

### P2 – hoàn thiện

- [ ] **UC-CH-04 gợi ý thông minh** — `get_smart_suggestion`
  - Chấm điểm (Hub, cổng, khung giờ) theo pin + giờ cần xe + khả năng trống dự kiến.
- [ ] **`apply_manual_override`** — hàm Member 3 gọi cho UC-OP09
  - Làm sau P0 nhưng trước tích hợp; phát `CHARGING_OVERRIDE`.
- [ ] **Giao diện** — trang sinh viên + phần thao tác cổng sạc trên `operator/charging.html` (làm chung với Member 3)

## B. Tài liệu cá nhân (đề bài: mỗi người làm cho UC của mình)

| Use case | Sequence diagram (#2) | Activity diagram (#2) | UC detail (#1) |
|---|---|---|---|
| UC-CH-01 Submit Charging Request | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-CH-02 Schedule Charging Session | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-CH-03 Select Charging Point | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-CH-04 Get Smart Charging Suggestion | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-CH-05 Cancel Charging Reservation | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-CH-06 View My Charging Status | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-CH-07 Monitor Charging Point Status | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-CH-08 Update Charging Point Status | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-CH-09 Run Smart Charging Prioritization | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC-CH-10 Report Real-time Charging & Battery Data | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |

- [ ] **Hạn #3 – Class & method description** cho: `ChargingPoint`, `ChargingSession`, `EVehicle` (getBatteryLevel, updateStatus, assignToHub) (mô tả *mọi* method trong class diagram của lớp mình; nếu code lệch diagram thì báo nhóm để sửa diagram).
- [ ] (Bonus) State-chart diagram cho đối tượng có vòng đời: xe, cổng sạc, reservation, charging session, incident, simulation.
- [ ] (Bonus) Test case: dùng danh sách ở mục D làm gốc.

## C. Phụ thuộc với người khác

- **Người khác cần bạn:** Member 3 gọi: `run_prioritization`, `get_queue`, `apply_manual_override`, `update_point_status`. Member 4 chỉ đọc snapshot.
- **Bạn cần người khác:** Member 1: không gọi trực tiếp (chung store `network.reservations`, nên lọc theo `kind`).
- Đổi chữ ký hàm / payload sự kiện đã ghi trong `docs/shared-contract.md` → nhắn cả nhóm trước.

## D. Test tối thiểu cần có

- [ ] Pin thấp có điểm ưu tiên cao hơn pin cao (cùng thời gian cần xe)
- [ ] Cổng OUT_OF_SERVICE không bao giờ được gán
- [ ] Hai đặt lịch trùng khung giờ trên cùng cổng → từ chối
- [ ] Telemetry với giá trị pin ngoài 0–100 bị từ chối

## E. Phần chung cả nhóm (bạn cùng làm)

- [ ] Use-case diagram toàn hệ thống (#1) · Mô tả bối cảnh/stakeholder/phạm vi (#1) · NFR chung (#1)
- [ ] UI mockup (#2) – phần màn hình của bạn: `student/charging-request.html` và (cùng Member 3) `operator/charging.html`
- [ ] Deployment view + Development view (#3)
- [ ] Slide demo + luyện demo – phần của bạn: Kịch bản 2 trong TEAM_TODO.md (yêu cầu sạc → chạy lịch ưu tiên → override).
- [ ] Đánh giá chéo thành viên cuối kỳ

## F. Definition of Done cho mỗi use case

- [ ] Hàm trong `service` chạy đúng luồng chính **và** luồng ngoại lệ trong spec
- [ ] Endpoint trả đúng mã lỗi (400/404/409), không còn 501
- [ ] Có ≥ 1 test cho luồng chính, 1 cho luồng lỗi; `pytest` xanh
- [ ] Trang giao diện dùng được (không còn khung TODO màu vàng)
- [ ] Sequence + activity diagram khớp với code thật
