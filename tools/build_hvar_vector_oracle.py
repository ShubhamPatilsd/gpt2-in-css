#!/usr/bin/env python3
"""Build vector-primitive upper-bound pages from the two-block HVAR fixture.

The oracle vectors are computed offline for the same four radio cases. Runtime
pages contain HTML/CSS/fonts only. They deliberately remove one or more costly
geometry handoffs while leaving every downstream font matrix stage unchanged.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "experiments" / "avar2-gelu-linear-hvar-full-mlp-g13"
OUTPUT_DIR = ROOT / "experiments" / "hvar-vector-oracle"
SOURCE_PAGE = SOURCE_DIR / "connected-two-block-serial-projection-layoutless.html"
REFERENCE_PATH = SOURCE_DIR / "reference.json"
CAPTURE_PATH = OUTPUT_DIR / "captured-boundaries.json"


def css_number(value: float) -> str:
    rendered = format(float(value), ".12g")
    return "0" if rendered in ("-0", "+0") else rendered


def balanced_css_stage(source: str, start: int) -> tuple[str, int]:
    """Return the custom-element substring beginning at start and its end."""
    cursor = start
    depth = 0
    close_tag = "</css-stage>"
    while cursor < len(source):
        opening = source.find("<css-stage", cursor)
        closing = source.find(close_tag, cursor)
        if closing < 0:
            raise ValueError("unbalanced css-stage tree")
        if opening >= 0 and opening < closing:
            depth += 1
            cursor = source.index(">", opening) + 1
        else:
            depth -= 1
            cursor = closing + len(close_tag)
            if depth == 0:
                return source[start:cursor], cursor
    raise ValueError("unbalanced css-stage tree")


def extract_stage(source: str, opening: str) -> str:
    start = source.index(opening)
    stage, _ = balanced_css_stage(source, start)
    return stage


def case_rules(
    selector: str,
    prefix: str,
    values: np.ndarray,
    index_digits: int = 3,
) -> str:
    rules = []
    for case_index, vector in enumerate(values):
        declarations = ";".join(
            f"--{prefix}{index:0{index_digits}d}:{css_number(value)}"
            for index, value in enumerate(vector)
        )
        rules.append(
            f"body:has(#case-{case_index}:checked) {selector}"
            f"{{{declarations}}}"
        )
    return "".join(rules)


def page_shell(title: str, global_css: str, controls: str, body: str) -> str:
    return (
        "<!doctype html><meta charset=\"utf-8\">"
        "<base href=\"../avar2-gelu-linear-hvar-full-mlp-g13/\">"
        f"<title>{title}</title><style>{global_css}</style>{controls}{body}"
    )


def main() -> None:
    # The imported builder is the source of truth for the quantization and
    # represented model path used by the existing browser fixture.
    os.environ["HVAR_FULL_MLP_BACKEND"] = "avar2-gelu"
    os.environ["HVAR_FULL_MLP_GROUPS"] = "13"
    sys.path.insert(0, str(ROOT / "tools"))
    from build_hvar_parallel_full_mlp import (  # noqa: PLC0415
        layer_norm,
        model_data,
        quantize_float_rows,
    )

    source = SOURCE_PAGE.read_text()
    reference = json.loads(REFERENCE_PATH.read_text())
    style_start = source.index("<style>") + len("<style>")
    style_end = source.index("</style>", style_start)
    global_css = source[style_start:style_end]
    body_start = style_end + len("</style>")
    first_stage = source.index('<css-stage class="attention-host"', body_start)
    controls = source[body_start:first_stage]

    b1_stage = extract_stage(source, '<css-stage class="b1-attention"')
    serial_chain = extract_stage(source, '<css-stage class="serial-group-0"')
    serial_projection = extract_stage(source, '<css-stage class="serial-projection"')

    states = np.asarray(reference["attentionBlockRepresentedOutputs"], dtype=np.float64)
    block1 = model_data(1)
    next_ln = np.stack(
        [layer_norm(vector, block1["ln1_gamma"], block1["ln1_beta"]) for vector in states]
    )
    composed_weight = block1["attn_proj_weight"] @ block1["v_weight"]
    composed_bias = (
        block1["attn_proj_weight"] @ block1["v_bias"]
        + block1["attn_proj_bias"]
    )
    q_composed = quantize_float_rows(composed_weight, bits=3)
    b1_residuals = states + next_ln @ q_composed.reconstructed.T + composed_bias
    b1_ln2 = np.stack(
        [layer_norm(vector, block1["ln2_gamma"], block1["ln2_beta"]) for vector in b1_residuals]
    )
    q_fc = quantize_float_rows(block1["fc_weight"], bits=3)
    preactivations = b1_ln2 @ q_fc.reconstructed.T + block1["fc_bias"]
    normalized_preactivations = preactivations / float(
        reference["block1PreactivationScale"]
    )
    expected_widths = (
        np.asarray(reference["block1RepresentedOutputs"], dtype=np.float64)
        * float(reference["block1OutputScale"])
        + float(reference["block1SerialProjectionBase"])
    )
    oracle_source = "model-reference-fallback"
    capture_chrome = None
    if CAPTURE_PATH.exists():
        capture = json.loads(CAPTURE_PATH.read_text())
        cases = capture["cases"]
        states = np.asarray([case["states"] for case in cases], dtype=np.float64)
        b1_residuals = np.asarray(
            [case["residuals"] for case in cases], dtype=np.float64
        )
        normalized_preactivations = np.asarray(
            [case["normalizedPreactivations"] for case in cases], dtype=np.float64
        )
        expected_widths = np.asarray(
            [case["outputWidths"] for case in cases], dtype=np.float64
        )
        if states.shape != (4, 768):
            raise ValueError(f"unexpected captured state shape: {states.shape}")
        if normalized_preactivations.shape != (4, 3072):
            raise ValueError(
                "unexpected captured preactivation shape: "
                f"{normalized_preactivations.shape}"
            )
        oracle_source = "captured-browser-boundaries"
        capture_chrome = capture["chrome"]

    state_css = case_rules(".oracle-state", "state-", states)
    preactivation_css = case_rules(
        ".oracle-fc", "serial-z-", normalized_preactivations, index_digits=4
    )
    residual_css = case_rules(".oracle-residual", "b1-r1-", b1_residuals)
    oracle_base_css = (
        ".oracle-state,.oracle-fc,.oracle-residual{display:contents!important}"
    )

    # Free only the block-0 -> block-1 state handoff. Block 1 attention, LN2,
    # FC, preactivation transport, GELU and projection remain real.
    handoff_b1 = b1_stage.replace(
        'class="b1-attention" slot="next"',
        'class="b1-attention oracle-state"',
        1,
    )
    handoff_page = page_shell(
        "Oracle block-0 state handoff",
        global_css + oracle_base_css + state_css,
        controls,
        handoff_b1,
    )

    # Free only the block-1 FC/preactivation boundary. Block 0 and block-1
    # attention remain live, while the original serial FC chain is replaced by
    # exact case-selected axes consumed by the unchanged real projection font.
    oracle_projection = (
        '<div class="oracle-fc">' + serial_projection + "</div>"
    )
    fc_free_page = source.replace(
        "<title>Layoutless serial projection two-block GPT-2</title>",
        "<title>Oracle block-1 FC preactivation</title>",
        1,
    ).replace(
        "<style>",
        '<base href="../avar2-gelu-linear-hvar-full-mlp-g13/"><style>'
        + oracle_base_css
        + preactivation_css,
        1,
    ).replace(serial_chain, oracle_projection, 1)

    # Free both the block-0 handoff and block-1 FC/preactivation boundary.
    # Block-1 attention/LN2 and the final 3072 -> 768 font projection remain.
    handoff_and_fc = handoff_b1.replace(serial_chain, oracle_projection, 1)
    handoff_fc_page = page_shell(
        "Oracle state handoff and block-1 FC preactivation",
        global_css + oracle_base_css + state_css + preactivation_css,
        controls,
        handoff_and_fc,
    )

    # Strongest upper bound: supply both the FC preactivations and attention
    # residual vector directly. Only GELU inside the unchanged projection HVAR
    # and the real 3072 -> 768 projection matrix remain live.
    projection_only = (
        '<div class="oracle-fc oracle-residual">' + serial_projection + "</div>"
    )
    projection_page = page_shell(
        "Oracle block-1 projection only",
        global_css + oracle_base_css + preactivation_css + residual_css,
        controls,
        projection_only,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = {
        "oracle-block0-handoff.html": handoff_page,
        "oracle-b1-fc-preactivation.html": fc_free_page,
        "oracle-block0-and-b1-fc.html": handoff_fc_page,
        "oracle-b1-projection-only.html": projection_page,
    }
    for name, page in pages.items():
        (OUTPUT_DIR / name).write_text(page)

    oracle_reference = {
        "sourcePage": str(SOURCE_PAGE.relative_to(ROOT)),
        "tokenIds": reference["tokenIds"],
        "block1SerialProjectionBase": reference["block1SerialProjectionBase"],
        "block1OutputScale": reference["block1OutputScale"],
        "expectedOutputs": reference["block1RepresentedOutputs"],
        "expectedOutputWidths": expected_widths.tolist(),
        "oracleSource": oracle_source,
        "captureChrome": capture_chrome,
        "stateVectors": states.tolist(),
        "block1ResidualVectors": b1_residuals.tolist(),
        "block1NormalizedPreactivations": normalized_preactivations.tolist(),
        "pages": {name: len(page.encode()) for name, page in pages.items()},
    }
    (OUTPUT_DIR / "reference.json").write_text(
        json.dumps(oracle_reference, indent=2) + "\n"
    )
    print(json.dumps({
        "output": str(OUTPUT_DIR),
        "pages": oracle_reference["pages"],
        "stateShape": list(states.shape),
        "preactivationShape": list(normalized_preactivations.shape),
        "oracleSource": oracle_source,
        "normalizedPreactivationMaximum": float(
            np.max(np.abs(normalized_preactivations))
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
