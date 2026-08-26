#!/usr/bin/env python3
"""Build CSS-GELU -> pure-HVAR projection probes for GPT-2 block 1.

All generated runtime pages are HTML/CSS/fonts only.  JavaScript is used only
by the separate benchmark harness.  The pages isolate whether computing the
3,072 GELU values once as inherited typed custom properties is cheaper than
performing the nonlinear remapping inside every projected output glyph.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

from build_gpt2_block_css import global_axis_tag, model_data
from build_hvar_parallel_mlp_group import replace_linear_hvar
from build_matrix_backend_prototypes import build_direct_font_backend
from build_pretrained_gpt2 import css_number


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "css-gelu-projection"
CAPTURE = ROOT / "experiments" / "hvar-vector-oracle" / "captured-boundaries.json"
SOURCE_AVAR_PAGE = (
    ROOT / "experiments" / "hvar-vector-oracle" / "oracle-b1-projection-only.html"
)

HIDDEN = 3072
OUTPUTS = 768
GROUPS = 13
PAIR_QUOTIENT, PAIR_REMAINDER = divmod(HIDDEN // 2, GROUPS)
GROUP_WIDTHS = [
    2 * (PAIR_QUOTIENT + (1 if group < PAIR_REMAINDER else 0))
    for group in range(GROUPS)
]
GROUP_STARTS = np.cumsum([0, *GROUP_WIDTHS[:-1]]).tolist()
CODEPOINT_START = 0xF0000
BASE_ADVANCE = 16_000
PREACTIVATION_SCALE = 19.0
HIDDEN_SCALE = 18.5
OUTPUT_SCALE = 66.0
FRESH_VECTORS = 16


def gelu(value: np.ndarray | float) -> np.ndarray | float:
    return 0.5 * value * (
        1 + np.tanh(math.sqrt(2 / math.pi) * (value + 0.044715 * value**3))
    )


def knot_vector(count: int, low: float, high: float) -> np.ndarray:
    """Spend knots where GELU curves; its tails are nearly constant/linear."""
    if count < 4:
        raise ValueError("at least four knots are required")
    return np.r_[low, np.linspace(-4.0, 4.0, count - 2), high]


def properties(prefix: str, count: int, digits: int) -> str:
    return "".join(
        f'@property --{prefix}-{index:0{digits}d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(count)
    )


def declarations(prefix: str, values: np.ndarray, digits: int) -> str:
    return "".join(
        f"--{prefix}-{index:0{digits}d}:{css_number(float(value))};"
        for index, value in enumerate(values)
    )


def settings(prefix: str = "g") -> str:
    parts = []
    for start, width in zip(GROUP_STARTS, GROUP_WIDTHS, strict=True):
        for hidden in range(start, start + width):
            parts.append(
                f'"{global_axis_tag(hidden)}" var(--{prefix}-{hidden:04d})'
            )
    return ",".join(parts)


def exact_function() -> str:
    return """@function --gelu(--z <number>) returns <number>{
--t:clamp(-20,calc(.7978845608028654 *
(var(--z) + .044715 * pow(var(--z),3))),20);
result:calc(.5 * var(--z) *
(1 + (exp(2 * var(--t)) - 1)/(exp(2 * var(--t)) + 1)) / 18.5)}"""


def hinge_function(count: int, knots: np.ndarray) -> str:
    ys = np.asarray(gelu(knots), dtype=np.float64)
    slopes = np.diff(ys) / np.diff(knots)
    terms = [
        css_number(float(ys[0])),
        f"{css_number(float(slopes[0]))} * (var(--x) - "
        f"{css_number(float(knots[0]))})",
    ]
    for index in range(1, len(slopes)):
        delta = slopes[index] - slopes[index - 1]
        terms.append(
            f"{css_number(float(delta))} * max(0, var(--x) - "
            f"{css_number(float(knots[index]))})"
        )
    expression = " + ".join(terms)
    return (
        f"@function --gelu-pw{count}(--z <number>) returns <number>{{"
        f"--x:clamp({css_number(float(knots[0]))},var(--z),"
        f"{css_number(float(knots[-1]))});result:calc(({expression})/18.5)}}"
    )


def output_markup() -> str:
    rows = []
    for output in range(OUTPUTS):
        chars = "".join(
            f"&#x{CODEPOINT_START + group * OUTPUTS + output:X};"
            for group in range(GROUPS)
        )
        rows.append(f'<i class="output output-{output}" data-output="{output}">{chars}</i>')
    return '<div id="bank">' + "".join(rows) + "</div>"


def build_fonts(block1: dict[str, np.ndarray]) -> tuple[str, int]:
    faces = []
    total_bytes = 0
    for group, (start, width) in enumerate(
        zip(GROUP_STARTS, GROUP_WIDTHS, strict=True)
    ):
        stop = start + width
        tags = [global_axis_tag(hidden) for hidden in range(start, stop)]
        codepoint = CODEPOINT_START + group * OUTPUTS
        ttf = OUT / f"pure-projection-{group}.ttf"
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
                block1["mlp_proj_weight"][:, start:stop],
                HIDDEN_SCALE,
                OUTPUT_SCALE,
            )
            font.recalcTimestamp = False
            font.save(ttf)
            font = TTFont(ttf, recalcTimestamp=False)
            font.flavor = "woff2"
            font.save(woff2)
        digest = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
        family = f"PureProjection{group}"
        faces.append(
            f'@font-face{{font-family:{family};src:url("{woff2.name}?v={digest}") '
            f'format("woff2");unicode-range:U+{codepoint:X}-'
            f'{codepoint + OUTPUTS - 1:X}}}'
        )
        total_bytes += woff2.stat().st_size
    return "".join(faces), total_bytes


def page(
    *,
    title: str,
    faces: str,
    p0: np.ndarray,
    g0: np.ndarray,
    mode: str,
    knots: np.ndarray | None = None,
) -> str:
    registered = (
        properties("p", HIDDEN, 4)
        + properties("g", HIDDEN, 4)
    )
    initial = declarations("p", p0, 4)
    if mode == "ideal":
        initial += declarations("g", g0 / HIDDEN_SCALE, 4)
        function = ""
        gelu_declarations = ""
        gelu_owner = ""
        axis_stylesheet = "axes-inherited.css"
    else:
        if mode == "exact" or mode == "exact-local":
            function = exact_function()
            call = "--gelu"
        else:
            assert knots is not None
            count = int(mode.removeprefix("hinge-"))
            function = hinge_function(count, knots)
            call = f"--gelu-pw{count}"
        gelu_declarations = "".join(
            f"--g-{index:04d}:{call}(var(--p-{index:04d}));"
            for index in range(HIDDEN)
        )
        if mode == "exact-local":
            gelu_owner = f".output{{{gelu_declarations}}}"
            axis_stylesheet = "axes-output-local.css"
        else:
            gelu_owner = f"#state{{{gelu_declarations}}}"
            axis_stylesheet = "axes-inherited.css"

    families = ",".join(f"PureProjection{group}" for group in range(GROUPS))
    css = (
        faces
        + registered
        + function
        + "html,body{margin:0;padding:0}"
        + "#state{position:fixed;left:-300000px;top:0;"
        + initial
        + "}"
        + gelu_owner
        + f"#bank{{font-family:{families};font-size:1000px;font-style:normal;"
        + "font-kerning:none;font-variant-ligatures:none;line-height:1;"
        + "white-space:pre}}"
        + ".output{position:fixed;inset:0 auto auto 0;display:inline-flex;"
        + "height:1px;overflow:hidden;"
        + "font-family:inherit;font-size:inherit;font-style:inherit;"
        + "font-kerning:inherit;font-variant-ligatures:inherit;"
        + "line-height:inherit;white-space:pre}"
    )
    return (
        "<!doctype html><meta charset=\"utf-8\">"
        f"<title>{title}</title><style>{css}</style>"
        f'<link rel="stylesheet" href="{axis_stylesheet}">'
        f'<div id="state">{output_markup()}</div>'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    capture = json.loads(CAPTURE.read_text())
    cases = capture["cases"]
    preactivations = (
        np.asarray(
            [case["normalizedPreactivations"] for case in cases], dtype=np.float64
        )
        * PREACTIVATION_SCALE
    )
    residuals = np.asarray([case["residuals"] for case in cases], dtype=np.float64)
    if preactivations.shape != (4, HIDDEN) or residuals.shape != (4, OUTPUTS):
        raise ValueError("unexpected captured boundary shapes")
    hidden = np.asarray(gelu(preactivations), dtype=np.float64)
    if np.max(np.abs(hidden)) >= HIDDEN_SCALE:
        raise ValueError("HIDDEN_SCALE does not contain captured GELU values")

    block1 = model_data(1)
    faces, font_bytes = build_fonts(block1)
    axis_settings = settings()
    (OUT / "axes-inherited.css").write_text(
        f"#bank{{font-variation-settings:{axis_settings}}}"
    )
    (OUT / "axes-output-local.css").write_text(
        f".output{{font-variation-settings:{axis_settings}}}"
    )
    low = float(np.min(preactivations)) - 0.25
    high = float(np.max(preactivations)) + 0.25
    knots_by_count = {
        count: knot_vector(count, low, high) for count in (8, 16, 32)
    }

    variants = {
        "exact-inherited": ("exact", None),
        "exact-output-local": ("exact-local", None),
        "hinge-8-inherited": ("hinge-8", knots_by_count[8]),
        "hinge-16-inherited": ("hinge-16", knots_by_count[16]),
        "hinge-32-inherited": ("hinge-32", knots_by_count[32]),
        "ideal-post-gelu": ("ideal", None),
    }
    for filename, (mode, knots) in variants.items():
        rendered = page(
            title=f"CSS GELU projection: {filename}",
            faces=faces,
            p0=preactivations[0],
            g0=hidden[0],
            mode=mode,
            knots=knots,
        )
        (OUT / f"{filename}.html").write_text(rendered)

    samples = []
    for index in range(FRESH_VECTORS):
        fraction = (index + 1) / (FRESH_VECTORS + 1)
        left = index % 4
        right = (index + 1) % 4
        z = preactivations[left] * (1 - fraction) + preactivations[right] * fraction
        r = residuals[left] * (1 - fraction) + residuals[right] * fraction
        exact_hidden = np.asarray(gelu(z), dtype=np.float64)
        exact_output = (
            r
            + exact_hidden @ block1["mlp_proj_weight"].T
            + block1["mlp_proj_bias"]
        )
        sample = {
            "index": index,
            "fraction": fraction,
            "leftCase": left,
            "rightCase": right,
            "preactivations": z.tolist(),
            "normalizedPreactivations": (z / PREACTIVATION_SCALE).tolist(),
            "residuals": r.tolist(),
            "exactGelu": exact_hidden.tolist(),
            "expectedOutput": exact_output.tolist(),
            "expectedProjection": (
                exact_hidden @ block1["mlp_proj_weight"].T
            ).tolist(),
            "expectedWidth": (
                GROUPS * BASE_ADVANCE + exact_output * OUTPUT_SCALE
            ).tolist(),
        }
        samples.append(sample)

    manifest = {
        "sourceCapture": str(CAPTURE.relative_to(ROOT)),
        "sourceAvarPage": str(SOURCE_AVAR_PAGE.relative_to(ROOT)),
        "chromeCapture": capture["chrome"],
        "hidden": HIDDEN,
        "outputs": OUTPUTS,
        "groups": GROUPS,
        "groupWidths": GROUP_WIDTHS,
        "preactivationScale": PREACTIVATION_SCALE,
        "hiddenScale": HIDDEN_SCALE,
        "outputScale": OUTPUT_SCALE,
        "baseWidth": GROUPS * BASE_ADVANCE,
        "pureProjectionFontBytes": font_bytes,
        "preactivationRange": [
            float(np.min(preactivations)),
            float(np.max(preactivations)),
        ],
        "geluRange": [float(np.min(hidden)), float(np.max(hidden))],
        "knots": {str(count): values.tolist() for count, values in knots_by_count.items()},
        "samples": samples,
    }
    (OUT / "reference.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"built {len(variants)} pages; pure fonts {font_bytes / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
