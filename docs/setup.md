# 🛠 Setup Guide

Step-by-step instructions to set up and run the **Smart E-Mobility Hub** locally.

---

## 1. Prerequisites

| Requirement | Version |
|---|---|
| Python | **3.10+** |
| pip | Latest |
| Browser | Chrome / Firefox / Edge |
| (Optional) VS Code | With **Live Server** extension |

Check Python:
```bash
python --version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/Tien30032006/smart-e-mobility-hub.git
cd smart-e-mobility-hub
```

---

## 3. Create a Virtual Environment

### Windows
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If you get an execution-policy error:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### Linux / macOS
```bash
python -m venv venv
source venv/bin/activate
```

---

## 4. Install Dependencies

```bash
pip install -r requirements.txt
```

Dependencies:

| Package | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI server |
| `pydantic` | Data validation |
| `python-dotenv` | Environment variables |
| `pytest` | Testing |
| `httpx` | HTTP client for tests |
| `rich` | Pretty console output |

---

## 5. Seed Data (Optional)

Load sample Hubs, vehicles, and scenarios into the state:

```bash
python scripts/seed_data.py
```

This reads `configs/hubs-data.json` and populates the in-memory state.

---

## 6. Run the Backend

```bash
python -m src.backend.app
```

Backend runs at: **`http://localhost:8000`**

Verify:
```bash
curl http://localhost:8000/
# → {"message":"Smart E-Mobility Hub API","status":"running"}
```

---

## 7. Run the Frontend

### Option A - Python http.server

```bash
python -m http.server 5500 --directory src/frontend
```

Open: **`http://localhost:5500`**

### Option B - VS Code Live Server

1. Install the **Live Server** extension.
2. Right-click `src/frontend/index.html`.
3. Click **Open with Live Server**.

---

## 8. Run Both in Parallel (Recommended for Demo)

### Terminal 1 - Backend
```bash
python -m src.backend.app
```

### Terminal 2 - Frontend
```bash
python -m http.server 5500 --directory src/frontend
```

Open `http://localhost:5500` in your browser.

---

## 9. Run Tests

```bash
pytest src/backend/tests/ -v
```

Run a specific test:
```bash
pytest src/backend/tests/test_reservation.py -v
```

---

## 10. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` | venv not activated, or deps not installed | Activate venv, run `pip install -r requirements.txt` |
| `CORS error` in browser | Backend CORS not enabled | Ensure `CORSMiddleware` is added in `app.py` |
| `Address already in use` (port 8000) | Another process using port 8000 | `uvicorn src.backend.app:app --port 8001` |
| `Address already in use` (port 5500) | Another process using port 5500 | `python -m http.server 5501 --directory src/frontend` |
| Frontend shows blank page | Backend not running, or wrong API URL | Start backend, check `api-client.js` base URL |
| Emoji / box-drawing chars broken in terminal | Terminal font doesn't support Unicode | Use VS Code terminal or Windows Terminal with a Unicode font |
| `Execution policy` error on Windows | PowerShell blocks script execution | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |

---

## 11. Project Structure Recap

```text
smart-e-mobility-hub/
├── configs/         → seed data, scenarios, app config
├── src/
│   ├── backend/     → FastAPI backend
│   │   ├── core/    → shared entities & state (Member 5)
│   │   ├── modules/ → 4 business modules (Member 1–4)
│   │   ├── data/    → seed data loading
│   │   └── tests/   → unit tests
│   ├── frontend/    → static HTML/CSS/JS UI
│   └── shared/      → shared frontend↔backend client
├── scripts/         → run scripts
└── docs/            → this documentation
```

---

## 12. Related Documents

- [`architecture.md`](architecture.md) - system architecture
- [`api-reference.md`](api-reference.md) - REST API endpoints