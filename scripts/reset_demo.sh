#!/usr/bin/env bash
# Put the running server back to the seed data between rehearsals (needs DEMO_MODE=true).
set -euo pipefail
BASE="${1:-http://localhost:8000}"
TOKEN=$(curl -fsS -X POST "$BASE/api/auth/demo-login" -H 'content-type: application/json' \
        -d '{"email":"operator@hub.vn"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -fsS -X POST "$BASE/api/demo/reset" -H "Authorization: Bearer $TOKEN"; echo
