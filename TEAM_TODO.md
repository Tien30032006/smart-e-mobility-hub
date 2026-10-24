# TEAM TODO – Smart E-Mobility Hub (Software Engineering Course Project)

Read this file first, then open **your personal TODO file** in `docs/todo/`.

| Member | Module (backend) | Use cases | Personal TODO |
|---|---|---|---|
| **Member 1** | `modules/reservation/` | U1–U9 (Student Discovery & Reservation) | [docs/todo/member1.md](docs/todo/member1.md) |
| **Member 2** | `modules/charging/` | UC-CH-01…10 (Charging & Scheduling) | [docs/todo/member2.md](docs/todo/member2.md) |
| **Member 3** | `modules/operations/` | UC01–UC-OP09 (Operator Management) | [docs/todo/member3.md](docs/todo/member3.md) |
| **Member 4** | `modules/simulation/` | UC1–UC7 (What-if Simulation) | [docs/todo/member4.md](docs/todo/member4.md) |
| **Member 5** | `core/`, `app.py`, `data/`, integration, shared docs | no dedicated module (Architecture & Integration) | [docs/todo/member5.md](docs/todo/member5.md) |

> This package ships with four use-case specification sets, so the four modules are assigned to Members 1–4. Member 5 owns the shared parts, architecture and integration, in the "Architecture & Integration Lead" role described in the main README. If your team splits the work differently, update this table and `docs/todo/member5.md`.

## 1. Shared parts already built (owned by Member 5; anyone who wants to change them must notify the whole team first)

| Component | File | Notes |
|---|---|---|
| `User` (abstract), `Student`, `Operator` classes | `core/entities.py` | Match the class diagram; `Student.find_vehicle/reserve_resource` and `Operator.handle_incident` delegate to each member's module |
| `MobilityHub`, `ParkingSpace`, `ChargingPoint`, `EVehicle`, `Reservation`, `ChargingSession`, `Event` | `core/entities.py` | Simple methods are implemented; business methods are `todo(...)` stubs that name their owner |
| Status enums + event types | `core/enums.py` | **Always use the enums, never raw strings** |
| `HubNetworkManager` (`network`) | `core/state_manager.py` | Single source of truth for state, `network.lock`, atomic `move_vehicle()`, `snapshot()` (deep copy for What-if) |
| `EventBus` (`bus`) | `core/event_bus.py` | Modules communicate through events (`bus.emit`, `bus.subscribe`) |
| Mock authentication + role checks | `core/auth.py` | `require_student`, `require_operator` |
| `AllocationService` | `core/allocation_service.py` | Delegation only: `allocate_vehicle/parking` → Member 1, `schedule_charging` → Member 2 |
| Demo data | `configs/hubs-data.json`, `data/seed_data.py` | 4 Hubs, 10 vehicles (1 private), 3 accounts |
| App + shared API | `app.py` | `/api/auth/login`, `/api/hubs`, `/api/network/status`; Swagger at `/docs` |
| Shared frontend | `index.html`, `assets/`, `shared/api-client.js` | Login, menu, and the 501 "not implemented – owner" display |
| Tests for shared parts | `tests/test_core.py` | Must always stay green |

Detailed contract (function names, event payloads, relocation-plan format…): [docs/shared-contract.md](docs/shared-contract.md).

## 2. Overlaps between use cases – who owns what

The member specs overlap in several places. These conventions avoid duplicated work:

| Topic | Logic OWNER | CALLER / consumer |
|---|---|---|
| Charging priority algorithm (priority score) | **Member 2** – `charging/scheduler.py` (UC-CH-09) | Member 3: UC-OP08 views/runs it, UC-OP09 overrides it |
| Reservation cancellation | **Member 1** – `reservation.service.cancel_reservation` (U4) | Member 3: UC-OP07 calls it with `by_system=True` |
| Issue reporting (student) | **Member 1** – U7 emits `ISSUE_REPORTED` | Member 3: UC05 listens to this event |
| Manual charging-point status change | **Member 2** – UC-CH-08 | Member 3: UC05 (charger failure) calls Member 2's function |
| Charging-point monitoring | **Member 2** – UC-CH-07 | Member 3: the UC01 dashboard re-displays the figures |
| Sensor data (battery, charging points) | **Member 2** – UC-CH-10 `telemetry.py` | Member 4: not used directly, reads `snapshot()` only |
| State snapshot | **Core** (`network.snapshot()`) | Member 4: UC4 |
| Vehicle relocation plan | **Member 3** – `plan` format in `redistribution.py` | Member 4: UC6 generates recommendations in the same format |
| Payment / smart lock (mock) | **Member 1** – U8, U9 | Member 1 uses them internally in U2/U5/U6 |

## 3. Team working rules

1. **Each member only edits their own module folder** (plus their own HTML pages). To change `core/` or a function signature that someone else calls, message the whole team and record it in the weekly meeting minutes.
2. Git branches: `main` (always runnable) + `feature/<name>-<usecase>` branches; open a Pull Request and have one other member review it.
3. Delete the `todo(...)` call once a function is done and **remove the `@SKIP`** on the matching test. Never merge while `pytest` is red.
4. Every "check availability → reserve" operation must happen inside `with network.lock:`.
5. Everyone must understand and be able to explain their own code during the demo.

## 4. Suggested roadmap (adjust to the deadlines on the LMS)

| Phase | Goal | Who |
|---|---|---|
| Week 1 | First meeting (communication, commitment, risks); everyone can run `run_backend.sh` and has read `shared-contract.md`; settle open questions | Whole team |
| Deadline #1 | Use-case details (specs exist), system-wide use-case diagram, shared NFRs | Team + individuals |
| Deadline #2 | Sequence + Activity diagram for each of your use cases, shared UI mockups (bonus: state-chart) | Individuals + team |
| Deadline #3 | Deployment view, Development view, Class diagram, method descriptions for your classes (bonus: test cases) | Team + individuals |
| In parallel with #2–#3 | Implement code in the priority order in your personal TODO (P0 → P1 → P2) | Individuals |
| Integration (≥ 1 week before demo) | Run the end-to-end demo script, fix integration bugs, rehearse the demo several times | Whole team |
| Final | One PDF file: #1 + #2 + #3 + the demo screen sequence | Whole team |

## 5. Suggested demo script (so everyone codes toward the same goal)

1. A student logs in → searches for a vehicle from the Metro station to the dormitory (Member 1, U1) → reserves a vehicle with a deposit (U2) → picks it up (U5) → returns it at a Hub that is full / not full (U6).
2. A student with a private EV submits a charging request (Member 2, CH-01) → the Operator runs the priority schedule (CH-09) and overrides one vehicle (Member 3, OP09).
3. A vehicle is reported broken (Member 1, U7) → the Operator handles the incident, creates a ticket and cancels the affected reservations (Member 3, UC05/OP06/OP07).
4. The dashboard shows the Metro Hub almost full (Member 3, UC01/UC02) → run the What-if scenario "students flood the Metro station at rush hour" (Member 4, UC1–UC5) → receive a recommendation (UC6) → apply it with a relocation order (Member 3, UC03/OP04).
