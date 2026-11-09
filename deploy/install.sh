#!/usr/bin/env bash
# Turnkey Raspberry Pi install for the HUD. Run on a fresh Raspberry Pi OS
# Lite (64-bit) either straight from GitHub:
#
#   curl -fsSL https://raw.githubusercontent.com/mkhawam/hud_toyota/main/deploy/install.sh \
#       | sudo bash -s -- --repo https://github.com/mkhawam/hud_toyota.git --can-hat pican2
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
#   --no-display      headless: backend + settings server only, no native HUD on HDMI
#   --ap-ssid NAME    Wi-Fi network the Pi broadcasts when no known Wi-Fi is in range
#                     (default HUD-<hostname>); phone joins it in the car for settings
#   --ap-password PW  its WPA2 password (default: kept from a previous install, else random)
#   --no-ap           don't create the fallback access point
#   --hdmi-mode M     force the HDMI output on at boot: auto (detect the attached
#                     panel's mode, default) | 640x480@60 | none. Cures panels that
#                     stay black until an HDMI replug.
#   --no-start        install but don't start services now
#
# Idempotent: re-running updates packages/units in place. Later updates go
# through deploy/update.sh (installed as `hud-update`), run over ssh from
# the PC by scripts/deploy.sh.
set -euo pipefail

HUD_REPO="${HUD_REPO:-https://github.com/mkhawam/hud_toyota.git}"
HUD_DIR="/opt/hud"
BRANCH="main"
HUD_USER="${SUDO_USER:-pi}"
SOURCE="auto"
CAN_HAT="none"
HDMI_MODE="auto"
KIOSK=1
AP=1
AP_SSID=""
AP_PASS=""
START=1

while [ $# -gt 0 ]; do
    case "$1" in
        --repo) HUD_REPO="$2"; shift 2 ;;
        --dir) HUD_DIR="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        --user) HUD_USER="$2"; shift 2 ;;
        --source) SOURCE="$2"; shift 2 ;;
        --can-hat) CAN_HAT="$2"; shift 2 ;;
        --hdmi-mode) HDMI_MODE="$2"; shift 2 ;;
        --no-display|--no-kiosk) KIOSK=0; shift ;;
        --ap-ssid) AP_SSID="$2"; shift 2 ;;
        --ap-password) AP_PASS="$2"; shift 2 ;;
        --no-ap) AP=0; shift ;;
        --no-start) START=0; shift ;;
        -h|--help) sed -n '2,29p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
[ "$HUD_USER" != "root" ] || HUD_USER="pi"
id "$HUD_USER" >/dev/null 2>&1 || { echo "user $HUD_USER does not exist (use --user)" >&2; exit 1; }
# The native HUD needs DRM + input device access; dialout for the ELM327 serial port.
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
PKGS="git python3-venv python3-pip can-utils curl ca-certificates avahi-daemon"
# shellcheck disable=SC2086
apt-get install -y -qq $PKGS
if [ "$KIOSK" -eq 1 ]; then
    # Native HUD: PySide6 + QML from Debian (Qt built for the Pi's GPU), used
    # by the venv via system site-packages. Names vary a little between
    # releases, so install what exists and verify the import afterwards.
    for pkg in python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtqml \
               python3-pyside6.qtquick python3-pyside6.qtnetwork qt6-qpa-plugins \
               qml6-module-qtquick qml6-module-qtquick-window qml6-module-qtquick-shapes \
               qml6-module-qtquick-effects qml6-module-qtqml-workerscript \
               qml6-module-qtquick-templates qml6-module-qtqml; do
        apt-get install -y -qq "$pkg" >/dev/null 2>&1 || echo "   (no apt package $pkg)"
    done
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
sudo -u "$HUD_USER" python3 -m venv --system-site-packages "$HUD_DIR/.venv"
sed -i "s/^include-system-site-packages = false/include-system-site-packages = true/" "$HUD_DIR/.venv/pyvenv.cfg"
sudo -u "$HUD_USER" "$HUD_DIR/.venv/bin/pip" install -q --upgrade pip
sudo -u "$HUD_USER" "$HUD_DIR/.venv/bin/pip" install -q -e "$HUD_DIR[vehicle]"
if [ "$KIOSK" -eq 1 ]; then
    QT_CHECK='from PySide6.QtQuick import QQuickView; from PySide6.QtQml import QQmlPropertyMap'
    if ! sudo -u "$HUD_USER" QT_QPA_PLATFORM=offscreen "$HUD_DIR/.venv/bin/python" -c "$QT_CHECK" 2>/dev/null; then
        log "apt PySide6 incomplete - installing PySide6 from PyPI into the venv"
        sudo -u "$HUD_USER" "$HUD_DIR/.venv/bin/pip" install -q "PySide6>=6.6"
    fi
    sudo -u "$HUD_USER" QT_QPA_PLATFORM=offscreen "$HUD_DIR/.venv/bin/python" -c "$QT_CHECK" \
        && echo "   PySide6 OK" || { echo "!! PySide6/QtQuick unavailable" >&2; exit 1; }
fi

log "frontend build"
sudo -u "$HUD_USER" bash -c "cd '$HUD_DIR/web' && npm ci --no-audit --no-fund --loglevel=error && npm run build --silent"

sudo -u "$HUD_USER" mkdir -p "$HUD_DIR/data" "$HUD_DIR/cache"

# ---- udev + systemd --------------------------------------------------------
log "udev rule (/dev/ttyOBD)"
cp "$HUD_DIR/deploy/99-obd-elm327.rules" /etc/udev/rules.d/
udevadm control --reload-rules

log "systemd units (user=$HUD_USER, source=$SOURCE)"
if [ "$KIOSK" -eq 1 ]; then
    sed -e "s|__HUD_DIR__|$HUD_DIR|g" -e "s|__USER__|$HUD_USER|g" \
        -e "s|--source auto|--source $SOURCE|g" \
        "$HUD_DIR/deploy/hud-server.service" > /etc/systemd/system/hud-server.service
else
    sed -e "s|__HUD_DIR__|$HUD_DIR|g" -e "s|__USER__|$HUD_USER|g" \
        -e "s|--source auto|--source $SOURCE|g" -e "s| --ui||" \
        -e "/# ---- DISPLAY ----/,/# ---- END DISPLAY ----/d" \
        "$HUD_DIR/deploy/hud-server.service" > /etc/systemd/system/hud-server.service
fi
# migrate from the old browser kiosk (cage + Chromium), now replaced by the native UI
if [ -f /etc/systemd/system/hud-kiosk.service ]; then
    log "removing the old Chromium kiosk unit"
    systemctl disable --now -q hud-kiosk 2>/dev/null || true
    rm -f /etc/systemd/system/hud-kiosk.service
fi
cp "$HUD_DIR/deploy/can0.service" /etc/systemd/system/
chmod +x "$HUD_DIR/deploy/update.sh"
systemctl daemon-reload
systemctl enable -q hud-server can0

# `hud-update` from anywhere; passwordless for the service user so
# `ssh hud sudo hud-update` from the PC never stops at a password prompt.
ln -sf "$HUD_DIR/deploy/update.sh" /usr/local/bin/hud-update
# `hud-view`: the HUD as text in a terminal (handy over ssh)
chmod +x "$HUD_DIR/deploy/hud-view.sh"
ln -sf "$HUD_DIR/deploy/hud-view.sh" /usr/local/bin/hud-view
{
    echo "$HUD_USER ALL=(root) NOPASSWD: $HUD_DIR/deploy/update.sh, /usr/local/bin/hud-update"
    echo "$HUD_USER ALL=(root) NOPASSWD: /bin/systemctl restart hud-server, /bin/systemctl status hud-server"
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
    # A desktop image (lightdm autologin → labwc on tty7) owns the seat, and
    # the HUD on tty1 would never get the screen. Boot to console.
    if [ "$(systemctl get-default)" = "graphical.target" ] || systemctl is-active -q display-manager 2>/dev/null; then
        log "desktop image detected — switching to console boot (the HUD owns the screen)"
        if command -v raspi-config >/dev/null 2>&1; then
            raspi-config nonint do_boot_behaviour B1
        else
            systemctl set-default multi-user.target
            systemctl disable lightdm 2>/dev/null || true
        fi
        REBOOT_NEEDED=1
    fi
    # Black screen until the HUD appears: no rainbow splash, no Plymouth
    # logo, no kernel chatter, no blinking console cursor.
    add_boot_line "disable_splash=1"
    CMDLINE="$(dirname "$CONFIG_TXT")/cmdline.txt"
    if [ -f "$CMDLINE" ]; then
        if grep -qw splash "$CMDLINE"; then
            sed -i "s/ splash//; s/ plymouth.ignore-serial-consoles//" "$CMDLINE"
            REBOOT_NEEDED=1
        fi
        for opt in quiet vt.global_cursor_default=0; do
            if ! grep -qw "$opt" "$CMDLINE"; then
                sed -i "1s/\$/ $opt/" "$CMDLINE"
                REBOOT_NEEDED=1
            fi
        done
        # Force the HDMI output on at a fixed mode ("D" = drive it even without
        # a hotplug/EDID handshake). Cheap panels otherwise stay black at boot
        # until the cable is replugged.
        if [ "$HDMI_MODE" != "none" ] && ! grep -q "video=HDMI-A-" "$CMDLINE"; then
            CONN=""; MODE="$HDMI_MODE"
            for st in /sys/class/drm/card*-HDMI-A-*/status; do
                if grep -qs '^connected' "$st"; then
                    CONN="$(basename "$(dirname "$st")" | sed 's/^card[0-9]*-//')"
                    [ "$MODE" = "auto" ] && MODE="$(head -1 "$(dirname "$st")/modes")@60"
                    break
                fi
            done
            if [ -n "$CONN" ] && [ "$MODE" != "auto" ] && [ "$MODE" != "@60" ]; then
                log "forcing HDMI output: $CONN at $MODE"
                sed -i "1s/\$/ video=$CONN:${MODE}D/" "$CMDLINE"
                REBOOT_NEEDED=1
            else
                echo "note: no HDMI panel detected now — re-run with --hdmi-mode 640x480@60 (etc.) with the panel attached"
            fi
        fi
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

# ---- fallback Wi-Fi access point ---------------------------------------------
# NetworkManager connection at the lowest autoconnect priority: at boot the
# Pi joins any known network (home Wi-Fi, phone hotspot) when one is in
# range, and otherwise broadcasts its own, so the phone settings page is
# reachable in the car with no other network. Not activated now (that would
# drop an ssh session over Wi-Fi); it takes over on the first boot away from home.
if [ "$AP" -eq 1 ] && command -v nmcli >/dev/null 2>&1; then
    WIFI_IF="$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="wifi"{print $1; exit}')"
    if [ -n "$WIFI_IF" ]; then
        PREV_PASS="$(sudo -u "$HUD_USER" "$HUD_DIR/.venv/bin/python" -c \
            "from hud.core.config import Config; print(Config.load('$HUD_DIR/config/hud.yaml').get('wifi_ap.password') or '')" 2>/dev/null || true)"
        [ -n "$AP_SSID" ] || AP_SSID="HUD-$(hostname)"
        [ -n "$AP_PASS" ] || AP_PASS="$PREV_PASS"
        # (pipefail off in this subshell: head closing the pipe SIGPIPEs tr)
        [ -n "$AP_PASS" ] || AP_PASS="$(set +o pipefail; tr -dc 'a-z2-9' < /dev/urandom | head -c 10)"
        [ "${#AP_PASS}" -ge 8 ] || { echo "--ap-password must be at least 8 characters" >&2; exit 2; }
        log "fallback access point: $AP_SSID on $WIFI_IF"
        nmcli connection delete hud-ap >/dev/null 2>&1 || true
        nmcli connection add type wifi ifname "$WIFI_IF" con-name hud-ap ssid "$AP_SSID" \
            autoconnect yes connection.autoconnect-priority -100 \
            802-11-wireless.mode ap 802-11-wireless.band bg \
            ipv4.method shared ipv6.method disabled \
            wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$AP_PASS" >/dev/null
        # the HUD menu shows these on the windshield
        sudo -u "$HUD_USER" "$HUD_DIR/.venv/bin/python" -c \
            "from hud.core.config import Config; Config.load('$HUD_DIR/config/hud.yaml').save_section('wifi_ap', {'ssid': '$AP_SSID', 'password': '$AP_PASS'})"
    else
        echo "note: no Wi-Fi interface - skipping the fallback access point"
    fi
fi

# ---- start -------------------------------------------------------------------
if [ "$START" -eq 1 ]; then
    log "starting services"
    systemctl restart hud-server
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

  HUD ......... native, on HDMI (OK = menu, C = calibrate)
  settings .... http://<pi-ip>:8000/settings
  drives ...... http://<pi-ip>:8000/trips
  update ...... sudo hud-update              (or from the PC: scripts/deploy.sh)
  logs ........ journalctl -u hud-server -f
${AP_SSID:+  in the car .. join Wi-Fi $AP_SSID (password $AP_PASS), then http://10.42.0.1:8000/settings
}
DONE
if [ "$REBOOT_NEEDED" -eq 1 ]; then
    echo "!! $CONFIG_TXT changed — reboot to apply (sudo reboot)"
elif [ "$CAN_HAT" = "none" ]; then
    echo "note: no CAN HAT overlay written — re-run with --can-hat pican2|waveshare when the HAT arrives"
fi
