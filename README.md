# ⚡ Smart E-Mobility Hub – Skeleton cho nhóm 4 người

Hệ thống điều phối phương tiện điện trong Khu đô thị ĐHQG-HCM (BTL Công nghệ phần mềm HK261).
Stack: **Python (FastAPI)** + **HTML/CSS/JavaScript thuần**, dữ liệu giả lập trong bộ nhớ (đề bài không yêu cầu database).

👉 **Bắt đầu từ [TEAM_TODO.md](TEAM_TODO.md)**, sau đó mở file TODO cá nhân:

| Thành viên | Module | TODO cá nhân |
|---|---|---|
| Member 1 | `modules/reservation/` | [docs/todo/member1.md](docs/todo/member1.md) |
| Member 2 | `modules/charging/` | [docs/todo/member2.md](docs/todo/member2.md) |
| Member 3 | `modules/operations/` | [docs/todo/member3.md](docs/todo/member3.md) |
| Member 4 | `modules/simulation/` | [docs/todo/member4.md](docs/todo/member4.md) |
| Member 5 | `core/`, tích hợp, tài liệu chung | [docs/todo/member5.md](docs/todo/member5.md) |

## Chạy thử (2 phút)

```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
pytest                                               # 10 passed, 32 skipped (skipped = TODO của từng người)
uvicorn src.backend.app:app --reload --port 8000     # hoặc scripts/run_backend.sh (Windows: scripts\run_backend.bat)
```

* Giao diện: http://localhost:8000/app/ (đăng nhập demo bằng 3 nút)
* Swagger (xem danh sách API): http://localhost:8000/docs. Endpoint cần đăng nhập thì gọi bằng `curl -H "Authorization: Bearer U-S01" ...` (sinh viên) hoặc `U-OP1` (operator), hoặc thử qua giao diện web
* Endpoint chưa làm trả **HTTP 501** kèm tên người phụ trách và use case.

## Cấu trúc

```text
smart-e-mobility-hub/
├── TEAM_TODO.md                 # phân công, điểm giao nhau, quy tắc nhóm, lộ trình, kịch bản demo
├── docs/
│   ├── shared-contract.md       # hợp đồng: class↔code, enum, sự kiện, hàm gọi chéo, format plan, API
│   └── todo/member{1,2,3,4,5}.md
├── configs/                     # hubs-data.json (dữ liệu demo), simulation-scenarios.json, app.config.json
├── src/
│   ├── backend/
│   │   ├── app.py               # entry point (CHUNG)
│   │   ├── core/                # CHUNG: entities, enums, state_manager, event_bus, auth, allocation_service, todo
│   │   ├── data/                # CHUNG: seed_data, loader
│   │   ├── modules/
│   │   │   ├── reservation/     # Member 1    – U1…U9
│   │   │   ├── charging/        # Member 2   – UC-CH-01…10
│   │   │   ├── operations/      # Member 3 – UC01…UC-OP09
│   │   │   └── simulation/      # Member 4   – UC1…UC7
│   │   └── tests/               # test_core (chung, đang xanh) + test_<module> (bỏ @SKIP khi làm)
│   ├── frontend/                # index.html + assets (CHUNG); student/*.html, operator/*.html (mỗi trang có chủ)
│   └── shared/api-client.js     # CHUNG
└── scripts/                     # run_backend.sh/.bat, seed_data.py
```

## Những gì đã chạy sẵn

* Mọi entity trong class diagram (đúng tên/thuộc tính/method), enum trạng thái, `network` (kho trạng thái + khóa chống đặt trùng + `move_vehicle` + `snapshot`), `bus` (sự kiện), đăng nhập giả lập + phân quyền.
* 4 Hub, 10 xe (kể cả 1 xe điện cá nhân), 3 tài khoản demo.
* Router của cả 4 module đã nối vào `app.py` với đầy đủ endpoint → mỗi người chỉ việc thay `todo(...)` bằng code thật.
* Frontend: đăng nhập, menu theo vai trò, trang tổng quan Hub (đang gọi API thật), 8 trang stub có sẵn khung hiển thị lỗi/"chưa làm".

## Quy tắc ngắn

1. Chỉ sửa module của mình; sửa `core/` hay chữ ký hàm người khác gọi → báo cả nhóm.
2. Trạng thái dùng chung chỉ đổi trong `with network.lock:`.
3. Làm xong UC → xóa `todo(...)`, bỏ `@SKIP`, `pytest` phải xanh.
