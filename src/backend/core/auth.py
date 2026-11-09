"""Authentication shared by all modules. SHARED FILE (owner: TV5).

* Token = signed JWT (PyJWT, HS256) in ``Authorization: Bearer <jwt>``.
  EventSource cannot send headers, so ``/api/stream`` accepts ``?token=``.
* E-mail + password: ``register_student`` (creates a Student, then the onboarding page asks for the
  student code) and ``login_password``. Passwords are PBKDF2-hashed, stored in ``user._db`` and persisted
  in SQLite like the rest of the profile.
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

import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import jwt
from fastapi import Depends, Header, HTTPException

from .config import settings
from .entities import Operator, Student, User, new_id
from .enums import UserRole
from .state_manager import network

ALGORITHM = "HS256"
MIN_PASSWORD_LEN = 8
PBKDF2_ROUNDS = 200_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


# ---- e-mail + password ---------------------------------------------------------------
def _meta(user: User) -> dict:
    meta = getattr(user, "_db", None)
    if meta is None:
        meta = user._db = {}
    return meta


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(calc.hex(), digest)
    except (ValueError, AttributeError):
        return False


_DUMMY_HASH = hash_password("not-a-real-password")      # makes "unknown e-mail" take as long as "wrong password"
_MAX_FAILS, _WINDOW_S = 5, 300
_fails: Dict[str, List[float]] = {}


def reset_throttle() -> None:
    _fails.clear()


def _throttle_check(key: str) -> None:
    now = time.time()
    _fails[key] = recent = [t for t in _fails.get(key, []) if now - t < _WINDOW_S]
    if len(recent) >= _MAX_FAILS:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")


def validate_password(password: str, email: str = "") -> None:
    if len(password) < MIN_PASSWORD_LEN:
        raise HTTPException(status_code=422, detail=f"Password must be at least {MIN_PASSWORD_LEN} characters.")
    if password.isdigit() or password.isalpha():
        raise HTTPException(status_code=422, detail="Password must contain both letters and digits.")
    if email and password.lower() == email.lower():
        raise HTTPException(status_code=422, detail="Password must not be your e-mail.")


def register_student(full_name: str, email: str, password: str) -> User:
    """Create a Student account. Operators can only come from Google + OPERATOR_EMAILS."""
    full_name, email = " ".join(full_name.split()), email.strip().lower()
    if len(full_name) < 2:
        raise HTTPException(status_code=422, detail="Please enter your full name.")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid e-mail address.")
    if email in settings.operator_emails:
        raise HTTPException(status_code=403, detail="Operator accounts sign in with Google.")
    if settings.allowed_student_domains and email.split("@")[-1] not in settings.allowed_student_domains:
        raise HTTPException(status_code=403, detail="E-mail domain is not allowed")
    validate_password(password, email)
    with network.lock:
        if find_by_email(email) is not None:
            raise HTTPException(status_code=409, detail="An account with this e-mail already exists.")
        user = Student(user_id=new_id("U-S"), full_name=full_name, email=email)
        user._db = {"created_at": datetime.now(timezone.utc).isoformat(), "onboarded": False,
                    "password_hash": hash_password(password)}
        network.register_user(user)
    return user


def login_password(email: str, password: str) -> User:
    key = email.strip().lower()
    _throttle_check(key)
    user = find_by_email(key)
    stored = _meta(user).get("password_hash", "") if user else ""
    ok = verify_password(password, stored or _DUMMY_HASH)
    if user is None or not stored or not ok:
        _fails.setdefault(key, []).append(time.time())
        raise HTTPException(status_code=401, detail="Wrong e-mail or password.")
    _fails.pop(key, None)
    return user


def change_password(user: User, new_password: str, current_password: str = "") -> None:
    validate_password(new_password, user.email)
    meta = _meta(user)
    if meta.get("password_hash") and not verify_password(current_password, meta["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    meta["password_hash"] = hash_password(new_password)


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
        from google.auth import exceptions as g_exc
        from google.auth.transport import requests as g_requests
        from google.oauth2 import id_token
    except ImportError:
        raise HTTPException(status_code=503, detail="Install google-auth to enable Google sign-in") from None
    try:
        claims = id_token.verify_oauth2_token(
            id_token_str, g_requests.Request(), settings.google_client_id,
            clock_skew_in_seconds=5,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {exc}") from None
    except g_exc.TransportError:   # the server cannot download Google's public keys (offline)
        raise HTTPException(status_code=503, detail="Cannot reach Google right now. Use e-mail sign-in or a demo account.") from None
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
        meta = _meta(user)
        if meta.get("google_sub") and meta["google_sub"] != claims.get("sub"):
            raise HTTPException(status_code=409, detail="This e-mail is linked to another Google account")
        if not meta.get("google_sub") and meta.get("password_hash"):
            # First Google login on an e-mail/password account. That password was never e-mail-verified,
            # so drop it: otherwise whoever pre-registered this address would keep access.
            meta["password_hash"] = ""
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
