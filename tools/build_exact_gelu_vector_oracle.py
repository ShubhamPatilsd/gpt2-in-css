#!/usr/bin/env python3
"""Build exact-GELU vector-boundary oracle pages for stage attribution."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "experiments" / "avar2-gelu-linear-hvar-full-mlp-g13"
OUTPUT_DIR = ROOT / "experiments" / "exact-gelu-vector-oracle"
SOURCE_PAGE = SOURCE_DIR / "connected-two-block-exact-css-gelu-layoutless.html"
CAPTURE_PATH = OUTPUT_DIR / "captured-boundaries.json"
REFERENCE_PATH = SOURCE_DIR / "reference.json"

sys.path.insert(0, str(ROOT / "tools"))
from build_hvar_vector_oracle import (  # noqa: E402
    balanced_css_stage,
    case_rules,
    extract_stage,
    page_shell,
)


def main() -> None:
    source = SOURCE_PAGE.read_text()
    capture = json.loads(CAPTURE_PATH.read_text())
    reference = json.loads(REFERENCE_PATH.read_text())
    cases = capture["cases"]
    if len(cases) != 4:
        raise ValueError(f"expected four captured cases, got {len(cases)}")

    states = [case["states"] for case in cases]
    preactivations = [case["normalizedPreactivations"] for case in cases]
    gelu_values = [case["geluValues"] for case in cases]
    residuals = [case["residuals"] for case in cases]
    expected_widths = [case["outputWidths"] for case in cases]
    if any(len(vector) != 768 for vector in states + residuals + expected_widths):
        raise ValueError("captured 768-vector has unexpected length")
    if any(len(vector) != 3072 for vector in preactivations + gelu_values):
        raise ValueError("captured 3072-vector has unexpected length")

    style_start = source.index("<style>") + len("<style>")
    style_end = source.index("</style>", style_start)
    global_css = source[style_start:style_end]
    body_start = style_end + len("</style>")
    first_stage = source.index('<css-stage class="attention-host"', body_start)
    controls = source[body_start:first_stage]

    b1_stage = extract_stage(source, '<css-stage class="b1-attention"')
    serial_chain = extract_stage(source, '<css-stage class="serial-group-0"')
    serial_projection = extract_stage(source, '<css-stage class="serial-projection"')

    state_css = case_rules(".oracle-state", "state-", states)
    preactivation_css = case_rules(
        ".oracle-fc", "serial-z-", preactivations, index_digits=4
    )
    residual_css = case_rules(".oracle-residual", "b1-r1-", residuals)
    gelu_css = case_rules(".oracle-gelu", "b1-g-", gelu_values, index_digits=4)
    oracle_base_css = (
        ".oracle-state,.oracle-fc,.oracle-residual,.oracle-gelu"
        "{display:contents!important}"
    )

    handoff_b1 = b1_stage.replace(
        'class="b1-attention" slot="next"',
        'class="b1-attention oracle-state"',
        1,
    )
    handoff_page = page_shell(
        "Exact GELU oracle: block-0 state handoff",
        global_css + oracle_base_css + state_css,
        controls,
        handoff_b1,
    )

    oracle_projection = '<div class="oracle-fc">' + serial_projection + "</div>"
    fc_free_page = source.replace(
        "<title>Layoutless serial projection two-block GPT-2</title>",
        "<title>Exact GELU oracle: block-1 FC preactivation</title>",
        1,
    ).replace(
        "<style>",
        '<base href="../avar2-gelu-linear-hvar-full-mlp-g13/"><style>'
        + oracle_base_css
        + preactivation_css,
        1,
    ).replace(serial_chain, oracle_projection, 1)

    handoff_and_fc = handoff_b1.replace(serial_chain, oracle_projection, 1)
    handoff_fc_page = page_shell(
        "Exact GELU oracle: state and FC handoffs",
        global_css + oracle_base_css + state_css + preactivation_css,
        controls,
        handoff_and_fc,
    )

    projection_only = (
        '<div class="oracle-fc oracle-residual">' + serial_projection + "</div>"
    )
    projection_page = page_shell(
        "Exact GELU oracle: GELU and projection",
        global_css + oracle_base_css + preactivation_css + residual_css,
        controls,
        projection_only,
    )

    # Remove the exact-GELU declarations from the projection stylesheet so the
    # already-computed values can inherit through the shadow host. The linear
    # font matrix and residual addition remain unchanged.
    projection_css_name = "stage-exact-css-gelu-serial-b1-projection.css"
    projection_css = (SOURCE_DIR / projection_css_name).read_text()
    stripped_css, substitutions = re.subn(
        r"--b1-g-\d{4}:--exact-gelu-b1\(calc\(var\(--serial-z-\d{4}\) \* 19\)\);",
        "",
        projection_css,
    )
    if substitutions != 3072:
        raise ValueError(f"removed {substitutions} GELU declarations, expected 3072")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stripped_name = "stage-oracle-pure-b1-projection.css"
    (OUTPUT_DIR / stripped_name).write_text(stripped_css)
    pure_projection_stage = serial_projection.replace(
        f'href="{projection_css_name}?v=3c994a842884"',
        f'href="../exact-gelu-vector-oracle/{stripped_name}"',
        1,
    )
    if pure_projection_stage == serial_projection:
        pure_projection_stage = re.sub(
            rf'href="{re.escape(projection_css_name)}\?v=[0-9a-f]+"',
            f'href="../exact-gelu-vector-oracle/{stripped_name}"',
            serial_projection,
            count=1,
        )
    pure_projection = (
        '<div class="oracle-gelu oracle-residual">'
        + pure_projection_stage
        + "</div>"
    )
    pure_projection_page = page_shell(
        "Exact GELU oracle: pure projection",
        global_css + oracle_base_css + gelu_css + residual_css,
        controls,
        pure_projection,
    )

    pages = {
        "oracle-block0-handoff.html": handoff_page,
        "oracle-b1-fc-preactivation.html": fc_free_page,
        "oracle-block0-and-b1-fc.html": handoff_fc_page,
        "oracle-b1-gelu-and-projection.html": projection_page,
        "oracle-b1-pure-projection.html": pure_projection_page,
    }
    for name, page in pages.items():
        (OUTPUT_DIR / name).write_text(page)

    oracle_reference = {
        "sourcePage": str(SOURCE_PAGE.relative_to(ROOT)),
        "captureChrome": capture["chrome"],
        "runtimeContainsJavaScript": False,
        "tokenIds": reference["tokenIds"],
        "block1SerialProjectionBase": reference["block1SerialProjectionBase"],
        "block1OutputScale": reference["block1OutputScale"],
        "expectedOutputWidths": expected_widths,
        "pages": {name: len(page.encode()) for name, page in pages.items()},
        "removedGeluDeclarations": substitutions,
    }
    (OUTPUT_DIR / "reference.json").write_text(
        json.dumps(oracle_reference, indent=2) + "\n"
    )
    print(json.dumps({
        "output": str(OUTPUT_DIR),
        "pages": oracle_reference["pages"],
        "removedGeluDeclarations": substitutions,
    }, indent=2))


if __name__ == "__main__":
    main()
