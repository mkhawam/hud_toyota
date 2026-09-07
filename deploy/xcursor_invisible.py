#!/usr/bin/env python3
"""Generate an invisible Xcursor theme.

The kiosk compositor (cage) draws its default arrow from boot until the
first mouse event lets Chromium apply the page's `cursor: none`. Pointing
XCURSOR_THEME at this theme makes that default arrow fully transparent, so
nothing ever shows on the windshield unless the HUD page deliberately
shows a cursor (it draws its own SVG cursor while the mouse is moving).

    sudo python3 deploy/xcursor_invisible.py            # → /usr/share/icons/hud-invisible
    python3 deploy/xcursor_invisible.py /tmp/theme      # anywhere else

File format is libXcursor's (all little-endian):
  header: magic "Xcur", header size 16, version 0x10000, ntoc
  toc:    ntoc × (type, subtype, position)
  image:  header 36, type 0xfffd0002, subtype=nominal size, version 1,
          width, height, xhot, yhot, delay, then width*height ARGB pixels
"""

import struct
import sys
from pathlib import Path

NAMES = [
    "default", "left_ptr", "arrow", "pointer", "hand", "hand1", "hand2",
    "text", "xterm", "ibeam", "crosshair", "wait", "watch", "progress",
    "left_ptr_watch", "grab", "grabbing", "move", "not-allowed", "help",
    "sb_h_double_arrow", "sb_v_double_arrow", "col-resize", "row-resize",
    "ew-resize", "ns-resize", "nwse-resize", "nesw-resize",
]

IMAGE_TYPE = 0xFFFD0002
SIZE = 24
W = H = 8  # a few transparent pixels — some loaders dislike 1×1


def invisible_cursor() -> bytes:
    image = struct.pack("<9I", 36, IMAGE_TYPE, SIZE, 1, W, H, 0, 0, 0) + b"\x00" * (W * H * 4)
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, 1)
    toc = struct.pack("<III", IMAGE_TYPE, SIZE, 16 + 12)
    return header + toc + image


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/usr/share/icons/hud-invisible")
    cursors = root / "cursors"
    cursors.mkdir(parents=True, exist_ok=True)
    blob = invisible_cursor()
    for name in NAMES:
        (cursors / name).write_bytes(blob)
    (root / "index.theme").write_text(
        "[Icon Theme]\nName=hud-invisible\nComment=fully transparent cursors for the HUD kiosk\n"
    )
    # self-check: parse it back the way libXcursor would
    data = (cursors / "default").read_bytes()
    magic, hsize, _ver, ntoc = struct.unpack_from("<4sIII", data)
    ctype, csub, pos = struct.unpack_from("<III", data, hsize)
    ihdr, itype, isize, _iver, w, h = struct.unpack_from("<6I", data, pos)
    assert magic == b"Xcur" and ntoc == 1 and ctype == itype == IMAGE_TYPE
    assert csub == isize == SIZE and ihdr == 36 and (w, h) == (W, H)
    assert len(data) == pos + 36 + w * h * 4
    print(f"wrote {len(NAMES)} invisible cursors to {cursors}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
