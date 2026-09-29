#!/bin/bash
# Creates relay/.env with fresh seat tokens (never committed). Idempotent.
cd "$(dirname "$0")"
[ -f .env ] && { echo ".env exists"; exit 0; }
t() { python3 -c 'import secrets;print(secrets.token_urlsafe(24))'; }
umask 077
cat > .env <<E
GOLDEN_PORT=8490
GOLDEN_TOKEN_R=$(t)
GOLDEN_TOKEN_N=$(t)
GOLDEN_TOKEN_APP=$(t)
GOLDEN_TOKEN_WATCHER=$(t)
E
echo "wrote relay/.env"
