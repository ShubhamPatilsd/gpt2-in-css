#!/usr/bin/env python3
"""Build a no-JS probe for packing one CSS-filter scalar into two channels."""

from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-rg16-transport"
WIDTH = 768
LEVELS = 65536


def values(items: np.ndarray) -> str:
    return " ".join(f"{item:.8g}" for item in items)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    codes = rng.integers(0, LEVELS, size=WIDTH, dtype=np.uint16)
    source = np.zeros((1, WIDTH, 4), dtype=np.uint8)
    source[0, :, 0] = codes >> 8
    source[0, :, 1] = codes & 255
    source[0, :, 3] = 255
    Image.fromarray(source, "RGBA").save(OUT / "source-rg16.png", optimize=True)

    indices = np.arange(LEVELS, dtype=np.uint32)
    high = (indices >> 8) / 255
    low = (indices & 255) / 255
    high_table = values(high)
    low_table = values(low)
    # Reconstruct x = code / 65535 from the source bytes. Pack that computed
    # scalar back into R/G with two 65,536-entry discrete transfer functions,
    # force a filter boundary, then decode the pair to grayscale.
    html = f'''<!doctype html><meta charset="utf-8"><title>RG16 SVG transport</title>
<style>html,body{{margin:0;background:black}}svg{{display:block;image-rendering:pixelated}}</style>
<svg width="{WIDTH}" height="1" viewBox="0 0 {WIDTH} 1" xmlns="http://www.w3.org/2000/svg">
<defs>
  <filter id="pack" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
    x="0" y="0" width="{WIDTH}" height="1" color-interpolation-filters="sRGB">
    <feColorMatrix values="{256/257} {1/257} 0 0 0  {256/257} {1/257} 0 0 0  {256/257} {1/257} 0 0 0  0 0 0 0 1" result="scalar"/>
    <feComponentTransfer in="scalar">
      <feFuncR type="discrete" tableValues="{high_table}"/>
      <feFuncG type="discrete" tableValues="{low_table}"/>
      <feFuncB type="discrete" tableValues="0"/>
      <feFuncA type="identity"/>
    </feComponentTransfer>
  </filter>
  <filter id="decode" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
    x="0" y="0" width="{WIDTH}" height="1" color-interpolation-filters="sRGB">
    <feColorMatrix values="{256/257} {1/257} 0 0 0  {256/257} {1/257} 0 0 0  {256/257} {1/257} 0 0 0  0 0 0 0 1"/>
  </filter>
</defs>
<image href="source-rg16.png" width="{WIDTH}" height="1" preserveAspectRatio="none"
  style="filter:url(#pack) url(#decode)"/>
</svg>'''
    (OUT / "index.html").write_text(html)
    np.save(OUT / "expected-codes.npy", codes)
    print({"html_bytes": len(html), "levels": LEVELS})


if __name__ == "__main__":
    main()
