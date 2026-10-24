# Personal TODO – Member 5 (Architecture, Integration & Report Lead)

Member 5 has no dedicated use-case module; this role owns the **shared** parts so the 4 modules fit together and the submission stays consistent.
(If your team splits roles differently, hand the items below to the appropriate people.)

* Folders/files you own: `src/backend/core/`, `src/backend/app.py`, `src/backend/data/`, `configs/`, `src/shared/`, `src/frontend/index.html` + `assets/`, `scripts/`, `docs/`
* Read first: `TEAM_TODO.md`, `docs/shared-contract.md`, the team's class diagram

## A. Code & integration

### P0
- [ ] Make sure everyone can run `pytest` + `run_backend.sh` in week 1; fix environment problems (Python, venv, port 8000)
- [ ] Finalize `docs/shared-contract.md` with the 4 members (enums, events, cross-module function signatures, relocation `plan` format); every change to `core/` goes through you
- [ ] Review `core/entities.py` ↔ class diagram: class names, attributes and methods must match 1:1; update whichever side deviates
- [ ] Set up the git workflow: `main` always runnable, PR + review, branch naming rules

### P1
- [ ] Wire Member 3's `register_event_handlers` into `app.py` startup and enable Member 2's simulator (`telemetry.start_simulator`) once those functions are done
- [ ] Extend `configs/hubs-data.json` / `seed_data.py` as the demo requires (nearly full Hub, low-battery vehicles, broken charging point) – ask the 4 members what data they need
- [ ] End-to-end integration tests for the 4 scenarios in `TEAM_TODO.md` (add `tests/test_integration.py`)
- [ ] Concurrency checks: many requests reserving the same resource (combine the tests of Members 1 and 2)

### P2
- [ ] Shared UI: menu, error / "not implemented yet" states, a consistent style across pages
- [ ] A script to quickly reset demo data before each rehearsal (`scripts/seed_data.py`)
- [ ] Cleanup: remove leftover `todo(...)` calls, outdated docstrings and unused files

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
