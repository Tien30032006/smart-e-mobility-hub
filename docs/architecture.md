# 🏗 System Architecture

Detailed architecture of the **Smart E-Mobility Hub** system.

---

## 1. Layered Overview

The system follows a **4-layer architecture**:

```text
┌─────────────────────────────────────────┐
│  Layer 1 - Presentation                 │
│  src/frontend/                          │
│  Student UI  ·  Operator UI             │
└──────────────────┬──────────────────────┘
                   │ HTTP / JSON
                   ▼
┌─────────────────────────────────────────┐
│  Layer 2 - Business Modules             │
│  src/backend/modules/                   │
│  • Reservation & Trip        (Member 1) │
│  • Charging & Scheduling     (Member 2) │
│  • Operations & Monitoring   (Member 3) │
│  • What-if Simulation        (Member 4) │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Layer 3 - Shared Data / State          │
│  src/backend/core/                      │
│  Hub · Vehicle · ParkingSlot ·          │
│  ChargingPoint · Reservation            │
└──────────────────┬──────────────────────┘
                   │ read-only snapshot()
                   ▼
┌─────────────────────────────────────────┐
│  Layer 4 - Simulation Engine            │
│  src/backend/modules/simulation/        │
│  Isolated from live state               │
└─────────────────────────────────────────┘
```

---

## 2. Module Boundaries

### Member 1 - Reservation & Trip
- **Responsibilities:** Find Hub/vehicle, view availability, reserve vehicle/parking, pick-up & return.
- **Exposes:** `ReservationService`
- **Depends on:** `StateManager`, `entities`

### Member 2 - Charging & Scheduling
- **Responsibilities:** Charging requests, session scheduling, smart charging-priority algorithm.
- **Exposes:** `ChargingService`, `ChargingScheduler`
- **Depends on:** `StateManager`, `entities`

### Member 3 - Operations & Monitoring
- **Responsibilities:** Network dashboard, overload detection, redistribution, incident handling.
- **Exposes:** `OperationsService`
- **Depends on:** `StateManager`, `entities`

### Member 4 - What-if Simulation
- **Responsibilities:** Scenario setup, state-evolution, impact evaluation, recommendations.
- **Exposes:** `SimulationEngine`
- **Depends on:** `StateManager` (read-only snapshot)

### Member 5 - Architecture & Integration
- **Responsibilities:** Shared entities, centralized state, event bus, cross-module integration.
- **Exposes:** `StateManager`, `EventBus`, `entities`, `logger`

---

## 3. Data Flow

### Example: Student reserves a vehicle

```text
[Student UI]
    │ POST /api/reservation/vehicle
    ▼
[ReservationService]
    │ lock state
    │ check vehicle availability
    │ mark vehicle as IN_USE
    │ create Reservation
    │ unlock state
    ▼
[StateManager]
    │ persist in-memory
    ▼
[Response → Student UI]
```

### Example: Operator runs What-if scenario

```text
[Operator UI]
    │ POST /api/simulation/run
    ▼
[SimulationEngine]
    │ deep copy current state (snapshot)
    │ apply scenario changes on snapshot only
    │ compute impact
    │ generate recommendations
    ▼
[Response → Operator UI]
    (live state unchanged)
```

---

## 4. Non-Functional Concerns

| Concern | Approach |
|---|---|
| **Consistency** | `StateManager` uses a `threading.Lock` to prevent double-booking of parking slots, charging points, vehicles |
| **Performance** | Near-real-time updates via polling or interval-based loop (simulated) |
| **Scalability** | New Hubs / vehicle types can be added via JSON config without changing core |
| **Observability** | Event logging via `logger.py` for post-incident tracing |
| **Isolation** | Simulation Engine reads snapshot, never mutates live state |

---

## 5. Deployment View

```text
┌──────────────────────────┐
│  Browser (Client)        │
│  Student UI · Operator UI│
└────────────┬─────────────┘
             │ HTTP
             ▼
┌──────────────────────────┐
│  Backend (FastAPI)       │
│  localhost:8000          │
│  - modules/              │
│  - core/                 │
└────────────┬─────────────┘
             │ in-memory
             ▼
┌──────────────────────────┐
│  State (in-memory)       │
│  + JSON seed data        │
└──────────────────────────┘
```

> No real database required for the MVP - state is kept in memory and seeded from `configs/hubs-data.json`.

---

## 6. Development View

| Layer | Folder | Responsibility |
|---|---|---|
| Frontend | `src/frontend/` | UI for Student & Operator |
| Business | `src/backend/modules/` | 4 business modules (Member 1–4) |
| Core | `src/backend/core/` | Shared entities, state, event bus (Member 5) |
| Data | `src/backend/data/` | Seed / mock data loading |
| Tests | `src/backend/tests/` | Unit tests per module |

---

## 7. Related Documents

- [`api-reference.md`](api-reference.md) - REST API endpoints
- [`setup.md`](setup.md) - Local setup & run instructions