# TEAM TODO – Smart E-Mobility Hub (BTL Công nghệ phần mềm HK261)

Đọc file này trước, sau đó mở **file TODO cá nhân** của bạn trong `docs/todo/`.

| Thành viên | Module (backend) | Use case | File TODO cá nhân |
|---|---|---|---|
| **Member 1** | `modules/reservation/` | U1–U9 (Student Discovery & Reservation) | [docs/todo/member1.md](docs/todo/member1.md) |
| **Member 2** | `modules/charging/` | UC-CH-01…10 (Charging & Scheduling) | [docs/todo/member2.md](docs/todo/member2.md) |
| **Member 3** | `modules/operations/` | UC01–UC-OP09 (Operator Management) | [docs/todo/member3.md](docs/todo/member3.md) |
| **Member 4** | `modules/simulation/` | UC1–UC7 (What-if Simulation) | [docs/todo/member4.md](docs/todo/member4.md) |
| **Member 5** | `core/`, `app.py`, `data/`, tích hợp, tài liệu chung | không có module riêng (Architecture & Integration) | [docs/todo/member5.md](docs/todo/member5.md) |

> Gói này có 4 bộ spec use case nên 4 module đã gắn Member 1–4. Member 5 phụ trách phần chung/kiến trúc/tích hợp theo vai trò "Architecture & Integration Lead" trong README gốc; nếu nhóm phân khác thì chỉnh lại bảng này và `docs/todo/member5.md`.

## 1. Phần CHUNG đã làm sẵn (Member 5 là người giữ; ai muốn sửa phải báo cả nhóm trước)

| Thành phần | File | Ghi chú |
|---|---|---|
| Class `User` (abstract), `Student`, `Operator` | `core/entities.py` | đúng class diagram; `Student.find_vehicle/reserve_resource` và `Operator.handle_incident` ủy quyền cho module của từng người |
| `MobilityHub`, `ParkingSpace`, `ChargingPoint`, `EVehicle`, `Reservation`, `ChargingSession`, `Event` | `core/entities.py` | các method đơn giản đã code; method nghiệp vụ là `todo(...)` ghi rõ chủ sở hữu |
| Enum trạng thái + loại sự kiện | `core/enums.py` | **luôn dùng enum, không dùng chuỗi thô** |
| `HubNetworkManager` (`network`) | `core/state_manager.py` | kho trạng thái duy nhất, `network.lock`, `move_vehicle()` nguyên tử, `snapshot()` (deep copy cho What-if) |
| `EventBus` (`bus`) | `core/event_bus.py` | module nói chuyện qua sự kiện (`bus.emit`, `bus.subscribe`) |
| Đăng nhập giả lập + phân quyền | `core/auth.py` | `require_student`, `require_operator` |
| `AllocationService` | `core/allocation_service.py` | chỉ ủy quyền: `allocate_vehicle/parking` → Member 1, `schedule_charging` → Member 2 |
| Dữ liệu demo | `configs/hubs-data.json`, `data/seed_data.py` | 4 Hub, 10 xe (1 xe cá nhân), 3 tài khoản |
| App + API chung | `app.py` | `/api/auth/login`, `/api/hubs`, `/api/network/status`; Swagger ở `/docs` |
| Frontend chung | `index.html`, `assets/`, `shared/api-client.js` | đăng nhập, menu, hiển thị 501 "chưa làm – của ai" |
| Test phần chung | `tests/test_core.py` | phải luôn xanh |

Hợp đồng chi tiết (tên hàm, payload sự kiện, format kế hoạch điều chuyển…): [docs/shared-contract.md](docs/shared-contract.md).

## 2. Điểm giao nhau giữa các use case – ai làm gì

Spec của các bạn có vài chỗ chồng nhau. Quy ước để không làm trùng:

| Chủ đề | Người SỞ HỮU logic | Người GỌI / dùng |
|---|---|---|
| Thuật toán ưu tiên sạc (priority score) | **Member 2** – `charging/scheduler.py` (UC-CH-09) | Member 3: UC-OP08 xem/chạy, UC-OP09 ghi đè |
| Hủy đặt chỗ | **Member 1** – `reservation.service.cancel_reservation` (U4) | Member 3: UC-OP07 gọi với `by_system=True` |
| Báo sự cố (sinh viên) | **Member 1** – U7 phát `ISSUE_REPORTED` | Member 3: UC05 lắng nghe sự kiện này |
| Đổi trạng thái cổng sạc thủ công | **Member 2** – UC-CH-08 | Member 3: UC05 (sự cố hỏng cổng) gọi hàm của Member 2 |
| Giám sát cổng sạc | **Member 2** – UC-CH-07 | Member 3: dashboard UC01 hiển thị lại số liệu |
| Dữ liệu cảm biến (pin, cổng sạc) | **Member 2** – UC-CH-10 `telemetry.py` | Member 4: không dùng, chỉ đọc `snapshot()` |
| Snapshot trạng thái | **Core** (`network.snapshot()`) | Member 4: UC4 |
| Kế hoạch điều chuyển xe | **Member 3** – định dạng `plan` ở `redistribution.py` | Member 4: UC6 sinh khuyến nghị cùng format |
| Thanh toán / khóa thông minh (giả lập) | **Member 1** – U8, U9 | Member 1 tự dùng trong U2/U5/U6 |

## 3. Quy tắc làm việc nhóm

1. **Mỗi người chỉ sửa thư mục module của mình** (+ trang HTML của mình). Muốn sửa `core/` hoặc đổi chữ ký hàm người khác đang gọi → nhắn cả nhóm, ghi vào biên bản họp tuần.
2. Nhánh git: `main` (luôn chạy được) + nhánh `feature/<tên>-<usecase>`; tạo Pull Request, 1 người khác review.
3. Xóa `todo(...)` khi làm xong hàm và **bỏ `@SKIP`** ở test tương ứng. Không merge khi `pytest` đỏ.
4. Mọi thao tác "kiểm tra còn trống → giữ chỗ" phải nằm trong `with network.lock:`.
5. Mỗi người phải hiểu và giải thích được code của mình khi demo.

## 4. Lộ trình gợi ý (chỉnh theo deadline trên LMS)

| Giai đoạn | Mục tiêu | Ai |
|---|---|---|
| Tuần 1 | Họp đầu tiên (giao tiếp, cam kết, rủi ro); cả nhóm chạy được `run_backend.sh`, đọc `shared-contract.md`, chốt chỗ còn tranh cãi | Cả nhóm |
| Hạn nộp #1 | UC detail (đã có spec), use-case diagram toàn hệ thống, NFR chung | Cả nhóm + cá nhân |
| Hạn nộp #2 | Sequence + Activity diagram mỗi UC của mình, UI mockup chung (bonus: State-chart) | Cá nhân + nhóm |
| Hạn nộp #3 | Deployment view, Development view, Class diagram, mô tả method của lớp mình (bonus: test case) | Nhóm + cá nhân |
| Song song với #2–#3 | Code theo thứ tự ưu tiên trong file TODO cá nhân (P0 → P1 → P2) | Cá nhân |
| Tích hợp (≥1 tuần trước demo) | Chạy kịch bản demo end-to-end, sửa lỗi tích hợp, luyện demo nhiều lần | Cả nhóm |
| Final | Một file PDF: #1 + #2 + #3 + chuỗi màn hình demo | Cả nhóm |

## 5. Kịch bản demo đề xuất (để mọi người code hướng tới cùng đích)

1. Sinh viên đăng nhập → tìm xe từ ga Metro tới KTX (Member 1 U1) → đặt xe + cọc (U2) → nhận xe (U5) → trả xe tại Hub đầy/không đầy (U6).
2. Sinh viên có xe điện cá nhân gửi yêu cầu sạc (Member 2 CH-01) → Operator chạy lịch ưu tiên (CH-09) và ghi đè một xe (Member 3 OP09).
3. Một xe bị báo hỏng (Member 1 U7) → Operator xử lý sự cố, tạo ticket, hủy đặt chỗ liên quan (Member 3 UC05/OP06/OP07).
4. Dashboard hiện Hub Metro sắp đầy (Member 3 UC01/UC02) → chạy What-if "sinh viên đổ về ga Metro giờ cao điểm" (Member 4 UC1–UC5) → nhận khuyến nghị (UC6) → áp dụng bằng lệnh điều chuyển (Member 3 UC03/OP04).
