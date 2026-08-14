"""Build a compact road/speed-limit SQLite DB from an OSM .pbf extract.

Runs on the dev PC only (pyosmium: pip install -e ".[osm]"; use WSL if the
Windows wheel misbehaves). The Pi just gets the resulting ~50-75 MB file.

    python scripts/build_speedlimits.py new-jersey-latest.osm.pbf \
        -o data/speedlimits-nj.sqlite

Get the extract from https://download.geofabrik.de/north-america/us/new-jersey.html
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hud.roads.db import RoadDB  # noqa: E402
from hud.roads.maxspeed import parse_maxspeed  # noqa: E402

DRIVEABLE = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "unclassified", "residential", "living_street",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
}

COMMIT_EVERY = 5000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pbf", help="OSM extract (.osm.pbf)")
    parser.add_argument("-o", "--output", default="data/speedlimits.sqlite")
    parser.add_argument("--include-service", action="store_true",
                        help="include service roads (parking aisles, driveways)")
    args = parser.parse_args()

    try:
        import osmium
    except ImportError:
        print("pyosmium missing — run: pip install -e '.[osm]'  (dev PC only)")
        return 1

    driveable = DRIVEABLE | ({"service"} if args.include_service else set())
    out = Path(args.output)
    if out.exists():
        out.unlink()
    db = RoadDB(out)

    stats = {"ways": 0, "tagged": 0, "points": 0}

    class RoadHandler(osmium.SimpleHandler):
        def way(self, w):  # noqa: ANN001 — osmium types
            hwy = w.tags.get("highway")
            if hwy not in driveable:
                return
            limit = (
                parse_maxspeed(w.tags.get("maxspeed"))
                or parse_maxspeed(w.tags.get("maxspeed:forward"))
                or parse_maxspeed(w.tags.get("maxspeed:backward"))
            )
            points = [(n.lat, n.lon) for n in w.nodes if n.location.valid()]
            if len(points) < 2:
                return
            db.insert_way(w.id, hwy, limit, w.tags.get("name"), points)
            stats["ways"] += 1
            stats["points"] += len(points)
            if limit is not None:
                stats["tagged"] += 1
            if stats["ways"] % COMMIT_EVERY == 0:
                db.commit()
                print(f"\r{stats['ways']:,} ways…", end="", flush=True)

    start = time.time()
    print(f"reading {args.pbf} (node location index in RAM — needs a PC)…")
    RoadHandler().apply_file(args.pbf, locations=True, idx="flex_mem")

    db.set_meta("source", Path(args.pbf).name)
    db.set_meta("built_at", time.strftime("%Y-%m-%d %H:%M:%S"))
    db.set_meta("include_service", str(args.include_service))
    print("\nfinalizing (ANALYZE + VACUUM)…")
    db.finalize()
    db.close()

    pct = stats["tagged"] / stats["ways"] * 100 if stats["ways"] else 0
    size_mb = out.stat().st_size / 1e6
    print(
        f"done in {time.time() - start:.0f}s: {stats['ways']:,} ways, "
        f"{stats['points']:,} points, {pct:.0f}% with tagged maxspeed "
        f"(the rest use NJ statutory defaults at runtime) → {out} ({size_mb:.0f} MB)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
