"""Shared HTTP endpoints: auth, profile, SSE stream, demo controls. SHARED FILE (owner: TV5)."""
from __future__ import annotations

import asyncio
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import auth
from .config import settings
from .database import persistence
from .demo import reset_demo
from .entities import Operator, Student, User
from .simulator import simulator
from .state_manager import network
from .stream import format_sse, stream_hub

router = APIRouter()
STUDENT_CODE = re.compile(r"^[A-Za-z0-9]{6,12}$")
PHONE = re.compile(r"^\+?[0-9 ]{9,13}$")


class GoogleIn(BaseModel):
    credential: str = Field(min_length=10, description="Google ID token (JWT) from Google Identity Services")


class EmailIn(BaseModel):
    email: str


class ProfilePatch(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    student_code: Optional[str] = None
    phone: Optional[str] = None
    onboarded: Optional[bool] = None


class TelemetryCut(BaseModel):
    target_type: Literal["hub", "vehicle"]
    target_id: str
    cut: bool = True


class SimulatorIn(BaseModel):
    enabled: Optional[bool] = None
    seed: Optional[int] = None
    interval: Optional[float] = Field(default=None, ge=0.5, le=60)
    fault_probability: Optional[float] = Field(default=None, ge=0, le=1)
    rush_hour: Optional[Literal["auto", "on", "off"]] = None


# ---- auth ---------------------------------------------------------------------------
@router.get("/api/auth/config", tags=["Auth"])
def auth_config():
    """What the login page needs: Google client id (public) and whether demo login is on."""
    return {"google_client_id": settings.google_client_id, "demo_mode": settings.demo_mode,
            "demo_accounts": auth.demo_accounts() if settings.demo_mode else []}


@router.post("/api/auth/google", tags=["Auth"])
def login_google(body: GoogleIn):
    claims = auth.verify_google_token(body.credential)
    user = auth.sign_in_with_google_claims(claims)
    return auth.session_payload(user)


@router.post("/api/auth/demo-login", tags=["Auth"])
def demo_login(body: EmailIn):
    return auth.session_payload(auth.demo_login(body.email))


@router.post("/api/auth/login", tags=["Auth"], deprecated=True)
def legacy_login(body: EmailIn):
    """Kept for old pages/tests: identical to demo-login (and only works when DEMO_MODE=true)."""
    return auth.session_payload(auth.demo_login(body.email))


# ---- profile --------------------------------------------------------------------------
def _profile(user: User) -> dict:
    meta = getattr(user, "_db", {}) or {}
    return {"user_id": user.user_id, "full_name": user.full_name, "email": user.email,
            "role": user.user_role.value, "student_code": getattr(user, "student_code", ""),
            "phone": meta.get("phone", ""), "picture": meta.get("picture", ""),
            "has_private_ev": bool(getattr(user, "has_private_ev", False)),
            "onboarded": bool(meta.get("onboarded", True))}


@router.get("/api/me", tags=["Auth"])
def me(user: User = Depends(auth.current_user)):
    return _profile(user)


@router.patch("/api/me", tags=["Auth"])
def update_me(body: ProfilePatch, user: User = Depends(auth.current_user)):
    with network.lock:
        meta = getattr(user, "_db", None)
        if meta is None:
            meta = user._db = {}
        if body.full_name is not None:
            user.full_name = body.full_name.strip()
        if body.student_code is not None:
            if not isinstance(user, Student):
                raise HTTPException(400, "Only students have a student code")
            if not STUDENT_CODE.match(body.student_code):
                raise HTTPException(422, detail="student_code must be 6-12 letters/digits")
            if any(isinstance(u, Student) and u.student_code == body.student_code and u.user_id != user.user_id
                   for u in network.users.values()):
                raise HTTPException(409, detail="student_code already used")
            user.student_code = body.student_code
        if body.phone is not None:
            if body.phone and not PHONE.match(body.phone):
                raise HTTPException(422, detail="invalid phone number")
            meta["phone"] = body.phone.replace(" ", "")
        if body.onboarded is not None:
            meta["onboarded"] = body.onboarded
    return _profile(user)


# ---- realtime ---------------------------------------------------------------------------
@router.get("/api/stream", tags=["Realtime"])
async def stream(request: Request, token: str):
    """Server-Sent Events. EventSource cannot set headers, so the JWT is a query parameter."""
    user = auth.user_from_token(token)
    stream_hub.bind_loop(asyncio.get_running_loop())
    sub = stream_hub.subscribe(user.user_id, user.user_role)

    async def gen():
        try:
            yield "retry: 3000\n\n"
            yield format_sse("hello", {"seq": 0, "user_id": user.user_id, "role": user.user_role.value})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    name, data = await asyncio.wait_for(sub.queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield format_sse(name, data)
        finally:
            stream_hub.unsubscribe(sub)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


# ---- demo controls (operator only) ---------------------------------------------------------
@router.post("/api/demo/reset", tags=["Demo"])
def demo_reset(seed: Optional[int] = None, _: Operator = Depends(auth.require_operator)):
    return reset_demo(seed)


@router.get("/api/demo/simulator", tags=["Demo"])
def simulator_status(_: Operator = Depends(auth.require_operator)):
    return simulator.status()


@router.post("/api/demo/simulator", tags=["Demo"])
def simulator_configure(body: SimulatorIn, _: Operator = Depends(auth.require_operator)):
    return simulator.configure(**body.model_dump())


@router.post("/api/demo/simulator/tick", tags=["Demo"])
def simulator_tick(_: Operator = Depends(auth.require_operator)):
    """Advance one step right now (useful when rehearsing)."""
    return simulator.tick()


@router.post("/api/demo/telemetry", tags=["Demo"])
def telemetry_cut(body: TelemetryCut, _: Operator = Depends(auth.require_operator)):
    if body.target_type == "hub":
        network.get_hub(body.target_id)
    else:
        network.get_vehicle(body.target_id)
    simulator.cut_telemetry(body.target_type, body.target_id, body.cut)
    stream_hub.publish("hub_updated", {"hub_id": body.target_id if body.target_type == "hub" else None,
                                       "reason": "telemetry_cut" if body.cut else "telemetry_restored"})
    return simulator.status()


@router.get("/api/demo/database", tags=["Demo"])
def database_info(limit: int = 20, _: Operator = Depends(auth.require_operator)):
    """Row counts and the latest audit events stored in SQLite."""
    persistence.flush()
    return {"enabled": persistence.enabled, "path": persistence.path,
            "tables": persistence.table_counts(), "recent_events": persistence.recent_events(min(limit, 200))}
