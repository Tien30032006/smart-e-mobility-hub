"""Distance helpers for hub discovery (U1).   OWNER: Member 1

Straight-line (great-circle) distance only. Real walking distance is fetched
by the browser from a routing service (see shared/map.js); the server value is
the always-available fallback and the sort key.
"""
from __future__ import annotations

import math
from typing import Iterable, List

EARTH_RADIUS_M = 6_371_008.8
WALK_SPEED_M_PER_MIN = 80          # ~4.8 km/h
DETOUR_FACTOR = 1.3                # streets are longer than the crow flies


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def walk_minutes(distance_m: float) -> int:
    return max(1, round(distance_m * DETOUR_FACTOR / WALK_SPEED_M_PER_MIN))


def rank_by_distance(hubs: Iterable[dict], lat: float, lng: float, limit: int = 0) -> List[dict]:
    """Return copies of hub status dicts with distance_m / walk_min, nearest first."""
    out = []
    for h in hubs:
        loc = h.get("location") or {}
        if "lat" not in loc or "lng" not in loc:
            continue
        d = haversine_m(lat, lng, loc["lat"], loc["lng"])
        out.append({**h, "distance_m": round(d), "walk_min": walk_minutes(d)})
    out.sort(key=lambda x: x["distance_m"])
    return out[:limit] if limit > 0 else out
