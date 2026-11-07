"""E-mail + password registration and login (TV5), and how it interacts with Google / persistence."""
import sqlite3

import jwt
import pytest

from src.backend.core import auth as core_auth
from src.backend.core.config import settings
from src.backend.core.database import Persistence
from src.backend.core.state_manager import HubNetworkManager, network

NEW = {"full_name": "Le Minh Chau", "email": "Chau@Example.com", "password": "matkhau123"}


@pytest.fixture(autouse=True)
def _clean_throttle():
    core_auth.reset_throttle()
    yield
    core_auth.reset_throttle()


def register(client, **over):
    return client.post("/api/auth/register", json={**NEW, **over})


def login(client, email="chau@example.com", password="matkhau123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---- register -----------------------------------------------------------------
def test_register_creates_student_that_must_onboard(client):
    r = register(client)
    assert r.status_code == 201
    data = r.json()
    assert data["role"] == "student" and data["email"] == "chau@example.com" and data["onboarded"] is False
    assert jwt.decode(data["token"], settings.jwt_secret, algorithms=["HS256"])["sub"] == data["user_id"]
    me = client.get("/api/me", headers=bearer(data["token"])).json()
    assert me["has_password"] is True and me["has_google"] is False and me["onboarded"] is False


def test_password_is_hashed_and_never_returned(client):
    r = register(client)
    stored = network.users[r.json()["user_id"]]._db["password_hash"]
    assert stored.startswith("pbkdf2_sha256$") and "matkhau123" not in stored
    assert "matkhau123" not in r.text and "password_hash" not in r.text


@pytest.mark.parametrize("over,code", [
    ({"password": "short1"}, 422), ({"password": "onlyletters"}, 422), ({"password": "12345678"}, 422),
    ({"password": "x" * 129 + "1"}, 422),
    ({"email": "not-an-email"}, 422), ({"full_name": " "}, 422), ({"full_name": "A"}, 422),
    ({"email": "an@hcmut.edu.vn"}, 409),                      # seeded account
])
def test_register_validation(client, over, code):
    assert register(client, **over).status_code == code


def test_register_duplicate_email_ignores_case(client):
    assert register(client).status_code == 201
    assert register(client, email="CHAU@example.com").status_code == 409


def test_register_cannot_become_operator(client, monkeypatch):
    assert register(client, email="ops@hub.vn").json()["role"] == "student"
    monkeypatch.setattr(settings, "operator_emails", ["boss@hub.vn"])
    assert register(client, email="boss@hub.vn").status_code == 403


def test_register_respects_allowed_domains(client, monkeypatch):
    monkeypatch.setattr(settings, "allowed_student_domains", ["hcmut.edu.vn"])
    assert register(client).status_code == 403
    assert register(client, email="ok@hcmut.edu.vn").status_code == 201


# ---- login --------------------------------------------------------------------
def test_login_with_password(client):
    register(client)
    r = login(client, email="CHAU@example.com")
    assert r.status_code == 200 and r.json()["role"] == "student"
    assert client.get("/api/me", headers=bearer(r.json()["token"])).status_code == 200


def test_wrong_password_and_unknown_email_are_indistinguishable(client):
    register(client)
    a, b = login(client, password="wrong-pass1"), login(client, email="ghost@example.com", password="wrong-pass1")
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_seeded_and_google_only_accounts_cannot_use_password_login(client):
    assert login(client, email="an@hcmut.edu.vn", password="anything1").status_code == 401
    assert login(client, email="an@hcmut.edu.vn", password="").status_code == 401


def test_login_is_throttled(client):
    register(client)
    for _ in range(5):
        assert login(client, password="bad-pass-1").status_code == 401
    assert login(client).status_code == 429                   # even the right password waits
    core_auth.reset_throttle()
    assert login(client).status_code == 200


def test_legacy_email_only_login_still_works_in_demo_mode_only(client, monkeypatch):
    assert client.post("/api/auth/login", json={"email": "an@hcmut.edu.vn"}).status_code == 200
    register(client)
    assert client.post("/api/auth/login", json={"email": "chau@example.com"}).status_code == 401  # not a demo account
    monkeypatch.setattr(settings, "demo_mode", False)
    assert client.post("/api/auth/login", json={"email": "an@hcmut.edu.vn"}).status_code == 403
    assert login(client).status_code == 200                   # password login does not depend on DEMO_MODE


def test_registered_student_completes_onboarding(client):
    tok = register(client).json()["token"]
    r = client.patch("/api/me", headers=bearer(tok), json={"student_code": "2399001", "onboarded": True})
    assert r.status_code == 200 and login(client).json()["onboarded"] is True


def test_student_token_has_no_operator_rights(client):
    tok = register(client).json()["token"]
    assert client.get("/api/demo/simulator", headers=bearer(tok)).status_code == 403


# ---- change / set password ----------------------------------------------------------
def test_change_password(client):
    tok = register(client).json()["token"]
    h = bearer(tok)
    assert client.post("/api/auth/password", headers=h, json={"new_password": "newpass456", "current_password": "nope"}).status_code == 401
    assert client.post("/api/auth/password", headers=h, json={"new_password": "weak"}).status_code == 422
    assert client.post("/api/auth/password", headers=h, json={"new_password": "newpass456", "current_password": "matkhau123"}).status_code == 200
    assert login(client).status_code == 401 and login(client, password="newpass456").status_code == 200
    assert client.post("/api/auth/password", json={"new_password": "newpass456"}).status_code == 401   # needs a token


# ---- Google interplay ------------------------------------------------------------------
def _google(monkeypatch, **claims):
    base = {"sub": "g-77", "email": "chau@example.com", "email_verified": True, "name": "Chau"}
    monkeypatch.setattr(core_auth, "verify_google_token", lambda t: {**base, **claims})


def test_google_login_on_password_account_links_it_and_drops_the_unverified_password(client, monkeypatch):
    uid = register(client).json()["user_id"]
    _google(monkeypatch)
    assert client.post("/api/auth/google", json={"credential": "x" * 20}).json()["user_id"] == uid
    assert network.users[uid]._db["google_sub"] == "g-77"
    assert login(client).status_code == 401                   # pre-registration takeover is closed
    tok = client.post("/api/auth/google", json={"credential": "x" * 20}).json()["token"]
    assert client.post("/api/auth/password", headers=bearer(tok), json={"new_password": "freshpass1"}).status_code == 200
    assert login(client, password="freshpass1").status_code == 200   # Google users can add a password later


def test_second_google_account_cannot_take_over_a_linked_email(client, monkeypatch):
    register(client)
    _google(monkeypatch)
    client.post("/api/auth/google", json={"credential": "x" * 20})
    _google(monkeypatch, sub="g-other")
    assert client.post("/api/auth/google", json={"credential": "x" * 20}).status_code == 409


def test_google_unreachable_gives_503_not_500(client, monkeypatch):
    from google.auth import exceptions as g_exc
    from google.oauth2 import id_token
    monkeypatch.setattr(settings, "google_client_id", "x.apps.googleusercontent.com")
    def offline(*a, **k): raise g_exc.TransportError("offline")
    monkeypatch.setattr(id_token, "verify_oauth2_token", offline)
    assert client.post("/api/auth/google", json={"credential": "x" * 20}).status_code == 503


# ---- persistence --------------------------------------------------------------------------
def test_password_survives_a_restart(client, tmp_path):
    uid = register(client).json()["user_id"]
    db = str(tmp_path / "hub.db")
    p = Persistence(network)
    p.connect(db)
    p.flush()
    net2 = HubNetworkManager()
    p2 = Persistence(net2)
    p2.connect(db)
    assert p2.load()
    stored = net2.users[uid]._db["password_hash"]
    assert core_auth.verify_password("matkhau123", stored) and not core_auth.verify_password("nope", stored)
    p.close(); p2.close()


def test_old_database_without_password_column_is_migrated(tmp_path):
    db = str(tmp_path / "old.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE users (user_id TEXT PRIMARY KEY, role TEXT NOT NULL, full_name TEXT NOT NULL, "
                "email TEXT NOT NULL UNIQUE COLLATE NOCASE, student_code TEXT DEFAULT '', operator_id TEXT DEFAULT '', "
                "phone TEXT DEFAULT '', has_private_ev INTEGER DEFAULT 0, google_sub TEXT, picture TEXT DEFAULT '', "
                "onboarded INTEGER DEFAULT 0, created_at TEXT)")
    con.execute("INSERT INTO users (user_id, role, full_name, email) VALUES ('U-OLD','student','Old User','old@x.vn')")
    con.commit(); con.close()
    p = Persistence(HubNetworkManager())
    p.connect(db)                                              # must not raise
    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(users)")}
    assert "password_hash" in cols
    assert p._conn.execute("SELECT email FROM users").fetchone()[0] == "old@x.vn"   # data kept
    p.close()
