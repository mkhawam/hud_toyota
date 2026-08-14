#!/bin/bash
# Pi setup: run once on the Raspberry Pi from the repo root (any location).
#   sudo bash deploy/install.sh
# Installs system packages, the Python venv, udev rule, and systemd units
# (paths and user substituted into the unit templates).
set -euo pipefail

HUD_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HUD_USER="${SUDO_USER:-pi}"

echo "==> HUD dir: $HUD_DIR  user: $HUD_USER"

echo "==> apt packages"
apt-get update -qq
apt-get install -y -qq python3-venv cage can-utils curl \
    chromium-browser 2>/dev/null || apt-get install -y -qq chromium

echo "==> python venv"
sudo -u "$HUD_USER" python3 -m venv "$HUD_DIR/.venv"
sudo -u "$HUD_USER" "$HUD_DIR/.venv/bin/pip" install -q -e "$HUD_DIR[vehicle]"

if [ ! -d "$HUD_DIR/web/dist" ]; then
    echo "!! web/dist missing — build on your PC (cd web && npm run build) and redeploy"
fi

echo "==> udev rule (/dev/ttyOBD)"
cp "$HUD_DIR/deploy/99-obd-elm327.rules" /etc/udev/rules.d/
udevadm control --reload-rules

echo "==> systemd units"
for unit in hud-server hud-kiosk; do
    sed -e "s|__HUD_DIR__|$HUD_DIR|g" -e "s|__USER__|$HUD_USER|g" \
        "$HUD_DIR/deploy/$unit.service" > "/etc/systemd/system/$unit.service"
done
cp "$HUD_DIR/deploy/can0.service" /etc/systemd/system/
chmod +x "$HUD_DIR/deploy/kiosk.sh"
systemctl daemon-reload
systemctl enable hud-server hud-kiosk can0

cat <<'EOF'

Done. Remaining manual steps:
  1. Pi 5 config — add to /boot/firmware/config.txt and reboot:
       usb_max_current_enable=1   # buck converter can't negotiate USB-PD; lifts the 600 mA USB cap
       dtparam=spi=on
       dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25   # PiCAN2
     (Waveshare CAN HAT: oscillator=12000000,interrupt=25 — check your board)
  2. Reboot: services start automatically.
Verify: journalctl -u hud-server -f   |   candump can0
EOF
