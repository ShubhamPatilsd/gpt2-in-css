#!/usr/bin/env python3
"""Repeat one live SVG layer-normalization filter to measure backend scaling."""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    os.environ.get(
        "SVG_LN_CHAIN_SOURCE", ROOT / "experiments" / "svg-live-layernorm-r256"
    )
).resolve()
OUT = Path(
    os.environ.get(
        "SVG_LN_CHAIN_OUT", ROOT / "experiments" / "svg-layernorm-scale-chain"
    )
).resolve()
STAGES = int(os.environ.get("SVG_LN_CHAIN_STAGES", "12"))


def extract_element(page: str, marker: str, closing: str) -> str:
    start = page.index(marker)
    end = page.index(closing, start) + len(closing)
    return page[start:end]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page = (SOURCE / "index.html").read_text()
    defs_start = page.index(">", page.index("<defs")) + 1
    defs_end = page.index("</defs>", defs_start)
    defs = page[defs_start:defs_end]
    stage = extract_element(defs, '<filter id="ln2-stage"', "</filter>")
    base_defs = defs.replace(stage, "", 1)
    content_start = defs_end + len("</defs>")
    content_end = page.rindex("</svg>")
    wrapped = page[content_start:content_end]
    opening = '<g filter="url(#ln2-stage)">'
    if not wrapped.startswith(opening) or not wrapped.endswith("</g>"):
        raise ValueError("unexpected live layernorm wrapper")
    source_content = wrapped[len(opening) : -len("</g>")]

    relative = os.path.relpath(SOURCE, OUT)
    stages = []
    for index in range(STAGES):
        definition = stage.replace('id="ln2-stage"', f'id="ln-stage-{index}"', 1)
        definition = definition.replace('href="', f'href="{relative}/')
        stages.append(definition)
    content = source_content
    for index in range(STAGES):
        content = f'<g filter="url(#ln-stage-{index})">{content}</g>'

    reference = json.loads((SOURCE / "reference.json").read_text())
    source_x = int(reference["sourceX"])
    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Repeated SVG layer normalization scaling probe</title>'
        '<style>html,body{margin:0;background:black}svg{display:block}</style>'
        f'<svg width="1" height="768" viewBox="{source_x} 0 1 768" '
        f'xmlns="http://www.w3.org/2000/svg"><defs>{base_defs}{"".join(stages)}</defs>'
        f'{content}</svg>'
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "source": os.path.relpath(SOURCE, OUT),
                "stages": STAGES,
                "reduction": reference.get("reduction"),
                "reductionShard": reference.get("reductionShard"),
                "gaussianSigma": reference.get("gaussianSigma"),
                "gaussianTiles": reference.get("gaussianTiles"),
                "htmlBytes": len(html.encode()),
            },
            indent=2,
        )
        + "\n"
    )
    print({"html_bytes": len(html.encode()), "stages": STAGES})


if __name__ == "__main__":
    main()
