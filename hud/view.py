"""Terminal HUD — a text version of the windshield display, for ssh.

    hud-view                      # live, full screen; q or Ctrl-C quits
    hud-view --once               # print one frame and exit (no screen control)
    hud-view --url http://hud.local:8000   # watch from another machine

Reads the running backend's bus snapshot (``/api/snapshot``) a few times a
second, so it shows exactly what the HUD shows — whichever vehicle source is
live — and never touches the CAN bus itself. Standard library only: it has
to work in a bare ssh session on the Pi.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

# 5-row block digits for the speed readout
BIG = {
    "0": ["█▀▀█", "█  █", "█  █", "█  █", "█▄▄█"],
    "1": ["  ▄█", "   █", "   █", "   █", "   █"],
    "2": ["▀▀▀█", "   █", "█▀▀▀", "█   ", "█▄▄▄"],
    "3": ["▀▀▀█", "   █", " ▀▀█", "   █", "▄▄▄█"],
    "4": ["█  █", "█  █", "▀▀▀█", "   █", "   █"],
    "5": ["█▀▀▀", "█   ", "▀▀▀█", "   █", "▄▄▄█"],
    "6": ["█▀▀▀", "█   ", "█▀▀█", "█  █", "█▄▄█"],
    "7": ["▀▀▀█", "   █", "  █ ", " █  ", " █  "],
    "8": ["█▀▀█", "█  █", "█▀▀█", "█  █", "█▄▄█"],
    "9": ["█▀▀█", "█  █", "▀▀▀█", "   █", "▄▄▄█"],
    "-": ["    ", "    ", "▀▀▀▀", "    ", "    "],
}

SOURCE_LABEL = {"can": "CAN", "can-obd": "CAN·OBD", "elm327": "OBD", "none": "NO VEHICLE"}
RPM_MAX = 7000
STALE_S = 3.0

RESET, BOLD, DIM = "\x1b[0m", "\x1b[1m", "\x1b[2m"
CYAN, AMBER, RED, GREEN = "\x1b[96m", "\x1b[93m", "\x1b[91m", "\x1b[92m"


# ---- formatting (pure, unit-tested) ---------------------------------------


def big_number(text: str) -> list[str]:
    rows = ["", "", "", "", ""]
    for ch in text:
        glyph = BIG.get(ch, BIG["-"])
        for i in range(5):
            rows[i] += glyph[i] + " "
    return [r.rstrip() for r in rows]


def speed_text(kph: Any, mph: bool) -> str:
    if not isinstance(kph, (int, float)):
        return "--"
    return str(round(kph / 1.609344 if mph else kph))


def temp_text(c: Any, fahrenheit: bool) -> str:
    if not isinstance(c, (int, float)):
        return "--"
    return f"{round(c * 9 / 5 + 32) if fahrenheit else round(c)}°{'F' if fahrenheit else 'C'}"


def num(v: Any, fmt: str = "{:.0f}", unit: str = "") -> str:
    return (fmt.format(v) + unit) if isinstance(v, (int, float)) else "--"


def bar(value: Any, maximum: float, width: int) -> str:
    frac = max(0.0, min(1.0, value / maximum)) if isinstance(value, (int, float)) else 0.0
    filled = round(frac * width)
    return "█" * filled + "░" * (width - filled)


def render(snap: dict[str, Any], cfg: dict[str, Any], width: int, color: bool,
           error: str | None = None) -> list[str]:
    """Snapshot → screen lines (no cursor control)."""
    c = (lambda code, s: f"{code}{s}{RESET}") if color else (lambda code, s: s)
    units = cfg.get("units") or {}
    mph = units.get("speed", "mph") != "kph"
    fahr = units.get("temp", "f") == "f"
    v = lambda k: snap.get(f"vehicle.{k}")  # noqa: E731
    w = max(40, width)

    source = snap.get("vehicle.source") or "none"
    badge = SOURCE_LABEL.get(source, str(source))
    badge = c(RED if source == "none" else GREEN, badge)
    clock = datetime.now().strftime("%-I:%M %p")
    lines = [f"{c(BOLD, clock)}   {badge}", ""]

    alerts = snap.get("alerts.active") or []
    for a in alerts[:3]:
        msg = a.get("message", a) if isinstance(a, dict) else a
        level = a.get("level") if isinstance(a, dict) else None
        lines.append(c(RED if level == "critical" else AMBER, f"⚠ {msg}"))
    if error:
        lines.append(c(RED, f"⚠ backend unreachable: {error}"))
    lines.append("")

    digits = big_number(speed_text(v("speed_kph"), mph))
    pad = max(0, (w - max(len(r) for r in digits)) // 2)
    for r in digits:
        lines.append(" " * pad + c(CYAN + BOLD, r))
    lines.append(" " * pad + c(DIM, "mph" if mph else "km/h"))
    lines.append("")

    rpm = v("rpm")
    bw = max(10, min(50, w - 20))
    rcol = RED if isinstance(rpm, (int, float)) and rpm > 5800 else CYAN
    lines.append(f"RPM  {c(rcol, bar(rpm, RPM_MAX, bw))} {num(rpm)}")
    lines.append(f"THR  {c(DIM, bar(v('throttle_pct'), 100, bw))} {num(v('throttle_pct'), unit='%')}")
    kw = v("power_kw")
    if isinstance(kw, (int, float)):
        half = bw // 2
        regen = bar(-kw, 50, half)[::-1] if kw < 0 else "░" * half
        drive = bar(kw, 150, bw - half) if kw > 0 else "░" * (bw - half)
        soc = v("hv_battery_pct")
        lines.append(f"PWR  {c(GREEN, regen)}│{c(CYAN, drive)} {kw:+.1f} kW"
                     + (f"  HV {soc:.0f}%" if isinstance(soc, (int, float)) else ""))
    lines.append("")

    fuel = v("fuel_pct")
    cells = [
        ("Coolant", temp_text(v("coolant_c"), fahr)),
        ("Fuel", num(fuel, unit="%")),
        ("Battery", num(v("battery_v"), "{:.1f}", " V")),
        ("Outside", temp_text(v("ambient_c"), fahr)),
        ("Intake", temp_text(v("intake_temp_c"), fahr)),
        ("Gear", str(v("gear") or "--")),
    ]
    col = max(18, w // 3)
    for i in range(0, len(cells), 3):
        row = ""
        for k, val in cells[i:i + 3]:
            plain = f"{k}: {val}"
            row += c(DIM, k + ":") + " " + val + " " * max(1, col - len(plain))
        lines.append(row.rstrip())

    odo = v("odometer_km")
    if isinstance(odo, (int, float)):
        lines.append(c(DIM, "Odometer:") + (f" {odo / 1.609344:,.0f} mi" if mph else f" {odo:,.0f} km"))

    dist = snap.get("trip.distance_km")
    secs = snap.get("trip.time_s")
    trip = []
    if isinstance(dist, (int, float)):
        trip.append(f"{dist / 1.609344:.1f} mi" if mph else f"{dist:.1f} km")
    if isinstance(secs, (int, float)):
        trip.append(f"{int(secs) // 3600}:{int(secs) % 3600 // 60:02d}")
    weather = snap.get("weather.current") or {}
    extra = []
    if trip:
        extra.append("Trip " + "  ".join(trip))
    if isinstance(weather, dict) and "temp_c" in weather:
        extra.append("Weather " + temp_text(weather["temp_c"], fahr))
    dtcs = v("dtc_codes")
    if dtcs:
        extra.append(c(AMBER, "DTC " + " ".join(dtcs)))
    lines.append("")
    lines.append("   ".join(extra))

    obd = snap.get("vehicle.can_obd")
    if isinstance(obd, dict) and source == "can-obd":
        lines.append(c(DIM, f"OBD over {obd.get('iface')} · {len(obd.get('channels', []))} PIDs"))
    return lines


# ---- I/O --------------------------------------------------------------------


def fetch(url: str, timeout: float = 1.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hud-view", description="Terminal version of the HUD display")
    p.add_argument("--url", default=os.environ.get("HUD_URL", "http://localhost:8000"))
    p.add_argument("--interval", type=float, default=0.2, help="refresh seconds (default 0.2)")
    p.add_argument("--once", action="store_true", help="print one frame and exit")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)
    base = args.url.rstrip("/")
    color = not args.no_color and sys.stdout.isatty() and "NO_COLOR" not in os.environ

    cfg: dict[str, Any] = {}
    cfg_at = 0.0

    def frame() -> list[str]:
        nonlocal cfg, cfg_at
        err = None
        snap: dict[str, Any] = {}
        try:
            if time.monotonic() - cfg_at > 10:
                cfg, cfg_at = fetch(f"{base}/api/config"), time.monotonic()
            snap = fetch(f"{base}/api/snapshot")
        except (urllib.error.URLError, OSError, ValueError) as e:
            err = str(getattr(e, "reason", e))
        width = shutil.get_terminal_size((80, 24)).columns
        return render(snap, cfg, width, color, err)

    if args.once or not sys.stdout.isatty():
        print("\n".join(frame()))
        return 0

    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd) if sys.stdin.isatty() else None
    sys.stdout.write("\x1b[?1049h\x1b[?25l")  # alt screen, hide cursor
    try:
        if old:
            tty.setcbreak(fd)
        while True:
            lines = frame()
            lines.append("")
            lines.append(f"{DIM if color else ''}q to quit{RESET if color else ''}")
            sys.stdout.write("\x1b[H" + "\x1b[K\n".join(lines) + "\x1b[K\x1b[J")
            sys.stdout.flush()
            if old and select.select([sys.stdin], [], [], args.interval)[0]:
                if sys.stdin.read(1).lower() == "q":
                    break
            elif not old:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if old:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
