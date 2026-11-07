"""Authentication shared by all modules. SHARED FILE (owner: TV5).

* Token = signed JWT (PyJWT, HS256) in ``Authorization: Bearer <jwt>``.
  EventSource cannot send headers, so ``/api/stream`` accepts ``?token=``.
* Google Sign-In: the browser sends a Google ID token to ``POST /api/auth/google``;
  we verify signature / audience / expiry with ``google-auth`` and create the
  Student on first login (that is the "register" step). Operators are only
  granted for e-mails listed in ``OPERATOR_EMAILS``.
* ``DEMO_MODE=true`` enables ``POST /api/auth/demo-login`` for the 3 seeded accounts.

Route dependencies keep the original signatures:

    @router.post("/x")
    def x(user: Student = Depends(require_student)): ...
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException

from .config import settings
from .entities import Operator, Student, User, new_id
from .enums import UserRole
from .state_manager import network

ALGORITHM = "HS256"


# ---- tokens ------------------------------------------------------------------
def issue_token(user: User, ttl_minutes: Optional[int] = None) -> str:
    now = datetime.now(timezone.utc)
    ttl = ttl_minutes if ttl_minutes is not None else settings.jwt_ttl_minutes
    payload = {"sub": user.user_id, "role": user.user_role.value, "email": user.email,
               "iat": now, "exp": now + timedelta(minutes=ttl)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def user_from_token(token: str) -> User:
    """Validate a JWT and return the matching user (raises HTTP 401)."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired") from None
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token") from None
    user = network.users.get(claims["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


def session_payload(user: User) -> dict:
    meta = getattr(user, "_db", {}) or {}
    return {"token": issue_token(user), "user_id": user.user_id, "full_name": user.full_name,
            "email": user.email, "role": user.user_role.value,
            "student_code": getattr(user, "student_code", ""), "picture": meta.get("picture", ""),
            "onboarded": bool(meta.get("onboarded", True)),
            "has_private_ev": bool(getattr(user, "has_private_ev", False))}


# ---- demo login ----------------------------------------------------------------
def find_by_email(email: str) -> Optional[User]:
    email = email.strip().lower()
    return next((u for u in network.users.values() if u.email.lower() == email), None)


def login(email: str) -> Optional[User]:
    """Look a user up by e-mail (used by demo-login and tests)."""
    return find_by_email(email)


def demo_accounts() -> list[dict]:
    from ..data.loader import load_json
    return [{"email": u["email"], "full_name": u["full_name"], "role": u["role"],
             "has_private_ev": u.get("has_private_ev", False)} for u in load_json("hubs-data.json")["users"]]


def demo_login(email: str) -> User:
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo login is disabled (DEMO_MODE=false)")
    if email.strip().lower() not in {a["email"].lower() for a in demo_accounts()}:
        raise HTTPException(status_code=401, detail="Unknown demo account")
    user = find_by_email(email)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown demo account")
    return user


# ---- Google Sign-In ---------------------------------------------------------------
def verify_google_token(id_token_str: str) -> dict:
    """Verify signature, audience and expiry of a Google ID token. Returns its claims."""
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="GOOGLE_CLIENT_ID is not configured")
    try:
        from google.auth.transport import requests as g_requests
        from google.oauth2 import id_token
        claims = id_token.verify_oauth2_token(id_token_str, g_requests.Request(), settings.google_client_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {exc}") from None
    return claims


def sign_in_with_google_claims(claims: dict) -> User:
    """Find or create the user for verified Google claims (first login = registration)."""
    email = (claims.get("email") or "").strip().lower()
    if not email or not claims.get("email_verified", False):
        raise HTTPException(status_code=401, detail="Google e-mail is not verified")
    is_operator = email in settings.operator_emails
    if not is_operator and settings.allowed_student_domains:
        if email.split("@")[-1] not in settings.allowed_student_domains:
            raise HTTPException(status_code=403, detail="E-mail domain is not allowed")
    with network.lock:
        user = find_by_email(email)
        if user is None:
            uid = new_id("U-OP" if is_operator else "U-S")
            name = claims.get("name") or email.split("@")[0]
            if is_operator:
                user = Operator(user_id=uid, full_name=name, email=email, operator_id=uid)
            else:
                user = Student(user_id=uid, full_name=name, email=email)
            user._db = {"created_at": datetime.now(timezone.utc).isoformat(), "onboarded": is_operator}  # students onboard once
            network.register_user(user)
        elif is_operator and not isinstance(user, Operator):
            raise HTTPException(status_code=409, detail="Account already exists as a student")
        meta = getattr(user, "_db", None)
        if meta is None:
            meta = user._db = {}
        meta["google_sub"] = claims.get("sub")
        meta["picture"] = claims.get("picture", meta.get("picture", ""))
    return user


# ---- FastAPI dependencies (signatures unchanged) -------------------------------------
def current_user(authorization: Optional[str] = Header(default=None)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing 'Authorization: Bearer <token>'")
    return user_from_token(authorization.split(" ", 1)[1].strip())


def require_student(user: User = Depends(current_user)) -> Student:
    if not isinstance(user, Student):
        raise HTTPException(status_code=403, detail="Student only")
    return user


def require_operator(user: User = Depends(current_user)) -> Operator:
    if not isinstance(user, Operator):
        raise HTTPException(status_code=403, detail="Operator only")
    return user
