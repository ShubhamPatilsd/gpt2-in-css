#!/usr/bin/env python3
"""Connect the accurate selective GPT-2 output head to the live two-block graph."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_pretrained_gpt2 import layer_norm
from build_output_head_benchmark import css_number


ROOT = Path(__file__).resolve().parents[1]
BLOCK_DIR = ROOT / "experiments" / "gpt2-block-css"
HEAD_NAME = "gpt2-hvar-grid-output-head-cascade-near-dither7"
HEAD_DIR = ROOT / "experiments" / HEAD_NAME
STAGED_HEAD_NAME = HEAD_NAME + "-staged"
INTERNAL_STAGING = os.environ.get("TWO_BLOCK_SELECTIVE_INTERNAL_STAGING", "0") == "1"
SOURCE_STEM = (
    "view-timeline-two-block-full-exact-b0-global-projection-"
    "fc-easing-gelu-s513-projection-easing-s257-global-projection"
)
OUTPUT_STEM = (
    "view-timeline-two-block-with-selective-gpt2-output-head-internally-staged"
    if INTERNAL_STAGING
    else "view-timeline-two-block-with-selective-gpt2-output-head"
)
WIDTH = 768
EPSILON = 1e-5
LN_CHUNK = 64
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4


def phrasing_markup(markup: str) -> str:
    """Keep the connected graph inside <output> so live CSS state inherits."""
    for source_tag, target_tag in (
        ("<main", "<span"), ("</main>", "</span>"),
        ("<div", "<span"), ("</div>", "</span>"),
        ("<section", "<span"), ("</section>", "</span>"),
        ("<output", "<i"), ("</output>", "</i>"),
    ):
        markup = markup.replace(source_tag, target_tag)
    return markup


def main() -> None:
    source_html_path = BLOCK_DIR / f"{SOURCE_STEM}.html"
    source_reference_path = BLOCK_DIR / f"{SOURCE_STEM}-reference.json"
    head_reference_path = HEAD_DIR / "reference.json"
    head_reference = json.loads(head_reference_path.read_text())
    source_reference = json.loads(source_reference_path.read_text())

    tensors = SafeTensors(MODEL_PATH)
    block_output = np.asarray(source_reference["expected"], dtype=np.float64)
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    final_hidden = layer_norm(block_output, gamma, beta)
    embeddings = np.asarray(tensors.tensor("wte.weight")[:50_257], dtype=np.float64)
    dense_logits = final_hidden @ embeddings.T
    dense_winner = int(np.argmax(dense_logits))
    score_floor = int(math.floor(float(np.min(dense_logits)))) - 1

    final_names = [f"--b1-final-{index:03d}" for index in range(WIDTH)]
    mean_chunks: list[str] = []
    variance_chunks: list[str] = []
    for chunk, start in enumerate(range(0, WIDTH, LN_CHUNK)):
        names = final_names[start:start + LN_CHUNK]
        mean_chunks.append(
            f"--head-sum-{chunk}:calc("
            + " + ".join(f"var({name})" for name in names)
            + ")"
        )
        variance_chunks.append(
            f"--head-vsum-{chunk}:calc("
            + " + ".join(
                f"pow(var({name}) - var(--head-mean),2)" for name in names
            )
            + ")"
        )
    mean_terms = " + ".join(
        f"var(--head-sum-{chunk})" for chunk in range(len(mean_chunks))
    )
    variance_terms = " + ".join(
        f"var(--head-vsum-{chunk})" for chunk in range(len(variance_chunks))
    )
    hidden_values = ";".join(
        f"--h{index}:calc((var({name}) - var(--head-mean)) / "
        f"sqrt(var(--head-var) + {EPSILON}) * {css_number(gamma[index])} + "
        f"{css_number(beta[index])})"
        for index, name in enumerate(final_names)
    )
    typed_names = (
        [f"--head-sum-{chunk}" for chunk in range(len(mean_chunks))]
        + ["--head-mean"]
        + [f"--head-vsum-{chunk}" for chunk in range(len(variance_chunks))]
        + ["--head-var"]
        + [f"--h{index}" for index in range(WIDTH)]
    )
    registrations = "".join(
        f'@property {name}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for name in typed_names
    )
    score_offset = -score_floor * SCORE_SCALE * SCORE_STRIDE_PX
    integration_css = (
        registrations
        + f"#two-block-full{{{';'.join(mean_chunks)};"
        f"--head-mean:calc(({mean_terms})/{WIDTH});"
        f"{';'.join(variance_chunks)};"
        f"--head-var:calc(({variance_terms})/{WIDTH});"
        f"--score-offset:{score_offset}px;{hidden_values}}}"
        + "#selective-head-run{position:fixed;left:-10000px;top:0}"
        + ".selective-head-gate{display:block}"
        + "#two-block-full:not(:has(#selective-head-run:checked)) "
        + ".selective-head-gate{content-visibility:hidden;contain-intrinsic-size:1px}"
    )

    head_html = (HEAD_DIR / "index.html").read_text()
    head_start = head_html.index('<main id="model"')
    head_end = head_html.rfind("</div>")
    head_markup = phrasing_markup(head_html[head_start:head_end])
    internal_controls = (
        '<input id="fine-stage-run" type="checkbox">'
        '<input id="near-stage-run" type="checkbox">'
        '<input id="dither-stage-run" type="checkbox">'
        if INTERNAL_STAGING else ""
    )
    connected_markup = (
        '<input id="selective-head-run" type="checkbox">'
        '<span class="selective-head-gate">' + internal_controls
        + '<span class="cascade">'
        + head_markup
        + "</span></span>"
    )

    source_html = source_html_path.read_text()
    links = (
        '<link rel="stylesheet" href="../gpt2-hvar-grid-output-head-'
        'global11-inline-tie/index.css">'
        f'<link rel="stylesheet" href="../{HEAD_NAME}/index.css">'
        + (
            f'<link rel="stylesheet" href="../{STAGED_HEAD_NAME}/index.css">'
            if INTERNAL_STAGING else ""
        )
        + f'<link rel="stylesheet" href="{OUTPUT_STEM}.css">'
    )
    combined = source_html.replace("</title>", f"</title>{links}", 1)
    output_start = combined.index('<output id="two-block-full"')
    insertion = combined.index("</output>", output_start)
    combined = combined[:insertion] + connected_markup + combined[insertion:]

    css_path = BLOCK_DIR / f"{OUTPUT_STEM}.css"
    html_path = BLOCK_DIR / f"{OUTPUT_STEM}.html"
    reference_path = BLOCK_DIR / f"{OUTPUT_STEM}-reference.json"
    css_path.write_text(integration_css)
    html_path.write_text(combined)
    reference = {
        "model": "openai-community/gpt2",
        "source": SOURCE_STEM,
        "head": HEAD_NAME,
        "width": WIDTH,
        "denseWinner": dense_winner,
        "scoreFloor": score_floor,
        "finalHidden": final_hidden.tolist(),
        "headBackend": head_reference["backend"],
        "nearDitherPhases": head_reference["nearDitherPhases"],
        "internalStaging": INTERNAL_STAGING,
        "blockHtmlBytes": source_html_path.stat().st_size,
        "combinedHtmlBytes": html_path.stat().st_size,
        "integrationCssBytes": css_path.stat().st_size,
        "headRuntimeBytes": head_reference["totalRuntimeBytes"],
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items() if key != "finalHidden"
    }, indent=2))


if __name__ == "__main__":
    main()
