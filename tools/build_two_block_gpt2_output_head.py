#!/usr/bin/env python3
"""Attach the accurate GPT-2 HVAR/Grid head to the fastest live two-block page."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_pretrained_gpt2 import layer_norm
from build_output_head_benchmark import css_number


ROOT = Path(__file__).resolve().parents[1]
BLOCK_DIR = ROOT / "experiments" / "gpt2-block-css"
HEAD_DIR = ROOT / "experiments" / "gpt2-hvar-grid-output-head"
SOURCE_STEM = (
    "view-timeline-two-block-full-exact-b0-global-projection-"
    "fc-easing-gelu-s513-projection-easing-s257-global-projection"
)
OUTPUT_STEM = "view-timeline-two-block-with-gpt2-output-head"
AUTO_OUTPUT_STEM = "view-timeline-two-block-with-gpt2-output-head-auto"
WIDTH = 768
EPSILON = 1e-5
LN_CHUNK = 64
SCORE_SCALE = 256
SCORE_STRIDE_PX = 4
WEIGHT_MAX = 511


def main() -> None:
    source_html_path = BLOCK_DIR / f"{SOURCE_STEM}.html"
    source_reference_path = BLOCK_DIR / f"{SOURCE_STEM}-reference.json"
    head_html_path = HEAD_DIR / "index.html"
    head_reference = json.loads((HEAD_DIR / "reference.json").read_text())
    source_reference = json.loads(source_reference_path.read_text())

    tensors = SafeTensors(MODEL_PATH)
    block_output = np.asarray(source_reference["expected"], dtype=np.float64)
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    final_hidden = layer_norm(block_output, gamma, beta)
    embeddings = np.asarray(tensors.tensor("wte.weight")[:50_257], dtype=np.float64)
    row_scales = np.max(np.abs(embeddings), axis=1) / WEIGHT_MAX
    row_scales[row_scales == 0] = 1
    codes = np.rint(embeddings / row_scales[:, None]).astype(np.int16)
    quantized_embeddings = codes.astype(np.float64) * row_scales[:, None]
    dense_logits = final_hidden @ embeddings.T
    quantized_logits = final_hidden @ quantized_embeddings.T
    dense_winner = int(np.argmax(dense_logits))
    quantized_winner = int(np.argmax(quantized_logits))
    floor = int(math.floor(float(np.min(quantized_logits)))) - 1
    winner_bucket = int(round(
        (quantized_logits[quantized_winner] - floor) * SCORE_SCALE
    ))

    final_names = [f"--b1-final-{index:03d}" for index in range(WIDTH)]
    chunk_starts = range(0, WIDTH, LN_CHUNK)
    mean_chunks = []
    variance_chunks = []
    for chunk, start in enumerate(chunk_starts):
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
    score_offset = -floor * SCORE_SCALE * SCORE_STRIDE_PX
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
    model_css = (
        registrations
        + f"#model{{{';'.join(mean_chunks)};"
        f"--head-mean:calc(({mean_terms})/{WIDTH});"
        f"{';'.join(variance_chunks)};"
        f"--head-var:calc(({variance_terms})/{WIDTH});"
        f"--score-offset:{score_offset}px;{hidden_values}}}\n"
    )
    integration_css = (
        model_css
        + ".head-gate{display:block}"
        + "#two-block-full:not(:has(#head-run:checked)) .head-gate{"
        + "content-visibility:hidden;contain-intrinsic-size:1px}"
        + "#head-run{position:fixed;left:-10000px;top:0}"
    )
    # The final projection's timeline tells us when the graph exists, but not
    # when every upstream value has stopped changing. A short time delay after
    # that generic signal is currently the only CSS-only scheduler that keeps
    # the 50k-node head out of the block graph's settling lifecycles.
    auto_css = (
        model_css
        + '@property --head-ready{syntax:"<integer>";inherits:false;initial-value:0}'
        + '@property --head-open{syntax:"<integer>";inherits:false;initial-value:0}'
        + "@keyframes head-ready{from{--head-ready:1}to{--head-ready:1}}"
        + "@keyframes head-open{to{--head-open:1}}"
        + ".head-gate{display:block;--head-ready:0;container:head-ready-stage/normal;"
        + "animation:head-ready 1s linear none;"
        + "animation-timeline:--b1pt767;animation-range:cover}"
        + ".head-body{display:block;--head-open:0;"
        + "content-visibility:if(style(--head-open:1):visible;else:hidden);"
        + "contain-intrinsic-size:1px}"
        + "@container head-ready-stage style(--head-ready:1){.head-body{"
        + "animation:head-open 1ms 1200ms steps(1,end) both}}"
    )

    head_html = head_html_path.read_text()
    head_start = head_html.index('<main id="model"')
    head_markup = head_html[head_start:]
    # `output` carries the live --b1-final-* values. Keep the connected head
    # inside it, but use phrasing tags so the HTML parser preserves that
    # inheritance relationship.
    for source_tag, target_tag in (
        ("<main", "<span"), ("</main>", "</span>"),
        ("<div", "<span"), ("</div>", "</span>"),
        ("<section", "<span"), ("</section>", "</span>"),
        ("<output", "<i"), ("</output>", "</i>"),
    ):
        head_markup = head_markup.replace(source_tag, target_tag)
    manual_head_markup = (
        '<input id="head-run" type="checkbox" checked>'
        '<span class="head-gate">' + head_markup + "</span>"
    )
    auto_head_markup = (
        '<span class="head-gate"><span class="head-body">'
        + head_markup + "</span></span>"
    )
    source_html = source_html_path.read_text()
    output_start = source_html.index('<output id="two-block-full"')
    output_close = source_html.index("</output>", output_start)

    def write_variant(stem: str, css: str, markup: str) -> tuple[Path, Path]:
        links = (
            '<link rel="stylesheet" '
            'href="../gpt2-hvar-grid-output-head/index.css">'
            f'<link rel="stylesheet" href="{stem}.css">'
        )
        linked_html = source_html.replace("</title>", f"</title>{links}", 1)
        # The insertion position is unchanged because the links are before the
        # output element, so locate it again in the linked document.
        linked_output_start = linked_html.index('<output id="two-block-full"')
        insertion = linked_html.index("</output>", linked_output_start)
        combined = linked_html[:insertion] + markup + linked_html[insertion:]
        css_path = BLOCK_DIR / f"{stem}.css"
        html_path = BLOCK_DIR / f"{stem}.html"
        css_path.write_text(css)
        html_path.write_text(combined)
        return css_path, html_path

    css_path, html_path = write_variant(
        OUTPUT_STEM, integration_css, manual_head_markup
    )
    auto_css_path, auto_html_path = write_variant(
        AUTO_OUTPUT_STEM, auto_css, auto_head_markup
    )
    reference_path = BLOCK_DIR / f"{OUTPUT_STEM}-reference.json"
    auto_reference_path = BLOCK_DIR / f"{AUTO_OUTPUT_STEM}-reference.json"
    reference = {
        "model": "openai-community/gpt2",
        "source": SOURCE_STEM,
        "width": WIDTH,
        "denseWinner": dense_winner,
        "quantizedWinner": quantized_winner,
        "scoreFloor": floor,
        "winnerBucket": winner_bucket,
        "finalHidden": final_hidden.tolist(),
        "headBackend": head_reference["backend"],
        "blockHtmlBytes": source_html_path.stat().st_size,
        "combinedHtmlBytes": html_path.stat().st_size,
        "integrationCssBytes": css_path.stat().st_size,
        "autoHtmlBytes": auto_html_path.stat().st_size,
        "autoIntegrationCssBytes": auto_css_path.stat().st_size,
        "headRuntimeBytes": (
            head_reference["htmlBytes"]
            + head_reference["cssBytes"]
            + head_reference["fontBytes"]
        ),
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    auto_reference = dict(reference)
    auto_reference["gateMode"] = "view-timeline-readiness"
    auto_reference_path.write_text(json.dumps(auto_reference, indent=2) + "\n")
    print(json.dumps({key: value for key, value in reference.items()
                      if key != "finalHidden"}, indent=2))


if __name__ == "__main__":
    main()
