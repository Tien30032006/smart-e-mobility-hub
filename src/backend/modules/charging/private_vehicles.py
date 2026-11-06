"""TV2 onboarding boundary. Ownership comes only from the authenticated student."""
from dataclasses import asdict

from fastapi import HTTPException

from ...core.entities import EVehicle, Student, new_id
from .domain import percentage
from .repository import repository


def register_vehicle(user_id, model, vehicle_type, battery_level=20, hub_id=None):
    with repository.network.lock:
        user = repository.network.users.get(user_id)
        if not isinstance(user, Student):
            raise HTTPException(403, "Student only")
        model = model.strip()
        if not model or len(model) > 80:
            raise HTTPException(400, "Vehicle model must contain 1 to 80 characters")
        if vehicle_type not in {"e-bike", "e-motorcycle", "e-scooter"}:
            raise HTTPException(400, "Unknown electric vehicle type")
        percentage(battery_level)
        if hub_id:
            hub = repository.network.get_hub(hub_id)
            if not hub.get_available_resources():
                raise HTTPException(409, "Hub parking is full; select another hub")
        repository.store  # Do not turn a user-entered estimate into accepted telemetry.
        vehicle = EVehicle(new_id("PV"), model=model, vehicle_type=vehicle_type,
                           battery_level=battery_level, hub_id=hub_id, owner_id=user_id)
        repository.network.register_vehicle(vehicle)
        user.has_private_ev = True
        result = {**asdict(vehicle), **repository.freshness("vehicle", vehicle.vehicle_id)}
    return result
