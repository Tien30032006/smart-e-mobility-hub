"""JWT + Google sign-in + profile (TV5)."""
from datetime import timedelta

import jwt
import pytest

from src.backend.core import auth as core_auth
from src.backend.core.config import settings
from src.backend.core.state_manager import network

from .conftest import OPERATOR, STUDENT


def test_demo_login_returns_signed_jwt_not_user_id(client):
    r = client.post("/api/auth/demo-login", json={"email": "an@hcmut.edu.vn"})
    assert r.status_code == 200
    data = r.json()
    assert data["token"] != data["user_id"] == "U-S01"
    claims = jwt.decode(data["token"], settings.jwt_secret, algorithms=["HS256"])
    assert claims["sub"] == "U-S01" and claims["role"] == "student"


def test_raw_user_id_is_no_longer_a_token(client):
    assert client.get("/api/me", headers={"Authorization": "Bearer U-S01"}).status_code == 401
    assert client.get("/api/me").status_code == 401


def test_tampered_and_expired_tokens_are_rejected(client):
    good = core_auth.issue_token(network.users["U-S01"])
    bad = good[:-3] + ("AAA" if not good.endswith("AAA") else "BBB")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    expired = core_auth.issue_token(network.users["U-S01"], ttl_minutes=-5)
    r = client.get("/api/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()
    other = jwt.encode({"sub": "U-S01", "exp": 9999999999}, "wrong-secret-wrong-secret-wrong-secret", algorithm="HS256")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {other}"}).status_code == 401


def test_role_checks_still_work(client):
    assert client.get("/api/demo/simulator", headers=STUDENT).status_code == 403
    assert client.get("/api/demo/simulator", headers=OPERATOR).status_code == 200


def test_demo_mode_switch_disables_demo_login(client, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    assert client.post("/api/auth/demo-login", json={"email": "an@hcmut.edu.vn"}).status_code == 403
    assert client.post("/api/auth/login", json={"email": "an@hcmut.edu.vn"}).status_code == 403
    cfg = client.get("/api/auth/config").json()
    assert cfg["demo_mode"] is False and cfg["demo_accounts"] == []


def test_demo_login_only_for_seed_accounts(client):
    assert client.post("/api/auth/demo-login", json={"email": "nobody@x.vn"}).status_code == 401


GOOGLE = {"sub": "g-123", "email": "newbie@hcmut.edu.vn", "email_verified": True,
          "name": "New Student", "picture": "http://img/p.png"}


def _patch_google(monkeypatch, claims):
    monkeypatch.setattr(core_auth, "verify_google_token", lambda token: claims)


def test_first_google_login_registers_a_student(client, monkeypatch):
    _patch_google(monkeypatch, GOOGLE)
    r = client.post("/api/auth/google", json={"credential": "x" * 20})
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "student" and data["onboarded"] is False and data["email"] == GOOGLE["email"]
    again = client.post("/api/auth/google", json={"credential": "x" * 20}).json()
    assert again["user_id"] == data["user_id"]                       # no duplicate account
    assert sum(u.email == GOOGLE["email"] for u in network.users.values()) == 1


def test_google_operator_only_from_allow_list(client, monkeypatch):
    claims = {**GOOGLE, "email": "boss@hub.vn"}
    _patch_google(monkeypatch, claims)
    assert client.post("/api/auth/google", json={"credential": "x" * 20}).json()["role"] == "student"
    monkeypatch.setattr(settings, "operator_emails", ["ops@hub.vn"])
    _patch_google(monkeypatch, {**GOOGLE, "email": "ops@hub.vn", "sub": "g-9"})
    assert client.post("/api/auth/google", json={"credential": "x" * 20}).json()["role"] == "operator"


def test_google_unverified_email_and_domain_rules(client, monkeypatch):
    _patch_google(monkeypatch, {**GOOGLE, "email_verified": False})
    assert client.post("/api/auth/google", json={"credential": "x" * 20}).status_code == 401
    monkeypatch.setattr(settings, "allowed_student_domains", ["hcmut.edu.vn"])
    _patch_google(monkeypatch, {**GOOGLE, "email": "x@gmail.com"})
    assert client.post("/api/auth/google", json={"credential": "x" * 20}).status_code == 403


def test_google_token_verification_needs_client_id(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    r = client.post("/api/auth/google", json={"credential": "x" * 20})
    assert r.status_code == 503


def test_onboarding_profile_patch(client, monkeypatch):
    _patch_google(monkeypatch, GOOGLE)
    session = client.post("/api/auth/google", json={"credential": "x" * 20}).json()
    h = {"Authorization": f"Bearer {session['token']}"}
    assert client.patch("/api/me", headers=h, json={"student_code": "12"}).status_code == 422
    assert client.patch("/api/me", headers=h, json={"student_code": "2310001"}).status_code == 409  # An's code
    assert client.patch("/api/me", headers=h, json={"phone": "abc"}).status_code == 422
    r = client.patch("/api/me", headers=h, json={"student_code": "2399999", "phone": "0901 234 567", "onboarded": True})
    assert r.status_code == 200
    me = client.get("/api/me", headers=h).json()
    assert me["student_code"] == "2399999" and me["phone"] == "0901234567" and me["onboarded"] is True
