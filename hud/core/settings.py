"""Validation for phone-editable config sections.

Pydantic v2 (already present as a FastAPI dependency). Every model forbids
unknown keys; ``SECTIONS`` maps an editable section name to a callable that
validates and returns plain data ready for Config.save_section. Anything
not listed here is not editable over HTTP.
"""

from __future__ import annotations

from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

SLOTS = (
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
)

MAX_LAYOUT_ITEMS = 24
MAX_ALERT_RULES = 32


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Units(_Strict):
    speed: Literal["mph", "kph"] = "mph"
    temp: Literal["f", "c"] = "f"


class LayoutItem(_Strict):
    widget: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    slot: Literal[
        "top-left", "top-center", "top-right",
        "center-left", "center", "center-right",
        "bottom-left", "bottom-center", "bottom-right",
    ]


class Location(_Strict):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Display(_Strict):
    aspect: Optional[str] = Field(default=None, pattern=r"^\d{1,3}:\d{1,3}$")
    scale: float = Field(default=1.0, ge=0.1, le=1.0)
    offset_x: float = Field(default=0.0, ge=-1, le=1)
    offset_y: float = Field(default=0.0, ge=-1, le=1)


class AlertRule(_Strict):
    topic: str = Field(pattern=r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
    above: Optional[float] = None
    below: Optional[float] = None
    above_topic: Optional[str] = Field(default=None, pattern=r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
    below_topic: Optional[str] = Field(default=None, pattern=r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
    tolerance: float = 0.0
    level: Literal["warn", "critical"] = "warn"
    message: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def _one_condition(self) -> "AlertRule":
        conditions = [self.above, self.below, self.above_topic, self.below_topic]
        if sum(c is not None for c in conditions) != 1:
            raise ValueError("exactly one of above/below/above_topic/below_topic required")
        return self


def _validate_layout(v: Any) -> list[dict]:
    items = TypeAdapter(list[LayoutItem]).validate_python(v)[:MAX_LAYOUT_ITEMS]
    return [i.model_dump() for i in items]


def _validate_rules(v: Any) -> list[dict]:
    rules = TypeAdapter(list[AlertRule]).validate_python(v)[:MAX_ALERT_RULES]
    return [r.model_dump(exclude_none=True) for r in rules]


SECTIONS: dict[str, Callable[[Any], Any]] = {
    "units": lambda v: Units.model_validate(v).model_dump(),
    "mirror": lambda v: TypeAdapter(bool).validate_python(v),
    "layout": _validate_layout,
    "alerts.rules": _validate_rules,
    "location": lambda v: Location.model_validate(v).model_dump(),
    "display": lambda v: Display.model_validate(v).model_dump(),
}
