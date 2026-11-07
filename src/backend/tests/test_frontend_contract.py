"""Static checks on the shared frontend (TV5): pages are served, i18n has EN+VI parity for TV5 keys."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]


def i18n_keys():
    text = (SRC / "shared" / "i18n.js").read_text(encoding="utf-8")
    en_start, vi_start = text.index("    en: {"), text.index("    vi: {")
    key = re.compile(r"^\s+'([\w.\-]+)':", re.M)
    return set(key.findall(text[en_start:vi_start])), set(key.findall(text[vi_start:]))


def test_new_pages_are_served(client):
    for page in ("login.html", "onboarding.html", "index.html"):
        assert client.get(f"/app/{page}").status_code == 200
    for js in ("api-client.js", "stream.js", "i18n.js"):
        assert client.get(f"/shared/{js}").status_code == 200


def test_tv5_i18n_keys_exist_in_both_languages():
    en, vi = i18n_keys()
    for ns in ("auth.", "live.", "common.cancel", "common.confirm", "home.signIn"):
        e = {k for k in en if k.startswith(ns)}
        v = {k for k in vi if k.startswith(ns)}
        assert e and e == v, f"{ns}: only in one language -> {e ^ v}"


def test_every_data_i18n_key_used_by_tv5_pages_is_defined():
    en, vi = i18n_keys()
    for page in ("login.html", "onboarding.html"):
        html = (SRC / "frontend" / page).read_text(encoding="utf-8")
        used = set(re.findall(r'data-i18n="([\w.\-]+)"', html)) | set(re.findall(r"Hub\.t\('([\w.\-]+)'", html))
        assert used <= en and used <= vi, f"{page}: missing {used - (en & vi)}"


def test_no_secrets_committed():
    root = SRC.parent
    assert (root / ".env.example").exists()
    assert ".env" in (root / ".gitignore").read_text().splitlines()
    example = (root / ".env.example").read_text()
    assert not re.search(r"GOOGLE_CLIENT_ID=\S", example) and "JWT_SECRET=change-me" in example
