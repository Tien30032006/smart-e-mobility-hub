"""Build the demo network from configs/hubs-data.json. SHARED FILE.

Call ``seed_network()`` once at startup (app.py does it) or in tests
(``seed_network(fresh=True)`` resets state first).
Add demo rows by editing the JSON, not this file.
"""
from __future__ import annotations

from ..core.entities import (
    ChargingPoint, EVehicle, MobilityHub, Operator, ParkingSpace, Student,
)
from ..core.enums import VehicleStatus
from ..core.state_manager import HubNetworkManager, network as default_network
from .loader import load_json


def seed_network(target: HubNetworkManager = default_network, fresh: bool = True) -> HubNetworkManager:
    data = load_json("hubs-data.json")
    with target.lock:
        if fresh:
            target.reset()
        for h in data["hubs"]:
            hub = MobilityHub(hub_id=h["id"], name=h["name"], location=h["location"], capacity=h["capacity"])
            for i in range(1, h["capacity"] + 1):
                sid = f"{h['id']}-P{i:02d}"
                hub.parking_spaces[sid] = ParkingSpace(space_id=sid, hub_id=hub.hub_id,
                                                       zone="A" if i <= h["capacity"] // 2 else "B")
            for i in range(1, h["charging_points"] + 1):
                pid = f"{h['id']}-C{i:02d}"
                hub.charging_points[pid] = ChargingPoint(point_id=pid, hub_id=hub.hub_id,
                                                         power_rating=h.get("charging_power_kw", 3.3))
            target.register_hub(hub)
        for v in data["vehicles"]:
            target.register_vehicle(EVehicle(
                vehicle_id=v["id"], model=v.get("model", ""), vehicle_type=v["type"],
                battery_level=v["battery"], status=VehicleStatus(v["status"]),
                hub_id=v["hub_id"], owner_id=v.get("owner_id")))
        for u in data["users"]:
            if u["role"] == "student":
                target.register_user(Student(user_id=u["id"], full_name=u["full_name"], email=u["email"],
                                             student_code=u.get("student_code", ""),
                                             has_private_ev=u.get("has_private_ev", False)))
            else:
                target.register_user(Operator(user_id=u["id"], full_name=u["full_name"], email=u["email"],
                                              operator_id=u.get("operator_id", "")))
        for user in target.users.values():          # seeded accounts skip onboarding
            user._db = {"onboarded": True, "created_at": None}
    return target
