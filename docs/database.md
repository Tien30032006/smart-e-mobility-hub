# Database (SQLite) – owner: TV5

`network` (in-memory) stays the single source of truth, so every module keeps using plain Python objects and
`with network.lock:`. `core/database.py` **mirrors** that state into a SQLite file (`DATABASE_PATH`, default `data/hub.db`).

```
request ──> module code ──> network (memory) ──┐
                                               ├─ flush() ──> SQLite (one transaction, only changed rows)
 simulator / bus events ───────────────────────┘
startup:  SQLite --load()--> network      (empty DB => seed from configs/hubs-data.json)
```

**When is data written?** after every successful `POST/PUT/PATCH/DELETE /api/*`, every `PERSIST_INTERVAL_SECONDS`
(captures the simulator) and on shutdown. Unchanged rows are skipped (hash cache), so a flush is cheap.

## Tables
| Table | Rows | Notes |
|---|---|---|
| `users` | Student / Operator | `email` unique, `google_sub`, `phone`, `student_code`, `onboarded` |
| `hubs`, `parking_spaces`, `charging_points` | physical resources | FK `hub_id` |
| `vehicles` | shared + private EVs | `status`, `battery_level`, `hub_id`, `owner_id` |
| `reservations` | vehicle / parking / charging holds | extra attributes in JSON column `extra` |
| `charging_sessions` | TV2 sessions | same `extra` mechanism |
| `events` | append-only audit log of every bus event | `payload` JSON |
| `module_state` | `(namespace, key) -> JSON` for module-owned stores | wallets, top-up orders, ledger, trips, issues, lock states |

## Persisting your own module store (3 lines)
Keep your data in a module-level `dict` of JSON-serialisable values (ISO strings for dates) and register it in
`core/demo.py::register_persisted_stores`:
```python
persistence.register_store("operations.alerts", lambda: alerts._store)   # TV3 example
```
It is then saved on every flush, restored at startup and wiped by `POST /api/demo/reset` once you add your
`reset` helper to `core/demo.py::reset_module_state`. (Done already: wallet, ledger, trips, issues, locks.
**TODO for owners:** TV3 alerts / incidents / relocation orders, TV2 notifications / audit / override log, TV4 results.)

## Handy commands
```bash
python scripts/seed_data.py --reset-db     # delete the file, next start re-seeds
sqlite3 data/hub.db "select vehicle_id,status,battery_level,hub_id from vehicles"
curl -H "Authorization: Bearer <operator jwt>" localhost:8000/api/demo/database   # row counts + recent events
```
Tests use `DATABASE_PATH=:memory:` (persistence off) except `test_persistence.py` / `test_e2e_demo.py`, which use temp files.
