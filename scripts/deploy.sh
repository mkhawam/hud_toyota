#!/usr/bin/env bash
# Deploy from the dev PC over the home network: push this branch to GitHub,
# then have the Pi pull, rebuild, restart, and health-check itself via its
# own updater (deploy/update.sh, installed on the Pi as `hud-update`).
#
#   scripts/deploy.sh                          # current branch → dominus@hud
#   scripts/deploy.sh --ref main --no-push     # deploy what's already on GitHub
#   scripts/deploy.sh --host pi@other-hud
#
# Needs: `ssh <host>` with keys, and the Pi able to reach GitHub (home Wi-Fi).
# From PowerShell the equivalent is just:  ssh dominus@hud sudo hud-update
set -euo pipefail

HOST="${HUD_HOST:-dominus@hud}"
REF=""
PUSH=1
while [ $# -gt 0 ]; do
    case "$1" in
        --host) HOST="$2"; shift 2 ;;
        --ref) REF="$2"; shift 2 ;;
        --no-push) PUSH=0; shift ;;
        -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[ -n "$REF" ] || REF="$BRANCH"

if [ "$PUSH" -eq 1 ]; then
    if [ -n "$(git status --porcelain)" ]; then
        echo "!! uncommitted changes — commit first, or --no-push to deploy what's on GitHub" >&2
        exit 1
    fi
    echo "==> pushing $BRANCH to origin"
    git push -q origin "$BRANCH"
fi

echo "==> $HOST: sudo hud-update --ref $REF"
ssh "$HOST" "sudo hud-update --ref '$REF'"
