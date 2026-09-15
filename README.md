# 🛴⚡ Smart E-Mobility Hub - Electric Mobility Coordination System for the VNU-HCM Urban Area

[![Status: Skeleton](https://img.shields.io/badge/status-skeleton%20%2F%20planning-lightgrey.svg)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Frontend HTML%2FCSS%2FJS](https://img.shields.io/badge/frontend-HTML%2FCSS%2FJS-orange.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Software Engineering Course Project - Talent Program, Computer Science**
> **Ho Chi Minh City University of Technology (HCMUT)**
>
> *Managing and coordinating a network of shared electric mobility resources
> (bicycles, motorcycles), parking capacity and charging infrastructure
> across the VNU-HCM Urban Area.*

---

## 🌍 Overview

The VNU-HCM Urban Area brings together multiple universities, dormitories,
libraries, service facilities and public transportation hubs. As Metro
Line 1 opens up new travel patterns, students will increasingly combine a
Metro ride with shared electric bicycles or motorcycles to move between
campuses and functional areas - turning last-mile mobility into a
distributed, multi-actor software problem, not just a hardware one.

**Smart E-Mobility Hub** is a system for managing and coordinating a
network of **Mobility Hubs** (Metro station, dormitories, campuses,
service areas), each containing parking spaces, charging points and
electric vehicles, with near-real-time state updates from either sensor
data or simulated data.

The project's core software-engineering focus is on:

- **State management** for vehicles, parking slots and charging points
  across many concurrently active Hubs.
- **Resource allocation & reservation handling** for shared, limited
  resources (parking, charging), avoiding double-booking.
- **Smart charging scheduling**, prioritizing vehicles by battery level
  and expected usage.
- **Operational monitoring & incident handling** for operators
  (overload detection, vehicle redistribution, vehicle/charger failures).
- **What-if Simulation**, evaluating hypothetical operating scenarios
  against a read-only state snapshot, without touching live data.

> This repository intentionally does **not** focus on IoT hardware or 3D
> map interfaces - data may be hard-coded or simulated, and no real
> database is required for the MVP.

---

## 🏗 System Architecture

```text
┌──────────────────────────────┐     ┌──────────────────────────────┐
│         Student UI           │     │         Operator UI          │
│   (src/frontend/student/)    │     │   (src/frontend/operator/)   │
└──────────────┬───────────────┘     └──────────────┬───────────────┘
               │                                    │
               └──────────────────┬─────────────────┘
                                  │  shared/api-client.js
                                  ▼
               ┌────────────────────────────────────┐
               │       Business Module Layer        │
               │      (src/backend/modules/)        │
               │                                    │
               │ • Reservation & Trip     (Member 1)│
               │ • Charging & Scheduling  (Member 2)│
               │ • Operations & Monitoring(Member 3)│
               │ • What-if Simulation     (Member 4)│
               └──────────────────┬─────────────────┘
                                  ▼
               ┌────────────────────────────────────┐
               │    Shared Data / State Layer       │
               │       (src/backend/core/)          │
               │  Hub · Vehicle · ParkingSlot ·     │
               │  ChargingPoint · Reservation       │
               └──────────────────┬─────────────────┘
                                  │ read-only snapshot()
                                  ▼
               ┌────────────────────────────────────┐
               │        Simulation Engine           │
               │  Isolated - evaluates What-if      │
               │  scenarios without mutating        │
               │  live operational state            │
               └────────────────────────────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) for the full design
(to be completed for Submission #3).

---

## 👥 Actors & Core Capabilities

| Actor | Capabilities |
|---|---|
| **Student** (shared or privately-owned vehicle) | Find a suitable Hub/vehicle for a trip · view vehicle availability & battery level · reserve a vehicle or parking space · pick up / return a vehicle · submit charging requests · schedule charging sessions in advance |
| **Operator** | Monitor the entire Hub network · detect Hubs approaching capacity · coordinate vehicle redistribution across Hubs · handle incidents (vehicle failures, charging-point outages) · run What-if scenarios and act on recommendations |
| **System** (scheduler / simulator / data source) | Drive near-real-time state updates from sensor or simulated data · run the smart charging-priority algorithm · execute What-if simulations |

---

## 🧩 Business Modules & Team Roles

Each team member owns one module end-to-end - requirement specification
through detailed design - while also contributing to shared group
deliverables (use-case diagram, non-functional requirements, class
diagram integration).

| # | Module | Responsible role | Scope |
|---|---|---|---|
| Member 1 | **Reservation & Trip** | Student Discovery & Reservation Lead | Find Hub/vehicle, view availability, reserve vehicle/parking, pick-up & return |
| Member 2 | **Charging & Scheduling** | Charging & Scheduling Lead | Charging requests, session scheduling, smart charging-priority algorithm |
| Member 3 | **Operations & Monitoring** | Operator Monitoring & Incident Lead | Network dashboard, overload detection, redistribution, incident handling |
| Member 4 | **What-if Simulation** | Simulation Lead | Scenario setup, state-evolution simulation, impact evaluation, recommendations |
| Member 5 | **Architecture & Integration** | Architecture, Integration & Report Lead | Overall architecture, shared data model, class diagram integration, deployment/development views, final report & demo |

> Replace the placeholder role names above with actual team member names
> once the team roster is finalized.

---

## 📂 Repository Structure

```text
smart-e-mobility-hub/
│
├── README.md
├── .gitignore
├── LICENSE
├── requirements.txt
│
├── configs/
│   ├── hubs-data.json              # Seed data: hubs, parking, charging points, vehicles
│   ├── simulation-scenarios.json   # Predefined What-if scenarios
│   └── app.config.json             # General app configuration
│
├── src/
│   ├── backend/
│   │   ├── app.py                  # Application entry point
│   │   │
│   │   ├── core/                   # Shared entities & infrastructure
│   │   │   ├── entities.py
│   │   │   ├── state_manager.py
│   │   │   ├── event_bus.py
│   │   │   └── logger.py
│   │   │
│   │   ├── modules/
│   │   │   ├── reservation/        # Member 1
│   │   │   ├── charging/           # Member 2
│   │   │   ├── operations/         # Member 3
│   │   │   └── simulation/         # Member 4
│   │   │
│   │   ├── data/                   # Seed/mock data loading
│   │   └── tests/                  # Unit tests per module
│   │
│   ├── frontend/
│   │   ├── index.html
│   │   ├── student/                # Student-facing screens
│   │   ├── operator/               # Operator-facing screens
│   │   └── assets/                 # css / js / img
│   │
│   └── shared/
│       └── api-client.js           # Shared frontend↔backend client
│
├── docs/
│   ├── architecture.md
│   ├── api-reference.md
│   └── setup.md
│
└── scripts/
    ├── run_backend.sh
    ├── run_frontend.sh
    └── seed_data.py
```

> **Status:** this repository is currently a **structural skeleton** -
> file and module responsibilities are documented via docstrings/comments,
> with no business logic implemented yet. See the roadmap below for what
> comes next.

---

## 🚀 Quick Start (once implemented)

### 1. Prerequisites
- Python 3.10+
- A modern browser (the MVP frontend is static HTML/CSS/JS)

### 2. Clone & set up
```bash
git clone <repo-url>
cd smart-e-mobility-hub
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Seed data & run
```bash
python scripts/seed_data.py
bash scripts/run_backend.sh
bash scripts/run_frontend.sh
```

Full setup notes: [`docs/setup.md`](docs/setup.md).

---

## ⚙️ Configuration

| File | Purpose |
|---|---|
| `configs/hubs-data.json` | Hub locations, parking slots, charging points, vehicle seed data |
| `configs/simulation-scenarios.json` | Predefined What-if scenarios (peak arrival, Hub full, charging surge, charger failure, vehicle concentration) |
| `configs/app.config.json` | Update interval, module toggles, logging configuration |

---

## 🧪 Non-Functional Requirements

- **Performance** - Hub/vehicle state is refreshed at near-real-time
  intervals (simulated via polling or an event-driven update loop).
- **Data consistency** - the shared Data/State layer prevents two
  students from reserving the same parking slot, charging point or
  vehicle at the same time.
- **Scalability** - new Hubs and vehicle types can be added without
  changing the core architecture.
- **Observability** - sufficient event logging for operators to trace
  incidents after the fact.

---

## 🔍 What-if Simulation

Operators can evaluate hypothetical scenarios - a sudden surge of
arrivals at the Metro Hub, a Hub reaching full parking capacity, a spike
in charging demand, partial charging-point failures, or excessive
vehicle concentration at one location - **before** applying any changes
to the live system. The Simulation Engine reads an immutable snapshot of
current state, projects how the network might evolve, evaluates impact
on service capacity, and proposes coordination actions such as vehicle
redistribution, charging-schedule adjustments, or redirecting users to
alternative Hubs. See [`configs/simulation-scenarios.json`](configs/simulation-scenarios.json)
for the scenario catalog.

---

## 📄 Course Deliverables Mapping

| Submission | Contents | Work type |
|---|---|---|
| **#1 - Requirement document** | Project/stakeholder specification · Use-case diagram (whole system) · Use-case detail for own module · Non-functional requirements | Group + Individual |
| **#2 - Requirement document** | UI mockups · Sequence diagrams · Activity diagrams · State-chart diagrams *(bonus)* | Group + Individual |
| **#3 - Design document** | Deployment view · Development/Implementation view · Class diagram + method descriptions · Test cases *(bonus)* | Group + Individual |
| **#final - Final document** | All of #1–#3 · Working demo (sequence of screens) · Generative AI usage disclosure | Group |

---

## 🤖 Generative AI Usage Disclosure

> **To be completed in the final submission**, per course requirements:
> clearly state which AI tools were used, for what scope (ideation,
> reference, code/document drafting, etc.), and the level of human
> analysis, refinement and original contribution applied on top. Any
> undisclosed or misrepresented AI usage is treated as academic
> misconduct by the course policy.

Suggested AI-assisted design tools referenced in course materials:
[Figma Make](https://www.figma.com/make/), [v0 by Vercel](https://v0.app/),
[Lovable](https://lovable.dev/) - for UI mockups (Submission #2).

---

## 📚 Reference Material

- [Use Case Diagram Tutorial (visual-paradigm)](https://www.visual-paradigm.com/guide/uml-unified-modeling-language/uml-use-case-diagram-tutorial/)
- [Free UML / Diagram Tutorials](https://www.visual-paradigm.com/tutorials/)

---

## 📄 License

This project is released under the **MIT License** - see [`LICENSE`](LICENSE).

---

<p align="center">
  🛴⚡ <b>Smart E-Mobility Hub</b><br>
  <i>Coordinating shared electric mobility across the VNU-HCM Urban Area</i>
</p>