#!/bin/sh
# Launched by cage (hud-kiosk.service). Waits for the backend, then runs
# Chromium in kiosk mode. --incognito matters in a car: after a hard power
# cut there is no "restore session?" bubble blocking the HUD.
# --password-store=basic: without it Chromium asks to create a GNOME keyring
# on desktop images — a modal dialog on the windshield.

until curl -sf http://localhost:8000/api/config >/dev/null 2>&1; do
    sleep 1
done

for BIN in chromium-browser chromium; do
    if command -v "$BIN" >/dev/null 2>&1; then break; fi
done

exec "$BIN" \
    --kiosk \
    --incognito \
    --no-first-run \
    --password-store=basic \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-component-update \
    --check-for-update-interval=31536000 \
    --autoplay-policy=no-user-gesture-required \
    --app=http://localhost:8000
