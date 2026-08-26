#!/usr/bin/env python3
"""Build browser probes for contiguous-block token uncertainty gates."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

import build_token_uncertainty_gate_probe as token_gate
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-token-uncertainty-block-gate"
BLOCK_SIZES = (4, 8, 16)
FAN_IN = 16


def render_html(
    coarse_rows: list[tuple[str, str, str, str]],
    fine_rows: list[tuple[str, str, str, str]],
    block_size: int,
) -> str:
    block_count = math.ceil(token_gate.GROUP_SIZE / block_size)
    coarse = "".join(
        f'<i id="coarse-{token}" class="coarse-candidate" '
        f'style="--base:{base};--factor:{factor};anchor-name:--coarse-{token}">'
        f"{glyphs}</i>"
        for token, (base, factor, _, glyphs) in enumerate(coarse_rows)
    )
    lower_chunks = "".join(
        f'<i id="lower-chunk-{chunk}" class="lower-chunk lower-chunk-{chunk}"></i>'
        for chunk in range(16)
    )
    blocks = []
    for block in range(block_count):
        start = block * block_size
        stop = min(start + block_size, token_gate.GROUP_SIZE)
        rows = "".join(
            f'<i id="gated-exact-{token}" class="exact-candidate gated-exact" '
            f'style="--base:{base};--factor:{factor};--local-tie:{tie}">{glyphs}</i>'
            for token, (base, factor, tie, glyphs) in enumerate(
                fine_rows[start:stop], start
            )
        )
        blocks.append(
            f'<i id="gate-block-{block}" class="gate-carrier gate-block-{block}">'
            f'<span id="exact-block-{block}" class="exact-block" '
            f'style="anchor-name:--gated-block-{block}">{rows}</span></i>'
        )
    reducer_count = math.ceil(block_count / FAN_IN) if block_count > FAN_IN else 0
    reducers = "".join(
        f'<i id="gated-chunk-{chunk}" class="gated-chunk gated-chunk-{chunk}"></i>'
        for chunk in range(reducer_count)
    )
    full = "".join(
        f'<i class="exact-candidate full-exact" '
        f'style="--base:{base};--factor:{factor};--local-tie:{tie}">{glyphs}</i>'
        for base, factor, tie, glyphs in fine_rows
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>GPT-2 token uncertainty block gate B={block_size}</title>
<link rel="stylesheet" href="index-b{block_size}.css">
<body class="mode-both">
<main id="probe" class="probe" data-block-size="{block_size}">
  <section id="gate-path" class="gate-path">
    <span id="coarse-stage" class="coarse-stage">{coarse}</span>
    {lower_chunks}
    <i id="lower-max" class="lower-max"></i>
    <span id="gate-stage" class="gate-stage">{''.join(blocks)}</span>
    {reducers}
    <i id="gated-max" class="gated-max"></i>
    <span class="gated-reader"><output id="gated-result" class="gated-result"></output></span>
  </section>
  <section id="full-control" class="full-control">
    <span id="full-stage" class="full-stage">{full}</span>
    <span class="full-reader"><output id="full-result" class="full-result"></output></span>
  </section>
</main>
<aside id="equality-probe" class="equality-probe">
  <i id="equality-gate" class="synthetic-gate synthetic-equal"><b></b></i>
  <i id="below-gate" class="synthetic-gate synthetic-below"><b></b></i>
  <span id="tie-stage" class="tie-stage"><i style="--local-tie:252"></i><i style="--local-tie:248"></i></span>
  <span class="tie-reader"><output id="tie-result" class="tie-result"></output></span>
</aside>
"""


def block_gate_rules(bound_factors: list[str], block_size: int) -> str:
    rules = []
    for block, start in enumerate(range(0, token_gate.GROUP_SIZE, block_size)):
        upper_terms = []
        for token in range(start, min(start + block_size, token_gate.GROUP_SIZE)):
            factor = bound_factors[token]
            upper_terms.append(
                "calc("
                f"anchor-size(--coarse-{token} width) + var(--query-norm)*{factor}*1px"
                f" + {token_gate.TOTAL_ALLOWANCE_BUCKETS * token_gate.SCORE_STRIDE_PX}px)"
            )
        upper = f"max({','.join(upper_terms)})"
        rules.append(
            f".gate-block-{block}{{width:calc(clamp(0,sign(calc({upper} - "
            "anchor-size(--lower-max width))) + 1,1)*1px)}"
        )
    return "".join(rules)


def reducer_css(block_size: int) -> tuple[str, str]:
    block_count = math.ceil(token_gate.GROUP_SIZE / block_size)
    block_sizes = [
        f"anchor-size(--gated-block-{block} width,0px)"
        for block in range(block_count)
    ]
    if block_count <= FAN_IN:
        return "", f"max({','.join(block_sizes)})"
    chunks = []
    chunk_sizes = []
    for chunk, start in enumerate(range(0, block_count, FAN_IN)):
        terms = block_sizes[start : start + FAN_IN]
        chunks.append(
            f".gated-chunk-{chunk}{{anchor-name:--gated-chunk-{chunk};"
            f"width:max({','.join(terms)})}}"
        )
        chunk_sizes.append(f"anchor-size(--gated-chunk-{chunk} width,0px)")
    common = (
        ".gated-chunk{position:fixed;position-anchor:--coarse-0;left:0;"
        "top:-86500px;height:1px}"
    )
    return common + "".join(chunks), f"max({','.join(chunk_sizes)})"


def render_css(
    coarse_reference: dict[str, object],
    fine_reference: dict[str, object],
    bound_factors: list[str],
    block_size: int,
) -> str:
    css = token_gate.render_css(coarse_reference, fine_reference, bound_factors)
    css, count = re.subn(r"\.gate-\d+\{width:[^}]+\}", "", css)
    if count != token_gate.GROUP_SIZE:
        raise RuntimeError(f"removed {count} token gates, expected 256")
    marker = ".gate-carrier{position:fixed;left:0;top:-88000px;height:1px;container:token-gate/inline-size}"
    if marker not in css:
        raise RuntimeError("gate-carrier marker changed")
    css = css.replace(marker, marker + block_gate_rules(bound_factors, block_size))

    old_exact = (
        ".gated-exact{display:none;position:fixed;left:0;top:-87000px}"
        "\n@container token-gate (width >= 1px){.gated-exact{display:block}}"
    )
    new_exact = (
        ".exact-block{display:none;position:fixed;left:0;top:-87000px;"
        "width:max-content;height:1px;grid-template-columns:max-content;"
        "grid-template-rows:1px}"
        "\n@container token-gate (width >= 1px){.exact-block{display:grid}}"
        "\n.exact-block>.gated-exact{display:block;grid-area:1/1;justify-self:start}"
    )
    if old_exact not in css:
        raise RuntimeError("gated exact marker changed")
    css = css.replace(old_exact, new_exact)

    reduction, maximum = reducer_css(block_size)
    css, count = re.subn(
        r"\.gated-chunk\{.*?(?=\.gated-max\{)",
        reduction,
        css,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError("gated chunk reduction marker changed")
    css, count = re.subn(
        r"\.gated-max\{[^}]+\}",
        ".gated-max{position:fixed;position-anchor:--coarse-0;left:0;"
        "top:-86000px;height:1px;anchor-name:--gated-winner;"
        f"width:{maximum}}}",
        css,
        count=1,
    )
    if count != 1:
        raise RuntimeError("gated max marker changed")
    return css


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    coarse_reference = json.loads((token_gate.COARSE / "reference.json").read_text())
    fine_reference = json.loads((token_gate.FINE / "reference.json").read_text())
    token_reference = json.loads((token_gate.OUTPUT / "reference.json").read_text())
    coarse_rows = token_gate.records(token_gate.COARSE / "index.html")[: token_gate.GROUP_SIZE]
    fine_rows = token_gate.records(token_gate.FINE / "index.html")[: token_gate.GROUP_SIZE]

    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[: token_gate.GROUP_SIZE],
        dtype=np.float64,
    )
    row_scales = np.max(np.abs(weights), axis=1) / token_gate.head.WEIGHT_MAX
    row_scales[row_scales == 0] = 1.0
    represented = np.rint(weights / row_scales[:, None]) * row_scales[:, None]
    fine_scale = float(fine_reference["weightScale"])
    target = np.rint(weights / fine_scale) * fine_scale
    error_norms = np.linalg.norm(target - represented, axis=1)
    bound_factors = [
        token_gate.outward_number(
            value * token_gate.SCORE_SCALE * token_gate.SCORE_STRIDE_PX
        )
        for value in error_norms
    ]

    variants = []
    for block_size in BLOCK_SIZES:
        block_count = math.ceil(token_gate.GROUP_SIZE / block_size)
        fixtures = []
        for fixture in token_reference["fixtures"]:
            active_blocks = sorted(
                {int(token) // block_size for token in fixture["activeTokens"]}
            )
            fixtures.append(
                {
                    **fixture,
                    "activeBlocks": active_blocks,
                    "activeBlockCount": len(active_blocks),
                    "shapedRows": sum(
                        min(block_size, token_gate.GROUP_SIZE - block * block_size)
                        for block in active_blocks
                    ),
                }
            )
        html_path = OUTPUT / f"index-b{block_size}.html"
        css_path = OUTPUT / f"index-b{block_size}.css"
        html_path.write_text(render_html(coarse_rows, fine_rows, block_size))
        css_path.write_text(
            render_css(coarse_reference, fine_reference, bound_factors, block_size)
        )
        variants.append(
            {
                "blockSize": block_size,
                "blockCount": block_count,
                "meanActiveBlocks": float(
                    np.mean([fixture["activeBlockCount"] for fixture in fixtures])
                ),
                "meanShapedRows": float(
                    np.mean([fixture["shapedRows"] for fixture in fixtures])
                ),
                "fixtures": fixtures,
                "htmlBytes": html_path.stat().st_size,
                "cssBytes": css_path.stat().st_size,
            }
        )

    reference = {
        "model": token_reference["model"],
        "backend": "fixed-group-int10-block-upper-plus-inclusive-css-exact-block-gate",
        "scope": token_reference["scope"],
        "group": token_reference["group"],
        "groupSize": token_reference["groupSize"],
        "target": token_reference["target"],
        "coarseModel": token_reference["coarseModel"],
        "bucketContract": token_reference["bucketContract"],
        "blockSizes": list(BLOCK_SIZES),
        "fanIn": FAN_IN,
        "coarseGlyphsPerToken": token_reference["coarseGlyphsPerToken"],
        "exactGlyphsPerShapedToken": token_reference["exactGlyphsPerActiveToken"],
        "fullControlExactRows": token_reference["fullControlExactRows"],
        "variants": variants,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({key: value for key, value in reference.items() if key != "variants"}, indent=2))


if __name__ == "__main__":
    main()
