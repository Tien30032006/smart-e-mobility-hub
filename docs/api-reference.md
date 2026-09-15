# 🔌 API Reference

REST API for the **Smart E-Mobility Hub** MVP.

- **Base URL:** `http://localhost:8000`
- **Content-Type:** `application/json`
- **Auth:** none (MVP - no authentication required)

---

## 1. Reservation & Trip - Member 1

### `GET /api/reservation/vehicles`
List available vehicles.

**Query params:**
- `hub_id` *(optional)* - filter by Hub
- `type` *(optional)* - `e-bike` | `e-motorcycle`

**Response:**
```json
[
  { "id": "V-001", "type": "e-bike", "battery": 85, "status": "available", "hub_id": "HUB-METRO" }
]
```

---

### `GET /api/reservation/slots`
List available parking slots at a Hub.

**Query params:**
- `hub_id` *(required)*

**Response:**
```json
[
  { "id": "HUB-METRO-S0", "hub_id": "HUB-METRO", "is_occupied": false }
]
```

---

### `POST /api/reservation/vehicle`
Reserve a vehicle.

**Request body:**
```json
{ "user_id": "STU-001", "vehicle_id": "V-001", "hub_id": "HUB-METRO" }
```

**Response:**
```json
{
  "id": "RES-a1b2c3d4",
  "user_id": "STU-001",
  "vehicle_id": "V-001",
  "hub_id": "HUB-METRO",
  "status": "confirmed",
  "start_time": "2026-01-15T08:30:00Z"
}
```

**Errors:**
- `400` - vehicle not available
- `404` - vehicle not found

---

### `POST /api/reservation/parking`
Reserve a parking slot (for private vehicles).

**Request body:**
```json
{ "user_id": "STU-002", "hub_id": "HUB-KTX", "slot_id": "HUB-KTX-S5" }
```

---

### `POST /api/reservation/return`
Return a vehicle to a Hub.

**Request body:**
```json
{ "reservation_id": "RES-a1b2c3d4", "target_hub_id": "HUB-KTX" }
```

---

## 2. Charging & Scheduling - Member 2

### `POST /api/charging/request`
Submit a charging request.

**Request body:**
```json
{ "user_id": "STU-001", "vehicle_id": "V-002", "hub_id": "HUB-METRO" }
```

**Response:**
```json
{ "id": "CHG-x9y8z7", "priority": 60, "scheduled_at": "2026-01-15T09:00:00Z" }
```

---

### `POST /api/charging/schedule`
Run the smart scheduling algorithm on all pending requests.

**Response:**
```json
[
  { "id": "CHG-x9y8z7", "priority": 60, "scheduled_at": "2026-01-15T09:00:00Z" },
  { "id": "CHG-p1q2r3", "priority": 45, "scheduled_at": "2026-01-15T09:30:00Z" }
]
```

---

### `GET /api/charging/points`
List charging points status.

**Query params:**
- `hub_id` *(required)*

**Response:**
```json
[
  { "id": "HUB-METRO-C0", "status": "available", "power_kw": 3.5 },
  { "id": "HUB-METRO-C1", "status": "occupied", "power_kw": 3.5 }
]
```

---

## 3. Operations & Monitoring - Member 3

### `GET /api/operations/overview`
Network dashboard snapshot.

**Response:**
```json
{
  "hubs": [
    {
      "hub_id": "HUB-METRO",
      "name": "Ga Metro ĐHQG",
      "parking_usage": "35/50",
      "parking_utilization": 0.7,
      "charging_available": "6/10",
      "vehicles_count": 12
    }
  ]
}
```

---

### `GET /api/operations/alerts`
Overload alerts.

**Response:**
```json
[
  { "hub_id": "HUB-KTX", "type": "near_capacity", "usage": 0.92 }
]
```

---

### `POST /api/operations/redistribute`
Trigger vehicle redistribution between Hubs.

**Request body:**
```json
{ "from_hub": "HUB-METRO", "to_hub": "HUB-KTX", "count": 3 }
```

---

### `POST /api/operations/incident`
Report an incident.

**Request body:**
```json
{
  "type": "vehicle_fault",
  "target_id": "V-005",
  "hub_id": "HUB-KTX",
  "description": "Battery not charging"
}
```

---

### `POST /api/operations/incident/{id}/resolve`
Mark an incident as resolved.

---

## 4. What-if Simulation - Member 4

### `POST /api/simulation/run`
Run a What-if scenario.

**Request body:**
```json
{
  "name": "Rush hour at Metro",
  "type": "demand_surge",
  "hub_id": "HUB-METRO",
  "surge_factor": 2.0
}
```

**Response:**
```json
{
  "scenario": "Rush hour at Metro",
  "impacts": [
    {
      "hub_id": "HUB-METRO",
      "projected_demand": 24,
      "current_supply": 12,
      "shortage": 12
    }
  ],
  "recommendations": [
    "Điều chuyển thêm xe đến HUB-METRO"
  ]
}
```

---

### `GET /api/simulation/scenarios`
List predefined scenarios.

**Response:**
```json
[
  { "id": "peak_arrival", "name": "Peak arrival at Metro" },
  { "id": "hub_full", "name": "Hub reaches full capacity" },
  { "id": "charging_surge", "name": "Charging demand surge" }
]
```

---

## 5. System - Member 5

### `GET /`
Health check.

**Response:**
```json
{ "message": "Smart E-Mobility Hub API", "status": "running" }
```

---

## Error Format

All errors follow this format:

```json
{
  "detail": "Vehicle not available"
}
```

| Code | Meaning |
|---|---|
| `400` | Bad request (invalid input) |
| `404` | Resource not found |
| `409` | Conflict (e.g., resource already booked) |
| `500` | Internal server error |