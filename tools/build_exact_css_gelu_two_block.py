#!/usr/bin/env python3
"""Add compute-once exact CSS GELU to the existing two-block HVAR page.

The baseline artifacts are read but never modified.  The generated comparison
page keeps the same attention, FC, geometry transport, residuals, and output
readback.  Only the two MLP projection nonlinearities change: GELU is evaluated
once on each projection ancestor and pure linear HVAR fonts consume the result.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

from build_gpt2_block_css import global_axis_tag, model_data
from build_hvar_parallel_mlp_group import replace_linear_hvar
from build_matrix_backend_prototypes import build_direct_font_backend
from build_pretrained_gpt2 import css_number


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "avar2-gelu-linear-hvar-full-mlp-g13"
SOURCE = OUT / "connected-two-block-serial-projection-layoutless.html"
OUTPUT = OUT / "connected-two-block-exact-css-gelu-layoutless.html"
SOURCE_B0_CSS = OUT / "stage-connected-mlp-b0.css"
SOURCE_B1_CSS = OUT / "stage-serial-b1-projection.css"
OUTPUT_B0_CSS = OUT / "stage-exact-css-gelu-mlp-b0.css"
OUTPUT_B1_CSS = OUT / "stage-exact-css-gelu-serial-b1-projection.css"

HIDDEN = 3072
OUTPUTS = 768
GROUPS = 13
PAIR_QUOTIENT, PAIR_REMAINDER = divmod(HIDDEN // 2, GROUPS)
GROUP_WIDTHS = [
    2 * (PAIR_QUOTIENT + (1 if group < PAIR_REMAINDER else 0))
    for group in range(GROUPS)
]
GROUP_STARTS = np.cumsum([0, *GROUP_WIDTHS[:-1]]).tolist()
BASE_ADVANCE = 16_000
B0_CODEPOINT = 0xE000
B1_CODEPOINT = 0xF0000
B0_PREACTIVATION_SCALE = 12.5
B1_PREACTIVATION_SCALE = 19.0
B0_OUTPUT_SCALE = 192.0
B1_OUTPUT_SCALE = 66.0


def exact_gelu_function(name: str, scale: float) -> str:
    return f"""@function --{name}(--z <number>) returns <number>{{
--t:clamp(-20,calc(.7978845608028654 *
(var(--z) + .044715 * pow(var(--z),3))),20);
result:calc(.5 * var(--z) *
(1 + (exp(2 * var(--t)) - 1)/(exp(2 * var(--t)) + 1)) / {css_number(scale)})}}
"""


def build_pure_fonts() -> tuple[str, dict[str, int]]:
    faces = []
    sizes = {"block0": 0, "block1": 0}
    blocks = [
        (0, model_data(0), B0_PREACTIVATION_SCALE, B0_OUTPUT_SCALE),
        (1, model_data(1), B1_PREACTIVATION_SCALE, B1_OUTPUT_SCALE),
    ]
    for block, data, hidden_scale, output_scale in blocks:
        for group, (start, width) in enumerate(
            zip(GROUP_STARTS, GROUP_WIDTHS, strict=True)
        ):
            stop = start + width
            if block == 0:
                tags = [global_axis_tag(local) for local in range(width)]
                codepoint = B0_CODEPOINT
            else:
                tags = [global_axis_tag(hidden) for hidden in range(start, stop)]
                codepoint = B1_CODEPOINT + group * OUTPUTS
            stem = f"exact-css-gelu-b{block}-projection-{group}"
            ttf = OUT / f"{stem}.ttf"
            woff2 = ttf.with_suffix(".woff2")
            if not woff2.exists():
                build_direct_font_backend(
                    np.zeros((OUTPUTS, width), dtype=np.int16),
                    ttf,
                    signed_axes=True,
                    base_advance=BASE_ADVANCE,
                    codepoint_start=codepoint,
                    axis_tags=tags,
                )
                font = TTFont(ttf, recalcTimestamp=False)
                replace_linear_hvar(
                    font,
                    tags,
                    data["mlp_proj_weight"][:, start:stop],
                    hidden_scale,
                    output_scale,
                )
                font.recalcTimestamp = False
                font.save(ttf)
                compressed = TTFont(ttf, recalcTimestamp=False)
                compressed.flavor = "woff2"
                compressed.save(woff2)
            digest = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
            family = f"ExactCssGeluB{block}Projection{group}"
            unicode_range = (
                f";unicode-range:U+{codepoint:X}-{codepoint + OUTPUTS - 1:X}"
                if block == 1
                else ""
            )
            faces.append(
                f'@font-face{{font-family:{family};src:url("{woff2.name}?v={digest}") '
                f'format("woff2"){unicode_range}}}'
            )
            sizes[f"block{block}"] += woff2.stat().st_size
    return "".join(faces), sizes


def build_b0_css() -> str:
    css = SOURCE_B0_CSS.read_text()
    css = exact_gelu_function("exact-gelu-b0", B0_PREACTIVATION_SCALE) + css
    for group, width in enumerate(GROUP_WIDTHS):
        declarations = "".join(
            f"--b0-g{local}:--exact-gelu-b0(calc(var(--z{local}) * "
            f"{css_number(B0_PREACTIVATION_SCALE)}));"
            for local in range(width)
        )
        settings = ",".join(
            f'"{global_axis_tag(local)}" var(--b0-g{local})'
            for local in range(width)
        )
        replacement = (
            f".projection-{group}{{{declarations}"
            f"font-family:ExactCssGeluB0Projection{group};"
            f"font-variation-settings:{settings}}}"
        )
        pattern = re.compile(
            rf"\.projection-{group}\{{font-family:GeluProjection{group};"
            rf"font-variation-settings:[^}}]+\}}"
        )
        css, count = pattern.subn(replacement, css, count=1)
        if count != 1:
            raise ValueError(f"could not replace block-0 projection group {group}")
    return css


def build_b1_css() -> str:
    css = SOURCE_B1_CSS.read_text()
    for group in range(GROUPS):
        css = css.replace(
            f"SerialB1Projection{group}",
            f"ExactCssGeluB1Projection{group}",
        )
    declarations = "".join(
        f"--b1-g-{hidden:04d}:--exact-gelu-b1("
        f"calc(var(--serial-z-{hidden:04d}) * {css_number(B1_PREACTIVATION_SCALE)}));"
        for hidden in range(HIDDEN)
    )
    settings = ",".join(
        f'"{global_axis_tag(hidden)}" var(--b1-g-{hidden:04d})'
        for hidden in range(HIDDEN)
    )
    pattern = re.compile(
        r"(\.serial-root\{[^}]*?)font-variation-settings:[^}]+\}", re.DOTALL
    )
    css, count = pattern.subn(
        rf"\1{declarations}font-variation-settings:{settings}}}",
        css,
        count=1,
    )
    if count != 1:
        raise ValueError("could not replace block-1 serial projection rule")
    return exact_gelu_function("exact-gelu-b1", B1_PREACTIVATION_SCALE) + css


def registrations() -> str:
    b0 = "".join(
        f'@property --b0-g{index}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for index in range(max(GROUP_WIDTHS))
    )
    b1 = "".join(
        f'@property --b1-g-{index:04d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(HIDDEN)
    )
    return b0 + b1


def main() -> None:
    faces, font_sizes = build_pure_fonts()
    OUTPUT_B0_CSS.write_text(build_b0_css())
    OUTPUT_B1_CSS.write_text(build_b1_css())
    b0_digest = hashlib.sha256(OUTPUT_B0_CSS.read_bytes()).hexdigest()[:12]
    b1_digest = hashlib.sha256(OUTPUT_B1_CSS.read_bytes()).hexdigest()[:12]

    html = SOURCE.read_text()
    html = html.replace(
        "<title>Layoutless serial projection two-block GPT-2</title>",
        "<title>Two-block GPT-2 with compute-once exact CSS GELU</title>",
        1,
    )
    html, b0_links = re.subn(
        r"stage-connected-mlp-b0\.css\?v=[0-9a-f]+",
        f"{OUTPUT_B0_CSS.name}?v={b0_digest}",
        html,
        count=1,
    )
    html, b1_links = re.subn(
        r"stage-serial-b1-projection\.css\?v=[0-9a-f]+",
        f"{OUTPUT_B1_CSS.name}?v={b1_digest}",
        html,
        count=1,
    )
    if b0_links != 1 or b1_links != 1:
        raise ValueError(f"unexpected projection link counts: b0={b0_links}, b1={b1_links}")
    html = html.replace("</style>", faces + registrations() + "</style>", 1)
    OUTPUT.write_text(html)

    manifest = {
        "source": SOURCE.name,
        "output": OUTPUT.name,
        "runtimeContainsJavaScript": "<script" in html.lower(),
        "htmlBytes": OUTPUT.stat().st_size,
        "newStageCssBytes": OUTPUT_B0_CSS.stat().st_size + OUTPUT_B1_CSS.stat().st_size,
        "pureProjectionFontBytes": font_sizes,
        "totalPureProjectionFontBytes": sum(font_sizes.values()),
        "groups": GROUPS,
        "groupWidths": GROUP_WIDTHS,
        "block0PreactivationScale": B0_PREACTIVATION_SCALE,
        "block1PreactivationScale": B1_PREACTIVATION_SCALE,
        "block0OutputScale": B0_OUTPUT_SCALE,
        "block1OutputScale": B1_OUTPUT_SCALE,
    }
    (OUT / "exact-css-gelu-two-block-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(
        f"built {OUTPUT.name}: {OUTPUT.stat().st_size / 1e6:.2f} MB HTML, "
        f"{sum(font_sizes.values()) / 1e6:.2f} MB pure fonts"
    )


if __name__ == "__main__":
    main()
