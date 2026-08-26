#!/usr/bin/env python3
"""Connect contiguous live QKV matrices directly to batched SVG attention."""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    os.environ.get(
        "SVG_CONTIGUOUS_QKV_SOURCE",
        ROOT / "experiments" / "svg-multitoken-attention-partized",
    )
).resolve()
COMPACT = Path(
    os.environ.get(
        "SVG_CONTIGUOUS_ATTENTION_CORE",
        ROOT / "experiments" / "svg-multitoken-attention-batched",
    )
).resolve()
OUT = Path(
    os.environ.get(
        "SVG_CONTIGUOUS_QKV_OUT",
        ROOT / "experiments" / "svg-contiguous-qkv-batched-attention",
    )
).resolve()
WIDTH = 768
QKV_WIDTH = 3 * WIDTH


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
    metadata = json.loads((SOURCE / "qkv-contiguous.json").read_text())
    layout = metadata["layout"]
    if layout not in {"part", "vector"}:
        raise ValueError(f"unsupported contiguous QKV layout: {layout}")

    source_relative = os.path.relpath(SOURCE, OUT)
    compact_relative = os.path.relpath(COMPACT, OUT)
    qkv = (SOURCE / "qkv-contiguous-fragment.svg").read_text().strip().replace(
        'href="', f'href="{source_relative}/'
    )
    compact = (COMPACT / "core-fragment.svg").read_text().strip().replace(
        'href="', f'href="{compact_relative}/'
    )
    compact_reference = json.loads((COMPACT / "reference.json").read_text())
    core_base_y = int(compact_reference.get("baseY", 0))
    adapters: list[str] = []
    surface_y = int(metadata["surfaceY"])
    native_part_handoff = layout == "part" and core_base_y == surface_y
    for token in range(2):
        for part_index, part in enumerate(("q", "k", "v")):
            result = f"t{token}-{part}"
            if native_part_handoff:
                source = f"live-t{token}-{part}-common"
                if token == 0 and part == "v":
                    compact = compact.replace('in="t0-v"', f'in="{source}"')
                adapters.append(split_markup(source, f"{result}-signed"))
                continue
            if layout == "vector":
                start = part_index * WIDTH
                crop = f"{result}-vector-crop"
                adapters.extend(
                    (
                        f'<feOffset in="live-t{token}-vector-common" '
                        f'x="{start}" y="{surface_y}" width="{WIDTH}" '
                        f'height="1" result="{crop}"/>',
                        f'<feOffset in="{crop}" dx="-{start}" dy="-{surface_y}" '
                        f'x="0" y="0" width="{WIDTH}" height="1" '
                        f'result="{result}"/>',
                    )
                )
            else:
                adapters.append(
                    f'<feOffset in="live-t{token}-{part}-common" '
                    f'dy="-{surface_y}" x="0" y="0" width="{WIDTH}" '
                    f'height="1" result="{result}"/>'
                )
            adapters.append(split_markup(result, f"{result}-signed"))

    primitives = qkv + "".join(adapters) + compact
    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Contiguous live QKV with batched attention</title>'
        '<style>html,body{margin:0;background:#000}'
        'svg{display:block;image-rendering:pixelated}</style>'
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
    reference = compact_reference
    reference.update(
        {
            "qkvLayout": layout,
            "qkvSource": str(SOURCE),
            "qkvPrimitiveCount": metadata["primitiveCount"],
            "adapterPrimitiveCount": len(adapters),
            "nativePartHandoff": native_part_handoff,
            "htmlBytes": len(html.encode()),
        }
    )
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: reference[key]
                for key in (
                    "qkvLayout",
                    "qkvPrimitiveCount",
                    "adapterPrimitiveCount",
                    "htmlBytes",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
