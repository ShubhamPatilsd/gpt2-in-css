#!/usr/bin/env python3
"""Inline compute-once CSS GELU results into projection axis lists.

The established exact page first writes every GELU result into a registered
custom property and then references those properties from
font-variation-settings.  This variant puts each typed CSS function call
directly in that inherited axis list, removing 3,310 intermediate properties
without changing the model graph, fonts, or numeric formula.
"""

from __future__ import annotations

import hashlib
import json
import re

from build_exact_css_gelu_two_block import (
    B0_PREACTIVATION_SCALE,
    B1_PREACTIVATION_SCALE,
    GROUP_STARTS,
    GROUP_WIDTHS,
    GROUPS,
    HIDDEN,
    OUT,
    SOURCE,
    SOURCE_B0_CSS,
    SOURCE_B1_CSS,
    build_pure_fonts,
    exact_gelu_function,
)
from build_gpt2_block_css import global_axis_tag
from build_pretrained_gpt2 import css_number


OUTPUT = OUT / "connected-two-block-exact-css-gelu-inline-layoutless.html"
OUTPUT_B0_CSS = OUT / "stage-exact-css-gelu-inline-mlp-b0.css"
OUTPUT_B1_CSS = OUT / "stage-exact-css-gelu-inline-serial-b1-projection.css"


def build_b0_css() -> str:
    css = SOURCE_B0_CSS.read_text()
    css = exact_gelu_function("exact-gelu-inline-b0", B0_PREACTIVATION_SCALE) + css
    for group, width in enumerate(GROUP_WIDTHS):
        settings = ",".join(
            f'"{global_axis_tag(local)}" --exact-gelu-inline-b0('
            f"calc(var(--z{local}) * {css_number(B0_PREACTIVATION_SCALE)}))"
            for local in range(width)
        )
        replacement = (
            f".projection-{group}{{font-family:ExactCssGeluB0Projection{group};"
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
    settings = ",".join(
        f'"{global_axis_tag(hidden)}" --exact-gelu-inline-b1('
        f"calc(var(--serial-z-{hidden:04d}) * "
        f"{css_number(B1_PREACTIVATION_SCALE)}))"
        for hidden in range(HIDDEN)
    )
    pattern = re.compile(
        r"(\.serial-root\{[^}]*?)font-variation-settings:[^}]+\}", re.DOTALL
    )
    css, count = pattern.subn(
        rf"\1font-variation-settings:{settings}}}",
        css,
        count=1,
    )
    if count != 1:
        raise ValueError("could not replace block-1 serial projection rule")
    return exact_gelu_function("exact-gelu-inline-b1", B1_PREACTIVATION_SCALE) + css


def main() -> None:
    faces, font_sizes = build_pure_fonts()
    OUTPUT_B0_CSS.write_text(build_b0_css())
    OUTPUT_B1_CSS.write_text(build_b1_css())
    b0_digest = hashlib.sha256(OUTPUT_B0_CSS.read_bytes()).hexdigest()[:12]
    b1_digest = hashlib.sha256(OUTPUT_B1_CSS.read_bytes()).hexdigest()[:12]

    html = SOURCE.read_text()
    html = html.replace(
        "<title>Layoutless serial projection two-block GPT-2</title>",
        "<title>Two-block GPT-2 with inline exact CSS GELU</title>",
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
    html = html.replace("</style>", faces + "</style>", 1)
    OUTPUT.write_text(html)

    manifest = {
        "source": SOURCE.name,
        "output": OUTPUT.name,
        "runtimeContainsJavaScript": "<script" in html.lower(),
        "htmlBytes": OUTPUT.stat().st_size,
        "newStageCssBytes": OUTPUT_B0_CSS.stat().st_size + OUTPUT_B1_CSS.stat().st_size,
        "pureProjectionFontBytes": font_sizes,
        "removedRegisteredGeluProperties": HIDDEN + max(GROUP_WIDTHS),
        "geluEvaluationSite": "directly inside inherited font-variation-settings",
    }
    (OUT / "exact-css-gelu-inline-two-block-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(
        f"built {OUTPUT.name}: {OUTPUT.stat().st_size / 1e6:.2f} MB HTML, "
        f"{(OUTPUT_B0_CSS.stat().st_size + OUTPUT_B1_CSS.stat().st_size) / 1e6:.2f} MB CSS"
    )


if __name__ == "__main__":
    main()
