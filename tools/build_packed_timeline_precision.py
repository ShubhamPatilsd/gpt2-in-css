#!/usr/bin/env python3
"""Build a no-JS probe for integer-packed view-timeline transport."""

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "packed-timeline-precision"
VIEWPORT = 32768
SAMPLES = 48
CONFIGS = (
    (8, 2, 1),
    (9, 2, 1),
    (10, 2, 1),
    (12, 2, 1),
    (14, 2, 16),
    (8, 3, 1),
    (9, 3, 8),
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(0xC55)
    registrations: list[str] = []
    keyframes: list[str] = []
    rules: list[str] = []
    markup: list[str] = []
    cases: list[dict[str, object]] = []
    index = 0
    max_width = 0.0
    for bits, digits, scale in CONFIGS:
        base = 1 << bits
        for sample in range(SAMPLES):
            values = [rng.randrange(base) for _ in range(digits)]
            packed = sum(value * base**place for place, value in enumerate(values))
            width = packed / scale
            max_width = max(max_width, width)
            timeline = f"--t{index}"
            progress = f"--p{index}"
            decoded = f"--d{index}"
            animation = f"k{index}"
            registrations.append(
                f'@property {progress}{{syntax:"<number>";inherits:true;initial-value:-1}}'
                f'@property {decoded}{{syntax:"<number>";inherits:true;initial-value:-1}}'
            )
            keyframes.append(
                f"@keyframes {animation}{{from{{{progress}:0}}to{{{progress}:1}}}}"
            )
            rules.append(
                f".scope-{index}{{timeline-scope:{timeline}}}"
                f".metric-{index}{{width:{width:.10f}px;view-timeline:{timeline} inline}}"
                f".result-{index}{{animation:{animation} 1s linear both;"
                f"animation-timeline:{timeline};animation-range:cover;"
                f"{decoded}:calc(round(nearest, ({VIEWPORT} / var({progress}) - "
                f"{VIEWPORT}) * {scale}, 1))}}"
            )
            markup.append(
                f'<div class="scope scope-{index}"><div class="scroller"><div class="track">'
                f'<i class="metric metric-{index}"></i></div></div>'
                f'<output class="result result-{index}" data-index="{index}"></output></div>'
            )
            cases.append(
                {
                    "index": index,
                    "bits": bits,
                    "digits": digits,
                    "scale": scale,
                    "values": values,
                    "packed": packed,
                }
            )
            index += 1
    track_width = int(max_width + VIEWPORT * 2)
    css = (
        "".join(registrations)
        + "".join(keyframes)
        + f".scroller{{position:fixed;left:0;top:-20000px;width:{VIEWPORT}px;height:1px;overflow-x:scroll}}"
        + f".track{{position:relative;width:{track_width}px;height:1px}}"
        + ".metric{position:absolute;left:0;top:0;display:block;height:1px}"
        + "".join(rules)
    )
    html = (
        '<!doctype html><meta charset="utf-8"><title>Packed timeline precision</title>'
        "<style>"
        + css
        + "</style>"
        + "".join(markup)
    )
    (OUT / "index.html").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "viewport": VIEWPORT,
                "samples": SAMPLES,
                "max_width": max_width,
                "cases": cases,
                "html_bytes": len(html.encode()),
            },
            indent=2,
        )
        + "\n"
    )

    pair_registrations: list[str] = []
    pair_keyframes: list[str] = []
    pair_rules: list[str] = []
    pair_markup: list[str] = []
    pair_cases: list[dict[str, object]] = []
    pair_index = 0
    for bits in (8, 9, 10):
        base = 1 << bits
        packed_max = base * base - 1
        viewport = 4 * base * base
        width_offset = 2 * packed_max
        left_offset = viewport - 3 * packed_max / 2
        track_width = int(viewport + 4 * packed_max)
        for sample in range(SAMPLES):
            values = [rng.randrange(base) for _ in range(4)]
            packed_left = values[0] + base * values[1]
            packed_width = values[2] + base * values[3]
            left = left_offset + packed_left
            width = width_offset + packed_width
            timeline = f"--pt{pair_index}"
            cover = f"--pc{pair_index}"
            entry = f"--pe{pair_index}"
            decoded_left = f"--pl{pair_index}"
            decoded_width = f"--pw{pair_index}"
            animation = f"pk{pair_index}"
            pair_registrations.append(
                f'@property {cover}{{syntax:"<number>";inherits:true;initial-value:-1}}'
                f'@property {entry}{{syntax:"<number>";inherits:true;initial-value:-1}}'
                f'@property {decoded_left}{{syntax:"<number>";inherits:true;initial-value:-1}}'
                f'@property {decoded_width}{{syntax:"<number>";inherits:true;initial-value:-1}}'
            )
            pair_keyframes.append(
                f"@keyframes {animation}{{cover 0%{{{cover}:0;{entry}:0}}"
                f"entry 100%{{{entry}:1}}cover 100%{{{cover}:1;{entry}:1}}}}"
            )
            pair_rules.append(
                f".pscope-{pair_index}{{timeline-scope:{timeline}}}"
                f".pscroller-{pair_index}{{width:{viewport}px}}"
                f".ptrack-{pair_index}{{width:{track_width}px}}"
                f".plead-{pair_index}{{width:{left:.10f}px}}"
                f".psubject-{pair_index}{{width:{width:.10f}px;view-timeline:{timeline} inline}}"
                f".presult-{pair_index}{{animation-name:{animation};animation-duration:1s;"
                f"animation-timing-function:linear;animation-fill-mode:both;"
                f"animation-timeline:{timeline};"
                f"--w:calc(var({cover}) * {viewport} / (var({entry}) - var({cover})));"
                f"{decoded_width}:calc(round(nearest, var(--w) - {width_offset}, 1));"
                f"{decoded_left}:calc(round(nearest, {viewport} - var({entry}) * var(--w) "
                f"- {left_offset:.10f}, 1))}}"
            )
            pair_markup.append(
                f'<div class="pscope pscope-{pair_index}"><div class="pscroller pscroller-{pair_index}">'
                f'<div class="ptrack ptrack-{pair_index}"><i class="plead plead-{pair_index}"></i>'
                f'<i class="psubject psubject-{pair_index}"></i></div></div>'
                f'<output class="presult presult-{pair_index}"></output></div>'
            )
            pair_cases.append(
                {
                    "index": pair_index,
                    "bits": bits,
                    "values": values,
                    "packed_left": packed_left,
                    "packed_width": packed_width,
                }
            )
            pair_index += 1
    pair_css = (
        "".join(pair_registrations)
        + "".join(pair_keyframes)
        + ".pscroller{position:fixed;left:0;top:-20000px;height:1px;overflow-x:scroll}"
        + ".ptrack{position:relative;height:1px;display:flex}"
        + ".plead,.psubject{display:block;flex:none;height:1px}"
        + "".join(pair_rules)
    )
    pair_html = (
        '<!doctype html><meta charset="utf-8"><title>Packed pair timeline precision</title>'
        "<style>"
        + pair_css
        + "</style>"
        + "".join(pair_markup)
    )
    (OUT / "paired.html").write_text(pair_html)
    (OUT / "paired-reference.json").write_text(
        json.dumps({"samples": SAMPLES, "cases": pair_cases, "html_bytes": len(pair_html.encode())}, indent=2)
        + "\n"
    )
    print(
        {
            "cases": len(cases),
            "max_width": max_width,
            "html_bytes": len(html.encode()),
            "paired_cases": len(pair_cases),
            "paired_html_bytes": len(pair_html.encode()),
        }
    )


if __name__ == "__main__":
    main()
