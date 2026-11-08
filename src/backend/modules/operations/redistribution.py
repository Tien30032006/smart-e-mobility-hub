"""Vehicle redistribution.   OWNER: Member 3

  UC03    Redistribute Vehicles
  UC-OP04 Create Relocation Order (included by UC03)

Member 4's What-if recommendations (UC6) produce *plans* in the SAME format as
``propose_redistribution`` so the operator can apply a simulated suggestion
directly via ``create_relocation_order``:

    plan = {"from_hub": str, "to_hub": str, "vehicle_ids": [str, ...], "reason": str}

Order life cycle:  PENDING -> ASSIGNED -> DONE   (or CANCELLED)
  create   : vehicles -> RELOCATING (hidden from the student App), destination spaces reserved,
             field staff notified (mock), RELOCATION_ORDER_CREATED emitted.
  complete : reservations on the spaces are released and ``network.move_vehicle`` (atomic, core)
             re-docks every vehicle at the destination; vehicles become AVAILABLE again.
  cancel   : vehicles back to AVAILABLE, spaces released.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException

from ...core.entities import new_id
from ...core.enums import EventType, Severity, VehicleStatus
from ...core.event_bus import bus
from ...core.state_manager import network
from . import service, store as ops_store
from .models import (ACTIVE_ORDER, MIN_RELOCATION_BATTERY, NEAR_CAPACITY, SHORTAGE_VEHICLES, TARGET_STOCK,
                     TARGET_UTILIZATION, AlertType, OrderStatus)

OWNER = "Member 3"


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def _committed_vehicles() -> set:
    """Vehicles already part of an active order."""
    return {vid for o in ops_store.current().orders.values() if o["status"] in ACTIVE_ORDER
            for vid in o["vehicle_ids"]}


def _movable(hub_id: str) -> list:
    """Vehicles that may be moved: shared, AVAILABLE (never reserved / in use / maintenance), enough battery,
    not already in an order. Fullest battery first (UC03 step 4)."""
    taken = _committed_vehicles()
    return sorted((v for v in network.vehicles_at(hub_id)
                   if v.is_shared and v.status == VehicleStatus.AVAILABLE and v.vehicle_id not in taken
                   and v.battery_level >= MIN_RELOCATION_BATTERY),
                  key=lambda v: (-v.battery_level, v.vehicle_id))


def get_candidates(from_hub: str, to_hub: str) -> dict:
    """UC03 step 3: movable vehicles at the source hub + free spaces at the destination."""
    with network.lock:
        src, dst = network.get_hub(from_hub), network.get_hub(to_hub)
        return {"from_hub": from_hub, "to_hub": to_hub,
                "vehicles": [{"vehicle_id": v.vehicle_id, "model": v.model, "vehicle_type": v.vehicle_type,
                              "battery_level": v.battery_level} for v in _movable(from_hub)],
                "free_spaces": dst.get_available_resources(), "source_name": src.name, "dest_name": dst.name}


# --------------------------------------------------------------------------- #
# UC03                                                                        #
# --------------------------------------------------------------------------- #
def propose_redistribution() -> List[dict]:
    """UC03: find surplus hubs (utilization high) and shortage hubs (few available vehicles);
    return a list of plans (format above). Never propose vehicles that are reserved/in use/maintenance."""
    plans: List[dict] = []
    with network.lock:
        hubs = [h for h in network.list_hubs() if h.hub_id not in network.cut_hubs]    # offline data = no plan
        taken = _committed_vehicles()
        used_vehicle: set = set(taken)
        free_left = {h.hub_id: h.get_available_resources() for h in hubs}
        available = {h.hub_id: sum(v.status == VehicleStatus.AVAILABLE for v in network.vehicles_at(h.hub_id))
                     for h in hubs}
        surplus = sorted((h for h in hubs if h.is_near_capacity(NEAR_CAPACITY)),
                         key=lambda h: -h.update_utilization())
        shortage = sorted((h for h in hubs if available[h.hub_id] <= SHORTAGE_VEHICLES
                           and h.hub_id not in {s.hub_id for s in surplus}),
                          key=lambda h: available[h.hub_id])
        # a full hub can give away vehicles until it is back to TARGET_UTILIZATION;
        # a hub with plenty of stock may also donate (keeps TARGET_STOCK + 1 for itself).
        donors = [(h, max(0, len(h.parking_spaces) - h.get_available_resources()
                          - int(TARGET_UTILIZATION * len(h.parking_spaces)))) for h in surplus]
        surplus_ids = {h.hub_id for h in surplus}
        donors += [(h, max(0, available[h.hub_id] - (TARGET_STOCK + 1))) for h in hubs
                   if h.hub_id not in surplus_ids and available[h.hub_id] > TARGET_STOCK + 1]
        for dest in shortage:
            need = TARGET_STOCK - available[dest.hub_id]
            for i, (src, spare) in enumerate(donors):
                if need <= 0:
                    break
                room = free_left[dest.hub_id]
                pick = [v for v in _movable(src.hub_id) if v.vehicle_id not in used_vehicle][:min(spare, need, room)]
                if not pick:
                    continue
                ids = [v.vehicle_id for v in pick]
                used_vehicle.update(ids)
                donors[i] = (src, spare - len(ids))
                free_left[dest.hub_id] -= len(ids)
                need -= len(ids)
                plans.append({"from_hub": src.hub_id, "to_hub": dest.hub_id, "vehicle_ids": ids,
                              "reason": (f"{src.name} is {round(src.update_utilization() * 100)}% full; "
                                         f"{dest.name} has only {available[dest.hub_id]} available vehicle(s)")})
    return plans


def _validate_plan(plan: dict) -> tuple:
    if not isinstance(plan, dict):
        raise HTTPException(400, "plan must be an object")
    from_hub, to_hub = plan.get("from_hub"), plan.get("to_hub")
    ids = plan.get("vehicle_ids")
    if not from_hub or not to_hub or from_hub == to_hub:
        raise HTTPException(400, "Choose two different hubs (source and destination)")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
        raise HTTPException(400, "Select at least one vehicle")
    if len(set(ids)) != len(ids):
        raise HTTPException(400, "A vehicle was selected twice")
    return from_hub, to_hub, ids


def create_relocation_order(plan: dict, operator_id: str) -> dict:
    """UC-OP04: validate plan, store order (status PENDING/ASSIGNED/DONE), notify field staff
    (mock), emit RELOCATION_ORDER_CREATED. Alternate flow: staff reject/timeout -> alert operator."""
    from_hub, to_hub, ids = _validate_plan(plan)
    with network.lock:
        src, dst = network.get_hub(from_hub), network.get_hub(to_hub)     # HubNotFound -> 404
        free = [s for s in sorted(dst.parking_spaces.values(), key=lambda s: s.space_id) if s.is_available()]
        if len(ids) > len(free):                                          # UC03 alt 4a
            raise HTTPException(400, "Exceeds the capacity of the destination Hub")
        taken = _committed_vehicles()
        for vid in ids:                                                   # UC03 alt 5a (race condition)
            v = network.vehicles.get(vid)
            if (v is None or v.hub_id != from_hub or not v.is_shared or v.status != VehicleStatus.AVAILABLE
                    or vid in taken):
                raise HTTPException(409, f"Vehicle {vid} just changed status. Please reload the list")
        order_id = new_id("RO")
        spaces = free[:len(ids)]
        for s in spaces:                                                  # UC03 step 6: hold the destination slots
            s.reserved_by = order_id
        for vid in ids:                                                   # UC03 step 5: lock the vehicles
            network.vehicles[vid].update_status(VehicleStatus.RELOCATING)
        order = {"order_id": order_id, "from_hub": from_hub, "to_hub": to_hub, "vehicle_ids": list(ids),
                 "space_ids": [s.space_id for s in spaces], "reason": str(plan.get("reason") or ""),
                 "status": OrderStatus.PENDING.value, "created_by": operator_id, "created_at": ops_store.now_iso(),
                 "assigned_to": None, "completed_at": None, "rejections": []}
        ops_store.current().orders[order_id] = order
        ops_store.notify("field_staff", "work_order", order_id=order_id, from_hub=src.name, to_hub=dst.name,
                         vehicles=list(ids))
        ops_store.log_audit("relocation_created", operator_id, order_id=order_id, vehicles=len(ids))
    bus.emit(EventType.RELOCATION_ORDER_CREATED, hub_id=from_hub, order_id=order_id, to_hub=to_hub,
             vehicle_ids=list(ids), message=f"Relocation {from_hub} -> {to_hub} ({len(ids)} vehicles)")
    service.scan_for_alerts()
    return order


def _order(order_id: str) -> dict:
    order = ops_store.current().orders.get(order_id)
    if order is None:
        raise HTTPException(404, f"Relocation order {order_id} not found")
    return order


def _release(order: dict) -> None:
    """Free the destination spaces held for the order."""
    dst = network.hubs.get(order["to_hub"])
    for sid in order["space_ids"]:
        space = dst.parking_spaces.get(sid) if dst else None
        if space is not None and space.reserved_by == order["order_id"]:
            space.reserved_by = None


def assign_relocation_order(order_id: str, staff_id: str = "field-staff") -> dict:
    """Field staff accepts the work order (mock: the operator UI simulates the staff App)."""
    with network.lock:
        order = _order(order_id)
        if order["status"] != OrderStatus.PENDING.value:
            raise HTTPException(409, f"Order is already {order['status']}")
        order.update(status=OrderStatus.ASSIGNED.value, assigned_to=staff_id)
        service.close_alerts_for(f"{AlertType.RELOCATION_UNASSIGNED.value}:{order_id}")
        return order


def reject_relocation_order(order_id: str, staff_id: str = "field-staff", reason: str = "") -> dict:
    """Alternate flow: staff reject -> the order stays PENDING and the Operator gets an alert."""
    with network.lock:
        order = _order(order_id)
        if order["status"] != OrderStatus.PENDING.value:
            raise HTTPException(409, f"Order is already {order['status']}")
        order["rejections"].append({"staff_id": staff_id, "reason": reason, "at": ops_store.now_iso()})
        service.raise_alert(f"{AlertType.RELOCATION_REJECTED.value}:{order_id}:{len(order['rejections'])}",
                            AlertType.RELOCATION_REJECTED, Severity.WARNING, order["from_hub"],
                            f"Field staff rejected relocation order {order_id}", reason or "No reason given.",
                            ["Re-assign the order or cancel it"], order_id)
        return order


def complete_relocation_order(order_id: str) -> dict:
    """Staff confirmed: re-dock every vehicle with the atomic core primitive and mark the order DONE."""
    with network.lock:
        order = _order(order_id)
        if order["status"] not in ACTIVE_ORDER:
            raise HTTPException(409, f"Order is already {order['status']}")
        _release(order)                       # the held spaces would otherwise block move_vehicle
        moved: list = []
        for vid in order["vehicle_ids"]:
            vehicle = network.get_vehicle(vid)
            if vehicle.status != VehicleStatus.RELOCATING or not network.move_vehicle(vid, order["to_hub"]):
                for done in moved:            # roll back: nothing is half-moved
                    network.move_vehicle(done, order["from_hub"])
                    network.get_vehicle(done).update_status(VehicleStatus.RELOCATING)
                dst = network.get_hub(order["to_hub"])
                again = [sp for sp in sorted(dst.parking_spaces.values(), key=lambda sp: sp.space_id)
                         if sp.is_available()][:len(order["space_ids"])]
                for sp in again:              # hold the destination slots again
                    sp.reserved_by = order_id
                order["space_ids"] = [sp.space_id for sp in again]
                raise HTTPException(409, f"Could not move vehicle {vid}; order unchanged")
            moved.append(vid)
        for vid in moved:
            network.get_vehicle(vid).update_status(VehicleStatus.AVAILABLE)
        order.update(status=OrderStatus.DONE.value, completed_at=ops_store.now_iso())
        service.close_alerts_for(f"{AlertType.RELOCATION_UNASSIGNED.value}:{order_id}")
    service.scan_for_alerts()
    bus.emit(EventType.RELOCATION_ORDER_CREATED, hub_id=order["to_hub"], order_id=order_id, done=True,
             vehicle_ids=list(order["vehicle_ids"]), message=f"Relocation {order_id} completed")
    return order


def cancel_relocation_order(order_id: str, operator_id: str) -> dict:
    with network.lock:
        order = _order(order_id)
        if order["status"] not in ACTIVE_ORDER:
            raise HTTPException(409, f"Order is already {order['status']}")
        _release(order)
        for vid in order["vehicle_ids"]:
            v = network.vehicles.get(vid)
            if v is not None and v.status == VehicleStatus.RELOCATING:
                v.update_status(VehicleStatus.AVAILABLE)
        order["status"] = OrderStatus.CANCELLED.value
        service.close_alerts_for(f"{AlertType.RELOCATION_UNASSIGNED.value}:{order_id}")
        ops_store.log_audit("relocation_cancelled", operator_id, order_id=order_id)
    service.scan_for_alerts()
    return order


def list_orders() -> List[dict]:
    return sorted(ops_store.current().orders.values(), key=lambda o: o["created_at"], reverse=True)


def redistribute_hubs(from_hub: str, to_hub: str) -> bool:
    """Back-end of ``HubNetworkManager.redistribute_vehicles`` (class diagram): move as many surplus vehicles
    as the destination can hold, immediately (MVP shortcut: order created and completed in one step).
    Returns True when at least one vehicle was moved."""
    with network.lock:
        src, dst = network.get_hub(from_hub), network.get_hub(to_hub)
        spare = max(0, len(src.parking_spaces) - src.get_available_resources()
                    - int(TARGET_UTILIZATION * len(src.parking_spaces)))
        n = min(len(_movable(from_hub)), dst.get_available_resources(), spare or len(_movable(from_hub)))
        if from_hub == to_hub or n <= 0:
            return False
        ids = [v.vehicle_id for v in _movable(from_hub)[:n]]
        order = create_relocation_order({"from_hub": from_hub, "to_hub": to_hub, "vehicle_ids": ids,
                                         "reason": "network.redistribute_vehicles"}, "system")
        complete_relocation_order(order["order_id"])
        return True
