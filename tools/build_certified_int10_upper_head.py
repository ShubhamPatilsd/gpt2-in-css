#!/usr/bin/env python3
"""Build a row-wise int10 head that ranks rigorous logit upper bounds."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = os.environ.get(
    "GPT2_CERTIFIED_SOURCE_DIR", "gpt2-hvar-grid-output-head"
)
OUTPUT_NAME = os.environ.get(
    "GPT2_CERTIFIED_OUTPUT_DIR", "gpt2-hvar-grid-output-head-certified-upper-int10"
)
SOURCE = ROOT / "experiments" / SOURCE_NAME
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
SOURCE_REFERENCE = ROOT / "experiments" / "svg-filter-full-block" / "reference.json"


def css_number_up(value: float) -> str:
    """Serialize a positive factor outward at the builder's 1e-9 precision."""
    return head.css_number(math.ceil(float(value) * 1_000_000_000) / 1_000_000_000)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    css = (SOURCE / "index.css").read_text()
    reference = json.loads((SOURCE / "reference.json").read_text())
    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(
        tensors.tensor("wte.weight")[: head.VOCABULARY], dtype=np.float64
    )
    scales = np.max(np.abs(weights), axis=1) / head.WEIGHT_MAX
    scales[scales == 0] = 1.0
    codes = np.rint(weights / scales[:, None]).astype(np.int16)
    represented = codes.astype(np.float64) * scales[:, None]
    error_norms = np.linalg.norm(weights - represented, axis=1)
    bound_factors = error_norms * head.SCORE_SCALE * head.SCORE_STRIDE_PX

    token = 0
    candidate_pattern = re.compile(
        r'(<i class="candidate" style="--base:[^;]+;--factor:[^;]+;)'
        r'(--local-tie:)'
    )

    def add_bound(match: re.Match[str]) -> str:
        nonlocal token
        value = css_number_up(bound_factors[token])
        token += 1
        return f"{match.group(1)}--bound-factor:{value};{match.group(2)}"

    html = candidate_pattern.sub(add_bound, html)
    if token != head.VOCABULARY:
        raise RuntimeError(f"annotated {token} candidates, expected {head.VOCABULARY}")
    html = html.replace(
        "GPT-2-small HVAR + Grid output head",
        "Certified-upper row-wise int10 GPT-2 head",
        1,
    )

    old = "+ var(--score-offset),4px)"
    new = (
        "+ var(--score-offset) + var(--query-norm)*var(--bound-factor)*1px "
        "+ 4px,4px)"
    )
    if css.count(old) != 1:
        raise RuntimeError("candidate score transform missing")
    css = css.replace(old, new, 1)
    old_round = "width:calc-size(max-content,calc(round(nearest,"
    if css.count(old_round) != 1:
        raise RuntimeError("candidate rounding rule missing")
    css = css.replace(
        old_round,
        "width:calc-size(max-content,calc(round(down,",
        1,
    )
    css = css.replace(
        'url("score-d',
        f'url("../{SOURCE_NAME}/score-d',
    )
    norm = " + ".join(
        f"var(--h{dimension})*var(--h{dimension})"
        for dimension in range(head.WIDTH)
    )
    norm_css = (
        '\n@property --query-norm{syntax:"<number>";inherits:true;initial-value:0}'
        # Computing the norm on .model exceeds Chrome's per-element custom-
        # property expansion budget because that element also expands all 768
        # values into font-variation-settings.  Its child inherits the already
        # computed font setting and can evaluate the norm independently.
        f".group-scroller{{--query-norm:sqrt(calc({norm}))}}\n"
    )
    # The baseline deliberately leaves nested container-query scopes open until
    # EOF.  Insert this top-level registration and scorer before that readback
    # chain rather than appending them inside its active query scopes.
    readback_marker = ".outer-reader{"
    if css.count(readback_marker) != 1:
        raise RuntimeError("outer readback marker missing")
    css = css.replace(readback_marker, norm_css + readback_marker, 1)

    source_reference = json.loads(SOURCE_REFERENCE.read_text())
    hidden = np.asarray([
        source_reference["bucket_final_ln_expected"],
        source_reference["bucket_final_ln_expected_alt"],
        *reference["validation"]["hiddenVectors"],
    ], dtype=np.float64)
    query_norms = np.linalg.norm(hidden, axis=1)
    approximate_scores = hidden @ represented.T
    upper_scores = approximate_scores + query_norms[:, None] * error_norms
    dense_winners = np.asarray(
        [
            *reference["denseWinners"],
            *reference["validation"]["denseWinners"],
        ],
        dtype=int,
    )
    floors = [
        *reference["scoreFloors"],
        *reference["validation"]["scoreFloors"],
    ]
    # The browser encodes an outward upper bucket as floor(x) + 1 by adding a
    # full stride before round(down).  The harmless extra bucket at exact
    # integers makes the transform conservative without relying on round(up).
    upper_buckets = np.floor(
        (upper_scores - np.asarray(floors)[:, None]) * head.SCORE_SCALE
    ).astype(int) + 1
    if int(upper_buckets.min()) < 0 or int(upper_buckets.max()) >= 65_535:
        raise RuntimeError(
            f"upper-bound bucket range {upper_buckets.min()}..{upper_buckets.max()} "
            "does not fit the head encoding"
        )
    raw_upper_winners = upper_scores.argmax(axis=1).astype(int)
    upper_winners = upper_buckets.argmax(axis=1).astype(int)
    updated = {
        **reference,
        "backend": "row-wise-int10-hvar-plus-cauchy-upper-bound-grid",
        "source": SOURCE_NAME,
        "bound": "h.wq + l2(h)*l2(w-wq)",
        "boundMetadataBytes": sum(len(head.css_number(value)) + 15 for value in bound_factors),
        "allFixtures": {
            "hiddenVectors": hidden.tolist(),
            "queryNorms": query_norms.tolist(),
            "scoreFloors": floors,
            "denseWinners": dense_winners.tolist(),
            "rawUpperWinners": raw_upper_winners.tolist(),
            "upperWinners": upper_winners.tolist(),
            "upperWinnerBuckets": upper_buckets[
                np.arange(len(upper_winners)), upper_winners
            ].tolist(),
            "denseGroups": (dense_winners // head.GROUP_SIZE).tolist(),
            "upperGroups": (upper_winners // head.GROUP_SIZE).tolist(),
        },
    }
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "index.css").write_text(css)
    (OUTPUT / "reference.json").write_text(json.dumps(updated, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "htmlBytes": len(html.encode()),
        "cssBytes": len(css.encode()),
        "boundMetadataBytes": updated["boundMetadataBytes"],
        "upperBucketRange": [int(upper_buckets.min()), int(upper_buckets.max())],
        "fixturesWhoseRawAndBucketedUpperWinnerAgree": int(np.sum(
            raw_upper_winners == upper_winners
        )),
        "fixturesWhoseFirstGroupContainsDenseWinner": int(np.sum(
            dense_winners // head.GROUP_SIZE == upper_winners // head.GROUP_SIZE
        )),
        "fixtures": len(hidden),
    }, indent=2))


if __name__ == "__main__":
    main()
