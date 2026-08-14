"""YAML config with dot-path access and a machine-written overlay.

Two layers:
- ``config/hud.yaml`` — hand-edited, commented, never rewritten by code.
- ``config/local.yaml`` — machine-written (settings page, calibration),
  deep-merged over hud.yaml at load. A corrupt overlay is ignored so the
  HUD always boots from the hand-edited file.

Merge semantics: dicts merge key-wise; lists and scalars replace wholesale
(layout and alert rules are ordered lists — element-wise merge would be
meaningless).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "hud.yaml"


def deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


@dataclass
class Config:
    data: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        p = Path(path) if path else DEFAULT_PATH
        data: dict[str, Any] = {}
        if p.exists():
            data = _read_yaml(p)
        cfg = cls(data=data, path=p)

        # Legacy calibration overlay (pre-local.yaml) — display section only.
        legacy = p.parent / "display.yaml"
        if legacy.exists():
            try:
                saved = _read_yaml(legacy)
                if isinstance(saved.get("display"), dict):
                    cfg.data = deep_merge(cfg.data, {"display": saved["display"]})
            except Exception:
                log.warning("ignoring corrupt %s", legacy)

        if cfg.overlay_path.exists():
            try:
                cfg.data = deep_merge(cfg.data, _read_yaml(cfg.overlay_path))
            except Exception:
                # Un-brickable: a bad phone edit must never stop the HUD.
                log.warning("ignoring corrupt %s", cfg.overlay_path)
        return cfg

    @property
    def overlay_path(self) -> Path:
        base = self.path if self.path is not None else DEFAULT_PATH
        return base.parent / "local.yaml"

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def save_section(self, section: str, value: Any) -> None:
        """Persist one dotted section into local.yaml (atomic) and apply it
        to the live config."""
        overlay: dict[str, Any] = {}
        if self.overlay_path.exists():
            try:
                overlay = _read_yaml(self.overlay_path)
            except Exception:
                overlay = {}  # start clean over a corrupt file

        node = overlay
        *parents, leaf = section.split(".")
        for part in parents:
            nxt = node.get(part)
            if not isinstance(nxt, dict):
                nxt = node[part] = {}
            node = nxt
        node[leaf] = value

        self.overlay_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.overlay_path.with_suffix(".yaml.tmp")
        tmp.write_text(yaml.safe_dump(overlay), encoding="utf-8")
        os.replace(tmp, self.overlay_path)  # atomic — power loss can't corrupt

        nested: Any = value
        for part in reversed(section.split(".")):
            nested = {part: nested}
        self.data = deep_merge(self.data, nested)

    def save_display(self, values: dict[str, Any]) -> None:
        """Back-compat wrapper used by the calibration endpoint."""
        merged = {**(self.get("display") or {}), **values}
        self.save_section("display", merged)
