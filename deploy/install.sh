#!/usr/bin/env bash
# Turnkey Raspberry Pi install for the HUD. Run on a fresh Raspberry Pi OS
# Lite (64-bit) either straight from GitHub:
#
#   curl -fsSL https://raw.githubusercontent.com/<you>/hud_toyota/main/deploy/install.sh \
#       | sudo bash -s -- --repo https://github.com/<you>/hud_toyota.git --can-hat pican2
#
# or from a checkout:   sudo bash deploy/install.sh [options]
#
# Options:
#   --repo URL        git URL to clone (bootstrap mode; default $HUD_REPO)
#   --dir PATH        install directory            (default /opt/hud)
#   --branch NAME     branch to check out          (default main)
#   --user NAME       service user                 (default: the sudo user, else pi)
#   --source MODE     vehicle source for the service: auto|elm327|can|sim (default auto)
#   --can-hat KIND    pican2 | waveshare | none — writes the MCP2515 overlay (default none)
#   --no-kiosk        skip Chromium/cage (headless box, HUD viewed from another device)
#   --no-start        install but don't start services now
#
# Idempotent: re-running updates packages/units in place. Later updates go
# through deploy/update.sh (installed as `hud-update`) or the GitHub runner.
set -euo pipefail

HUD_REPO="${HUD_REPO:-https://github.com/dominusmars/hud_toyota.git}"
HUD_DIR="/opt/hud"
BRANCH="main"
HUD_USER="${SUDO_USER:-pi}"
SOURCE="auto"
CAN_HAT="none"
KIOSK=1
START=1

while [ $# -gt 0 ]; do
    case "$1" in
        --repo) HUD_REPO="$2"; shift 2 ;;
        --dir) HUD_DIR="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        --user) HUD_USER="$2"; shift 2 ;;
        --source) SOURCE="$2"; shift 2 ;;
        --can-hat) CAN_HAT="$2"; shift 2 ;;
        --no-kiosk) KIOSK=0; shift ;;
        --no-start) START=0; shift ;;
        -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
[ "$HUD_USER" != "root" ] || HUD_USER="pi"
id "$HUD_USER" >/dev/null 2>&1 || { echo "user $HUD_USER does not exist (use --user)" >&2; exit 1; }
# cage needs DRM + input device access; dialout for the ELM327 serial port.
usermod -aG video,input,render,tty,dialout "$HUD_USER" 2>/dev/null || true

log() { printf '\n==> %s\n' "$*"; }

# ---- source tree: running from a checkout, or bootstrap-clone -------------
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$SELF_DIR" ] && [ -f "$SELF_DIR/../pyproject.toml" ]; then
    HUD_DIR="$(cd "$SELF_DIR/.." && pwd)"
    log "installing from checkout at $HUD_DIR"
else
    log "bootstrap: cloning $HUD_REPO ($BRANCH) into $HUD_DIR"
    apt-get update -qq
    apt-get install -y -qq git
    if [ -d "$HUD_DIR/.git" ]; then
        sudo -u "$HUD_USER" git -C "$HUD_DIR" fetch -q origin
        sudo -u "$HUD_USER" git -C "$HUD_DIR" checkout -q -B "$BRANCH" "origin/$BRANCH"
    else
        mkdir -p "$(dirname "$HUD_DIR")"
        git clone -q --branch "$BRANCH" "$HUD_REPO" "$HUD_DIR"
    fi
fi
chown -R "$HUD_USER:$HUD_USER" "$HUD_DIR"
# git refuses to touch a repo owned by another user (CVE-2022-24765); the
# updater runs git as $HUD_USER, but root invocations shouldn't trip either.
git config --global --add safe.directory "$HUD_DIR" 2>/dev/null || true

# ---- system packages -------------------------------------------------------
log "apt packages"
apt-get update -qq
PKGS="git python3-venv python3-pip can-utils curl ca-certificates"
[ "$KIOSK" -eq 1 ] && PKGS="$PKGS cage"
# shellcheck disable=SC2086
apt-get install -y -qq $PKGS
if [ "$KIOSK" -eq 1 ]; then
    apt-get install -y -qq chromium-browser 2>/dev/null || apt-get install -y -qq chromium
fi

# Node 22 LTS (Bookworm's apt nodejs is too old for Vite) so the Pi can
# rebuild its own frontend during updates — no build artifacts to ship.
if ! command -v node >/dev/null 2>&1 || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
    log "Node.js 22 (NodeSource)"
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null
    apt-get install -y -qq nodejs
fi

# ---- python + frontend ----------------------------------------------------
log "python venv"
sudo -u "$HUD_USER" python3 -m venv "$HUD_DIR/.venv"
sudo -u "$HUD_USER" "$HUD_DIR/.venv/bin/pip" install -q --upgrade pip
sudo -u "$HUD_USER" "$HUD_DIR/.venv/bin/pip" install -q -e "$HUD_DIR[vehicle]"

log "frontend build"
sudo -u "$HUD_USER" bash -c "cd '$HUD_DIR/web' && npm ci --no-audit --no-fund --loglevel=error && npm run build --silent"

sudo -u "$HUD_USER" mkdir -p "$HUD_DIR/data" "$HUD_DIR/cache"

# ---- udev + systemd --------------------------------------------------------
log "udev rule (/dev/ttyOBD)"
cp "$HUD_DIR/deploy/99-obd-elm327.rules" /etc/udev/rules.d/
udevadm control --reload-rules

log "systemd units (user=$HUD_USER, source=$SOURCE)"
UNITS="hud-server"
[ "$KIOSK" -eq 1 ] && UNITS="$UNITS hud-kiosk"
for unit in $UNITS; do
    sed -e "s|__HUD_DIR__|$HUD_DIR|g" -e "s|__USER__|$HUD_USER|g" \
        -e "s|--source auto|--source $SOURCE|g" \
        "$HUD_DIR/deploy/$unit.service" > "/etc/systemd/system/$unit.service"
done
cp "$HUD_DIR/deploy/can0.service" /etc/systemd/system/
chmod +x "$HUD_DIR/deploy/kiosk.sh" "$HUD_DIR/deploy/update.sh" "$HUD_DIR/deploy/install-runner.sh"
systemctl daemon-reload
# shellcheck disable=SC2086
systemctl enable -q $UNITS can0

# `hud-update` from anywhere; passwordless for the service user so the
# GitHub runner (and you) can deploy without a root shell.
ln -sf "$HUD_DIR/deploy/update.sh" /usr/local/bin/hud-update
{
    echo "$HUD_USER ALL=(root) NOPASSWD: $HUD_DIR/deploy/update.sh"
    echo "$HUD_USER ALL=(root) NOPASSWD: /bin/systemctl restart hud-server, /bin/systemctl restart hud-kiosk, /bin/systemctl status hud-server, /bin/systemctl status hud-kiosk"
} > /etc/sudoers.d/hud
chmod 0440 /etc/sudoers.d/hud
visudo -cf /etc/sudoers.d/hud >/dev/null

# ---- boot config (Pi 5 USB current, CAN HAT overlay) -----------------------
CONFIG_TXT=/boot/firmware/config.txt
[ -f "$CONFIG_TXT" ] || CONFIG_TXT=/boot/config.txt
REBOOT_NEEDED=0
add_boot_line() {
    if [ -f "$CONFIG_TXT" ] && ! grep -qxF "$1" "$CONFIG_TXT"; then
        echo "$1" >> "$CONFIG_TXT"
        REBOOT_NEEDED=1
    fi
}
if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
    log "Pi 5: lifting the USB current cap (buck converters can't negotiate USB-PD)"
    add_boot_line "usb_max_current_enable=1"
fi
if [ "$KIOSK" -eq 1 ]; then
    # Black screen until the HUD appears: no rainbow splash, no kernel
    # chatter, no blinking console cursor (the kiosk unit owns tty1).
    add_boot_line "disable_splash=1"
    CMDLINE="$(dirname "$CONFIG_TXT")/cmdline.txt"
    if [ -f "$CMDLINE" ]; then
        for opt in quiet vt.global_cursor_default=0; do
            if ! grep -qw "$opt" "$CMDLINE"; then
                sed -i "1s/\$/ $opt/" "$CMDLINE"
                REBOOT_NEEDED=1
            fi
        done
    fi
fi
case "$CAN_HAT" in
    pican2)
        log "CAN HAT overlay: PiCAN2 (16 MHz)"
        add_boot_line "dtparam=spi=on"
        add_boot_line "dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25" ;;
    waveshare)
        log "CAN HAT overlay: Waveshare (12 MHz)"
        add_boot_line "dtparam=spi=on"
        add_boot_line "dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25" ;;
    none) ;;
    *) echo "unknown --can-hat $CAN_HAT (pican2|waveshare|none)" >&2; exit 2 ;;
esac

# ---- start -------------------------------------------------------------------
if [ "$START" -eq 1 ]; then
    log "starting services"
    systemctl restart hud-server
    if [ "$KIOSK" -eq 1 ]; then systemctl restart hud-kiosk; fi
    systemctl start can0 2>/dev/null || true   # fails harmlessly until the overlay is live
    for _ in $(seq 1 30); do
        curl -sf http://localhost:8000/api/config >/dev/null 2>&1 && break
        sleep 1
    done
    if curl -sf http://localhost:8000/api/config >/dev/null 2>&1; then
        echo "backend healthy: http://$(hostname -I | awk '{print $1}'):8000"
    else
        echo "backend not responding — journalctl -u hud-server -n 50" >&2
        exit 1
    fi
fi

cat <<DONE

Installed $(git -C "$HUD_DIR" rev-parse --short HEAD) at $HUD_DIR (user $HUD_USER, source $SOURCE).

  HUD ......... http://<pi-ip>:8000          (kiosk shows it on tty1)
  settings .... http://<pi-ip>:8000/settings
  drives ...... http://<pi-ip>:8000/trips
  update ...... sudo hud-update              (or push to main with the runner: deploy/install-runner.sh)
  logs ........ journalctl -u hud-server -f

DONE
if [ "$REBOOT_NEEDED" -eq 1 ]; then
    echo "!! $CONFIG_TXT changed — reboot to apply (sudo reboot)"
elif [ "$CAN_HAT" = "none" ]; then
    echo "note: no CAN HAT overlay written — re-run with --can-hat pican2|waveshare when the HAT arrives"
fi
