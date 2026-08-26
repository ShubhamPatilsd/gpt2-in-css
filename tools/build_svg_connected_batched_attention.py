#!/usr/bin/env python3
"""Connect the live two-token QKV graph to the compact batched attention core."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "svg-multitoken-attention"
COMPACT = ROOT / "experiments" / "svg-multitoken-attention-batched"
OUT = ROOT / "experiments" / "svg-connected-batched-attention"
HEADS = 12
HEAD_WIDTH = 64
WIDTH = HEADS * HEAD_WIDTH
QKV_WIDTH = 3 * WIDTH
QKV_CY = 255


def filter_body(page: str) -> str:
    marker = 'color-interpolation-filters="sRGB">'
    start = page.index(marker) + len(marker)
    end = page.index("</filter>", start)
    return page[start:end]


def split_markup(source: str, result: str) -> str:
    center = 128 / 255
    grid = [index / 255 for index in range(256)]
    positive = " ".join(
        f"{max(0.0, min(1.0, 2 * (value - center))):.8g}" for value in grid
    )
    negative = " ".join(
        f"{max(0.0, min(1.0, 2 * (center - value))):.8g}" for value in grid
    )
    return (
        f'<feComponentTransfer in="{source}" result="{result}">'
        f'<feFuncR type="table" tableValues="{positive}"/>'
        f'<feFuncG type="table" tableValues="{negative}"/>'
        '<feFuncB type="table" tableValues="0 0"/>'
        '<feFuncA type="identity"/></feComponentTransfer>'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    qkv_page = (SOURCE / "qkv-debug.html").read_text()
    qkv_primitives = filter_body(qkv_page).replace(
        'href="', 'href="../svg-multitoken-attention/'
    )
    compact_core = (COMPACT / "core-fragment.svg").read_text().strip().replace(
        'href="', 'href="../svg-multitoken-attention-batched/'
    )
    adapters: list[str] = []
    for token in range(2):
        for part in ("q", "k", "v"):
            positioned: list[str] = []
            for head in range(HEADS):
                source = f"live-t{token}-{part}-h{head}-common"
                crop = f"t{token}-{part}-h{head}-crop"
                result = f"t{token}-{part}-h{head}-positioned"
                x = head * HEAD_WIDTH
                adapters.extend(
                    (
                        f'<feOffset in="{source}" x="0" y="{QKV_CY}" '
                        f'width="{HEAD_WIDTH}" height="1" result="{crop}"/>',
                        f'<feOffset in="{crop}" dx="{x}" dy="-{QKV_CY}" '
                        f'x="{x}" y="0" width="{HEAD_WIDTH}" height="1" '
                        f'result="{result}"/>',
                    )
                )
                positioned.append(result)
            common = f"t{token}-{part}"
            adapters.append(
                f'<feMerge result="{common}">'
                + "".join(f'<feMergeNode in="{name}"/>' for name in positioned)
                + '</feMerge>'
            )
            adapters.append(split_markup(common, f"{common}-signed"))

    primitives = qkv_primitives + "".join(adapters) + compact_core
    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Live QKV with compact batched attention</title>'
        '<style>html,body{margin:0;background:#000}svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="{WIDTH}" height="3" viewBox="0 0 {WIDTH} 3" '
        'xmlns="http://www.w3.org/2000/svg"><defs>'
        '<filter id="connected" filterUnits="userSpaceOnUse" '
        f'primitiveUnits="userSpaceOnUse" x="0" y="0" width="{QKV_WIDTH}" '
        f'height="768" color-interpolation-filters="sRGB">{primitives}</filter>'
        '</defs>'
        f'<rect width="{QKV_WIDTH}" height="768" fill="white" '
        'filter="url(#connected)"/></svg>'
    )
    (OUT / "index.html").write_text(html)
    reference = json.loads((COMPACT / "reference.json").read_text())
    reference.update(
        {
            "htmlBytes": len(html.encode()),
            "adapterPrimitiveCount": len(adapters),
            "qkvSource": str(SOURCE / "qkv-debug.html"),
        }
    )
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(
        json.dumps(
            {
                "htmlBytes": reference["htmlBytes"],
                "adapterPrimitiveCount": reference["adapterPrimitiveCount"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
