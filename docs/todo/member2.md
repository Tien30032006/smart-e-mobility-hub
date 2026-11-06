# Personal TODO – Member 2 (Charging & Scheduling Lead)

* Your spec document: **Charging__Scheduling.docx**
* Code folder: `src/backend/modules/charging/`
* UI pages: `student/charging-request.html`, `charging-vehicles.html`, `charging-schedule.html`, `charging-status.html` and (shared with Member 3) `operator/charging.html`
* Your tests: `src/backend/tests/test_charging.py` (remove `@SKIP` as each use case is finished)
* Read first: `TEAM_TODO.md`, `docs/shared-contract.md`, `core/entities.py`, `core/state_manager.py`

The Member 2 code stubs have been implemented. The code/test checklist below is updated;
personal diagrams, reports and group deliverables remain tracked separately. Verification:
`python -m pytest -q` reports **26 passed, 24 skipped** (16 selected TV2 cases; extended 75-case regression suite runs separately) (the remaining skips belong to other modules).

Implementation notes, API workflow, SOLID rationale and demo assumptions: [charging-implementation.md](../charging-implementation.md).

## A. Code (work in order P0 → P1 → P2)

### P0 – do first; others depend on it / foundation

- [x] **UC-CH-09 priority algorithm** — `scheduler.calculate_priority` (pure function), `run_prioritization`, `get_queue`
  - Suggested formula is in the docstring; low-battery / soon-needed vehicles are charged first; never assign a broken or reserved point. **Members 3 and 4 depend on this** – do it first.
- [x] **UC-CH-01 submit charging request** — `service.submit_charging_request`
  - Private EVs only; create a QUEUED session; emit `CHARGING_REQUESTED`.
- [x] **UC-CH-10 sensor data** — `telemetry.ingest_readings`, `start_simulator`
  - Near-real-time battery / charging-point updates → makes the demo feel "live" for the whole team.

### P1 – main features for the demo

- [x] **UC-CH-02 + 03 schedule + select point** — `schedule_charging_session`, `list_available_points`
  - Prevent overlapping time slots on the same point (inside `network.lock`); create `Reservation(kind=CHARGING)`.
- [x] **UC-CH-05 cancel** — `cancel_charging_reservation`
  - Release the point/time slot and move the queue forward.
- [x] **UC-CH-07 + 08 monitor / change point status** — `point_monitor.py`
  - A point set to OUT_OF_SERVICE while charging → return the session to the queue. Emit `CHARGER_STATUS_CHANGED`.
- [x] **UC-CH-06 view charging status** — `get_my_charging_status`
  - Queue position, assigned point, current battery, ETA = (100 − battery) / power.

### P2 – polish

- [x] **UC-CH-04 smart suggestion** — `get_smart_suggestion`
  - Score (Hub, point, time slot) by battery + the time the vehicle is needed + expected availability.
- [x] **`apply_manual_override`** — the function Member 3 calls for UC-OP09
  - Do it after P0 but before integration; emit `CHARGING_OVERRIDE`.
- [x] **UI** — the student page + the charging-point controls on `operator/charging.html` (shared with Member 3)

## B. Personal documents (course requirement: each member covers their own use cases)

| Use case | Sequence diagram (#2) | Activity diagram (#2) | UC detail (#1) |
|---|---|---|---|
| UC-CH-01 Submit Charging Request | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-CH-02 Schedule Charging Session | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-CH-03 Select Charging Point | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-CH-04 Get Smart Charging Suggestion | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-CH-05 Cancel Charging Reservation | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-CH-06 View My Charging Status | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-CH-07 Monitor Charging Point Status | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-CH-08 Update Charging Point Status | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-CH-09 Run Smart Charging Prioritization | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-CH-10 Report Real-time Charging & Battery Data | ☐ | ☐ | ☐ (already in the spec file – review it) |

- [ ] **Deadline #3 – Class & method description** for: `ChargingPoint`, `ChargingSession`, `EVehicle` (getBatteryLevel, updateStatus, assignToHub) (describe *every* method in the class diagram for your classes; if the code deviates from the diagram, tell the team so the diagram gets fixed).
- [ ] (Bonus) State-chart diagram for objects with a lifecycle: vehicle, charging point, reservation, charging session, incident, simulation.
- [ ] (Bonus) Test cases: use the list in section D as a starting point.

## C. Dependencies on other members

- **Others need you:** Member 3 calls `run_prioritization`, `get_queue`, `apply_manual_override`, `update_point_status`. Member 4 only reads the snapshot.
- **You need others:** Member 1: no direct calls (you share the `network.reservations` store, so filter by `kind`).
- Changing a function signature / event payload recorded in `docs/shared-contract.md` → message the whole team first.

## D. Minimum tests required

- [x] A low battery gets a higher priority score than a high battery (same time-needed)
- [x] An OUT_OF_SERVICE point is never assigned
- [x] Two bookings overlapping on the same point → rejected
- [x] Telemetry with a battery value outside 0–100 is rejected

## E. Shared team work (you contribute too)

- [ ] System-wide use-case diagram (#1) · Context/stakeholder/scope description (#1) · Shared NFRs (#1)
- [ ] UI mockups (#2) – your screens: `student/charging-request.html` and (shared with Member 3) `operator/charging.html`
- [ ] Deployment view + Development view (#3)
- [ ] Demo slides + demo rehearsal – your part: Scenario 2 in TEAM_TODO.md (charging request → run priority schedule → override).
- [ ] End-of-term peer evaluation

## F. Definition of Done for each use case

- [ ] The `service` function handles the main flow **and** the exception flows from the spec
- [ ] The endpoint returns the correct error codes (400/404/409) and no longer returns 501
- [ ] At least 1 test for the main flow and 1 for an error flow; `pytest` is green
- [ ] The UI page is usable (no more yellow TODO box)
- [ ] Sequence + activity diagrams match the real code


## TV2 pipeline demo update

- [x] GET/POST `/api/me/vehicles`; ownership from authenticated student.
- [x] Mobile request wizard, availability and nearby Hub information.
- [x] Slot grid, smart suggestions, collision alternatives and cancellation.
- [x] Charging progress, needed-by edit and live priority read model.
- [x] Event-bus adapter for TV5 simulator; Data Update Log with reception-time freshness.
- [x] SSE consumer with polling fallback; shared SSE server and Google/JWT remain TV5 tasks.
- [x] Four test categories, 16 cases; Word Test Plan plus 16 testcase tables.

Integration contracts and limitations: [charging-tv2-integration.md](../charging-tv2-integration.md).
