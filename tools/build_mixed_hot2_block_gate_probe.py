#!/usr/bin/env python3
"""Gate the retained mixed hot-2 exact upper rows in contiguous token blocks."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

import build_mixed_precision_hot2_upper_probe as mixed
import build_token_uncertainty_gate_probe as token_gate
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-precision-hot2-upper"
BLOCK_SIZES = (4, 8)
FAN_IN = 16
HOT_GROUPS = (0, 1)


def center_candidate(
    group: int,
    local: int,
    row: tuple[str, str, str, str],
) -> str:
    base, factor, tie, glyphs = row
    return (
        '<i class="candidate hot-coarse-candidate" '
        f'style="--base:{base};--factor:{factor};--local-tie:{tie};'
        f'anchor-name:--hot-coarse-{group}-{local}">{glyphs}</i>'
    )


def gate_markup(
    block_size: int,
    fine_rows: list[tuple[str, str, str, str]],
) -> str:
    groups = []
    for group in HOT_GROUPS:
        lower_chunks = "".join(
            f'<i class="hot-lower-chunk hot-lower-chunk-{group}-{chunk}"></i>'
            for chunk in range(16)
        )
        lower_max = f'<i class="hot-lower-max hot-lower-max-{group}"></i>'
        blocks = []
        for block, local_start in enumerate(range(0, token_gate.GROUP_SIZE, block_size)):
            rows = []
            for local in range(local_start, min(local_start + block_size, token_gate.GROUP_SIZE)):
                token = group * token_gate.GROUP_SIZE + local
                base, factor, tie, glyphs = fine_rows[token]
                rows.append(
                    '<i class="candidate hot-exact-candidate" '
                    f'style="--base:{base};--factor:{factor};--local-tie:{tie}">'
                    f"{glyphs}</i>"
                )
            blocks.append(
                f'<i class="hot-gate-carrier hot-gate-{group}-{block}">'
                f'<span class="hot-exact-block hot-exact-block-{group}-{block}" '
                f'style="anchor-name:--hot-block-{group}-{block}">'
                f"{''.join(rows)}</span></i>"
            )
        block_count = math.ceil(token_gate.GROUP_SIZE / block_size)
        reducers = "".join(
            f'<i class="hot-exact-chunk hot-exact-chunk-{group}-{chunk}"></i>'
            for chunk in range(math.ceil(block_count / FAN_IN))
        ) if block_count > FAN_IN else ""
        groups.append(
            f'<span class="hot-token-gate hot-token-gate-{group}">'
            f"{lower_chunks}{lower_max}{''.join(blocks)}{reducers}"
            f'<i class="hot-exact-max hot-exact-max-{group}"></i></span>'
        )
    return '<aside id="hot-token-gates">' + "".join(groups) + "</aside>"


def build_html(block_size: int, coarse_rows: list, fine_rows: list) -> str:
    html = (SOURCE / "index.html").read_text()
    replacements = [
        center_candidate(group, local, coarse_rows[group * 256 + local])
        for group in HOT_GROUPS
        for local in range(token_gate.GROUP_SIZE)
    ]
    replacement_index = 0

    def restore_coarse(match: re.Match[str]) -> str:
        nonlocal replacement_index
        result = replacements[replacement_index]
        replacement_index += 1
        return result

    html, count = re.subn(
        r'<i class="candidate mixed-hot-candidate"[^>]*>.*?</i>',
        restore_coarse,
        html,
    )
    if count != len(HOT_GROUPS) * token_gate.GROUP_SIZE:
        raise RuntimeError(f"restored {count} hot rows, expected 512")
    if html.count("</main>") != 1:
        raise RuntimeError("mixed source main insertion point changed")
    html = html.replace("</main>", gate_markup(block_size, fine_rows) + "</main>", 1)
    return html.replace(
        "Mixed-precision hot-two certified upper head",
        f"Mixed hot-two block-gated exact upper B={block_size}",
        1,
    )


def font_settings(input_range: float) -> str:
    return token_gate.font_settings(input_range)


def exact_reduction(group: int, block_count: int) -> tuple[str, str]:
    terms = [
        f"anchor-size(--hot-block-{group}-{block} width,0px)"
        for block in range(block_count)
    ]
    if block_count <= FAN_IN:
        return "", f"max({','.join(terms)})"
    rules = []
    chunk_terms = []
    for chunk, start in enumerate(range(0, block_count, FAN_IN)):
        rules.append(
            f".hot-exact-chunk-{group}-{chunk}{{"
            f"anchor-name:--hot-exact-chunk-{group}-{chunk};"
            f"width:max({','.join(terms[start:start + FAN_IN])})}}"
        )
        chunk_terms.append(
            f"anchor-size(--hot-exact-chunk-{group}-{chunk} width,0px)"
        )
    return "".join(rules), f"max({','.join(chunk_terms)})"


def gate_css(
    block_size: int,
    coarse_reference: dict[str, object],
    fine_reference: dict[str, object],
    bound_factors: np.ndarray,
) -> str:
    coarse_faces = "".join(
        f'@font-face{{font-family:HotCoarse{shard};src:url("../gpt2-hvar-grid-output-head/'
        f'score-d{shard}.woff2") format("woff2")}}'
        for shard in range(len(coarse_reference["rowBaseMaximums"]))
    )
    coarse_families = ",".join(
        f"HotCoarse{shard}" for shard in range(len(coarse_reference["rowBaseMaximums"]))
    )
    fine_families = ",".join(
        f"Score{plane}{shard}"
        for shard in range(fine_reference["shards"])
        for plane in ("H", "L")
    )
    allowance_px = token_gate.TOTAL_ALLOWANCE_BUCKETS * token_gate.SCORE_STRIDE_PX
    rules = [
        coarse_faces,
        "body{anchor-scope:all}",
        ".hot-coarse-candidate{"
        f"font-family:{coarse_families};font-size:1000px;line-height:1;"
        f"font-variation-settings:{font_settings(float(coarse_reference['inputRange']))};"
        "font-kerning:none;width:calc-size(max-content,calc("
        "(size - var(--base)*1px)*var(--factor) + var(--score-offset)))}",
        ".hot-token-gate{position:fixed;left:0;top:-98000px}",
        ".hot-lower-chunk,.hot-lower-max,.hot-gate-carrier,.hot-exact-chunk,.hot-exact-max{"
        "position:fixed;left:0;height:1px}",
        ".hot-gate-carrier{top:-97000px;container:hot-token-gate/inline-size}",
        ".hot-exact-block{display:none;position:fixed;left:0;top:-96000px;"
        "width:max-content;height:1px;grid-template-columns:max-content;grid-template-rows:1px}",
        "@container hot-token-gate (width >= 1px){.hot-exact-block{display:grid}}",
        ".hot-exact-block>.hot-exact-candidate{display:block;grid-area:1/1;justify-self:start}",
        ".hot-exact-candidate{"
        f"font-family:{fine_families};font-size:100px;line-height:1;"
        f"font-variation-settings:{font_settings(float(fine_reference['inputRange']))};"
        "font-kerning:none;width:calc-size(max-content,calc(round(nearest,"
        "(size - var(--base)*1px)*var(--factor) + var(--score-offset),4px) + "
        "var(--local-tie)/64*1px))}",
    ]
    block_count = math.ceil(token_gate.GROUP_SIZE / block_size)
    for group in HOT_GROUPS:
        lower_terms = []
        for local in range(token_gate.GROUP_SIZE):
            factor = token_gate.outward_number(bound_factors[group, local])
            lower_terms.append(
                "calc("
                f"anchor-size(--hot-coarse-{group}-{local} width) - "
                f"var(--query-norm)*{factor}*1px - {allowance_px}px)"
            )
        for chunk in range(16):
            terms = lower_terms[chunk * 16 : (chunk + 1) * 16]
            rules.append(
                f".hot-lower-chunk-{group}-{chunk}{{top:-99000px;"
                f"anchor-name:--hot-lower-chunk-{group}-{chunk};"
                f"width:max({','.join(terms)})}}"
            )
        lower_chunks = ",".join(
            f"anchor-size(--hot-lower-chunk-{group}-{chunk} width)"
            for chunk in range(16)
        )
        rules.append(
            f".hot-lower-max-{group}{{top:-98500px;"
            f"anchor-name:--hot-lower-max-{group};width:max({lower_chunks})}}"
        )
        for block, start in enumerate(range(0, token_gate.GROUP_SIZE, block_size)):
            upper_terms = []
            for local in range(start, min(start + block_size, token_gate.GROUP_SIZE)):
                factor = token_gate.outward_number(bound_factors[group, local])
                upper_terms.append(
                    "calc("
                    f"anchor-size(--hot-coarse-{group}-{local} width) + "
                    f"var(--query-norm)*{factor}*1px + {allowance_px}px)"
                )
            rules.append(
                f".hot-gate-{group}-{block}{{width:calc(clamp(0,sign(calc("
                f"max({','.join(upper_terms)}) - anchor-size(--hot-lower-max-{group} width)"
                ")) + 1,1)*1px)}"
            )
        reduction, maximum = exact_reduction(group, block_count)
        rules.append(reduction)
        rules.append(
            f".hot-exact-max-{group}{{top:-95000px;"
            f"anchor-name:--hot-exact-{group};width:{maximum}}}"
        )
        route_allowance_px = mixed.HOT_UPPER_ALLOWANCE_BUCKETS * token_gate.SCORE_STRIDE_PX
        rules.append(
            f".group-wrapper:has(>.group-{group}){{width:calc("
            f"round(down,anchor-size(--hot-exact-{group} width),4px) + "
            f"{route_allowance_px}px)}}"
        )
    return "".join(rules) + "\n"


def main() -> None:
    for required in (SOURCE / "index.html", SOURCE / "topology.css", SOURCE / "reference.json"):
        if not required.exists():
            raise FileNotFoundError(required)
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    coarse_reference = json.loads((token_gate.COARSE / "reference.json").read_text())
    fine_reference = json.loads((token_gate.FINE / "reference.json").read_text())
    coarse_rows = token_gate.records(token_gate.COARSE / "index.html")
    fine_rows = token_gate.records(token_gate.FINE / "index.html")

    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[: 2 * token_gate.GROUP_SIZE],
        dtype=np.float64,
    )
    fine_scale = float(fine_reference["weightScale"])
    target = np.rint(weights / fine_scale) * fine_scale
    maximum_code = 2 ** 9 - 1
    row_scales = np.max(np.abs(weights), axis=1) / maximum_code
    row_scales[row_scales == 0] = 1.0
    represented = np.rint(weights / row_scales[:, None]) * row_scales[:, None]
    error_norms = np.linalg.norm(target - represented, axis=1)
    bound_factors = (
        error_norms.reshape(2, token_gate.GROUP_SIZE)
        * token_gate.SCORE_SCALE
        * token_gate.SCORE_STRIDE_PX
    )

    source_topology = (SOURCE / "topology.css").read_text()
    source_topology = source_topology.replace(
        "anchor-size(--group-0 width)", "anchor-size(--hot-exact-0 width)"
    ).replace(
        "anchor-size(--group-1 width)", "anchor-size(--hot-exact-1 width)"
    )
    variants = []
    for block_size in BLOCK_SIZES:
        output = ROOT / "experiments" / f"gpt2-mixed-hot2-block-gate-b{block_size}"
        output.mkdir(parents=True, exist_ok=True)
        html = build_html(block_size, coarse_rows, fine_rows)
        topology = source_topology + gate_css(
            block_size, coarse_reference, fine_reference, bound_factors
        )
        (output / "index.html").write_text(html)
        (output / "topology.css").write_text(topology)
        reference = {
            **source_reference,
            "backend": f"mixed-hot2-block-gated-global-int16-b{block_size}-six-stage",
            "sourceMixed": SOURCE.name,
            "blockSize": block_size,
            "blockCountPerHotGroup": token_gate.GROUP_SIZE // block_size,
            "fanIn": FAN_IN,
            "upperRowsAdded": 2 * token_gate.GROUP_SIZE,
            "upperRowsReplacedWithGlobalInt16": 0,
            "tokenGateAllowanceBuckets": token_gate.TOTAL_ALLOWANCE_BUCKETS,
            "topologyStrategy": (
                "restore int10 centers for hot groups 0/1, use them for inclusive "
                f"B={block_size} token-block uncertainty gates, and expose each gated "
                "global-int16 block maximum both to routing and selected-stage reuse"
            ),
            "generatedBytes": {
                "index.html": len(html.encode()),
                "topology.css": len(topology.encode()),
            },
        }
        (output / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
        variants.append(
            {
                "blockSize": block_size,
                "directory": output.name,
                "htmlBytes": len(html.encode()),
                "cssBytes": len(topology.encode()),
                "coarseHotRows": 512,
                "conditionallyShapedExactRows": 512,
            }
        )
    print(json.dumps({"variants": variants}, indent=2))


if __name__ == "__main__":
    main()
