# 📚 Technical Documentation

Internal technical documentation for the **Smart E-Mobility Hub** source code repository.

> 📄 Course submissions, UML diagrams, UI mockups, and the final report are kept
> in a separate repository: [`smart-e-mobility-hub-docs`](https://github.com/<username>/smart-e-mobility-hub-docs).

---

## 📂 Contents

| File | Description |
|---|---|
| [`architecture.md`](architecture.md) | System architecture, layered design, module boundaries, data flow |
| [`api-reference.md`](api-reference.md) | REST API endpoints exposed by the backend |
| [`setup.md`](setup.md) | Local development setup, environment, and run instructions |

---

## 🧩 Module Ownership

| Member | Module | Directory |
|---|---|---|
| Member 1 | Reservation & Trip | [`src/backend/modules/reservation/`](../src/backend/modules/reservation/) |
| Member 2 | Charging & Scheduling | [`src/backend/modules/charging/`](../src/backend/modules/charging/) |
| Member 3 | Operations & Monitoring | [`src/backend/modules/operations/`](../src/backend/modules/operations/) |
| Member 4 | What-if Simulation | [`src/backend/modules/simulation/`](../src/backend/modules/simulation/) |
| Member 5 | Architecture & Integration | [`src/backend/core/`](../src/backend/core/) |

---

## 🚀 Quick Reference

### Run the backend
```bash
python -m src.backend.app
```

### Run the frontend
```bash
python -m http.server 5500 --directory src/frontend
# Then open http://localhost:5500
```

### Run tests
```bash
pytest src/backend/tests/
```

---

## 📄 License

MIT - see [`../LICENSE`](../LICENSE).