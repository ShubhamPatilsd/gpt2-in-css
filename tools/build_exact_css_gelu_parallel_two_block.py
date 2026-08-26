#!/usr/bin/env python3
"""Build the parallel two-block page with compute-once exact CSS GELU.

The source page already evaluates the 13 block-1 MLP slices in parallel and
adds their 768 partial projections with anchor-size().  This variant preserves
that graph while replacing the projection fonts' repeated avar2 GELU with one
typed CSS GELU evaluation per hidden coordinate and pure linear HVAR fonts.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

from build_exact_css_gelu_two_block import (
    BASE_ADVANCE,
    B1_OUTPUT_SCALE,
    B1_PREACTIVATION_SCALE,
    GROUP_STARTS,
    GROUP_WIDTHS,
    GROUPS,
    OUTPUTS,
    OUT,
    build_b0_css,
    exact_gelu_function,
)
from build_gpt2_block_css import global_axis_tag, model_data
from build_hvar_parallel_mlp_group import replace_linear_hvar
from build_matrix_backend_prototypes import build_direct_font_backend
from build_pretrained_gpt2 import css_number


SOURCE = OUT / "connected-two-block-shadow-staged-layoutless.html"
OUTPUT = OUT / "connected-two-block-parallel-exact-css-gelu-layoutless.html"
SOURCE_B1_CSS = OUT / "stage-connected-mlp-b1.css"
OUTPUT_B0_CSS = OUT / "stage-exact-css-gelu-mlp-b0.css"
OUTPUT_B1_CSS = OUT / "stage-exact-css-gelu-parallel-b1.css"
B1_CODEPOINT = 0xE000


def build_b1_pure_fonts() -> tuple[str, int]:
    data = model_data(1)
    faces = []
    total_bytes = 0
    for group, (start, width) in enumerate(
        zip(GROUP_STARTS, GROUP_WIDTHS, strict=True)
    ):
        stop = start + width
        tags = [global_axis_tag(local) for local in range(width)]
        stem = f"exact-css-gelu-parallel-b1-projection-{group}"
        ttf = OUT / f"{stem}.ttf"
        woff2 = ttf.with_suffix(".woff2")
        if not woff2.exists():
            build_direct_font_backend(
                np.zeros((OUTPUTS, width), dtype=np.int16),
                ttf,
                signed_axes=True,
                base_advance=BASE_ADVANCE,
                codepoint_start=B1_CODEPOINT,
                axis_tags=tags,
            )
            font = TTFont(ttf, recalcTimestamp=False)
            replace_linear_hvar(
                font,
                tags,
                data["mlp_proj_weight"][:, start:stop],
                B1_PREACTIVATION_SCALE,
                B1_OUTPUT_SCALE,
            )
            font.recalcTimestamp = False
            font.save(ttf)
            compressed = TTFont(ttf, recalcTimestamp=False)
            compressed.flavor = "woff2"
            compressed.save(woff2)
        digest = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
        family = f"ExactCssGeluParallelB1Projection{group}"
        faces.append(
            f'@font-face{{font-family:{family};'
            f'src:url("{woff2.name}?v={digest}") format("woff2");'
            f'unicode-range:U+{B1_CODEPOINT:X}-{B1_CODEPOINT + OUTPUTS - 1:X}}}'
        )
        total_bytes += woff2.stat().st_size
    return "".join(faces), total_bytes


def build_b1_css() -> str:
    css = SOURCE_B1_CSS.read_text()
    css = exact_gelu_function("exact-gelu-parallel-b1", B1_PREACTIVATION_SCALE) + css
    for group, width in enumerate(GROUP_WIDTHS):
        declarations = "".join(
            f"--b1-g{local}:--exact-gelu-parallel-b1("
            f"calc(var(--b1-z{local}) * {css_number(B1_PREACTIVATION_SCALE)}));"
            for local in range(width)
        )
        settings = ",".join(
            f'"{global_axis_tag(local)}" var(--b1-g{local})'
            for local in range(width)
        )
        replacement = (
            f".b1-projection-{group}{{{declarations}"
            f"font-family:ExactCssGeluParallelB1Projection{group};"
            f"font-variation-settings:{settings}}}"
        )
        pattern = re.compile(
            rf"\.b1-projection-{group}\{{font-family:B1GeluProjection{group};"
            rf"font-variation-settings:[^}}]+\}}"
        )
        css, count = pattern.subn(replacement, css, count=1)
        if count != 1:
            raise ValueError(f"could not replace block-1 projection group {group}")
    return css


def registrations() -> str:
    width = max(GROUP_WIDTHS)
    b0 = "".join(
        f'@property --b0-g{index}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for index in range(width)
    )
    b1 = "".join(
        f'@property --b1-g{index}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for index in range(width)
    )
    return b0 + b1


def b0_faces() -> tuple[str, int]:
    faces = []
    total_bytes = 0
    for group in range(GROUPS):
        woff2 = OUT / f"exact-css-gelu-b0-projection-{group}.woff2"
        if not woff2.exists():
            raise FileNotFoundError(
                f"{woff2} is missing; run build_exact_css_gelu_two_block.py first"
            )
        digest = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
        faces.append(
            f'@font-face{{font-family:ExactCssGeluB0Projection{group};'
            f'src:url("{woff2.name}?v={digest}") format("woff2")}}'
        )
        total_bytes += woff2.stat().st_size
    return "".join(faces), total_bytes


def main() -> None:
    OUTPUT_B0_CSS.write_text(build_b0_css())
    OUTPUT_B1_CSS.write_text(build_b1_css())
    b0_font_faces, b0_font_bytes = b0_faces()
    b1_font_faces, b1_font_bytes = build_b1_pure_fonts()
    b0_digest = hashlib.sha256(OUTPUT_B0_CSS.read_bytes()).hexdigest()[:12]
    b1_digest = hashlib.sha256(OUTPUT_B1_CSS.read_bytes()).hexdigest()[:12]

    html = SOURCE.read_text()
    html = html.replace(
        "<title>Layoutless shadow-staged two-block GPT-2</title>",
        "<title>Parallel two-block GPT-2 with compute-once exact CSS GELU</title>",
        1,
    )
    html, b0_links = re.subn(
        r"stage-connected-mlp-b0\.css\?v=[0-9a-f]+",
        f"{OUTPUT_B0_CSS.name}?v={b0_digest}",
        html,
        count=1,
    )
    html, b1_links = re.subn(
        r"stage-connected-mlp-b1\.css\?v=[0-9a-f]+",
        f"{OUTPUT_B1_CSS.name}?v={b1_digest}",
        html,
        count=1,
    )
    if b0_links != 1 or b1_links != 1:
        raise ValueError(f"unexpected projection link counts: b0={b0_links}, b1={b1_links}")
    html = html.replace(
        "</style>",
        b0_font_faces + b1_font_faces + registrations() + "</style>",
        1,
    )
    OUTPUT.write_text(html)

    manifest = {
        "source": SOURCE.name,
        "output": OUTPUT.name,
        "runtimeContainsJavaScript": "<script" in html.lower(),
        "htmlBytes": OUTPUT.stat().st_size,
        "newStageCssBytes": OUTPUT_B0_CSS.stat().st_size + OUTPUT_B1_CSS.stat().st_size,
        "pureProjectionFontBytes": {
            "block0": b0_font_bytes,
            "block1": b1_font_bytes,
        },
        "groups": GROUPS,
        "groupWidths": GROUP_WIDTHS,
        "block1Graph": "13 parallel FC/GELU/projection slices plus anchor-size sum",
        "block1PreactivationScale": B1_PREACTIVATION_SCALE,
        "block1OutputScale": B1_OUTPUT_SCALE,
    }
    (OUT / "exact-css-gelu-parallel-two-block-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(
        f"built {OUTPUT.name}: {OUTPUT.stat().st_size / 1e6:.2f} MB HTML, "
        f"{(b0_font_bytes + b1_font_bytes) / 1e6:.2f} MB pure fonts"
    )


if __name__ == "__main__":
    main()
