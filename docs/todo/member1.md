# Personal TODO – Member 1 (Student Discovery & Reservation Lead)

* Your spec document: **Student_Discovery__Reservation_Specification.docx**
* Code folder: `src/backend/modules/reservation/`
* UI pages: `student/find-hub.html`, `student/reserve-vehicle.html`, `student/my-trips.html`
* Your tests: `src/backend/tests/test_reservation.py` (remove `@SKIP` as each use case is finished)
* Read first: `TEAM_TODO.md`, `docs/shared-contract.md`, `core/entities.py`, `core/state_manager.py`

Every place that needs work already has a stub function that calls `todo(...)` with a docstring of guidance – find them with `grep -rn "todo(" src/backend/modules/reservation/`. Calling an unfinished endpoint returns HTTP 501 with your name.

## A. Code (work in order P0 → P1 → P2)

### P0 – do first; others depend on it / foundation

- [ ] **U1 search Hubs & vehicles** — `service.search_hubs_and_vehicles`, `get_vehicle_detail`
  - Filter by vehicle type / minimum battery; return battery %, number of free parking spaces; for a private vehicle only a Hub with free space is needed.
- [ ] **U2 reserve a vehicle** — `service.reserve_vehicle` + `core/allocation_service.allocate_vehicle`
  - Inside `network.lock`: pick an AVAILABLE vehicle → RESERVED, create `Reservation(kind=VEHICLE)`, hold for 15 minutes, take a deposit via U8. Two students reserving the same vehicle → the second gets 409.
- [ ] **U3 reserve a parking space** — `service.reserve_parking_slot` + `allocate_parking_space`
  - Set `ParkingSpace.reserved_by`; two modes: returning a rented vehicle (shared_return) and a private vehicle (private).
- [ ] **U8 payment (mock)** — `payment_gateway.py`
  - In-memory ledger, fake `transaction_id`, and the ability to decline a payment to demo the exception flow.

### P1 – main features for the demo

- [ ] **U4 cancel** — `service.cancel_reservation`
  - Release the vehicle/space, refund the deposit, emit `RESERVATION_CANCELLED`. **Member 3 calls this function (UC-OP07)**, so do it early.
- [ ] **U5 pick up vehicle + U9** — `pick_up_vehicle`, `smart_lock.unlock`
  - Check the QR / reservation is still valid → unlock → vehicle IN_USE → create a trip record. Support walk-up pickup without a reservation.
- [ ] **U6 return vehicle** — `return_vehicle`, `smart_lock.lock`
  - Use `network.move_vehicle`; if the Hub is full, suggest another Hub; compute the trip fee (U8).
- [ ] **U7 report issue** — `report_issue`
  - Store the issue and `bus.emit(ISSUE_REPORTED, payload exactly as in the contract)` – **Member 3 depends on this**.

### P2 – polish

- [ ] **Reservation expiry** — a job/function that scans `Reservation.is_expired()` → EXPIRED and releases the resource
- [ ] **Trip history** — `list_my_trips` + the `my-trips.html` page
- [ ] **UI** — the 3 student pages fully built, showing 409/400 errors clearly

## B. Personal documents (course requirement: each member covers their own use cases)

| Use case | Sequence diagram (#2) | Activity diagram (#2) | UC detail (#1) |
|---|---|---|---|
| U1 Search Hub and Vehicle detail | ☐ | ☐ | ☐ (already in the spec file – review it) |
| U2 Reserve Vehicle | ☐ | ☐ | ☐ (already in the spec file – review it) |
| U3 Reserve Parking Slot | ☐ | ☐ | ☐ (already in the spec file – review it) |
| U4 Cancel Reservation | ☐ | ☐ | ☐ (already in the spec file – review it) |
| U5 Pick Up Vehicle | ☐ | ☐ | ☐ (already in the spec file – review it) |
| U6 Return Vehicle | ☐ | ☐ | ☐ (already in the spec file – review it) |
| U7 Report Issue | ☐ | ☐ | ☐ (already in the spec file – review it) |
| U8 Process Payment (mock) | ☐ | ☐ | ☐ (already in the spec file – review it) |
| U9 Control Smart Lock (mock) | ☐ | ☐ | ☐ (already in the spec file – review it) |

- [ ] **Deadline #3 – Class & method description** for: `User`, `Student`, `ParkingSpace`, `Reservation`, `AllocationService` (allocateVehicle, allocateParkingSpace) (describe *every* method in the class diagram for your classes; if the code deviates from the diagram, tell the team so the diagram gets fixed).
- [ ] (Bonus) State-chart diagram for objects with a lifecycle: vehicle, charging point, reservation, charging session, incident, simulation.
- [ ] (Bonus) Test cases: use the list in section D as a starting point.

## C. Dependencies on other members

- **Others need you:** Member 2: no. Member 3: uses `cancel_reservation(by_system=True)` and listens to `ISSUE_REPORTED`.
- **You need others:** `network.move_vehicle`, `network.lock`, `bus` (core). You may need Member 2 for the "private vehicle parked + charging" scenario (only as a hint in the UI).
- Changing a function signature / event payload recorded in `docs/shared-contract.md` → message the whole team first.

## D. Minimum tests required

- [ ] Two students reserve the same vehicle → only one succeeds (use `threading` to simulate concurrency)
- [ ] Cancel → vehicle returns to AVAILABLE, deposit refunded
- [ ] Returning a vehicle to a full Hub is rejected
- [ ] `report_issue` emits the correct event

## E. Shared team work (you contribute too)

- [ ] System-wide use-case diagram (#1) · Context/stakeholder/scope description (#1) · Shared NFRs (#1)
- [ ] UI mockups (#2) – your screens: `student/find-hub.html`, `student/reserve-vehicle.html`, `student/my-trips.html`
- [ ] Deployment view + Development view (#3)
- [ ] Demo slides + demo rehearsal – your part: Scenarios 1 and 3 in TEAM_TODO.md (reserve → pick up → return; report a broken vehicle).
- [ ] End-of-term peer evaluation

## F. Definition of Done for each use case

- [ ] The `service` function handles the main flow **and** the exception flows from the spec
- [ ] The endpoint returns the correct error codes (400/404/409) and no longer returns 501
- [ ] At least 1 test for the main flow and 1 for an error flow; `pytest` is green
- [ ] The UI page is usable (no more yellow TODO box)
- [ ] Sequence + activity diagrams match the real code
