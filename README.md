# hud_toyota

Windshield-projected HUD for a Toyota Camry (2018+), hosted on a Raspberry Pi 5.
A 5" high-brightness screen lies flat on the dash and reflects off the windshield,
so the UI renders **mirror-flipped on pure black** — only lit pixels appear to float.

```
providers (CAN / ELM327 / sim, weather, ...) ─► async event bus ─► WebSocket ─► SolidJS widgets
```

- **Backend** — Python 3.11+ / FastAPI. Providers publish normalized topics
  (`vehicle.speed_kph`, `alerts.active`, ...) onto an asyncio pub/sub bus;
  the server coalesces them into 50 ms batches over `/ws`.
- **Frontend** — TypeScript + SolidJS + Vite. Each topic maps to a signal;
  widgets are single `.tsx` files registered by name and placed by
  `config/hud.yaml`'s layout grid.
- **Vehicle data** — unified interface (`hud/providers/vehicle/base.py`):
  CAN HAT (SocketCAN) primary, ELM327 USB fallback, simulator for desktop dev.

## Quickstart (desktop, simulated vehicle)

```sh
.\start_dev            # Windows (PowerShell or cmd)
./start_dev            # Git Bash / Linux / macOS
# open http://localhost:5173/?mirror=0
```

That's it — first run bootstraps the venv and node_modules, then starts the
backend (sim vehicle + live weather) plus the Vite dev server with hot reload.
Pass `elm327` to use a real adapter plugged into this machine.

Production-style run (serves the built frontend, no Node needed):

```sh
cd web && npm run build && cd ..
.venv/Scripts/python -m hud --source sim      # .venv/bin on Linux
# open http://localhost:8000        (mirrored — as projected)
# open http://localhost:8000/?mirror=0   (readable, for dev)
```

## Tests

```sh
.venv/Scripts/python -m pytest -q     # bus, alerts engine
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
2. ✅ ELM327 USB path (`python-obd`), kiosk + systemd + udev deploy assets ([deploy/](deploy/))
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
