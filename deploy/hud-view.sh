#!/usr/bin/env bash
# Terminal version of the HUD display — `hud-view` (symlinked by install.sh).
# Resolve the symlink to find the checkout, then run the venv's Python.
HUD_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$HUD_DIR" && exec "$HUD_DIR/.venv/bin/python" -m hud.view "$@"
