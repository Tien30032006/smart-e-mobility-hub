# Personal TODO – Member 4 (What-if Simulation Lead)

* Your spec document: **what_if_template.docx**
* Code folder: `src/backend/modules/simulation/`
* UI pages: `operator/what-if.html`
* Your tests: `src/backend/tests/test_simulation.py` (remove `@SKIP` as each use case is finished)
* Read first: `TEAM_TODO.md`, `docs/shared-contract.md`, `core/entities.py`, `core/state_manager.py`

Every place that needs work already has a stub function that calls `todo(...)` with a docstring of guidance – find them with `grep -rn "todo(" src/backend/modules/simulation/`. Calling an unfinished endpoint returns HTTP 501 with your name.

## A. Code (work in order P0 → P1 → P2)

### P0 – do first; others depend on it / foundation

- [ ] **UC4 + UC3 run a simulation** — `engine.fetch_snapshot`, `engine.run`
  - Run on `network.snapshot()` (deep copy) in time steps (e.g. 5 minutes), **never touching the live state**. Support a `seed` so demos are repeatable.
- [ ] **UC1 configure a scenario** — `scenarios.create_scenario`, `SimulationScenario.configure`
  - Validate: the Hub exists, factors are valid, failed points ≤ the Hub's number of points. 5 types: demand_surge (Metro rush hour), hub_full, charging surge, charging_fault, vehicle_concentration.
- [ ] **UC5 impact evaluation** — `engine.evaluate_impact`
  - Per Hub: demand served / unserved, peak utilization, charging queue length, time to full; classify `impact_level`.

### P1 – main features for the demo

- [ ] **UC6 recommendations** — `recommender.generate`
  - 3 kinds: vehicle relocation (exact `plan` format from Member 3), charging reschedule, redirecting users to another Hub.
- [ ] **UC2 scenario templates** — `scenarios.list_templates`, `create_from_template`
  - Read `configs/simulation-scenarios.json` (4 templates already there; add `vehicle_concentration`).
- [ ] **API + UI** — `routes.py` is already scaffolded; build the `operator/what-if.html` page
  - Parameter form, per-Hub impact table, recommendation list.

### P2 – polish

- [ ] **UC7 export report** — `report.export_report`
  - Pick ONE format first (xlsx or pdf); add the library to `requirements.txt`.
- [ ] **`compare_with_current`** — compare the final state with the initial snapshot
- [ ] **Time-series chart** — on the What-if page

## B. Personal documents (course requirement: each member covers their own use cases)

| Use case | Sequence diagram (#2) | Activity diagram (#2) | UC detail (#1) |
|---|---|---|---|
| UC1 Configure Simulation Scenario | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC2 Load Scenario Template | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC3 Run Scenario Simulation | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC4 Fetch Operational State Snapshot | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC5 Evaluate Service Impact & Overload Risk | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC6 Generate Rebalancing Recommendations | ☐ | ☐ | ☐ (already in the spec file – review it) |
| UC7 Export Simulation Report | ☐ | ☐ | ☐ (already in the spec file – review it) |

- [ ] **Deadline #3 – Class & method description** for: `SimulationScenario`, `SimulationResult` (describe *every* method in the class diagram for your classes; if the code deviates from the diagram, tell the team so the diagram gets fixed).
- [ ] (Bonus) State-chart diagram for objects with a lifecycle: vehicle, charging point, reservation, charging session, incident, simulation.
- [ ] (Bonus) Test cases: use the list in section D as a starting point.

## C. Dependencies on other members

- **Others need you:** Nobody calls your code directly; Member 3 consumes your recommendations through the UI.
- **You need others:** `network.snapshot()` (core). The relocation `plan` format from Member 3 (`redistribution.py`). Member 2's charging-priority logic is only a reference when simulating queues (you may use your own simplified formula, documented in the report).
- Changing a function signature / event payload recorded in `docs/shared-contract.md` → message the whole team first.

## D. Minimum tests required

- [ ] **After a simulation finishes, the live state is unchanged** (compare before/after)
- [ ] Invalid parameters are rejected
- [ ] Same seed → same result
- [ ] A surge at Metro raises an overload-risk alert; recommendations use the exact `plan` format

## E. Shared team work (you contribute too)

- [ ] System-wide use-case diagram (#1) · Context/stakeholder/scope description (#1) · Shared NFRs (#1)
- [ ] UI mockups (#2) – your screens: `operator/what-if.html`
- [ ] Deployment view + Development view (#3)
- [ ] Demo slides + demo rehearsal – your part: Scenario 4 in TEAM_TODO.md (What-if Metro rush hour → recommendation).
- [ ] End-of-term peer evaluation

## F. Definition of Done for each use case

- [ ] The `service` function handles the main flow **and** the exception flows from the spec
- [ ] The endpoint returns the correct error codes (400/404/409) and no longer returns 501
- [ ] At least 1 test for the main flow and 1 for an error flow; `pytest` is green
- [ ] The UI page is usable (no more yellow TODO box)
- [ ] Sequence + activity diagrams match the real code
