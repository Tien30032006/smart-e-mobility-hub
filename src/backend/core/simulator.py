"""Background simulator that makes the *real* system state move. SHARED FILE (owner: TV5).

Every ``interval`` seconds (3-5 s) ``tick()``:
  * vehicles IN_USE lose battery, vehicles CHARGING gain battery;
  * ambient students arrive at / leave hubs following a (fake) rush-hour profile
    by moving AVAILABLE shared vehicles between hubs with ``network.move_vehicle``;
  * with a configurable probability a free charging point breaks (and is repaired later).
Each change is published on the event bus (BATTERY_UPDATED, CHARGER_STATUS_CHANGED ...),
which the SSE hub forwards to browsers and TV2's telemetry adapter ingests.

Reproducible: ``random.Random(seed)`` - same seed => same demo run.

IMPORTANT: this changes the REAL state. The What-if module (TV4) works on
``network.snapshot()`` copies and must never be affected by it.

Demo switches (operator only, /api/demo/telemetry): cut telemetry of one vehicle or
hub -> no BATTERY_UPDATED for it, so TV2's 120 s rule shows "battery level unconfirmed"
and the hub is shown as "Data connection lost" (UC01 exception flow).
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional

from .config import settings
from .entities import utcnow
from .enums import ChargingPointStatus, EventType, Severity, VehicleStatus
from .event_bus import bus
from .logger import get_logger
from .state_manager import HubNetworkManager, network as default_network

log = get_logger("simulator")

# Hour-of-day -> demand multiplier (fake campus rhythm: 7-9h and 16-19h are peaks).
RUSH_PROFILE = {h: 0.3 for h in range(24)}
RUSH_PROFILE.update({7: 1.0, 8: 1.0, 9: 0.7, 11: 0.6, 12: 0.6, 16: 0.9, 17: 1.0, 18: 1.0, 19: 0.6})
HUB_BIAS = {"HUB-METRO": 1.6, "HUB-CAMPUS": 1.0, "HUB-KTX": 0.9, "HUB-LIB": 0.6}


class Simulator:
    def __init__(self, state: HubNetworkManager = default_network, seed: Optional[int] = None) -> None:
        self.network = state
        self.seed = settings.simulator_seed if seed is None else seed
        self.rng = random.Random(self.seed)
        self.enabled = settings.simulator_enabled
        self.interval = settings.simulator_interval_seconds
        self.fault_probability = settings.simulator_fault_probability
        self.rush_hour = settings.simulator_rush_hour           # auto | on | off
        self.ticks = 0
        self.broken_since: Dict[str, int] = {}                  # point_id -> tick when it broke
        self._task: Optional[asyncio.Task] = None

    # ---- controls -------------------------------------------------------------
    def configure(self, **kw) -> dict:
        for key in ("enabled", "interval", "fault_probability", "rush_hour"):
            if key in kw and kw[key] is not None:
                setattr(self, key, kw[key])
        if kw.get("seed") is not None:
            self.seed = int(kw["seed"])
            self.rng = random.Random(self.seed)
        return self.status()

    def status(self) -> dict:
        return {"enabled": self.enabled, "interval": self.interval, "seed": self.seed, "ticks": self.ticks,
                "fault_probability": self.fault_probability, "rush_hour": self.rush_hour,
                "cut_hubs": sorted(self.network.cut_hubs), "cut_vehicles": sorted(self.network.cut_vehicles),
                "broken_points": sorted(self.broken_since)}

    def reseed(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.seed = seed
        self.rng = random.Random(self.seed)
        self.ticks = 0
        self.broken_since.clear()

    def cut_telemetry(self, target_type: str, target_id: str, cut: bool) -> None:
        bucket = self.network.cut_hubs if target_type == "hub" else self.network.cut_vehicles
        if target_type not in ("hub", "vehicle"):
            raise ValueError("target_type must be 'hub' or 'vehicle'")
        (bucket.add if cut else bucket.discard)(target_id)

    # ---- one step ----------------------------------------------------------------
    def demand_factor(self, now: Optional[datetime] = None) -> float:
        if self.rush_hour == "on":
            return 1.0
        if self.rush_hour == "off":
            return 0.2
        return RUSH_PROFILE[(now or datetime.now()).hour]

    def tick(self, now: Optional[datetime] = None) -> dict:
        """Advance the simulation one step. Pure-sync so tests can call it directly."""
        stats = {"battery": 0, "moves": 0, "faults": 0, "repairs": 0}
        n = self.network
        with n.lock:
            self.ticks += 1
            self._update_batteries(stats)
            self._move_students(stats, self.demand_factor(now))
            self._update_chargers(stats)
        return stats

    def _telemetry_cut(self, vehicle) -> bool:
        return vehicle.vehicle_id in self.network.cut_vehicles or (
            vehicle.hub_id in self.network.cut_hubs if vehicle.hub_id else False)

    def _update_batteries(self, stats: dict) -> None:
        for v in list(self.network.vehicles.values()):
            if self._telemetry_cut(v):
                continue
            old = v.battery_level
            if v.status == VehicleStatus.IN_USE:
                v.battery_level = max(0, old - self.rng.randint(1, 3))
            elif v.status == VehicleStatus.CHARGING:
                v.battery_level = min(100, old + self.rng.randint(3, 6))
                if v.battery_level >= 100:
                    self._finish_charging(v)
            else:
                continue
            if v.battery_level != old:
                stats["battery"] += 1
                bus.emit(EventType.BATTERY_UPDATED, hub_id=v.hub_id, vehicle_id=v.vehicle_id,
                         battery_level=v.battery_level, origin="core.simulator",
                         device_timestamp=utcnow().isoformat())

    def _finish_charging(self, vehicle) -> None:
        """Battery full: free the charger and let the vehicle be rented / collected."""
        vehicle.status = VehicleStatus.AVAILABLE
        if vehicle.hub_id and vehicle.hub_id in self.network.hubs:
            for p in self.network.hubs[vehicle.hub_id].charging_points.values():
                session = self.network.charging_sessions.get(p.current_session_id or "")
                if session is not None and session.vehicle_id == vehicle.vehicle_id:
                    return          # TV2 owns the session lifecycle; do not touch the point
        bus.emit(EventType.CHARGING_COMPLETED, hub_id=vehicle.hub_id, vehicle_id=vehicle.vehicle_id,
                 origin="core.simulator")

    def _move_students(self, stats: dict, factor: float) -> None:
        """Ambient traffic: move a free shared vehicle from a calm hub to a busy one."""
        if self.rng.random() > min(1.0, 0.35 + factor * 0.6):
            return
        hubs = list(self.network.hubs.values())
        if len(hubs) < 2:
            return
        weights = [HUB_BIAS.get(h.hub_id, 1.0) * (0.5 + factor) for h in hubs]
        dest = self.rng.choices(hubs, weights=weights)[0]
        if dest.hub_id in self.network.cut_hubs or dest.get_available_resources() <= 1:
            return                  # keep one slot free so student returns do not all fail
        sources = [h for h in hubs if h is not dest and h.hub_id not in self.network.cut_hubs]
        self.rng.shuffle(sources)
        for src in sources:
            candidates = [v for v in self.network.vehicles_at(src.hub_id)
                          if v.is_shared and v.status == VehicleStatus.AVAILABLE and v.battery_level >= 20]
            if candidates:
                vehicle = self.rng.choice(sorted(candidates, key=lambda v: v.vehicle_id))
                if self.network.move_vehicle(vehicle.vehicle_id, dest.hub_id):
                    stats["moves"] += 1
                    bus.emit(EventType.VEHICLE_RETURNED, hub_id=dest.hub_id, vehicle_id=vehicle.vehicle_id,
                             user_id=None, origin="core.simulator", from_hub=src.hub_id)
                return

    def _update_chargers(self, stats: dict) -> None:
        # repair after ~6 ticks
        for pid, since in list(self.broken_since.items()):
            if self.ticks - since >= 6:
                point = self._find_point(pid)
                if point is not None and point.status == ChargingPointStatus.OUT_OF_SERVICE:
                    self._set_point(point, ChargingPointStatus.AVAILABLE)
                    stats["repairs"] += 1
                del self.broken_since[pid]
        if self.rng.random() < self.fault_probability:
            free = sorted((p for h in self.network.hubs.values() for p in h.charging_points.values()
                           if p.status == ChargingPointStatus.AVAILABLE and p.hub_id not in self.network.cut_hubs),
                          key=lambda p: p.point_id)
            if free:
                point = self.rng.choice(free)
                self._set_point(point, ChargingPointStatus.OUT_OF_SERVICE)
                self.broken_since[point.point_id] = self.ticks
                stats["faults"] += 1

    def _find_point(self, point_id: str):
        for h in self.network.hubs.values():
            if point_id in h.charging_points:
                return h.charging_points[point_id]
        return None

    def _set_point(self, point, status: ChargingPointStatus) -> None:
        old = point.status
        point.status = status
        bus.emit(EventType.CHARGER_STATUS_CHANGED, hub_id=point.hub_id,
                 severity=Severity.WARNING if status == ChargingPointStatus.OUT_OF_SERVICE else Severity.INFO,
                 point_id=point.point_id, old_status=ChargingPointStatus(old).value,
                 new_status=status.value, origin="core.simulator",
                 device_timestamp=utcnow().isoformat())

    # ---- asyncio runner ----------------------------------------------------------------
    async def run(self) -> None:
        log.info("simulator started (seed=%s, every %ss)", self.seed, self.interval)
        while True:
            await asyncio.sleep(max(0.5, self.interval + self.rng.uniform(-1, 1)))
            if not self.enabled:
                continue
            try:
                await asyncio.to_thread(self.tick)
            except Exception:  # noqa: BLE001
                log.exception("simulator tick failed")

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self.run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


simulator = Simulator()
