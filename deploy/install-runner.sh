#!/usr/bin/env bash
# Register this Pi as a GitHub Actions self-hosted runner (label: hud-pi) so
# every push to main deploys itself via .github/workflows/deploy.yml.
#
#   sudo bash deploy/install-runner.sh \
#       --repo https://github.com/<you>/hud_toyota --token <REGISTRATION_TOKEN>
#
# Token: GitHub → your repo → Settings → Actions → Runners → "New self-hosted
# runner" → Linux / ARM64 — copy the token from the `./config.sh --token ...`
# line. It expires after an hour; rerun this script with a fresh one if so.
#
# Runs as the HUD service user (the repo dir's owner). Outbound HTTPS only —
# no inbound port, works from behind the car hotspot / LTE. Jobs queued while
# the car is off run when the Pi next boots online (GitHub holds them ~24 h).
set -euo pipefail

REPO=""
TOKEN=""
RUNNER_DIR="/opt/actions-runner"
LABELS="hud-pi"
HUD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
while [ $# -gt 0 ]; do
    case "$1" in
        --repo) REPO="$2"; shift 2 ;;
        --token) TOKEN="$2"; shift 2 ;;
        --dir) RUNNER_DIR="$2"; shift 2 ;;
        --labels) LABELS="$2"; shift 2 ;;
        --remove) REMOVE=1; shift ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
RUN_USER="$(stat -c %U "$HUD_DIR")"

if [ "${REMOVE:-0}" -eq 1 ]; then
    [ -n "$TOKEN" ] || { echo "--remove needs --token (a removal token from the runner's page)" >&2; exit 2; }
    cd "$RUNNER_DIR"
    ./svc.sh stop || true
    ./svc.sh uninstall || true
    sudo -u "$RUN_USER" ./config.sh remove --token "$TOKEN"
    echo "runner removed"
    exit 0
fi
[ -n "$REPO" ] && [ -n "$TOKEN" ] || { echo "need --repo and --token (see --help)" >&2; exit 2; }

case "$(uname -m)" in
    aarch64) ARCH=arm64 ;;
    armv7l) ARCH=arm ;;
    x86_64) ARCH=x64 ;;
    *) echo "unsupported arch $(uname -m)" >&2; exit 1 ;;
esac

# Latest runner release (fallback pin if the API is unreachable).
VERSION="$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest 2>/dev/null \
    | grep -m1 '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/' || true)"
VERSION="${VERSION:-2.325.0}"
TARBALL="actions-runner-linux-${ARCH}-${VERSION}.tar.gz"

echo "==> installing actions-runner $VERSION ($ARCH) to $RUNNER_DIR as $RUN_USER"
mkdir -p "$RUNNER_DIR"
chown "$RUN_USER:$RUN_USER" "$RUNNER_DIR"
cd "$RUNNER_DIR"
if [ ! -f ./config.sh ]; then
    sudo -u "$RUN_USER" curl -fsSL -o "$TARBALL" \
        "https://github.com/actions/runner/releases/download/v${VERSION}/${TARBALL}"
    sudo -u "$RUN_USER" tar xzf "$TARBALL"
    rm -f "$TARBALL"
fi
./bin/installdependencies.sh >/dev/null

# Re-registering replaces a stale entry with the same name (e.g. after reflash).
if [ -f .runner ]; then
    ./svc.sh stop 2>/dev/null || true
    ./svc.sh uninstall 2>/dev/null || true
fi
sudo -u "$RUN_USER" ./config.sh --unattended --replace \
    --url "$REPO" --token "$TOKEN" \
    --name "hud-pi-$(hostname)" --labels "$LABELS" --work _work

./svc.sh install "$RUN_USER"
./svc.sh start

# The deploy job calls `sudo /opt/hud/deploy/update.sh` — install.sh already
# granted that passwordless; make sure it's there for older installs too.
if ! grep -qs "deploy/update.sh" /etc/sudoers.d/hud 2>/dev/null; then
    echo "$RUN_USER ALL=(root) NOPASSWD: $HUD_DIR/deploy/update.sh" > /etc/sudoers.d/hud
    chmod 0440 /etc/sudoers.d/hud
    visudo -cf /etc/sudoers.d/hud >/dev/null
fi

cat <<DONE

Runner "hud-pi-$(hostname)" is online (service: $(./svc.sh status 2>/dev/null | grep -m1 -oE 'active \([a-z]+\)' || echo 'see ./svc.sh status')).
Push to main → the workflow's deploy job runs here: sudo $HUD_DIR/deploy/update.sh --ref <sha>
Check: GitHub → Settings → Actions → Runners (idle/green), and Actions tab after a push.
DONE
