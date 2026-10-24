# TODO cá nhân – Member 1 (Student Discovery & Reservation Lead)

* Tài liệu spec của bạn: **Student_Discovery__Reservation_Specification.docx**
* Thư mục code: `src/backend/modules/reservation/`
* Trang giao diện: `student/find-hub.html`, `student/reserve-vehicle.html`, `student/my-trips.html`
* Test của bạn: `src/backend/tests/test_reservation.py` (bỏ `@SKIP` khi làm xong từng UC)
* Đọc trước: `TEAM_TODO.md`, `docs/shared-contract.md`, `core/entities.py`, `core/state_manager.py`

Mỗi chỗ cần làm trong code đã có hàm stub gọi `todo(...)` kèm docstring hướng dẫn – tìm bằng `grep -rn "todo(" src/backend/modules/reservation/`. Gọi endpoint chưa làm sẽ nhận HTTP 501 ghi tên bạn.

## A. Code (làm theo thứ tự P0 → P1 → P2)

### P0 – làm trước, người khác đang phụ thuộc / nền tảng

- [ ] **U1 tìm Hub & xe** — `service.search_hubs_and_vehicles`, `get_vehicle_detail`
  - Lọc theo loại xe / pin tối thiểu; trả % pin, số chỗ đỗ trống; xe cá nhân → chỉ cần Hub còn chỗ.
- [ ] **U2 đặt xe** — `service.reserve_vehicle` + `core/allocation_service.allocate_vehicle`
  - Trong `network.lock`: chọn xe AVAILABLE → RESERVED, tạo `Reservation(kind=VEHICLE)`, giữ 15 phút, cọc qua U8. Hai sinh viên cùng đặt 1 xe → người sau nhận 409.
- [ ] **U3 đặt chỗ đỗ** — `service.reserve_parking_slot` + `allocate_parking_space`
  - Đặt `ParkingSpace.reserved_by`; 2 chế độ: trả xe thuê (shared_return) và xe cá nhân (private).
- [ ] **U8 thanh toán (mock)** — `payment_gateway.py`
  - Ledger trong bộ nhớ, `transaction_id` giả, có thể từ chối thanh toán để demo luồng ngoại lệ.

### P1 – chức năng chính để demo

- [ ] **U4 hủy** — `service.cancel_reservation`
  - Giải phóng xe/chỗ, hoàn cọc, phát `RESERVATION_CANCELLED`. **Member 3 gọi hàm này (UC-OP07)** nên làm sớm.
- [ ] **U5 nhận xe + U9** — `pick_up_vehicle`, `smart_lock.unlock`
  - Kiểm tra QR/đặt chỗ còn hạn → mở khóa → xe IN_USE → tạo bản ghi chuyến. Hỗ trợ walk-up không đặt trước.
- [ ] **U6 trả xe** — `return_vehicle`, `smart_lock.lock`
  - Dùng `network.move_vehicle`; Hub đầy → gợi ý Hub khác; tính phí chuyến (U8).
- [ ] **U7 báo sự cố** — `report_issue`
  - Lưu issue và `bus.emit(ISSUE_REPORTED, payload đúng hợp đồng)` – **Member 3 phụ thuộc**.

### P2 – hoàn thiện

- [ ] **Hết hạn giữ chỗ** — job/hàm quét `Reservation.is_expired()` → EXPIRED, nhả tài nguyên
- [ ] **Lịch sử chuyến** — `list_my_trips` + trang `my-trips.html`
- [ ] **Giao diện** — 3 trang student đầy đủ, hiển thị lỗi 409/400 rõ ràng

## B. Tài liệu cá nhân (đề bài: mỗi người làm cho UC của mình)

| Use case | Sequence diagram (#2) | Activity diagram (#2) | UC detail (#1) |
|---|---|---|---|
| U1 Search Hub and Vehicle detail | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| U2 Reserve Vehicle | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| U3 Reserve Parking Slot | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| U4 Cancel Reservation | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| U5 Pick Up Vehicle | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| U6 Return Vehicle | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| U7 Report Issue | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| U8 Process Payment (mock) | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| U9 Control Smart Lock (mock) | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |

- [ ] **Hạn #3 – Class & method description** cho: `User`, `Student`, `ParkingSpace`, `Reservation`, `AllocationService` (allocateVehicle, allocateParkingSpace) (mô tả *mọi* method trong class diagram của lớp mình; nếu code lệch diagram thì báo nhóm để sửa diagram).
- [ ] (Bonus) State-chart diagram cho đối tượng có vòng đời: xe, cổng sạc, reservation, charging session, incident, simulation.
- [ ] (Bonus) Test case: dùng danh sách ở mục D làm gốc.

## C. Phụ thuộc với người khác

- **Người khác cần bạn:** Member 2: không. Member 3: dùng `cancel_reservation(by_system=True)` và nghe `ISSUE_REPORTED`.
- **Bạn cần người khác:** Dùng `network.move_vehicle`, `network.lock`, `bus` (core). Có thể cần Member 2 cho tình huống "xe cá nhân đỗ + sạc" (chỉ ở mức gợi ý trên UI).
- Đổi chữ ký hàm / payload sự kiện đã ghi trong `docs/shared-contract.md` → nhắn cả nhóm trước.

## D. Test tối thiểu cần có

- [ ] Hai sinh viên đặt cùng 1 xe → chỉ một thành công (dùng `threading` để mô phỏng đồng thời)
- [ ] Hủy → xe về AVAILABLE, cọc được hoàn
- [ ] Trả xe vào Hub đầy bị từ chối
- [ ] `report_issue` phát đúng sự kiện

## E. Phần chung cả nhóm (bạn cùng làm)

- [ ] Use-case diagram toàn hệ thống (#1) · Mô tả bối cảnh/stakeholder/phạm vi (#1) · NFR chung (#1)
- [ ] UI mockup (#2) – phần màn hình của bạn: `student/find-hub.html`, `student/reserve-vehicle.html`, `student/my-trips.html`
- [ ] Deployment view + Development view (#3)
- [ ] Slide demo + luyện demo – phần của bạn: Kịch bản 1 và 3 trong TEAM_TODO.md (đặt → nhận → trả xe; báo xe hỏng).
- [ ] Đánh giá chéo thành viên cuối kỳ

## F. Definition of Done cho mỗi use case

- [ ] Hàm trong `service` chạy đúng luồng chính **và** luồng ngoại lệ trong spec
- [ ] Endpoint trả đúng mã lỗi (400/404/409), không còn 501
- [ ] Có ≥ 1 test cho luồng chính, 1 cho luồng lỗi; `pytest` xanh
- [ ] Trang giao diện dùng được (không còn khung TODO màu vàng)
- [ ] Sequence + activity diagram khớp với code thật
