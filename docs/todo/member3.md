# Personal TODO – Member 3 (Operator Monitoring & Incident Lead)

* Your spec document: **Operator_Use_Case_Specification.docx**
* Code folder: `src/backend/modules/operations/`
* UI pages: `src/frontend/operator/dashboard.html`, `src/frontend/operator/incidents.html` and (shared with Member 2) `src/frontend/operator/charging.html`
* Your tests: `src/backend/tests/test_operations.py` (remove `@SKIP` as each use case is finished)
* Read first: `TEAM_TODO.md`, `docs/shared-contract.md`, `src/backend/core/entities.py`, `src/backend/core/state_manager.py`

The Operations backend and operator pages are implemented for the listed flows. Use the checklist below for course-spec and deliverable tracking; it may not reflect every code change. Search with `rg "todo\\(" src/backend/modules/operations/` to find any remaining runtime stubs.

## A. Code (work in order P0 → P1 → P2)

### P0 – do first; others depend on it / foundation

- [x] **UC01 dashboard** — `service.get_dashboard`, `get_hub_detail`
  - Start from `network.get_network_status()` (it already has per-Hub KPIs); add alerts, charging points, map markers.
- [x] **UC02 alerts** — `service.scan_for_alerts`, `list_alerts`, `acknowledge_alert`
  - Near-full Hub (`hub.is_near_capacity()`), mass low battery, disconnected charging points; de-duplicate; emit `ALERT_RAISED`/`HUB_NEAR_CAPACITY`.
- [x] **UC03 + UC-OP04 vehicle redistribution** — `redistribution.py`, `HubNetworkManager.redistribute_vehicles`
  - `propose_redistribution` → `create_relocation_order` → complete with `network.move_vehicle`. Define the **`plan` format** (Member 4 reuses it).

### P1 – main features for the demo

- [x] **UC05 + UC-OP06 incident handling** — `incident_handler.on_issue_reported`, `handle_incident`, `create_maintenance_ticket`
  - Listen to `ISSUE_REPORTED` (emitted by Member 1); vehicle → MAINTENANCE, charging point → OUT_OF_SERVICE (call Member 2's function if it is charging); create a ticket.
- [x] **UC-OP07 cancel reservations affected by an incident** — `cancel_affected_reservations`
  - Call Member 1's `reservation.service.cancel_reservation(by_system=True)` + suggest a replacement vehicle.
- [x] **UC-OP08 + OP09 charging oversight / override** — `charging_oversight.py`
  - **Do not rewrite the algorithm** – call Member 2's `scheduler`; keep an override log (who, why, when).

### P2 – polish

- [x] **`register_event_handlers`** — register `bus.subscribe` handlers at startup (called from `app.py` – notify the team when editing it)
- [x] **UI** — dashboard (table + utilization bars), incidents page, the charging-priority section of `operator/charging.html`
- [x] **Relocation order list** — `list_orders` + PENDING/ASSIGNED/DONE statuses

## B. Personal documents (course requirement: each member covers their own use cases)

| Use case | Sequence diagram (#2) | Activity diagram (#2) | UC detail (#1) |
|---|---|---|---|
| UC01 Monitor Network-wide Status | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC02 Manage System Alerts | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC03 Redistribute Vehicles | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-OP04 Create Relocation Order | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC05 Handle Device Incident | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-OP06 Create Maintenance Ticket | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-OP07 Cancel Reservation | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-OP08 Smart Charging Scheduling and Allocation | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC-OP09 Override Charging Priority | ☐ | ☐ | ☐ (already in the spec file – review it) |

- [ ] **Deadline #3 – Class & method description** for: `Operator` (monitorNetwork, handleIncident), `MobilityHub` (getAvailableResources, updateUtilization, isNearCapacity), `HubNetworkManager`, `Event` (describe *every* method in the class diagram for your classes; if the code deviates from the diagram, tell the team so the diagram gets fixed).
- [ ] (Bonus) State-chart diagram for objects with a lifecycle: vehicle, charging point, reservation, charging session, incident, simulation.
- [ ] (Bonus) Test cases: use the list in section D as a starting point.

## C. Dependencies on other members

- **Others need you:** Member 4: relocation recommendations must use the exact `plan` format.
- **You need others:** Member 1: `cancel_reservation`, the `ISSUE_REPORTED` event. Member 2: `run_prioritization`, `get_queue`, `apply_manual_override`, `update_point_status`.
- Changing a function signature / event payload recorded in `docs/shared-contract.md` → message the whole team first.

## D. Minimum tests required

- [x] Dashboard: total KPIs match `network.get_network_status()`
- [x] A Hub exceeding 85% raises exactly 1 alert (no duplicates)
- [x] Redistribution never picks a vehicle that is reserved / in use / under maintenance
- [x] Incident handling: vehicle → MAINTENANCE + related reservations cancelled

## E. Shared team work (you contribute too)

- [ ] System-wide use-case diagram (#1) · Context/stakeholder/scope description (#1) · Shared NFRs (#1)
- [ ] UI mockups (#2) – your screens: `operator/dashboard.html`, `operator/incidents.html` and (shared with Member 2) `operator/charging.html`
- [ ] Deployment view + Development view (#3)
- [ ] Demo slides + demo rehearsal – your part: Scenarios 3 and 4 in TEAM_TODO.md (incident handling; Metro Hub nearly full → apply redistribution).
- [ ] End-of-term peer evaluation

## F. Definition of Done for each use case

- [x] The `service` function handles the main flow **and** the exception flows from the spec
- [x] The endpoint returns the correct error codes (400/404/409) and no longer returns 501
- [x] At least 1 test for the main flow and 1 for an error flow; `pytest` is green
- [x] The UI page is usable (no more yellow TODO box)
- [ ] Sequence + activity diagrams match the real code
