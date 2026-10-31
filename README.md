# hud_toyota

Windshield-projected HUD for a Toyota Camry (2018+), hosted on a Raspberry Pi 5.
A 5" high-brightness screen lies flat on the dash and reflects off the windshield,
so the UI renders **mirror-flipped on pure black** — only lit pixels appear to float.

```
providers (CAN / ELM327 / sim, weather, ...) ─► async event bus ─► native QML display (eglfs)
                                                        └────────► settings web server (phone)
```

- **Display** — native PySide6 + QML (`hud/ui/`), running in the same Python
  process as the backend. The bus feeds QML property maps directly; on the Pi,
  Qt's `eglfs` backend draws straight to the panel with no compositor or
  browser. Widgets are single files in `hud/ui/qml/widgets/`, placed by
  `config/hud.yaml`'s layout grid.
- **Backend** — Python 3.11+ asyncio. Providers publish normalized topics
  (`vehicle.speed_kph`, `alerts.active`, ...) onto a pub/sub bus.
- **Settings server** — small FastAPI app serving the phone settings and
  drives pages (TypeScript + SolidJS, `web/`). In the car the Pi broadcasts
  its own Wi-Fi when no known network is around, so the phone can reach it.
  The common settings are also on the HUD itself (OK button → menu).
- **Vehicle data** — unified interface (`hud/providers/vehicle/base.py`):
  CAN HAT (SocketCAN) primary, ELM327 USB fallback, simulator for desktop dev.

## Quickstart (desktop, simulated vehicle)

```sh
.\start_dev            # Windows (PowerShell or cmd)
./start_dev            # Git Bash / Linux / macOS
```

First run bootstraps the venv (with PySide6) and node_modules. The native HUD
opens in a 640×480 window with simulated data; the phone pages run with hot
reload at http://localhost:5173/settings/. Pass `elm327` to use a real adapter
plugged into this machine.

Keys on the HUD (a keyboard-emulating button panel works the same):

| Key | Action |
|---|---|
| OK / Enter | on-device menu: theme, units, night mode, brightness, glow, mirror, calibration, debug, trip reset, phone-settings address |
| C | calibrate the projection box (arrows move, +/− scale, OK saves) |
| D | debug overlay (every bus topic with value and age) |

Direct runs:

```sh
.venv/Scripts/python -m hud --ui --source sim --mirror off   # readable dev window
.venv/Scripts/python -m hud --source sim                     # headless: backend + settings server
.venv/Scripts/python -m hud --ui --source sim --screenshot out.png --screenshot-after 8
```

`--press Return,Down` synthesizes key presses after startup, handy with
`--screenshot` to capture the menu or calibration screens.

## Tests

```sh
.venv/Scripts/python -m pytest -q     # backend + native UI (QML loads with zero warnings)
cd web && npm run typecheck
python scripts/ws_check.py            # live WS smoke check against a running server
```

## Deploy to the Pi

One command on a fresh Raspberry Pi OS Lite install (clones, builds, installs
services, writes `config.txt`, starts, health-checks):

```sh
curl -fsSL https://raw.githubusercontent.com/mkhawam/hud_toyota/main/deploy/install.sh \
    | sudo bash -s -- --repo https://github.com/mkhawam/hud_toyota.git --can-hat pican2
```

Updates over the home network: commit, then `scripts/deploy.sh` (pushes to
GitHub, then runs `hud-update` on the Pi over ssh: fetch → build → restart →
health check → rollback on failure). Or just `ssh dominus@hud sudo hud-update`.
Details in [deploy/README.md](deploy/README.md).

## Configuration — `config/hud.yaml`

Mirroring, units (mph/°F), widget layout, and alert rules — served at
`/api/config`, so display changes never require a rebuild. Add a widget by
writing `web/src/widgets/<Name>.tsx`, registering it in `widgets/index.ts`,
and referencing it in `layout`.

## Roadmap

1. ✅ Core loop: bus → server → widgets, sim source, mirror mode, alerts engine
2. ✅ ELM327 USB path (`python-obd`), systemd + udev deploy assets ([deploy/](deploy/))
3. ✅ CAN path: SocketCAN + cantools + vendored opendbc Toyota DBC, auto manager
   (CAN fast channels + ELM327 slow channels, failover both ways) — **on-car
   validation pending**, see [deploy/README.md](deploy/README.md)
4. ✅ Internet: `net.online` monitor, weather (Open-Meteo + disk cache),
   gpsd provider, TomTom traffic (key-gated) — all opportunistic/offline-safe
5. ✅ Night-dim (sun-down from weather), DTC banner, overlayfs guide
   ([deploy/README.md](deploy/README.md))
6. ✅ Projection viewport: 3:1 content strip scaled/positioned on the panel,
   live keyboard calibration (`C`), persisted to a config overlay
7. ✅ **Phone settings page** (`/settings`) — units, mirror, layout, alert
   rules, location; validated writes to `config/local.yaml`, HUD updates live
8. ✅ **Trip computer** — MAF-based fuel economy, distance/time, 0–60 timer
9. ✅ **Drive logging** — 1 Hz SQLite telemetry per drive, review at `/trips`
   with a speed/limit chart
10. ✅ **Offline speed limits** — OSM-derived road DB (build once with
    `scripts/build_speedlimits.py`), GPS map-matching with bearing/hysteresis,
    limit chip + overspeed coloring, `above_topic` alert rules

11. ✅ **Toyota camera & body CAN extras** — lane-marking indicator
    (per-side status from the FCM camera, like the stock cluster), blind-spot
    edge arrows, headlight-driven night-dim, ACC set-speed chip, PCS-ready
    alert rule, trans/intake temp stats, odometer + steering in the drive
    log, camera-read speed signs (RSA, TSS 2.5+) preferred over OSM limits.
    All CAN-only — the ELM327 fallback keeps the standardized basics.

Remaining: on-car validation (ELM327/CAN/GPS hardware; CAN signal enums need
one candump observation session — see deploy/README.md), compass widget,
audio chimes.
