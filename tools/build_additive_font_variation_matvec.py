#!/usr/bin/env python3
"""Build dense matvec probes using additive font-variation animations."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "additive-font-variation-matvec"
SHAPES = (
    (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (768, 768),
    (3_072, 768),
)
CASES = 4
SHADOW_CHUNK = 240
PACKED_VALUES = 4
PACKED_2D_VALUES = 8
PACKED_LEVELS = 63


def tag(index: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digits = ""
    value = index
    for _ in range(3):
        digits = alphabet[value % 36] + digits
        value //= 36
    return "A" + digits


def settings(values: np.ndarray) -> str:
    return ",".join(
        f'"{tag(index)}" {float(value):.8g}'
        for index, value in enumerate(values)
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"cases": CASES, "sizes": []}
    rng = np.random.default_rng(0xADD17A)
    for input_size, output_size in SHAPES:
        label = f"{input_size}x{output_size}"
        matrix = rng.normal(
            0, 1 / math.sqrt(input_size), (output_size, input_size)
        )
        inputs = rng.uniform(0.05, 0.95, (CASES, input_size))
        expected = inputs @ matrix.T
        packed_codes = np.rint(inputs * PACKED_LEVELS).astype(np.int64)
        packed_inputs = packed_codes / PACKED_LEVELS
        packed_expected = packed_inputs @ matrix.T
        axes_zero = settings(np.zeros(output_size))
        keyframes = []
        for column in range(input_size):
            keyframes.append(
                f"@keyframes c{column}{{from{{font-variation-settings:"
                f"var(--zero)}}to{{font-variation-settings:"
                f"{settings(matrix[:, column])}}}}}"
            )
        variables = ";".join(
            f"--x{index}:{inputs[0, index]:.8g}" for index in range(input_size)
        )
        names = ",".join(f"c{index}" for index in range(input_size))
        delays = ",".join(
            f"calc(-1s * var(--x{index}))" for index in range(input_size)
        )
        css = (
            f":root{{--zero:{axes_zero}}}"
            + "".join(keyframes)
            + f"#result{{{variables};font-variation-settings:var(--zero);"
            f"animation-name:{names};animation-duration:1s;"
            f"animation-delay:{delays};animation-play-state:paused;"
            "animation-timing-function:linear;animation-fill-mode:both;"
            "animation-composition:add}}"
        )
        html = (
            "<!doctype html><meta charset=\"utf-8\">"
            f"<title>Additive font-variation {label} matvec</title>"
            f"<link rel=\"stylesheet\" href=\"n{label}.css\">"
            f"<output id=\"result\">{label}</output>"
        )
        (OUT / f"n{label}.css").write_text(css)
        (OUT / f"n{label}.html").write_text(html)
        nested = '<output id="nested-result">result</output>'
        for index in reversed(range(input_size)):
            nested = (
                f'<div class="nested-carrier" data-index="{index}" '
                f'style="width:{inputs[0, index] * 100:.8g}px">'
                f'<div class="nested-contribution" style="animation-name:c{index}">'
                f"{nested}</div></div>"
            )
        nested_css = (
            "#nested-root{font-variation-settings:var(--zero)}"
            ".nested-carrier{container-type:inline-size;position:relative;height:1px}"
            ".nested-contribution{position:absolute;animation-duration:1s;"
            "animation-delay:calc(-1s * (100cqi / 100px));"
            "animation-play-state:paused;animation-timing-function:linear;"
            "animation-fill-mode:both;animation-composition:add}"
        )
        nested_html = (
            "<!doctype html><meta charset=\"utf-8\">"
            f"<title>Nested additive font-variation {label} matvec</title>"
            f"<link rel=\"stylesheet\" href=\"n{label}.css\">"
            f"<link rel=\"stylesheet\" href=\"n{label}-nested.css\">"
            f'<div id="nested-root">{nested}</div>'
        )
        nested_xhtml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            f'<title>Nested additive font-variation {label} matvec</title>'
            f'<link rel="stylesheet" href="n{label}.css" />'
            f'<link rel="stylesheet" href="n{label}-nested.css" />'
            f'</head><body><div id="nested-root">{nested}</div></body></html>'
        )
        one_level = (
            '<output id="one-result" class="one-contribution" '
            f'style="animation-name:c{input_size - 1}">result</output>'
        )
        for index in reversed(range(1, input_size)):
            one_level = (
                f'<div class="one-carrier one-contribution" data-index="{index}" '
                f'style="width:{inputs[0, index] * 100:.8g}px;'
                f'animation-name:c{index - 1}">{one_level}</div>'
            )
        one_level = (
            f'<div class="one-carrier" data-index="0" '
            f'style="width:{inputs[0, 0] * 100:.8g}px">{one_level}</div>'
        )
        one_css = (
            "#one-root{font-variation-settings:var(--zero)}"
            ".one-carrier{container-type:inline-size;position:relative;height:1px}"
            ".one-contribution{position:absolute;animation-duration:1s;"
            "animation-delay:calc(-1s * (100cqi / 100px));"
            "animation-play-state:paused;animation-timing-function:linear;"
            "animation-fill-mode:both;animation-composition:add}"
        )
        one_xhtml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            f'<title>One-level additive font-variation {label} matvec</title>'
            f'<link rel="stylesheet" href="n{label}.css" />'
            f'<link rel="stylesheet" href="n{label}-one.css" />'
            f'</head><body><div id="one-root">{one_level}</div></body></html>'
        )
        (OUT / f"n{label}-nested.css").write_text(nested_css)
        (OUT / f"n{label}-nested.html").write_text(nested_html)
        (OUT / f"n{label}-nested.xhtml").write_text(nested_xhtml)
        (OUT / f"n{label}-one.css").write_text(one_css)
        (OUT / f"n{label}-one.xhtml").write_text(one_xhtml)

        chunk_ranges = [
            (start, min(start + SHADOW_CHUNK, input_size))
            for start in range(0, input_size, SHADOW_CHUNK)
        ]
        next_shadow = ""
        for chunk_index, (start, stop) in reversed(list(enumerate(chunk_ranges))):
            leaf_tag = "output" if stop == input_size else "div"
            leaf_id = ' id="shadow-result"' if stop == input_size else ""
            leaf_class = "one-contribution"
            if stop != input_size:
                leaf_class += " chunk-host"
            chain = (
                f'<{leaf_tag}{leaf_id} class="{leaf_class}" '
                f'style="animation-name:c{stop - 1}">'
                + ("result" if stop == input_size else next_shadow)
                + f"</{leaf_tag}>"
            )
            for index in reversed(range(start + 1, stop)):
                chain = (
                    f'<div class="one-carrier one-contribution" data-index="{index}" '
                    f'style="width:{inputs[0, index] * 100:.8g}px;'
                    f'animation-name:c{index - 1}">{chain}</div>'
                )
            chain = (
                f'<div class="one-carrier" data-index="{start}" '
                f'style="width:{inputs[0, start] * 100:.8g}px">{chain}</div>'
            )
            chunk_css = one_css + "".join(keyframes[start:stop])
            chunk_name = f"n{label}-shadow-{chunk_index}.css"
            (OUT / chunk_name).write_text(chunk_css)
            next_shadow = (
                '<template shadowrootmode="open">'
                f'<link rel="stylesheet" href="{chunk_name}">'
                + chain
                + "</template>"
            )
        shadow_html = (
            "<!doctype html><meta charset=\"utf-8\">"
            f"<title>Shadow-chunk additive font-variation {label} matvec</title>"
            f"<style>:root{{--zero:{axes_zero}}}#shadow-root-base{{"
            "font-variation-settings:var(--zero)}}</style>"
            f'<div id="shadow-root-base">{next_shadow}</div>'
        )
        (OUT / f"n{label}-shadow.html").write_text(shadow_html)

        packed_widths = []
        packed_groups = []
        for start in range(0, input_size, PACKED_VALUES):
            stop = min(start + PACKED_VALUES, input_size)
            codes = packed_codes[0, start:stop]
            packed_integer = sum(
                int(code) * 64**place for place, code in enumerate(codes)
            )
            # Four radix-64 digits fit exactly in the 24-bit integer range.
            # A fifth digit would require fractional pixels at ~2^24px, where
            # Chromium's float-backed layout drops the low digit.
            packed_widths.append(float(packed_integer))
            packed_groups.append((start, stop))
        packed_delays = []
        packed_integer_expr = "(100cqi / 1px)"
        for place in range(PACKED_VALUES):
            if place == 0:
                digit = f"mod(round(nearest,{packed_integer_expr},1),64)"
            elif place == PACKED_VALUES - 1:
                digit = (
                    f"round(down,{packed_integer_expr} / {64**place},1)"
                )
            else:
                digit = (
                    f"mod(round(down,{packed_integer_expr} / {64**place},1),64)"
                )
            packed_delays.append(f"calc(-1s * {digit} / {PACKED_LEVELS})")
        packed_css = (
            "#packed-root{font-variation-settings:var(--zero)}"
            ".packed-carrier{container-type:inline-size;position:relative;height:1px}"
            ".packed-contribution{position:absolute;animation-duration:1s;"
            f"animation-delay:{','.join(packed_delays)};"
            "animation-play-state:paused;animation-timing-function:linear;"
            "animation-fill-mode:both;animation-composition:add}"
        )
        packed_chain = (
            f'<div class="packed-carrier" data-group="0" '
            f'style="width:{packed_widths[0]:.0f}px">'
        )
        closing = ["</div>"]
        for group in range(1, len(packed_groups)):
            previous_start, previous_stop = packed_groups[group - 1]
            names = ",".join(
                f"c{index}" for index in range(previous_start, previous_stop)
            )
            packed_chain += (
                f'<div class="packed-carrier packed-contribution" '
                f'data-group="{group}" '
                f'style="width:{packed_widths[group]:.0f}px;'
                f'animation-name:{names}">'
            )
            closing.append("</div>")
        final_start, final_stop = packed_groups[-1]
        final_names = ",".join(
            f"c{index}" for index in range(final_start, final_stop)
        )
        packed_chain += (
            f'<output id="packed-result" class="packed-contribution" '
            f'style="animation-name:{final_names}">result</output>'
            + "".join(reversed(closing))
        )
        packed_xhtml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            f'<title>Packed-container additive {label} matvec</title>'
            f'<link rel="stylesheet" href="n{label}.css" />'
            f'<link rel="stylesheet" href="n{label}-packed.css" />'
            f'</head><body><div id="packed-root">{packed_chain}</div></body></html>'
        )
        (OUT / f"n{label}-packed.css").write_text(packed_css)
        (OUT / f"n{label}-packed.xhtml").write_text(packed_xhtml)

        packed_2d_widths = []
        packed_2d_heights = []
        packed_2d_groups = []
        for start in range(0, input_size, PACKED_2D_VALUES):
            stop = min(start + PACKED_2D_VALUES, input_size)
            codes = packed_codes[0, start:stop]
            width_codes = codes[:PACKED_VALUES]
            height_codes = codes[PACKED_VALUES:]
            packed_2d_widths.append(sum(
                int(code) * 64**place
                for place, code in enumerate(width_codes)
            ))
            packed_2d_heights.append(sum(
                int(code) * 64**place
                for place, code in enumerate(height_codes)
            ))
            packed_2d_groups.append((start, stop))

        def packet_delays(container_unit: str) -> list[str]:
            integer_expr = f"(100{container_unit} / 1px)"
            result = []
            for place in range(PACKED_VALUES):
                if place == 0:
                    digit = f"mod(round(nearest,{integer_expr},1),64)"
                elif place == PACKED_VALUES - 1:
                    digit = f"round(down,{integer_expr} / {64**place},1)"
                else:
                    digit = (
                        f"mod(round(down,{integer_expr} / {64**place},1),64)"
                    )
                result.append(f"calc(-1s * {digit} / {PACKED_LEVELS})")
            return result

        packed_2d_delays = packet_delays("cqi") + packet_delays("cqb")
        packed_2d_css = (
            "#packed2d-root{font-variation-settings:var(--zero)}"
            ".packed2d-carrier{container-type:size;position:relative}"
            ".packed2d-contribution{position:absolute;animation-duration:1s;"
            f"animation-delay:{','.join(packed_2d_delays)};"
            "animation-play-state:paused;animation-timing-function:linear;"
            "animation-fill-mode:both;animation-composition:add}"
        )
        packed_2d_chain = (
            f'<div class="packed2d-carrier" data-group="0" '
            f'style="width:{packed_2d_widths[0]}px;'
            f'height:{packed_2d_heights[0]}px">'
        )
        packed_2d_closing = ["</div>"]
        for group in range(1, len(packed_2d_groups)):
            previous_start, previous_stop = packed_2d_groups[group - 1]
            names = ",".join(
                f"c{index}" for index in range(previous_start, previous_stop)
            )
            packed_2d_chain += (
                f'<div class="packed2d-carrier packed2d-contribution" '
                f'data-group="{group}" '
                f'style="width:{packed_2d_widths[group]}px;'
                f'height:{packed_2d_heights[group]}px;'
                f'animation-name:{names}">'
            )
            packed_2d_closing.append("</div>")
        final_start, final_stop = packed_2d_groups[-1]
        final_names = ",".join(
            f"c{index}" for index in range(final_start, final_stop)
        )
        packed_2d_chain += (
            f'<output id="packed2d-result" class="packed2d-contribution" '
            f'style="animation-name:{final_names}">result</output>'
            + "".join(reversed(packed_2d_closing))
        )
        packed_2d_xhtml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            f'<title>2D packed-container additive {label} matvec</title>'
            f'<link rel="stylesheet" href="n{label}.css" />'
            f'<link rel="stylesheet" href="n{label}-packed2d.css" />'
            f'</head><body><div id="packed2d-root">{packed_2d_chain}</div>'
            '</body></html>'
        )
        (OUT / f"n{label}-packed2d.css").write_text(packed_2d_css)
        (OUT / f"n{label}-packed2d.xhtml").write_text(packed_2d_xhtml)
        (OUT / f"n{label}.json").write_text(json.dumps({
            "inputSize": input_size,
            "outputSize": output_size,
            "inputs": inputs.tolist(),
            "expected": expected.tolist(),
            "packedInputs": packed_inputs.tolist(),
            "packedExpected": packed_expected.tolist(),
            "packedWidths": [
                [
                    sum(
                        int(code) * 64**place
                        for place, code in enumerate(
                            row[start:min(start + PACKED_VALUES, input_size)]
                        )
                    )
                    for start in range(0, input_size, PACKED_VALUES)
                ]
                for row in packed_codes
            ],
            "packed2dWidths": [
                [
                    sum(
                        int(code) * 64**place
                        for place, code in enumerate(
                            row[start:min(start + PACKED_VALUES, input_size)]
                        )
                    )
                    for start in range(0, input_size, PACKED_2D_VALUES)
                ]
                for row in packed_codes
            ],
            "packed2dHeights": [
                [
                    sum(
                        int(code) * 64**place
                        for place, code in enumerate(
                            row[start + PACKED_VALUES:min(
                                start + PACKED_2D_VALUES, input_size
                            )]
                        )
                    )
                    for start in range(0, input_size, PACKED_2D_VALUES)
                ]
                for row in packed_codes
            ],
        }))
        manifest["sizes"].append({
            "label": label,
            "inputSize": input_size,
            "outputSize": output_size,
            "cssBytes": len(css.encode()),
            "htmlBytes": len(html.encode()),
            "nestedHtmlBytes": len(nested_html.encode()),
            "nestedXhtmlBytes": len(nested_xhtml.encode()),
            "oneXhtmlBytes": len(one_xhtml.encode()),
            "oneCssBytes": len(one_css.encode()),
            "shadowHtmlBytes": len(shadow_html.encode()),
            "shadowChunks": len(chunk_ranges),
            "packedXhtmlBytes": len(packed_xhtml.encode()),
            "packedCssBytes": len(packed_css.encode()),
            "packedGroups": len(packed_groups),
            "packed2dXhtmlBytes": len(packed_2d_xhtml.encode()),
            "packed2dCssBytes": len(packed_2d_css.encode()),
            "packed2dGroups": len(packed_2d_groups),
            "nestedCssBytes": len(nested_css.encode()),
            "weightValues": input_size * output_size,
        })
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
