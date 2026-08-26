#!/usr/bin/env python3
"""Build a two-candidate probe for the global-int16 HVAR score margin."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-pair-probe"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
SUBFONTS = ROOT / "experiments" / "gpt2-hvar-grid-output-head-cascade-subfonts"
TOKENS = (11, 13)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((FINE / "reference.json").read_text())
    fixture = reference["validation"]["tokenIds"].index(11776)
    hidden = reference["validation"]["hiddenVectors"][fixture]
    fine_html = (FINE / "index.html").read_text()
    candidates = re.findall(
        r'<i class="candidate" style="--base:([^;]+);'
        r'--factor:([^;]+);--local-tie:([^\"]+)">(.*?)</i>',
        fine_html,
    )
    subfont_css = (SUBFONTS / "index.css").read_text()
    font_faces = subfont_css.split("\n", 1)[0].replace(
        'url("score-',
        'url("../gpt2-hvar-grid-output-head-cascade-subfonts/score-',
    )
    families = ",".join(
        f"Score{plane}{shard}G0"
        for shard in range(6)
        for plane in ("H", "L")
    )
    compact_css = (
        ROOT / "experiments" / "gpt2-hvar-grid-output-head-cascade-compact" / "index.css"
    ).read_text()
    settings = re.search(
        r"\.fine-stage\{.*?font-variation-settings:(.*?);font-kerning",
        compact_css,
    ).group(1)
    hidden_css = ";".join(f"--h{index}:{value}" for index, value in enumerate(hidden))
    markup = "".join(
        f'<i id="token-{token}" class="candidate" data-base="{base}" '
        f'data-factor="{factor}" style="--base:{base};--factor:{factor}">'
        f"{html.escape(glyphs)}</i>"
        for token in TOKENS
        for base, factor, _, glyphs in (candidates[token],)
    )
    css = f"""{font_faces}
*{{box-sizing:border-box}}
.stage{{{hidden_css};font-family:{families};font-size:100px;line-height:1;
font-variation-settings:{settings};font-kerning:none;white-space:pre}}
.candidate{{display:block;width:max-content;height:1px;overflow:hidden;font-style:normal}}
"""
    (OUTPUT / "index.css").write_text(css)
    (OUTPUT / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="index.css">'
        f'<div class="stage">{markup}</div>'
    )
    (OUTPUT / "reference.json").write_text(json.dumps({
        "inputToken": 11776,
        "tokens": list(TOKENS),
        "denseWinner": reference["validation"]["denseWinners"][fixture],
        "quantizedWinner": reference["validation"]["quantizedWinners"][fixture],
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
