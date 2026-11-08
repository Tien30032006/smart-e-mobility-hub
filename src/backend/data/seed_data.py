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


def sync_seed_catalog(target: HubNetworkManager = default_network) -> HubNetworkManager:
    """Add newly configured demo hubs/resources while preserving the live saved state."""
    data = load_json("hubs-data.json")
    with target.lock:
        for item in data["hubs"]:
            hub = target.hubs.get(item["id"])
            if hub is None:
                hub = MobilityHub(hub_id=item["id"], name=item["name"],
                                  location=item["location"], capacity=item["capacity"])
                target.register_hub(hub)
            else:
                hub.name = item["name"]
                hub.location = item["location"]
                hub.capacity = item["capacity"]
            for i in range(1, item["capacity"] + 1):
                sid = f"{item['id']}-P{i:02d}"
                if sid not in hub.parking_spaces:
                    hub.parking_spaces[sid] = ParkingSpace(
                        space_id=sid, hub_id=hub.hub_id,
                        zone="A" if i <= item["capacity"] // 2 else "B")
            for i in range(1, item["charging_points"] + 1):
                pid = f"{item['id']}-C{i:02d}"
                if pid not in hub.charging_points:
                    hub.charging_points[pid] = ChargingPoint(
                        point_id=pid, hub_id=hub.hub_id,
                        power_rating=item.get("charging_power_kw", 3.3))
        for item in data["vehicles"]:
            if item["id"] not in target.vehicles:
                target.register_vehicle(EVehicle(
                    vehicle_id=item["id"], model=item.get("model", ""),
                    vehicle_type=item["type"], battery_level=item["battery"],
                    status=VehicleStatus(item["status"]), hub_id=item["hub_id"],
                    owner_id=item.get("owner_id")))
        for item in data["users"]:
            if item["id"] in target.users:
                continue
            if item["role"] == "student":
                user = Student(user_id=item["id"], full_name=item["full_name"],
                               email=item["email"], student_code=item.get("student_code", ""),
                               has_private_ev=item.get("has_private_ev", False))
            else:
                user = Operator(user_id=item["id"], full_name=item["full_name"],
                                email=item["email"], operator_id=item.get("operator_id", ""))
            user._db = {"onboarded": True, "created_at": None}
            target.register_user(user)
    return target
