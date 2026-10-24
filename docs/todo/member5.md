# TODO cá nhân – Member 5 (Architecture, Integration & Report Lead)

Member 5 không có module use case riêng; giữ phần **chung** để 4 module ghép được với nhau và bài nộp nhất quán.
(Nếu nhóm chia vai khác, chuyển các mục dưới đây cho người phù hợp.)

* Thư mục/file phụ trách: `src/backend/core/`, `src/backend/app.py`, `src/backend/data/`, `configs/`, `src/shared/`, `src/frontend/index.html` + `assets/`, `scripts/`, `docs/`
* Đọc trước: `TEAM_TODO.md`, `docs/shared-contract.md`, class diagram của nhóm

## A. Code & tích hợp

### P0
- [ ] Cả nhóm chạy được `pytest` + `run_backend.sh` ngay tuần đầu; xử lý lỗi môi trường (Python, venv, cổng 8000)
- [ ] Chốt `docs/shared-contract.md` với 4 thành viên (enum, sự kiện, chữ ký hàm gọi chéo, format `plan` điều chuyển); mọi thay đổi `core/` đi qua bạn
- [ ] Rà `core/entities.py` ↔ class diagram: tên lớp, thuộc tính, method khớp 1:1; cập nhật bên nào lệch
- [ ] Thiết lập quy trình git: nhánh `main` luôn chạy được, PR + review, quy tắc đặt tên nhánh

### P1
- [ ] Nối `register_event_handlers` của Member 3 vào lúc khởi động `app.py` và bật simulator của Member 2 (`telemetry.start_simulator`) khi các hàm đó xong
- [ ] Mở rộng `configs/hubs-data.json` / `seed_data.py` theo nhu cầu demo (Hub gần đầy, xe pin thấp, cổng hỏng) – hỏi 4 bạn cần dữ liệu gì
- [ ] Test tích hợp end-to-end theo 4 kịch bản trong `TEAM_TODO.md` (thêm `tests/test_integration.py`)
- [ ] Kiểm tra đồng thời: nhiều request cùng đặt 1 tài nguyên (kết hợp test của Member 1 và 2)

### P2
- [ ] Giao diện chung: menu, trạng thái lỗi/"chưa làm", thống nhất style giữa các trang
- [ ] Script reset dữ liệu demo nhanh trước mỗi lần diễn tập (`scripts/seed_data.py`)
- [ ] Dọn code: xóa `todo(...)` còn sót, docstring lỗi thời, file không dùng

## B. Tài liệu chung (làm chính, các bạn khác góp ý)

| Mục | Nộp | Trạng thái |
|---|---|---|
| Mô tả bối cảnh, stakeholder, mục tiêu, phạm vi | #1 | ☐ |
| Use-case diagram toàn hệ thống (gộp 4 spec) | #1 | ☐ |
| Non-functional requirements chung | #1 | ☐ |
| UI mockup chung | #2 | ☐ |
| Architectural design + Deployment view + Development/Implementation view | #3 | ☐ |
| Class diagram tích hợp | #3 | ☐ |
| Test case tổng hợp (bonus) | #3 | ☐ |
| Gộp #1 + #2 + #3 + chuỗi màn hình demo thành **1 file PDF** | Final | ☐ |

Ngoài ra, giống các thành viên khác, Member 5 vẫn phải nộp tài liệu **cá nhân** theo yêu cầu của đề (xác nhận với thầy phần cá nhân của Member 5 gồm những use case nào, vì 4 bộ spec hiện đã có chủ).

## C. Họp nhóm & theo dõi
- [ ] Họp mỗi tuần + biên bản (đề yêu cầu): họp đầu tiên bàn giao tiếp, cam kết, rủi ro chung và cách xử lý
- [ ] Cập nhật bảng "điểm giao nhau" trong `TEAM_TODO.md` khi phát sinh thỏa thuận mới
- [ ] Tổ chức buổi tích hợp ≥ 1 tuần trước demo và các buổi diễn tập demo
- [ ] Đánh giá chéo thành viên cuối kỳ
