#!/usr/bin/env python3
"""Build a no-JS probe for 16-bit PNG precision inside SVG filters."""

from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-16bit-precision"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    values = np.asarray([[1, 2, 4, 8, 16, 32, 64, 128, 256, 512]], dtype=np.uint16)
    Image.fromarray(values).save(OUT / "values-16.png")
    Image.fromarray(np.rint(values / 65535 * 255).astype(np.uint8), mode="L").save(
        OUT / "values-8.png"
    )
    rows = []
    for row, bits in enumerate((16, 8)):
        rows.append(
            f'<feImage href="values-{bits}.png" x="0" y="{row}" width="10" '
            f'height="1" preserveAspectRatio="none" result="source-{bits}"/>'
            f'<feColorMatrix in="source-{bits}" '
            f'values="8191.875 0 0 0 0  0 8191.875 0 0 0  '
            f'0 0 8191.875 0 0  0 0 0 0 1" result="scaled-{bits}"/>'
        )
    html = (
        '<!doctype html><meta charset="utf-8"><title>16-bit SVG source probe</title>'
        '<style>html,body{margin:0;background:black}svg{display:block;image-rendering:pixelated}</style>'
        '<svg width="10" height="2" viewBox="0 0 10 2" xmlns="http://www.w3.org/2000/svg">'
        '<defs><filter id="probe" filterUnits="userSpaceOnUse" '
        'primitiveUnits="userSpaceOnUse" x="0" y="0" width="10" height="2" '
        'color-interpolation-filters="sRGB">'
        + "".join(rows)
        + '<feMerge><feMergeNode in="scaled-16"/><feMergeNode in="scaled-8"/></feMerge>'
        '</filter></defs><rect width="10" height="2" fill="white" filter="url(#probe)"/>'
        '</svg>'
    )
    (OUT / "index.html").write_text(html)


if __name__ == "__main__":
    main()
