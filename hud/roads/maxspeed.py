"""OSM maxspeed parsing + New Jersey statutory fallbacks (pure functions).

OSM realities: ``"25 mph"`` dominates in the US; a bare number means km/h
per the OSM spec; ``none``/``signals``/``walk`` and junk appear. Untagged
ways fall back to NJ statutory defaults (NJSA 39:4-98) by highway class at
*runtime* — resolved limits carry an ``estimated`` flag so the HUD can be
honest about them, and tweaking the table never requires rebuilding the DB.
"""

from __future__ import annotations

MPH_TO_KPH = 1.609344

# NJSA 39:4-98 statutory limits, in mph for hand-editing sanity.
NJ_DEFAULTS_MPH: dict[str, float] = {
    "motorway": 65, "motorway_link": 45,
    "trunk": 55, "trunk_link": 45,
    "primary": 50, "primary_link": 40,
    "secondary": 45, "secondary_link": 35,
    "tertiary": 35, "tertiary_link": 30,
    "unclassified": 30,
    "residential": 25,
    "living_street": 15,
}


def parse_maxspeed(raw: str | None) -> float | None:
    """'25 mph' → 40.2 ; '50' → 50.0 (km/h per OSM) ; 'none'/junk → None."""
    if not raw:
        return None
    val = raw.split(";")[0].strip().lower()
    if val.endswith("mph"):
        num, factor = val[:-3].strip(), MPH_TO_KPH
    elif val.endswith("km/h") or val.endswith("kmh"):
        num, factor = val.rstrip("km/h").strip(), 1.0
    else:
        num, factor = val, 1.0  # bare number = km/h per OSM spec
    try:
        kph = float(num) * factor
    except ValueError:
        return None  # none / signals / walk / zone tokens / garbage
    return round(kph, 1) if 5 <= kph <= 200 else None


def resolve_limit(
    maxspeed_kph: float | None,
    highway: str,
    defaults_mph: dict[str, float] | None = None,
) -> tuple[float | None, bool]:
    """(limit_kph, estimated). Tagged limit wins; else the class default."""
    if maxspeed_kph is not None:
        return maxspeed_kph, False
    table = defaults_mph if defaults_mph is not None else NJ_DEFAULTS_MPH
    mph = table.get(highway)
    if mph is None:
        return None, True
    return round(mph * MPH_TO_KPH, 1), True
