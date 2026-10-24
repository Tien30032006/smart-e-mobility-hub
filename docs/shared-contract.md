# Shared Contract Between Modules

If you want to change anything below, notify the whole team and record it in the meeting minutes.

## 1. Class diagram → code

| Class diagram | Code | Who implements the business logic |
|---|---|---|
| `User` (abstract), `Student`, `Operator` | `core/entities.py` | shared (done) |
| `MobilityHub`, `ParkingSpace`, `ChargingPoint`, `EVehicle` | `core/entities.py` | shared (done) |
| `Reservation` | `core/entities.py` + `reservation/repository.py` | Member 1 |
| `ChargingSession` | `core/entities.py` (`schedule/complete/calculate_priority` = todo) | Member 2 |
| `Event` | `core/entities.py` | shared (done) |
| `HubNetworkManager` | `core/state_manager.py` (`redistribute_vehicles` = todo) | shared / Member 3 |
| `AllocationService` | `core/allocation_service.py` | Member 1 (vehicle, parking), Member 2 (charging) |
| `SimulationScenario`, `SimulationResult` | `modules/simulation/models.py` | Member 4 |

Naming convention: camelCase in the diagram → snake_case in Python (`getAvailableResources` → `get_available_resources`).
When submitting deliverable #3, describe methods **exactly as in the class diagram**; if the code deviates from the diagram, update the diagram.

## 2. Statuses (enums in `core/enums.py`)

* `VehicleStatus`: available, reserved, in_use, charging, maintenance, offline
* `ChargingPointStatus`: available, reserved, occupied, out_of_service
* `ReservationKind`: vehicle, parking, charging — `ReservationStatus`: pending, confirmed, active, completed, cancelled, expired
* `ChargingSessionStatus`: queued, scheduled, charging, completed, cancelled

Shared vehicle: `EVehicle.owner_id is None`. Private vehicle: `owner_id` = the student's `user_id`.

## 3. Events (`bus.emit(EventType.X, hub_id=..., **payload)`)

| Event | Emitted by | Consumed by | Required payload |
|---|---|---|---|
| `ISSUE_REPORTED` | Member 1 (U7) | Member 3 (UC05) | `issue_id, target_type ('vehicle'/'charging_point'/'parking_space'), target_id, category, description` |
| `RESERVATION_CANCELLED` | Member 1 (U4) | Member 3 (dashboard) | `reservation_id, reason, by_system` |
| `VEHICLE_PICKED_UP` / `VEHICLE_RETURNED` | Member 1 | Member 3, Member 2 | `vehicle_id, user_id` |
| `CHARGING_REQUESTED` / `CHARGING_SCHEDULED` | Member 2 | Member 3 | `session_id, vehicle_id` |
| `CHARGER_STATUS_CHANGED` | Member 2 (CH-08, CH-10) | Member 3 (UC02 alerts) | `point_id, old_status, new_status` |
| `BATTERY_UPDATED` | Member 2 (CH-10) | — | `vehicle_id, battery_level` |
| `HUB_NEAR_CAPACITY`, `ALERT_RAISED` | Member 3 (UC02) | — | `alert_id, message` |
| `INCIDENT_OPENED` | Member 3 (UC05) | — | `incident_id, target_id` |
| `RELOCATION_ORDER_CREATED` | Member 3 (UC-OP04) | — | `order_id` |
| `CHARGING_OVERRIDE` | Member 2 (when Member 3 calls override) | — | `session_id, operator_id, reason` |
| `SIMULATION_COMPLETED` | Member 4 | — | `result_id, impact_level` |

## 4. Cross-module functions (keep signatures unchanged)

| Function | Owner | Caller |
|---|---|---|
| `reservation.service.cancel_reservation(reservation_id, user_id=None, reason, by_system=False)` | Member 1 | Member 3 UC-OP07 |
| `charging.scheduler.run_prioritization(hub_id)` | Member 2 | Member 3 UC-OP08 |
| `charging.scheduler.get_queue(hub_id)` | Member 2 | Member 3 UC-OP08 |
| `charging.scheduler.apply_manual_override(hub_id, session_id, operator_id, reason)` | Member 2 | Member 3 UC-OP09 |
| `charging.point_monitor.update_point_status(point_id, status, operator_id, reason)` | Member 2 | Member 3 UC05 |
| `network.move_vehicle(vehicle_id, to_hub_id)` → bool | Core | Member 1 U6, Member 3 UC-OP04 |
| `network.snapshot()` → `NetworkSnapshot` (deep copy) | Core | Member 4 UC4 |

## 5. Vehicle relocation plan format (defined by Member 3, produced by Member 4 in UC6)

```json
{ "from_hub": "HUB-METRO", "to_hub": "HUB-KTX", "vehicle_ids": ["V-001", "V-003"], "reason": "Metro 92% full" }
```

## 6. API conventions

* Prefixes: `/api/reservation` (Member 1), `/api/charging` (Member 2), `/api/operator` (Member 3), `/api/simulation` (Member 4); shared APIs `/api/auth`, `/api/hubs`, `/api/network`.
* Login: `POST /api/auth/login {email}` → token = `user_id`; send `Authorization: Bearer <user_id>`.
* Business errors: `HTTPException(400/404/409, detail="…")` (409 = the resource was just taken by someone else). Not implemented yet: automatic HTTP 501.
* Timestamps: ISO-8601 UTC (`datetime.now(timezone.utc)`).

## 7. Demo accounts

| Email | Role | user_id |
|---|---|---|
| an@hcmut.edu.vn | Student, shared vehicles | U-S01 |
| binh@hcmut.edu.vn | Student, owns private EV `PV-001` | U-S02 |
| operator@hub.vn | Operator | U-OP1 |

## 8. Demo data (`configs/hubs-data.json`)

Hubs are deliberately small (Metro 12 spaces, Library 8 spaces…) so that full / overloaded situations are easy to create during the demo. To add data, edit this JSON file, not the module code.

## 9. Frontend conventions (bilingual UI + design system)

* The UI is bilingual (EN / VI). All visible text goes through `src/shared/i18n.js` (`data-i18n` / `Hub.t`); add new keys to both languages.
* Use the CSS tokens and components in `assets/css/style.css`; no raw colors, no emoji icons; support light + dark mode.
* Details and checklist: [`docs/ui-guidelines.md`](ui-guidelines.md).
