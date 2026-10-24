# 🛴⚡ Smart E-Mobility Hub - Electric Mobility Coordination System for the VNU-HCM Urban Area

[![Status: Skeleton](https://img.shields.io/badge/status-skeleton%20%2F%20in%20development-lightgrey.svg)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Frontend HTML/CSS/JS](https://img.shields.io/badge/frontend-HTML%2FCSS%2FJS-orange.svg)]()
[![Tests](https://img.shields.io/badge/tests-10%20passed%20%7C%2032%20todo-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Software Engineering Course Project - Talent Program, Computer Science**
> **Ho Chi Minh City University of Technology (HCMUT)**
>
> *Managing and coordinating a network of shared electric mobility resources
> (bicycles, motorcycles, scooters), parking capacity and charging infrastructure
> across the VNU-HCM Urban Area.*

---

## 🌍 Overview

The VNU-HCM Urban Area brings together multiple universities, dormitories,
libraries, service facilities and public transportation hubs. As Metro Line 1
opens up new travel patterns, students will increasingly combine a Metro ride
with shared electric vehicles to move between campuses and functional areas -
turning last-mile mobility into a distributed, multi-actor software problem,
not just a hardware one.

**Smart E-Mobility Hub** manages a network of **Mobility Hubs** (Metro station,
dormitories, campuses, service areas), each containing parking spaces,
charging points and electric vehicles, with near-real-time state updates from
simulated data.

The core software-engineering focus:

- 🧠 **State management** for vehicles, parking spaces and charging points across many concurrently active Hubs.
- 🔒 **Resource allocation & reservation handling** for shared, limited resources, with no double-booking.
- 🔋 **Smart charging scheduling** that prioritizes vehicles by battery level and expected usage.
- 📊 **Operational monitoring & incident handling** (overload detection, vehicle redistribution, device failures).
- 🔮 **What-if Simulation** that evaluates hypothetical scenarios on a read-only snapshot, without touching live data.

> This project intentionally does **not** focus on IoT hardware or 3D map
> interfaces. Data is simulated and kept in memory; no real database is required.

---

## 🏗 System Architecture

```text
┌──────────────────────────────┐     ┌──────────────────────────────┐
│         Student UI           │     │         Operator UI          │
│   (src/frontend/student/)    │     │   (src/frontend/operator/)   │
└──────────────┬───────────────┘     └──────────────┬───────────────┘
               └──────────────────┬─────────────────┘
                                  │  shared/api-client.js  (REST + Bearer token)
                                  ▼
               ┌────────────────────────────────────┐
               │      FastAPI app  (app.py)         │
               │  auth · hubs · network status      │
               └──────────────────┬─────────────────┘
                                  ▼
               ┌────────────────────────────────────┐
               │       Business Module Layer        │
               │      (src/backend/modules/)        │
               │                                    │
               │ • Reservation & Trip      Member 1 │
               │ • Charging & Scheduling   Member 2 │
               │ • Operations & Monitoring Member 3 │
               │ • What-if Simulation      Member 4 │
               └───────┬────────────────────┬───────┘
                       │ events             │ read / write under lock
                       ▼                    ▼
        ┌─────────────────────┐   ┌────────────────────────────────┐
        │  Event Bus          │   │  Shared Core        Member 5   │
        │  core/event_bus.py  │   │  entities · enums · network    │
        └─────────────────────┘   │  (HubNetworkManager)           │
                                  └───────────────┬────────────────┘
                                                  │ read-only snapshot()
                                                  ▼
                               ┌────────────────────────────────────┐
                               │         Simulation Engine          │
                               │ Works on a deep copy; never mutates│
                               │ the live operational state         │
                               └────────────────────────────────────┘
```

Modules never import each other's internals when an event will do: they publish
and subscribe through the **Event Bus**. Shared state lives only in
`HubNetworkManager` and is always changed under `network.lock`.

---

## 👥 Actors & Core Capabilities

| Actor | Capabilities |
|---|---|
| **Student** (shared or private vehicle) | Find a suitable Hub/vehicle · view availability & battery level · reserve a vehicle or parking space · pick up / return a vehicle · report issues · submit charging requests · schedule charging sessions |
| **Operator** | Monitor the whole Hub network · handle alerts · redistribute vehicles · handle incidents · supervise and override smart charging · run What-if scenarios |
| **System** (scheduler / simulator / sensors) | Push near-real-time state updates · run the charging-priority algorithm · execute What-if simulations |

---

## 🧩 Team & Modules

Each member owns one module end-to-end, from requirement specification to
detailed design, and also contributes to the shared group deliverables.

| Member | Module | Use cases | Personal TODO |
|---|---|---|---|
| **Member 1** | 🚲 Reservation & Trip<br>`modules/reservation/` | U1-U9: search, reserve vehicle/parking, cancel, pick up, return, report issue, payment & smart lock (mock) | [member1.md](docs/todo/member1.md) |
| **Member 2** | 🔋 Charging & Scheduling<br>`modules/charging/` | UC-CH-01…10: charging requests, scheduling, priority algorithm, point monitoring, telemetry | [member2.md](docs/todo/member2.md) |
| **Member 3** | 📊 Operations & Monitoring<br>`modules/operations/` | UC01-UC-OP09: dashboard, alerts, redistribution, incidents, charging oversight | [member3.md](docs/todo/member3.md) |
| **Member 4** | 🔮 What-if Simulation<br>`modules/simulation/` | UC1-UC7: scenarios, templates, simulation, impact evaluation, recommendations, report | [member4.md](docs/todo/member4.md) |
| **Member 5** | 🏛 Architecture & Integration<br>`core/`, `app.py`, docs | Shared core, integration tests, shared diagrams, final report & demo | [member5.md](docs/todo/member5.md) |

👉 **Start with [`TEAM_TODO.md`](TEAM_TODO.md)**, then open your personal TODO file.
The contract between modules (class ↔ code mapping, enums, events, cross-module
functions) is in [`docs/shared-contract.md`](docs/shared-contract.md).

---

## 📂 Repository Structure

```text
smart-e-mobility-hub/
│
├── README.md
├── TEAM_TODO.md                  # assignments, overlaps, team rules, roadmap, demo script
├── requirements.txt
├── pytest.ini
│
├── configs/
│   ├── hubs-data.json            # Demo data: hubs, vehicles, users
│   ├── simulation-scenarios.json # Predefined What-if scenarios
│   └── app.config.json
│
├── src/
│   ├── backend/
│   │   ├── app.py                # Application entry point (shared)
│   │   ├── core/                 # Shared: entities, enums, state manager, event bus, auth
│   │   ├── data/                 # Shared: seed data & config loader
│   │   ├── modules/
│   │   │   ├── reservation/      # Member 1
│   │   │   ├── charging/         # Member 2
│   │   │   ├── operations/       # Member 3
│   │   │   └── simulation/       # Member 4
│   │   └── tests/                # test_core (shared, green) + one test file per module
│   │
│   ├── frontend/
│   │   ├── index.html            # Login + live Hub overview (shared)
│   │   ├── student/              # Student screens
│   │   ├── operator/             # Operator screens
│   │   └── assets/               # css / js / img
│   │
│   └── shared/
│       └── api-client.js         # Shared frontend ↔ backend client
│
├── docs/
│   ├── shared-contract.md        # Inter-module contract
│   └── todo/member{1..5}.md      # Personal task lists
│
└── scripts/
    ├── run_backend.sh / .bat
    ├── run_frontend.sh
    └── seed_data.py
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- A modern browser (the frontend is static HTML/CSS/JS served by the backend)

### 2. Set up
```bash
git clone <repo-url>
cd smart-e-mobility-hub
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the tests
```bash
python -m pytest                # expected: 10 passed, 32 skipped
```
Skipped tests are the members' TODOs. Remove `@SKIP` as each use case is implemented.

### 4. Start the app
```bash
uvicorn src.backend.app:app --reload --port 8000
# or: scripts/run_backend.sh   (Windows: scripts\run_backend.bat)
```

| What | URL |
|---|---|
| 🖥 Web UI | http://localhost:8000/app/ |
| 📖 API docs (Swagger) | http://localhost:8000/docs |
| ❤️ Health check | http://localhost:8000/api/health |

### 5. Demo accounts

| Role | Email | user_id |
|---|---|---|
| Student (shared vehicles) | `an@hcmut.edu.vn` | `U-S01` |
| Student (owns private EV `PV-001`) | `binh@hcmut.edu.vn` | `U-S02` |
| Operator | `operator@hub.vn` | `U-OP1` |

Log in from the web UI, or send the header `Authorization: Bearer <user_id>`:
```bash
curl -H "Authorization: Bearer U-OP1" http://localhost:8000/api/operator/dashboard
```

> Endpoints that are not implemented yet return **HTTP 501** with the owner and
> use case, e.g. `{"owner": "Member 3", "use_case": "UC01"}`.

---

## 🔌 API Overview

| Prefix | Module | Audience |
|---|---|---|
| `/api/auth`, `/api/hubs`, `/api/network` | Shared | everyone |
| `/api/reservation` | Reservation & Trip (Member 1) | students |
| `/api/charging` | Charging & Scheduling (Member 2) | students, operators, sensors (`/telemetry`) |
| `/api/operator` | Operations & Monitoring (Member 3) | operators |
| `/api/simulation` | What-if Simulation (Member 4) | operators |

Full, interactive reference: **`/docs`** while the server is running.

---

## ✅ What Is Already Working

- Every entity from the class diagram, status enums, `HubNetworkManager` (thread-safe state, atomic `move_vehicle`, isolated `snapshot()`), event bus, mock authentication with role checks.
- Demo network: 4 Hubs, 10 vehicles (including one private EV), 3 accounts.
- All four module routers are wired into the app, so each member only replaces `todo(...)` stubs with real logic.
- Frontend: login, role-based menu, live Hub overview, and 8 stub pages that show a clear "not implemented yet - owner" message.

---

## 🛣 Roadmap

- [x] Shared core, demo data, authentication, event bus
- [x] Module skeletons, API routes and test placeholders
- [ ] Reservation & Trip (U1-U9)
- [ ] Charging & Scheduling (UC-CH-01…10)
- [ ] Operations & Monitoring (UC01-UC-OP09)
- [ ] What-if Simulation (UC1-UC7)
- [ ] End-to-end integration & demo rehearsal
- [ ] Final report (requirements, design, demo screens)

---

## 🤝 Team Rules

1. Work only inside your own module (and your own HTML pages). To change `core/` or a function signature another member calls, tell the whole team first.
2. Shared state may only be changed inside `with network.lock:`.
3. When a use case is done, delete its `todo(...)` call, remove its `@SKIP` test marker, and keep `python -m pytest` green.
4. Work on `feature/*` branches and open a Pull Request into `main`; never push directly to `main`.

---

## 📄 License

Released under the [MIT License](LICENSE).
