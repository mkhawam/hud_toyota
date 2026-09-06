# Pi deployment guide

## Hardware

| Part | Notes |
|---|---|
| Raspberry Pi 5 | 2 GB is plenty; add the official Active Cooler — a car dash gets hot |
| MCP2515 CAN HAT | PiCAN2 (16 MHz osc) or Waveshare (12 MHz) — note which for the overlay |
| ELM327 USB adapter | OBDLink SX or a genuine-chip v1.5; avoid $5 clones |
| 5" HDMI display, 640×480, ≥800 nits | lies flat on the dash, faces up (layout is resolution-independent) |
| HUD reflective film | on the windshield above the display |
| 12 V → 5 V / 5 A buck converter | from an **ignition-switched** fuse via add-a-fuse tap |

> Pi 5 power note: a buck converter can't negotiate USB-PD, so the firmware
> assumes a 3 A supply and caps the USB ports at 600 mA total — enough for the
> ELM327, but set `usb_max_current_enable=1` in `config.txt` anyway (the
> installer prints it) so a USB LTE dongle or future peripherals aren't starved.
> Size the converter at 5 A regardless; the Pi 5 itself can pull ~25 W peaks.

**OBD-II port pins** (for the CAN HAT tap): 6 = CAN-H, 14 = CAN-L,
16 = +12 V battery, 4/5 = ground. A splitter cable lets the ELM327 and the
CAN HAT share the port. Toyota PT bus is 500 kbit/s.

> Heads-up: on some newer Toyotas a security gateway filters broadcast CAN
> at the OBD port. If `candump can0` shows nothing while driving, the HUD
> still works fully via ELM327 (`--source elm327` or just leave `auto`).

## Software setup (one command)

Flash **Raspberry Pi OS Lite (64-bit)** with SSH enabled in the imager, then
on the Pi:

```sh
curl -fsSL https://raw.githubusercontent.com/mkhawam/hud_toyota/main/deploy/install.sh \
    | sudo bash -s -- --repo https://github.com/mkhawam/hud_toyota.git --can-hat pican2
```

[install.sh](install.sh) clones to `/opt/hud`, installs apt packages + Node 22
+ the Python venv, builds the frontend, installs the udev rule and systemd
units, writes the Pi 5 `usb_max_current_enable=1` and the CAN overlay into
`config.txt`, starts everything, and health-checks the backend. Re-running
it is safe. Options: `--can-hat pican2|waveshare|none`, `--source
auto|elm327|can|sim`, `--user`, `--branch`, `--no-kiosk` (headless), `--no-start`.
Reboot once if it says `config.txt` changed.

Boot flow: `hud-server.service` (backend) → `hud-kiosk.service` (Chromium in
the cage compositor on tty1, `--incognito` so hard power cuts never leave a
restore-session prompt). The full **desktop** image works too: the installer
detects lightdm and switches the Pi to console boot (`raspi-config` "B1"),
because a desktop session on tty7 would otherwise own the screen and the
kiosk would sit at "Timeout waiting session to become active". To get the
desktop back on the bench: `sudo raspi-config nonint do_boot_behaviour B4`.

## Updating

**Manually on the Pi:** `sudo hud-update` (fast-forwards the current
branch; `--ref <sha|branch>` for a specific target). It fetches, reinstalls
Python deps and rebuilds the frontend only when those paths changed,
restarts the services, health-checks `/api/config`, and **rolls back to the
previous commit if the backend doesn't come up** — exit code 1 so you know.

**From the PC over the home network:** commit, then

```sh
scripts/deploy.sh            # git push → ssh dominus@hud sudo hud-update --ref <branch>
scripts/deploy.sh --ref main --no-push
```

or simply `ssh dominus@hud sudo hud-update` from PowerShell. The Pi pulls
from GitHub itself, so this works from any machine on the LAN with an ssh
key on the Pi (`HUD_HOST=user@host` overrides the default). CI
([.github/workflows/ci.yml](../.github/workflows/ci.yml)) runs the tests and
frontend build on every push so a broken commit is visible before you deploy.

## Verify on the car

```sh
candump can0                                   # broadcast frames flowing?
journalctl -u hud-server -f                    # provider status, failover
/opt/hud/.venv/bin/python -m hud --source elm327   # ELM path alone
```

Failover test: with the engine running, pull the CAN HAT connector — the
`vehicle.source` badge should flip CAN → OBD within ~5 s, speed/RPM keep
updating (at 5 Hz instead of 20 Hz), and recover when reconnected.

### Camera/body signal observation session (one drive, passenger seat)

Several decoded-but-unconfirmed enums need one observation pass. Record and
correlate with what the car does:

```sh
candump -l can0,412:7FF,3F6:7FF,343:7FF,344:7FF,391:7FF
```

- `0x412` `LKAWLSL/R`: values while lines detected vs during a deliberate
  lane drift (empty road!) → adjust `DETECTED_MIN`/`ALERT_VALUE` in
  `web/src/widgets/Lanes.tsx` if they differ.
- `0x3F6` `BSD_STAT`: pass a car on each side → set `LEFT_VALUES`/
  `RIGHT_VALUES` in `web/src/widgets/BlindSpot.tsx` (both arrows light on
  any nonzero until then).
- `0x343` `CACC`: engage ACC at a known set speed → confirm it's the set
  speed and its unit (`web/src/widgets/Cruise.tsx` gates 30–200 kph).
- `0x391` `HLLI`: toggle headlights → confirm polarity for night-dim.
- 29-bit meter frames (`candump can0 | grep ' 002106'`): if absent at the
  OBD port, odometer/drive-log odo columns simply stay empty.
- RSA (`0x489`): drive past a speed-limit sign — TSS 2.5+ only; absent on
  a TSS-P car and the HUD falls back to the OSM database.

## Speed limits (optional, needs the GPS puck)

On the **PC**: download the NJ extract from Geofabrik, build the road DB,
and deploy — the Pi never runs the builder:

```sh
pip install -e ".[osm]"       # pyosmium, dev PC only (WSL if the wheel fails)
python scripts/build_speedlimits.py new-jersey-latest.osm.pbf -o data/speedlimits-nj.sqlite
scp data/speedlimits-nj.sqlite dominus@hud:/opt/hud/data/   # data/ is gitignored — copy it once
```

Then set `providers.gps.enabled: true` and `providers.speedlimit.enabled: true`
and uncomment the OVERSPEED rule in `config/hud.yaml`. Limits shown with `~`
are NJ statutory defaults for untagged roads, not posted signs.

## Hardening against power cuts (do this once everything works)

The Pi loses power the instant the ignition turns off — SD cards corrupt
under repeated hard cuts. Raspberry Pi OS ships an overlay-filesystem mode
that makes the root filesystem read-only (all writes go to RAM):

```sh
sudo raspi-config nonint enable_overlayfs   # Performance Options → Overlay FS
sudo reboot
```

With overlayfs on, nothing persists between boots — which is fine: the HUD
is stateless except for `cache/weather.json` (best-effort, it just refetches).
`hud-update` **refuses to run** while overlayfs is active, because the update
would look successful and then vanish at the next power cut. To update:
`sudo raspi-config nonint disable_overlayfs`, reboot, `sudo hud-update`, then
re-enable. Drive logging also needs a writable `drivelog.data_dir`
(USB stick / second partition) under overlayfs.

## Replaying real CAN logs off-car (any Linux box / WSL2)

```sh
sudo modprobe vcan && sudo ip link add dev vcan0 type vcan && sudo ip link set up vcan0
candump -l can0            # record in the car (log file)
canplayer -I candump.log vcan0=can0   # replay at home
python -m hud --source can            # with providers.vehicle.can.channel: vcan0
```
