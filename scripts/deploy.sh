#!/bin/bash
# Deploy from the dev PC to the Pi: build the frontend, rsync the repo,
# restart the server.  Usage: scripts/deploy.sh pi@hud.local [/opt/hud]
set -euo pipefail

TARGET="${1:?usage: deploy.sh user@host [remote_dir]}"
REMOTE_DIR="${2:-/opt/hud}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

(cd "$ROOT/web" && npm run build)

rsync -az --delete \
    --exclude .git --exclude .venv --exclude node_modules \
    --exclude __pycache__ --exclude .pytest_cache --exclude .shots \
    "$ROOT/" "$TARGET:$REMOTE_DIR/"

ssh "$TARGET" "sudo systemctl restart hud-server 2>/dev/null || true"
echo "deployed to $TARGET:$REMOTE_DIR"
