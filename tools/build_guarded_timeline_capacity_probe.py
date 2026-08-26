#!/usr/bin/env python3
"""Build fixtures that measure exact payload capacity of a view timeline.

Each timeline exposes two independent geometric coordinates (position and
width).  A payload integer is optionally multiplied by a power-of-two guard
before it enters geometry, then divided and rounded after timeline readback.
This distinguishes useful payload bits from spacing used only to tolerate
browser rounding.
"""

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "guarded-timeline-capacity"
SAMPLES = 96
PAYLOAD_BITS = range(14, 21)
GUARD_BITS = range(4)


def payload_pairs(bits: int, rng: random.Random) -> list[tuple[int, int]]:
    maximum = (1 << bits) - 1
    middle = 1 << (bits - 1)
    edges = [
        (0, 0),
        (maximum, maximum),
        (0, maximum),
        (maximum, 0),
        (1, maximum - 1),
        (maximum - 1, 1),
        (middle, middle - 1),
        (middle - 1, middle),
    ]
    return edges + [
        (rng.randrange(maximum + 1), rng.randrange(maximum + 1))
        for _ in range(SAMPLES - len(edges))
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    for payload_bits in PAYLOAD_BITS:
        for guard_bits in GUARD_BITS:
            rng = random.Random(0xC55000 + payload_bits * 16 + guard_bits)
            guard = 1 << guard_bits
            payload_max = (1 << payload_bits) - 1
            encoded_max = payload_max * guard

            # These are the smallest integer constants satisfying, for every
            # payload pair, V - W < L < V.  Keeping all geometry compact gives
            # timeline progress the best chance of retaining low bits.
            width_offset = encoded_max + 2
            left_offset = encoded_max + 1
            viewport = 2 * encoded_max + 2
            track_width = 4 * encoded_max + 4

            rules: list[str] = []
            markup: list[str] = []
            cases: list[dict[str, int]] = []
            for index, (left_payload, width_payload) in enumerate(payload_pairs(payload_bits, rng)):
                left = left_offset + left_payload * guard
                width = width_offset + width_payload * guard
                timeline = f"--t{index}"
                rules.append(
                    f".s{index}{{timeline-scope:{timeline}}}"
                    f".v{index}{{view-timeline-name:{timeline};left:{left}px;width:{width}px}}"
                    f".r{index}{{animation-timeline:{timeline}}}"
                )
                markup.append(
                    f'<div class="scope s{index}"><div class="scroller"><div class="track">'
                    f'<i class="subject v{index}"></i></div></div><output class="result r{index}" '
                    f'data-left="{left_payload}" data-width="{width_payload}"></output></div>'
                )
                cases.append({"left": left_payload, "width": width_payload})

            css = (
                '@property --cover{syntax:"<number>";inherits:true;initial-value:-1}'
                '@property --entry{syntax:"<number>";inherits:true;initial-value:-1}'
                '@property --left-code{syntax:"<number>";inherits:true;initial-value:-1}'
                '@property --width-code{syntax:"<number>";inherits:true;initial-value:-1}'
                '@keyframes read{cover 0%{--cover:0;--entry:0}'
                'entry 100%{--entry:1}cover 100%{--cover:1;--entry:1}}'
                f'.scroller{{position:fixed;left:0;top:-20000px;width:{viewport}px;'
                'height:1px;overflow-x:scroll}}'
                f'.track{{position:relative;width:{track_width}px;height:1px}}'
                '.subject{position:absolute;top:0;height:1px;display:block;view-timeline-axis:inline}'
                '.result{animation-name:read;animation-duration:1s;animation-timing-function:linear;'
                'animation-fill-mode:both;'
                f'--recovered-width:calc(var(--cover)*{viewport}/(var(--entry) - var(--cover)));'
                f'--width-code:calc(round(nearest,(var(--recovered-width) - {width_offset})/{guard},1));'
                f'--left-code:calc(round(nearest,({viewport} - var(--entry)*var(--recovered-width)'
                f' - {left_offset})/{guard},1))}}'
                + ''.join(rules)
            )
            name = f"p{payload_bits}-g{guard_bits}"
            html = (
                '<!doctype html><meta charset="utf-8">'
                f'<title>Timeline payload {payload_bits} guard {guard_bits}</title>'
                f'<style>{css}</style>{"".join(markup)}'
            )
            (OUT / f"{name}.html").write_text(html)
            reference = {
                "name": name,
                "payload_bits": payload_bits,
                "guard_bits": guard_bits,
                "guard": guard,
                "viewport": viewport,
                "encoded_max": encoded_max,
                "samples": len(cases),
                "cases": cases,
                "html_bytes": len(html.encode()),
            }
            (OUT / f"{name}.json").write_text(json.dumps(reference, indent=2) + "\n")
            manifest.append(reference | {"cases": None})

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print({"configurations": len(manifest), "samples_each": SAMPLES, "output": str(OUT)})


if __name__ == "__main__":
    main()
