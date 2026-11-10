"""Single-use e-mail password reset links."""
from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
import threading
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException

from . import auth
from .config import settings
from .database import persistence
from .state_manager import network

log = logging.getLogger(__name__)
RESET_TTL_MINUTES = 20
_RATE_WINDOW_SECONDS = 60 * 60
_RATE_LIMITS = {"email": 3, "ip": 30}
_requests: Dict[str, List[float]] = {}
_request_lock = threading.Lock()


def is_enabled() -> bool:
    return settings.password_reset_email_enabled and persistence.enabled


def _allowed(email: str, ip_address: str) -> bool:
    now = time.time()
    keys = ("email:" + email, "ip:" + (ip_address or "unknown"))
    allowed = True
    with _request_lock:
        for key in keys:
            recent = [stamp for stamp in _requests.get(key, []) if now - stamp < _RATE_WINDOW_SECONDS]
            _requests[key] = recent
            if len(recent) >= _RATE_LIMITS[key.split(":", 1)[0]]:
                allowed = False
        if allowed:
            for key in keys:
                _requests[key].append(now)
        if len(_requests) > 10_000:
            for key in list(_requests):
                live = [stamp for stamp in _requests[key] if now - stamp < _RATE_WINDOW_SECONDS]
                if live:
                    _requests[key] = live
                else:
                    _requests.pop(key, None)
    return allowed


def create_reset_email(email: str, ip_address: str) -> Optional[Tuple[str, List[str]]]:
    """Return recipient/link for background delivery, without disclosing account existence."""
    normalized = email.strip().lower()
    if not auth.EMAIL_RE.fullmatch(normalized) or not _allowed(normalized, ip_address):
        return None
    with network.lock:
        user = auth.find_by_email(normalized)
        if user is None or not auth._meta(user).get("password_hash"):
            return None
        user_id, recipient = user.user_id, user.email

    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MINUTES)
    persistence.replace_password_reset_token(user_id, digest, expires_at.isoformat())
    bases = [settings.public_base_url]
    local = settings.password_reset_local_url
    local_origin = urlparse(local)
    if (local_origin.scheme in {"http", "https"}
            and local_origin.hostname in {"localhost", "127.0.0.1"}
            and local_origin.path in {"", "/"}
            and not local_origin.query and not local_origin.fragment
            and local not in bases):
        bases.append(local)
    links = [f"{base}/app/reset-password.html?token={token}" for base in bases]
    return recipient, links


def send_reset_email(recipient: str, links: List[str]) -> None:
    """Send the reset link using the configured authenticated SMTP relay."""
    message = EmailMessage()
    message["Subject"] = "Reset your Smart E-Mobility Hub password"
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message.set_content(
        "We received a request to reset the password for your Smart E-Mobility Hub account.\n\n"
        f"Open one of these one-time links within {RESET_TTL_MINUTES} minutes:\n"
        + "\n".join(f"- {link}" for link in links)
        + "\n\nThe links share the same token; completing the reset with one link invalidates the others.\n"
        "If you did not request this, you can ignore this e-mail."
    )
    safe_links = [escape(link, quote=True) for link in links]
    link_labels = ["Public link (for example, ngrok)", "Local link"]
    html_links = "".join(
        f'<p><a href="{safe_link}">{label}</a></p>'
        for safe_link, label in zip(safe_links, link_labels)
    )
    message.add_alternative(
        "<p>We received a request to reset the password for your Smart E-Mobility Hub account.</p>"
        f"<p>Choose one link. Both expire in {RESET_TTL_MINUTES} minutes and share the same one-time token:</p>"
        f"{html_links}<p>Completing the reset with one link invalidates the others. "
        "If you did not request this, you can ignore this e-mail.</p>",
        subtype="html",
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            if settings.smtp_starttls:
                server.starttls()
                server.ehlo()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except Exception:
        # Do not log recipient, token, or link. The public response remains generic.
        log.exception("Password reset e-mail delivery failed")


def complete_reset(token: str, new_password: str) -> None:
    if not token or len(token) > 200:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    user_id = persistence.password_reset_user(digest)
    user = network.users.get(user_id) if user_id else None
    if user is None or not auth._meta(user).get("password_hash"):
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")

    # Validate before consuming the one-time token so a typo does not waste the link.
    auth.validate_password(new_password, user.email)
    if not persistence.consume_password_reset_token(digest):
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")
    # The one-time e-mail token is the proof of ownership; the user does not know
    # the old password in this flow.
    auth.change_password(user, new_password, verify_current_password=False)
    # Persist the new password and auth-version immediately; a process restart must
    # not restore the previous password after a successful reset response.
    persistence.flush()
