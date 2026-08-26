#!/usr/bin/env python3
"""Compose groupwise Cauchy bounds into the retained six-stage block-flow head."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_groupwise_cauchy_head import upper_block_norms
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / os.environ.get(
    "GROUPWISE_CASCADE_SOURCE", "gpt2-mixed-hot2-blockflow-group-max-shard256"
)
BOUND = ROOT / "experiments" / "gpt2-groupwise-cauchy-head"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
OUTPUT = ROOT / "experiments" / os.environ.get(
    "GROUPWISE_CASCADE_OUTPUT", "gpt2-groupwise-cauchy-blockflow-cascade"
)
GROUPS = 197
HOT_GROUPS = (0, 1)
BLOCK_COUNT = 96
BLOCK_WIDTH = 8
AXIS_STEPS = 16_384
SCORE_STRIDE_PX = 4
BOUND_CODEPOINT_START = 0xA8000
BOUND_QUANTIZATION = 128
BOUND_FONT = "group-bound-q16-q10-96"


def css_number(value: float) -> str:
    text = f"{float(value):.12g}"
    if text.startswith("0."):
        return text[1:]
    if text.startswith("-0."):
        return "-" + text[2:]
    return text


def add_bound_glyphs(document: str) -> str:
    seen = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal seen
        group = seen
        seen += 1
        section = match.group(0)
        if group in HOT_GROUPS:
            return section
        glyph = (
            f'<i class="group-bound" data-group="{group}">'
            f'&#x{BOUND_CODEPOINT_START + group:X};</i>'
        )
        return section[:-len("</section>")] + glyph + "</section>"

    result = re.sub(
        r'<section class="group-wrapper"[^>]*>.*?</section>',
        replace,
        document,
        flags=re.DOTALL,
    )
    if seen != GROUPS:
        raise RuntimeError(f"expected {GROUPS} groups, found {seen}")
    return result


def bound_css(block_axis_range: float, axis_pad: float) -> str:
    registrations = "".join(
        f'@property --bn{block}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for block in range(BLOCK_COUNT)
    )
    norms = []
    settings = []
    for block in range(BLOCK_COUNT):
        terms = " + ".join(
            f"var(--h{dimension})*var(--h{dimension})"
            for dimension in range(block * BLOCK_WIDTH, (block + 1) * BLOCK_WIDTH)
        )
        norms.append(f"--bn{block}:sqrt(calc({terms}))")
        settings.append(
            f'"b{block:03d}" calc(min(1,var(--bn{block})/'
            f"{css_number(block_axis_range)} + {css_number(axis_pad)}))"
        )
    settings_text = ",".join(settings).replace('))"', "))")
    return "".join((
        registrations,
        '@font-face{font-family:GroupBound96;src:url("' + BOUND_FONT
        + '.woff2") format("woff2");size-adjust:800%}',
        ".cascade{" + ";".join(norms) + "}",
        ".group-wrapper:has(>.group-bound){display:grid!important;"
        "grid-template-columns:max-content max-content!important;"
        "grid-template-rows:1px!important}",
        ".group-wrapper:has(>.group-bound)>.group-grid{grid-column:1;grid-row:1}",
        ".group-bound{display:block;grid-column:2;grid-row:1;height:0;overflow:hidden;"
        "white-space:pre;font-family:GroupBound96;font-style:normal;font-size:1000px;"
        "line-height:1;font-variation-settings:",
        settings_text,
        ";width:calc-size(max-content,round(down,size + 4px,4px))}",
    ))


def predicted_bounds(
    hidden: np.ndarray,
    coefficients: np.ndarray,
    group_norms: np.ndarray,
    block_axis_range: float,
    axis_pad: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    block_norms = np.linalg.norm(
        hidden.reshape(len(hidden), BLOCK_COUNT, BLOCK_WIDTH), axis=2
    )
    coordinates = np.minimum(1.0, block_norms / block_axis_range + axis_pad)
    coordinates = np.where(block_norms == 0.0, 0.0, coordinates)
    coordinates = np.rint(coordinates * AXIS_STEPS) / AXIS_STEPS
    carrier_pixels = coordinates @ coefficients.T * 8.0
    widths = (
        np.floor((carrier_pixels + SCORE_STRIDE_PX) / SCORE_STRIDE_PX)
        * SCORE_STRIDE_PX
    )
    certified = block_norms @ group_norms.T * (256 * SCORE_STRIDE_PX)
    widths[:, list(HOT_GROUPS)] = 0.0
    certified[:, list(HOT_GROUPS)] = 0.0
    return block_norms, widths, certified


def build_target_bound(
    block_axis_range: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:head.VOCABULARY],
        dtype=np.float64,
    )
    fine_reference = json.loads((FINE / "reference.json").read_text())
    fine_scale = float(fine_reference["weightScale"])
    target = np.rint(weights / fine_scale).astype(np.int16).astype(np.float64) * fine_scale
    row_scales = np.max(np.abs(weights), axis=1) / 511.0
    row_scales[row_scales == 0] = 1.0
    coarse = (
        np.rint(weights / row_scales[:, None]).clip(-511, 511)
        * row_scales[:, None]
    )
    residual = target - coarse
    row_norms = upper_block_norms(residual, BLOCK_WIDTH)
    padding = GROUPS * head.GROUP_SIZE - head.VOCABULARY
    padded = np.pad(row_norms, ((0, padding), (0, 0)), constant_values=0.0)
    group_norms = np.nextafter(
        np.max(padded.reshape(GROUPS, head.GROUP_SIZE, BLOCK_COUNT), axis=1),
        np.inf,
    )
    coefficients = np.ceil(
        group_norms * block_axis_range * BOUND_QUANTIZATION
    ).astype(np.int16)
    coefficients[list(HOT_GROUPS)] = 0
    if np.any(coefficients < 0) or int(coefficients.max()) > 32_767:
        raise RuntimeError("target-bound coefficients do not fit int16")
    bases = np.sum(coefficients.astype(np.int64), axis=1)
    if int(bases.max()) > 65_535:
        raise RuntimeError("target-bound base advance does not fit uint16")
    font_path = OUTPUT / f"{BOUND_FONT}.ttf"
    build_direct_font_backend(
        coefficients,
        font_path,
        signed_axes=False,
        base_advance=bases,
        codepoint_start=BOUND_CODEPOINT_START,
        axis_tags=[f"b{block:03d}" for block in range(BLOCK_COUNT)],
        allow_out_of_range_result=True,
    )
    font = TTFont(font_path, recalcTimestamp=False)
    for glyph, (_advance, lsb) in font["hmtx"].metrics.items():
        font["hmtx"].metrics[glyph] = (0, lsb)
    font["hhea"].advanceWidthMax = 0
    font.recalcTimestamp = False
    font.save(font_path)
    compressed = TTFont(font_path, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(font_path.with_suffix(".woff2"))
    np.save(OUTPUT / "group-q16-minus-q10-norms-96.npy", group_norms)
    return group_norms, coefficients, int(np.sum(np.any(residual != 0, axis=1)))


def main() -> None:
    required = (
        SOURCE / "index.html",
        SOURCE / "topology.css",
        SOURCE / "reference.json",
        BOUND / "reference.json",
        FINE / "reference.json",
    )
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    source_reference = json.loads((SOURCE / "reference.json").read_text())
    bound_reference = json.loads((BOUND / "reference.json").read_text())
    source_fixtures = source_reference["certifiedFixtures"]
    hidden = np.asarray(source_fixtures["hiddenVectors"], dtype=np.float64)
    bound_hidden = np.asarray(
        bound_reference["fixtures"]["hiddenVectors"], dtype=np.float64
    )
    if not np.array_equal(hidden, bound_hidden):
        raise RuntimeError("retained and groupwise fixture vectors differ")
    if int(source_reference["groups"]) != GROUPS:
        raise RuntimeError("retained group count changed")
    if not 2 <= int(source_reference["stages"]) <= 197:
        raise RuntimeError("invalid exact-stage count")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    group_norms, coefficients, residual_rows = build_target_bound(
        float(bound_reference["blockAxisRange"])
    )
    block_norms, widths, certified = predicted_bounds(
        hidden,
        coefficients,
        group_norms,
        float(bound_reference["blockAxisRange"]),
        float(bound_reference["boundAxisPad"]),
    )
    if np.any(widths[:, 2:] + 1e-9 < certified[:, 2:]):
        raise RuntimeError("predicted browser bound rounded inward")

    source_html = (SOURCE / "index.html").read_text()
    control_html = source_html.replace(
        "Mixed hot-two 3-shard block-flow group maximum",
        "Rowwise-int10 no-bound block-flow control",
        1,
    )
    html = add_bound_glyphs(source_html).replace(
        "Mixed hot-two 3-shard block-flow group maximum",
        "Groupwise-Cauchy six-stage block-flow cascade",
        1,
    )
    topology = (SOURCE / "topology.css").read_text() + "\n" + bound_css(
        float(bound_reference["blockAxisRange"]),
        float(bound_reference["boundAxisPad"]),
    ) + (
        ".candidate:not(.mixed-hot-candidate){width:calc-size(max-content,"
        "calc(round(down,(size - var(--base)*1px)*var(--factor) + "
        "var(--score-offset) + 4px,4px) + var(--local-tie)/64*1px))}\n"
    )

    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "control.html").write_text(control_html)
    (OUTPUT / "topology.css").write_text(topology)
    reference = {
        **source_reference,
        "backend": "groupwise-cauchy-mixed-hot2-shard256-blockflow-cascade",
        "sourceRetained": SOURCE.name,
        "groupwiseBoundSource": BOUND.name,
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "runtimeContainsJavaScript": False,
        "groupwiseBoundGroups": GROUPS - len(HOT_GROUPS),
        "groupwiseHotGroupsSkipped": list(HOT_GROUPS),
        "groupwiseBlockCount": BLOCK_COUNT,
        "groupwiseBlockWidth": BLOCK_WIDTH,
        "groupwiseResidual": "global-int16 target minus row-wise int10 coarse",
        "groupwiseResidualRows": residual_rows,
        "groupwiseBoundFont": f"{BOUND_FONT}.woff2",
        "groupwiseBoundFontBytes": (OUTPUT / f"{BOUND_FONT}.woff2").stat().st_size,
        "groupwiseCoefficientMaximum": int(coefficients.max()),
        "browserOracleContract": (
            "live retained group width plus independently predicted outward "
            "groupwise bound; hot groups retain their existing exact upper"
        ),
        "groupwiseFixtures": {
            "blockNorms": block_norms.tolist(),
            "predictedBoundWidths": widths.tolist(),
            "certifiedRadiusPixels": certified.tolist(),
        },
        "generatedBytes": {
            **source_reference.get("generatedBytes", {}),
            "index.html": len(html.encode()),
            "control.html": len(control_html.encode()),
            "topology.css": len(topology.encode()),
        },
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "groups": GROUPS,
        "boundedGroups": GROUPS - len(HOT_GROUPS),
        "stages": source_reference["stages"],
        "fixtures": len(hidden),
        "htmlBytes": len(html.encode()),
        "cssBytes": len(topology.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
