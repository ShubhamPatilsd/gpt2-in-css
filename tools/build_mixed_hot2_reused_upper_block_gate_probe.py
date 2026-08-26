#!/usr/bin/env python3
"""Gate hot-2 exact rows from already-paid int10 upper-row geometry."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

import build_certified_int10_upper_head as certified
import build_mixed_hot2_block_gate_probe as duplicated
import build_mixed_precision_hot2_upper_probe as mixed
import build_token_uncertainty_gate_probe as token_gate
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_certified_tail_strategies import AXIS_STEPS, STATES


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-precision-hot2-upper"
PAID_UPPER = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-certified-upper-int10-one-step"
)
BLOCK_SIZES = (4, 8)
HOT_GROUPS = (0, 1)
FAN_IN = 16


def paid_upper_candidates() -> list[str]:
    candidates = re.findall(
        r'<i class="candidate"[^>]*>.*?</i>',
        (PAID_UPPER / "index.html").read_text(),
    )
    if len(candidates) != token_gate.head.VOCABULARY:
        raise RuntimeError(f"expected full paid upper bank, found {len(candidates)}")
    return candidates


def partitioned_gate_markup(
    partitions_by_group: list[list[list[int]]],
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
        for block, locals_ in enumerate(partitions_by_group[group]):
            rows = []
            for local in locals_:
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
        block_count = len(partitions_by_group[group])
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


def build_html(
    block_size: int,
    upper_rows: list[str],
    fine_rows: list,
    partitions_by_group: list[list[list[int]]] | None = None,
) -> str:
    html = (SOURCE / "index.html").read_text()
    paid_rows = []
    for group in HOT_GROUPS:
        for local in range(token_gate.GROUP_SIZE):
            token = group * token_gate.GROUP_SIZE + local
            row = upper_rows[token].replace(
                'class="candidate"',
                'class="candidate hot-paid-upper-candidate"',
                1,
            ).replace(
                'style="',
                f'style="anchor-name:--hot-paid-upper-{group}-{local};',
                1,
            )
            paid_rows.append(row)
    html, count = re.subn(
        r'<i class="candidate mixed-hot-candidate"[^>]*>.*?</i>',
        "",
        html,
    )
    if count != len(paid_rows):
        raise RuntimeError(f"restored {count} paid upper rows, expected 512")
    for group in HOT_GROUPS:
        old_anchor = f"anchor-name:--score-group-{group};"
        new_anchor = f"anchor-name:--paid-score-group-{group};"
        if html.count(old_anchor) != 1:
            raise RuntimeError(f"group {group} score anchor replacement changed")
        html = html.replace(old_anchor, new_anchor, 1)
    gates = (
        duplicated.gate_markup(block_size, fine_rows)
        if partitions_by_group is None
        else partitioned_gate_markup(partitions_by_group, fine_rows)
    )
    gate_marker = '<aside id="hot-token-gates">'
    if gates.count(gate_marker) != 1:
        raise RuntimeError("paid upper stage insertion point changed")
    gates = gates.replace(
        gate_marker,
        gate_marker + '<span class="hot-paid-upper-stage">' + "".join(paid_rows) + "</span>",
        1,
    )
    gates = gates.replace(
        "</aside>",
        "".join(
            f'<i class="hot-route-proxy hot-route-proxy-{group}"></i>'
            for group in HOT_GROUPS
        ) + "</aside>",
        1,
    )
    marker = '<div class="group-track">\n'
    if html.count(marker) != 1:
        raise RuntimeError("in-track gate insertion point changed")
    html = html.replace(
        marker,
        marker + gates,
        1,
    )
    outer_reader = '<div class="outer-reader">'
    if html.count(outer_reader) != 1:
        raise RuntimeError("direct outer max insertion point changed")
    html = html.replace(
        outer_reader,
        '<i class="direct-outer-max"></i>' + outer_reader,
        1,
    )
    return html.replace(
        "Mixed-precision hot-two certified upper head",
        f"Mixed hot-two reused-upper block gate B={block_size}",
        1,
    )


def gate_css(
    block_size: int,
    fine_reference: dict[str, object],
    float_bound_factors: list[list[str]],
    target_bound_factors: list[list[str]],
    partitions_by_group: list[list[list[int]]] | None = None,
) -> str:
    fine_families = ",".join(
        f"Score{plane}{shard}"
        for shard in range(fine_reference["shards"])
        for plane in ("H", "L")
    )
    allowance_px = token_gate.TOTAL_ALLOWANCE_BUCKETS * token_gate.SCORE_STRIDE_PX
    norm = " + ".join(
        f"var(--h{dimension})*var(--h{dimension})"
        for dimension in range(token_gate.head.WIDTH)
    )
    rules = [
        "body{anchor-scope:all}",
        f"#hot-token-gates{{--query-norm:sqrt(calc({norm}));display:contents}}",
        ".hot-paid-upper-candidate{position:fixed;left:0;top:-99500px;height:1px;display:block}",
        ".hot-route-proxy,.direct-outer-max{position:fixed;left:0;height:1px}",
        ".group-0,.group-1{anchor-name:none}",
        ".hot-lower-chunk,.hot-lower-max,.hot-gate-carrier,.hot-exact-chunk,.hot-exact-max{"
        "position:fixed;left:0;height:1px}",
        ".hot-gate-carrier{top:-97000px;container:hot-token-gate/inline-size}",
        ".hot-exact-block{display:none;position:fixed;left:0;top:-96000px;"
        "width:max-content;height:1px;grid-template-columns:max-content;grid-template-rows:1px}",
        "@container hot-token-gate (width >= 1px){.hot-exact-block{display:grid}}",
        ".hot-exact-block>.hot-exact-candidate{display:block;grid-area:1/1;justify-self:start}",
        ".hot-exact-candidate{"
        f"font-family:{fine_families};font-size:100px;line-height:1;"
        f"font-variation-settings:{token_gate.font_settings(float(fine_reference['inputRange']))};"
        "font-kerning:none;width:calc-size(max-content,calc(round(nearest,"
        "(size - var(--base)*1px)*var(--factor) + var(--score-offset),4px) + "
        "var(--local-tie)/64*1px))}",
    ]
    for group in HOT_GROUPS:
        lower_terms = []
        upper_terms = []
        for local in range(token_gate.GROUP_SIZE):
            paid = (
                f"round(down,anchor-size(--hot-paid-upper-{group}-{local} width),4px)"
            )
            float_factor = float_bound_factors[group][local]
            target_factor = target_bound_factors[group][local]
            lower_terms.append(
                "calc("
                f"{paid} - var(--query-norm)*{float_factor}*1px - "
                f"var(--query-norm)*{target_factor}*1px - 4px - {allowance_px}px)"
            )
            upper_terms.append(
                "calc("
                f"{paid} - var(--query-norm)*{float_factor}*1px + "
                f"var(--query-norm)*{target_factor}*1px + {allowance_px}px)"
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
        partitions = (
            [
                list(range(start, start + block_size))
                for start in range(0, token_gate.GROUP_SIZE, block_size)
            ]
            if partitions_by_group is None
            else partitions_by_group[group]
        )
        for block, locals_ in enumerate(partitions):
            rules.append(
                f".hot-gate-{group}-{block}{{width:calc(clamp(0,sign(calc("
                f"max({','.join(upper_terms[local] for local in locals_)}) - "
                f"anchor-size(--hot-lower-max-{group} width))) + 1,1)*1px)}}"
            )
        block_count = len(partitions)
        reduction, maximum = duplicated.exact_reduction(group, block_count)
        rules.append(reduction)
        route_allowance_px = mixed.HOT_UPPER_ALLOWANCE_BUCKETS * token_gate.SCORE_STRIDE_PX
        rules.append(
            f".hot-exact-max-{group}{{top:-95000px;"
            f"anchor-name:--hot-exact-{group},--group-{group};width:{maximum}}}"
        )
        rules.append(
            f".hot-route-proxy-{group}{{top:-94500px;anchor-name:--score-group-{group};"
            f"width:calc(round(down,anchor-size(--hot-exact-{group} width),4px) + "
            f"{route_allowance_px}px)}}"
        )
    outer_terms = ",".join(
        f"anchor-size(--score-group-{group} width)"
        for group in range(math.ceil(token_gate.head.VOCABULARY / token_gate.GROUP_SIZE))
    )
    rules.append(
        ".direct-outer-max{top:-94000px;anchor-name:--direct-outer-max;"
        f"width:max({outer_terms})}}"
    )
    rules.append(
        ".outer-reader{position-anchor:--direct-outer-max;"
        "width:anchor-size(--direct-outer-max width)}"
    )
    return "".join(rules) + "\n"


def screen(
    hidden: np.ndarray,
    query_norms: np.ndarray,
    represented: np.ndarray,
    target: np.ndarray,
    float_errors: np.ndarray,
    target_errors: np.ndarray,
) -> dict[str, object]:
    centers = hidden @ represented.T * token_gate.SCORE_SCALE
    paid_upper = np.floor(
        centers + query_norms[:, None] * float_errors[None, :] * token_gate.SCORE_SCALE
    ) + 1
    float_radius = query_norms[:, None] * float_errors[None, :] * token_gate.SCORE_SCALE
    target_radius = query_norms[:, None] * target_errors[None, :] * token_gate.SCORE_SCALE
    lower = (
        paid_upper
        - float_radius
        - target_radius
        - 1
        - token_gate.TOTAL_ALLOWANCE_BUCKETS
    )
    upper = (
        paid_upper
        - float_radius
        + target_radius
        + token_gate.TOTAL_ALLOWANCE_BUCKETS
    )
    exact = hidden @ target.T
    reports = []
    for group in HOT_GROUPS:
        start = group * token_gate.GROUP_SIZE
        stop = start + token_gate.GROUP_SIZE
        group_lower = lower[:, start:stop]
        group_upper = upper[:, start:stop]
        threshold = np.max(group_lower, axis=1)
        winner = np.argmax(exact[:, start:stop], axis=1)
        variants = []
        for block_size in BLOCK_SIZES:
            blocks = token_gate.GROUP_SIZE // block_size
            active = np.max(
                group_upper.reshape(len(hidden), blocks, block_size), axis=2
            ) >= threshold[:, None]
            retained = active[np.arange(len(hidden)), winner // block_size]
            if not np.all(retained):
                raise RuntimeError(
                    f"derived paid-upper gate lost group {group} winners for B={block_size}"
                )
            shaped = np.sum(active, axis=1) * block_size
            variants.append(
                {
                    "blockSize": block_size,
                    "winnerRetainedStates": int(np.sum(retained)),
                    "meanShapedRows": float(np.mean(shaped)),
                    "medianShapedRows": float(np.median(shaped)),
                    "maximumShapedRows": int(np.max(shaped)),
                }
            )
        reports.append({"group": group, "variants": variants})
    return {"states": len(hidden), "groups": reports}


def main() -> None:
    fine_reference = json.loads((token_gate.FINE / "reference.json").read_text())
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    upper_rows = paid_upper_candidates()
    fine_rows = token_gate.records(token_gate.FINE / "index.html")
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[: 2 * token_gate.GROUP_SIZE],
        dtype=np.float64,
    )
    maximum_code = 2 ** 9 - 1
    row_scales = np.max(np.abs(weights), axis=1) / maximum_code
    row_scales[row_scales == 0] = 1.0
    represented = np.rint(weights / row_scales[:, None]) * row_scales[:, None]
    fine_scale = float(fine_reference["weightScale"])
    target = np.rint(weights / fine_scale) * fine_scale
    float_errors = np.linalg.norm(weights - represented, axis=1)
    target_errors = np.linalg.norm(target - represented, axis=1)
    recomputed_float_factors = [
        certified.css_number_up(
            value * token_gate.SCORE_SCALE * token_gate.SCORE_STRIDE_PX
        )
        for value in float_errors
    ]
    float_factors = []
    for token, row in enumerate(upper_rows[: 2 * token_gate.GROUP_SIZE]):
        match = re.search(r"--bound-factor:([^;]+);", row)
        if match is None:
            raise RuntimeError(f"paid upper row {token} has no bound factor")
        paid_factor = match.group(1)
        if paid_factor != recomputed_float_factors[token]:
            raise RuntimeError(
                f"paid/recomputed float factor mismatch at token {token}: "
                f"{paid_factor} != {recomputed_float_factors[token]}"
            )
        # The algebra must subtract exactly the serialized radius that the
        # paid upper row added. Reusing its literal avoids directional drift.
        float_factors.append(paid_factor)
    target_factors = [
        token_gate.outward_number(
            value * token_gate.SCORE_SCALE * token_gate.SCORE_STRIDE_PX
        )
        for value in target_errors
    ]
    float_factors_by_group = np.asarray(float_factors).reshape(2, 256).tolist()
    target_factors_by_group = np.asarray(target_factors).reshape(2, 256).tolist()

    fixture_hidden = np.asarray(
        source_reference["certifiedFixtures"]["hiddenVectors"], dtype=np.float64
    )
    fixture_screen = screen(
        fixture_hidden,
        np.linalg.norm(fixture_hidden, axis=1),
        represented,
        target,
        float_errors,
        target_errors,
    )
    saved = np.load(STATES)
    corpus_hidden = np.asarray(saved["hidden"], dtype=np.float64)
    production_range = float(np.max(np.abs(corpus_hidden))) * 1.01
    corpus_realized = (
        np.rint(corpus_hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    corpus_screen = screen(
        corpus_realized,
        np.linalg.norm(corpus_realized, axis=1),
        represented,
        target,
        float_errors,
        target_errors,
    )

    topology = (SOURCE / "topology.css").read_text().replace(
        "anchor-size(--group-0 width)", "anchor-size(--hot-exact-0 width)"
    ).replace(
        "anchor-size(--group-1 width)", "anchor-size(--hot-exact-1 width)"
    )
    variants = []
    for block_size in BLOCK_SIZES:
        output = (
            ROOT
            / "experiments"
            / f"gpt2-mixed-hot2-reused-upper-block-gate-b{block_size}"
        )
        output.mkdir(parents=True, exist_ok=True)
        html = build_html(block_size, upper_rows, fine_rows)
        css = topology + gate_css(
            block_size,
            fine_reference,
            float_factors_by_group,
            target_factors_by_group,
        )
        (output / "index.html").write_text(html)
        (output / "topology.css").write_text(css)
        reference = {
            **source_reference,
            "backend": f"mixed-hot2-reused-paid-upper-block-gate-b{block_size}",
            "sourceMixed": SOURCE.name,
            "sourcePaidUpper": PAID_UPPER.name,
            "blockSize": block_size,
            "blockCountPerHotGroup": token_gate.GROUP_SIZE // block_size,
            "fanIn": FAN_IN,
            "upperRowsAdded": 2 * token_gate.GROUP_SIZE,
            "upperRowsReplacedWithGlobalInt16": 0,
            "additionalCoarseRows": 0,
            "tokenGateAllowanceBuckets": token_gate.TOTAL_ALLOWANCE_BUCKETS,
            "derivedBound": {
                "paidUpper": "A=floor4(center + norm*r_float + 4px)",
                "targetUpper": "A - norm*r_float + norm*r_target + allowance",
                "targetLower": "A - norm*r_float - norm*r_target - 4px - allowance",
            },
            "offlineScreens": {
                "fixtures": fixture_screen,
                "corpus": corpus_screen,
            },
            "topologyStrategy": (
                "restore already-paid int10 upper rows for hot groups 0/1, derive "
                "global-int16 lower/upper bounds from those quantized upper widths, "
                f"and conditionally shape exact B={block_size} blocks without adding "
                "a second coarse center bank"
            ),
            "generatedBytes": {
                "index.html": len(html.encode()),
                "topology.css": len(css.encode()),
            },
        }
        (output / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
        variants.append(
            {
                "blockSize": block_size,
                "directory": output.name,
                "htmlBytes": len(html.encode()),
                "cssBytes": len(css.encode()),
                "additionalCoarseRows": 0,
            }
        )
    print(json.dumps({
        "variants": variants,
        "offlineFixtures": fixture_screen,
        "offlineCorpus": corpus_screen,
    }, indent=2))


if __name__ == "__main__":
    main()
