# Personal TODO – Member 5 (Architecture, Integration & Report Lead)

Member 5 has no dedicated use-case module; this role owns the **shared** parts so the 4 modules fit together and the submission stays consistent.
(If your team splits roles differently, hand the items below to the appropriate people.)

* Folders/files you own: `src/backend/core/`, `src/backend/app.py`, `src/backend/data/`, `configs/`, `src/shared/`, `src/frontend/index.html` + `src/frontend/assets/`, `scripts/`, `docs/`
* Read first: `TEAM_TODO.md`, `docs/shared-contract.md`, the team's class diagram

## A. Code & integration

### P0
- [ ] Make sure everyone can run `pytest` + `run_backend.sh` in week 1; fix environment problems (Python, venv, port 8000)
- [ ] Finalize `docs/shared-contract.md` with the 4 members (enums, events, cross-module function signatures, relocation `plan` format); every change to `core/` goes through you
- [ ] Review `core/entities.py` ↔ class diagram: class names, attributes and methods must match 1:1; update whichever side deviates
- [ ] Set up the git workflow: `main` always runnable, PR + review, branch naming rules

### P1
- [x] Wire Operations event handlers into `app.py` startup and run the shared simulator/charging telemetry integration
- [ ] Extend `configs/hubs-data.json` / `seed_data.py` as the demo requires (nearly full Hub, low-battery vehicles, broken charging point) – ask the 4 members what data they need
- [ ] End-to-end integration tests for the 4 scenarios in `TEAM_TODO.md` (add `tests/test_integration.py`)
- [ ] Concurrency checks: many requests reserving the same resource (combine the tests of Members 1 and 2)

### P2
- [ ] Shared UI: keep `shared/i18n.js` complete (EN + VI keys for every page), review members' pages against `docs/ui-guidelines.md` (contrast, 44px targets, dark mode, no hard-coded text)
- [x] Provide demo reset commands (`scripts/reset_demo.sh`, `POST /api/demo/reset`, and `scripts/seed_data.py --reset-db`)
- [ ] Review remaining cleanup candidates; module runtime stubs can be searched with `rg "todo\\(" src/backend/modules`

## B. Shared documents (you lead; the others give feedback)

| Item | Deadline | Status |
|---|---|---|
| Context, stakeholders, goals, scope description | #1 | ☐ |
| System-wide use-case diagram (merging the 4 specs) | #1 | ☐ |
| Shared non-functional requirements | #1 | ☐ |
| Shared UI mockups | #2 | ☐ |
| Architectural design + Deployment view + Development/Implementation view | #3 | ☐ |
| Integrated class diagram | #3 | ☐ |
| Consolidated test cases (bonus) | #3 | ☐ |
| Merge #1 + #2 + #3 + the demo screen sequence into **1 PDF file** | Final | ☐ |

In addition, like every other member, Member 5 must still submit **individual** documents as required by the course (confirm with the instructor which use cases make up Member 5's individual part, since all 4 specs already have owners).

## C. Team meetings & tracking
- [ ] Hold a weekly meeting with minutes (required by the course): the first meeting covers communication, commitment, shared risks and how to handle them
- [ ] Update the "overlaps" table in `TEAM_TODO.md` whenever a new agreement is made
- [ ] Organize an integration session ≥ 1 week before the demo, plus demo rehearsals
- [ ] End-of-term peer evaluation


## D. Pipeline-demo foundation (done in code - tick after the team reviews)
- [x] `core/auth.py` JWT (HS256), same `require_student/require_operator` signatures; `POST /api/auth/google`, `/api/auth/demo-login`, `GET/PATCH /api/me`
- [x] `login.html`, `onboarding.html`, `shared/api-client.js` (Bearer JWT, 401 -> login), `shared/stream.js` (SSE + polling fallback)
- [x] `core/simulator.py` (seeded, asyncio), telemetry-cut switches, `core/stream.py` + `GET /api/stream`
- [x] SQLite persistence (`core/database.py`, [docs/database.md](../database.md)), `POST /api/demo/reset`
- [x] Toast / modal / bottom-sheet / progress components, EN+VI keys `auth.*`, `live.*`
- [x] `.env.example`, `scripts/run_demo.sh`, `scripts/reset_demo.sh`, tests: `test_auth`, `test_persistence`, `test_stream_simulator`, `test_e2e_demo`, `tests_js/client.test.js`
- [ ] Confirm the Web OAuth client matches `GOOGLE_CLIENT_ID` in the local `.env` and allow `http://localhost:8000` plus the current HTTPS tunnel origin (cannot be configured in code)
- [x] Register persistent Operations stores in `core/demo.py`; simulation results remain in memory and are lost on restart
- [ ] Rehearse 3x with `scripts/reset_demo.sh`; test on a real phone through the tunnel
