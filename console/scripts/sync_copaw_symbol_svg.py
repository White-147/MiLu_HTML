"""Regenerate public/copaw-symbol.svg as inline PNG (favicon-safe; no external href).

Uses Pillow (repo dependency) to embed a downscaled copy of milu-logo.png so
browsers that use copaw-symbol.svg as icon still render MiLu (external <image>
URLs are often blocked for favicons).

Run from repo root or console/:
  python console/scripts/sync_copaw_symbol_svg.py
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "public" / "milu-logo.png"
OUT = ROOT / "public" / "copaw-symbol.svg"
FAVICON_OUT = ROOT / "public" / "milu-favicon.png"
MAX_EDGE = 128


def main() -> None:
    if not PNG.is_file():
        raise SystemExit(f"Missing {PNG}")
    img = Image.open(PNG).convert("RGBA")
    img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    w, h = img.size
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()
    FAVICON_OUT.write_bytes(png_bytes)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Inline MiLu bitmap (from milu-logo.png, max {MAX_EDGE}px); favicon-safe. Regenerate: python scripts/sync_copaw_symbol_svg.py -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="MiLu">
  <image width="{w}" height="{h}" href="data:image/png;base64,{b64}" preserveAspectRatio="xMidYMid meet"/>
</svg>
"""
    OUT.write_text(svg, encoding="utf-8")
    print(
        f"embedded {w}x{h} png={len(png_bytes)} bytes -> {OUT} + {FAVICON_OUT.name}",
    )


if __name__ == "__main__":
    main()
