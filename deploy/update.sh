#!/usr/bin/env bash
# In-place HUD update on the Pi (installed as `hud-update`; scripts/deploy.sh
# runs it over ssh from the PC after pushing to GitHub).
#
#   sudo hud-update                 # fast-forward the current branch
#   sudo hud-update --ref <sha>     # deploy an exact commit
#   sudo hud-update --ref feature   # switch to a branch
#   sudo hud-update --force         # rebuild + restart even if already at that ref
#
# fetch → checkout → pip → npm build (only if web/ changed) → restart →
# health check. If the backend doesn't come up, rolls back to the previous
# commit and exits non-zero.
set -euo pipefail

# `hud-update` is a symlink into the repo — resolve it, or HUD_DIR would be
# /usr/local and git would say "not a git repository".
HUD_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
REF=""
FORCE=0
BUILD=1
while [ $# -gt 0 ]; do
    case "$1" in
        --ref) REF="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        --no-build) BUILD=0; shift ;;
        -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done
[ "$(id -u)" -eq 0 ] || { echo "run with sudo (services need root)" >&2; exit 1; }
[ -d "$HUD_DIR/.git" ] || { echo "$HUD_DIR is not a git checkout" >&2; exit 1; }
if [ "$(findmnt -n -o FSTYPE / 2>/dev/null)" = "overlay" ]; then
    echo "root filesystem is in overlayfs (read-only) mode — an update would vanish at reboot." >&2
    echo "disable it first:  sudo raspi-config nonint disable_overlayfs && sudo reboot" >&2
    exit 1
fi

HUD_USER="$(stat -c %U "$HUD_DIR")"
as_user() { sudo -u "$HUD_USER" -H "$@"; }
# Every git call runs as the repo owner: root would trip git's
# "dubious ownership" guard on a user-owned checkout.
g() { as_user git -C "$HUD_DIR" "$@"; }
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

# One update at a time — two runs must not interleave.
exec 9>/run/lock/hud-update.lock
flock -n 9 || { echo "another hud-update is running" >&2; exit 1; }

cd "$HUD_DIR"
PREV="$(g rev-parse HEAD)"
BRANCH="$(g rev-parse --abbrev-ref HEAD)"   # "HEAD" when detached
[ -n "$REF" ] || REF="${BRANCH/HEAD/main}"

log "fetching origin"
g fetch -q --prune origin

# Branch name → track origin/<branch>; anything else → detached at that commit.
# -f: the deploy target's working tree is disposable — git is the truth.
if g show-ref -q --verify "refs/remotes/origin/$REF"; then
    g checkout -q -f -B "$REF" "origin/$REF"
else
    g checkout -q -f --detach "$REF"
fi
NEW="$(g rev-parse HEAD)"

if [ "$NEW" = "$PREV" ] && [ "$FORCE" -eq 0 ]; then
    log "already at $(g rev-parse --short HEAD) — nothing to do"
    systemctl is-active -q hud-server || systemctl restart hud-server
    exit 0
fi
log "updating $(g rev-parse --short "$PREV") → $(g rev-parse --short "$NEW")"

changed() { [ "$FORCE" -eq 1 ] || ! g diff --quiet "$PREV" "$NEW" -- "$@"; }

install_and_build() {
    if changed pyproject.toml hud/; then
        log "python deps"
        as_user "$HUD_DIR/.venv/bin/pip" install -q -e "$HUD_DIR[vehicle]"
    fi
    if [ "$BUILD" -eq 1 ] && { changed web/ || [ ! -d web/dist ]; }; then
        log "frontend build"
        as_user bash -c "cd '$HUD_DIR/web' && npm ci --no-audit --no-fund --loglevel=error && npm run build --silent"
        WEB_CHANGED=1
    fi
    if changed deploy/; then
        log "refreshing systemd units"
        # keep whatever --source the installer chose (auto/elm327/can/sim)
        SRC="$(grep -oE -- '--source [a-z0-9]+' /etc/systemd/system/hud-server.service 2>/dev/null | head -1 || true)"
        SRC="${SRC:---source auto}"
        for unit in hud-server hud-kiosk; do
            [ -f "/etc/systemd/system/$unit.service" ] || continue
            sed -e "s|__HUD_DIR__|$HUD_DIR|g" -e "s|__USER__|$HUD_USER|g" \
                -e "s|--source auto|$SRC|g" \
                "deploy/$unit.service" > "/etc/systemd/system/$unit.service"
        done
        cp deploy/can0.service /etc/systemd/system/
        cp deploy/99-obd-elm327.rules /etc/udev/rules.d/
        chmod +x deploy/kiosk.sh deploy/update.sh
        systemctl daemon-reload
        udevadm control --reload-rules
    fi
}

healthy() {
    for _ in $(seq 1 30); do
        curl -sf http://localhost:8000/api/config >/dev/null 2>&1 && return 0
        sleep 1
    done
    return 1
}

restart_services() {
    systemctl restart hud-server
    if [ "${WEB_CHANGED:-0}" -eq 1 ] && systemctl is-active -q hud-kiosk; then
        systemctl restart hud-kiosk   # load the new bundle
    fi
}

WEB_CHANGED=0
if install_and_build && restart_services && healthy; then
    log "deployed $(g rev-parse --short HEAD) — backend healthy"
    exit 0
fi

# ---- rollback ---------------------------------------------------------------
log "!! backend unhealthy after update — last log lines:"
journalctl -u hud-server -n 40 --no-pager || true
log "rolling back to $(g rev-parse --short "$PREV")"
if [ "$BRANCH" != "HEAD" ]; then
    g checkout -q -f -B "$BRANCH" "$PREV"
else
    g checkout -q -f --detach "$PREV"
fi
NEW="$PREV"; PREV="$(g rev-parse HEAD)"; FORCE=1
install_and_build || true
restart_services || true
if healthy; then
    log "rollback OK — running $(g rev-parse --short HEAD); the new commit is NOT deployed"
else
    log "!! rollback also unhealthy — inspect journalctl -u hud-server"
fi
exit 1
