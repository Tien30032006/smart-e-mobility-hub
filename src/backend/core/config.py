"""Runtime settings read from environment / .env. SHARED FILE (owner: TV5).

Secrets (JWT_SECRET, PAYMENT_SECRET) live only in .env - never commit it.
Only ``.env.example`` is committed.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str) -> list[str]:
    return [x.strip().lower() for x in os.getenv(name, "").split(",") if x.strip()]


@dataclass
class Settings:
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", True))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET") or secrets.token_urlsafe(32))
    jwt_ttl_minutes: int = field(default_factory=lambda: int(os.getenv("JWT_TTL_MINUTES", "720")))
    google_client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_ID", ""))
    operator_emails: list[str] = field(default_factory=lambda: _list("OPERATOR_EMAILS"))
    allowed_student_domains: list[str] = field(default_factory=lambda: _list("ALLOWED_STUDENT_DOMAINS"))
    # --- password reset email (SMTP) ---
    public_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", "").rstrip("/"))
    password_reset_local_url: str = field(default_factory=lambda: os.getenv(
        "PASSWORD_RESET_LOCAL_URL", "http://localhost:8000").rstrip("/"))
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_username: str = field(default_factory=lambda: os.getenv("SMTP_USERNAME", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_from: str = field(default_factory=lambda: os.getenv("SMTP_FROM", ""))
    smtp_starttls: bool = field(default_factory=lambda: _bool("SMTP_STARTTLS", True))
    # --- database (SQLite file; ":memory:" disables persistence) ---
    database_path: str = field(default_factory=lambda: os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "hub.db")))
    persist_interval_seconds: float = field(default_factory=lambda: float(os.getenv("PERSIST_INTERVAL_SECONDS", "5")))
    # --- simulator ---
    simulator_enabled: bool = field(default_factory=lambda: _bool("SIMULATOR_ENABLED", True))
    simulator_seed: int = field(default_factory=lambda: int(os.getenv("SIMULATOR_SEED", "2026")))
    simulator_interval_seconds: float = field(default_factory=lambda: float(os.getenv("SIMULATOR_INTERVAL", "4")))
    simulator_fault_probability: float = field(default_factory=lambda: float(os.getenv("SIMULATOR_FAULT_PROBABILITY", "0.02")))
    simulator_rush_hour: str = field(default_factory=lambda: os.getenv("SIMULATOR_RUSH_HOUR", "auto"))  # auto|on|off

    @property
    def persistence_enabled(self) -> bool:
        return self.database_path != ":memory:"

    @property
    def password_reset_email_enabled(self) -> bool:
        parsed = urlparse(self.public_base_url)
        secure_origin = parsed.scheme == "https" or (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"})
        valid_origin = secure_origin and bool(parsed.netloc) and parsed.path in {"", "/"} \
            and not parsed.query and not parsed.fragment
        return valid_origin and all((self.smtp_host, self.smtp_username,
                                     self.smtp_password, self.smtp_from))


settings = Settings()
