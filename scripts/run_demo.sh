#!/usr/bin/env bash
# One command from a clean machine:   scripts/run_demo.sh [--tunnel] [--fresh]
#   --fresh   delete data/hub.db first (start from the seed data)
#   --tunnel  also open an HTTPS tunnel (cloudflared or ngrok) so a real phone can use
#             geolocation, Google Sign-In and PWA install (all need HTTPS).
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  secret=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
  sed -i.bak "s|^JWT_SECRET=.*|JWT_SECRET=${secret}|" .env && rm -f .env.bak
  echo "Created .env with a fresh JWT_SECRET. Add GOOGLE_CLIENT_ID to enable Google login."
fi

for arg in "$@"; do
  [ "$arg" = "--fresh" ] && rm -f data/hub.db data/hub.db-wal data/hub.db-shm && echo "Database deleted."
done

if [[ " $* " == *" --tunnel "* ]]; then
  if command -v cloudflared >/dev/null; then
    (cloudflared tunnel --url http://localhost:8000 2>&1 | grep -m1 -o 'https://[a-z0-9-]*\.trycloudflare\.com' | sed 's/^/HTTPS URL for phones: /') &
  elif command -v ngrok >/dev/null; then
    (ngrok http 8000 --log=stdout >/dev/null &) ; echo "ngrok started: open http://localhost:4040 to see the HTTPS URL"
  else
    echo "Install cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) or ngrok for --tunnel."
  fi
  echo "Remember: add the HTTPS URL to 'Authorised JavaScript origins' of your Google OAuth client."
fi

echo "Open http://localhost:8000/app/login.html   (API docs: /docs)"
exec uvicorn src.backend.app:app --host 0.0.0.0 --port 8000
