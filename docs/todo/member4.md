# TODO cá nhân – Member 4 (What-if Simulation Lead)

* Tài liệu spec của bạn: **what_if_template.docx**
* Thư mục code: `src/backend/modules/simulation/`
* Trang giao diện: `operator/what-if.html`
* Test của bạn: `src/backend/tests/test_simulation.py` (bỏ `@SKIP` khi làm xong từng UC)
* Đọc trước: `TEAM_TODO.md`, `docs/shared-contract.md`, `core/entities.py`, `core/state_manager.py`

Mỗi chỗ cần làm trong code đã có hàm stub gọi `todo(...)` kèm docstring hướng dẫn – tìm bằng `grep -rn "todo(" src/backend/modules/simulation/`. Gọi endpoint chưa làm sẽ nhận HTTP 501 ghi tên bạn.

## A. Code (làm theo thứ tự P0 → P1 → P2)

### P0 – làm trước, người khác đang phụ thuộc / nền tảng

- [ ] **UC4 + UC3 chạy mô phỏng** — `engine.fetch_snapshot`, `engine.run`
  - Chạy trên `network.snapshot()` (deep copy) theo bước thời gian (vd 5 phút), **không bao giờ đụng trạng thái thật**. Có `seed` để demo lặp lại được.
- [ ] **UC1 cấu hình kịch bản** — `scenarios.create_scenario`, `SimulationScenario.configure`
  - Validate: Hub tồn tại, hệ số hợp lệ, số cổng hỏng ≤ số cổng của Hub. 5 loại: demand_surge (Metro giờ cao điểm), hub_full, charging surge, charging_fault, vehicle_concentration.
- [ ] **UC5 đánh giá tác động** — `engine.evaluate_impact`
  - Mỗi Hub: nhu cầu được đáp ứng/không, độ đầy đỉnh, độ dài hàng đợi sạc, thời điểm đầy; phân loại `impact_level`.

### P1 – chức năng chính để demo

- [ ] **UC6 khuyến nghị** — `recommender.generate`
  - 3 loại: điều chuyển xe (đúng format `plan` của Member 3), đổi lịch sạc, điều hướng người dùng sang Hub khác.
- [ ] **UC2 mẫu kịch bản** — `scenarios.list_templates`, `create_from_template`
  - Đọc `configs/simulation-scenarios.json` (đã có 4 mẫu; thêm `vehicle_concentration`).
- [ ] **API + giao diện** — `routes.py` đã có khung; trang `operator/what-if.html`
  - Form tham số, bảng tác động theo Hub, danh sách khuyến nghị.

### P2 – hoàn thiện

- [ ] **UC7 xuất báo cáo** — `report.export_report`
  - Chọn MỘT định dạng trước (xlsx hoặc pdf); thêm thư viện vào `requirements.txt`.
- [ ] **`compare_with_current`** — so sánh trạng thái cuối với snapshot ban đầu
- [ ] **Biểu đồ diễn biến theo thời gian** — trên trang What-if

## B. Tài liệu cá nhân (đề bài: mỗi người làm cho UC của mình)

| Use case | Sequence diagram (#2) | Activity diagram (#2) | UC detail (#1) |
|---|---|---|---|
| UC1 Configure Simulation Scenario | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC2 Load Scenario Template | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC3 Run Scenario Simulation | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC4 Fetch Operational State Snapshot | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC5 Evaluate Service Impact & Overload Risk | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC6 Generate Rebalancing Recommendations | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |
| UC7 Export Simulation Report | ☐ | ☐ | ☐ (đã có trong file spec – rà lại) |

- [ ] **Hạn #3 – Class & method description** cho: `SimulationScenario`, `SimulationResult` (mô tả *mọi* method trong class diagram của lớp mình; nếu code lệch diagram thì báo nhóm để sửa diagram).
- [ ] (Bonus) State-chart diagram cho đối tượng có vòng đời: xe, cổng sạc, reservation, charging session, incident, simulation.
- [ ] (Bonus) Test case: dùng danh sách ở mục D làm gốc.

## C. Phụ thuộc với người khác

- **Người khác cần bạn:** Không ai gọi code của bạn trực tiếp; Member 3 dùng khuyến nghị của bạn qua giao diện.
- **Bạn cần người khác:** `network.snapshot()` (core). Format `plan` điều chuyển từ Member 3 (`redistribution.py`). Logic ưu tiên sạc của Member 2 chỉ tham khảo khi mô phỏng hàng đợi (có thể dùng công thức đơn giản riêng, ghi rõ trong báo cáo).
- Đổi chữ ký hàm / payload sự kiện đã ghi trong `docs/shared-contract.md` → nhắn cả nhóm trước.

## D. Test tối thiểu cần có

- [ ] **Chạy mô phỏng xong, trạng thái thật không đổi** (so sánh trước/sau)
- [ ] Tham số không hợp lệ bị từ chối
- [ ] Cùng seed → cùng kết quả
- [ ] Surge tại Metro gây cảnh báo nguy cơ quá tải; khuyến nghị đúng format `plan`

## E. Phần chung cả nhóm (bạn cùng làm)

- [ ] Use-case diagram toàn hệ thống (#1) · Mô tả bối cảnh/stakeholder/phạm vi (#1) · NFR chung (#1)
- [ ] UI mockup (#2) – phần màn hình của bạn: `operator/what-if.html`
- [ ] Deployment view + Development view (#3)
- [ ] Slide demo + luyện demo – phần của bạn: Kịch bản 4 trong TEAM_TODO.md (What-if Metro giờ cao điểm → khuyến nghị).
- [ ] Đánh giá chéo thành viên cuối kỳ

## F. Definition of Done cho mỗi use case

- [ ] Hàm trong `service` chạy đúng luồng chính **và** luồng ngoại lệ trong spec
- [ ] Endpoint trả đúng mã lỗi (400/404/409), không còn 501
- [ ] Có ≥ 1 test cho luồng chính, 1 cho luồng lỗi; `pytest` xanh
- [ ] Trang giao diện dùng được (không còn khung TODO màu vàng)
- [ ] Sequence + activity diagram khớp với code thật
