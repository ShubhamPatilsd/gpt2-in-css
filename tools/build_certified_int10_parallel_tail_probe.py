#!/usr/bin/env python3
"""Build a six-stage certified prefix with one parallel uncertainty tail."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated"
OUTPUT_NAME = "gpt2-hvar-grid-output-head-certified-int10-parallel-tail"
SOURCE = ROOT / "experiments" / SOURCE_NAME
OUTPUT = ROOT / "experiments" / OUTPUT_NAME
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
FINE_REFERENCE = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
    / "reference.json"
)
GROUPS = 197
PREFIX_GROUPS = 6
CURRENT_COARSE_ALLOWANCE = 10
CURRENT_FINE_ALLOWANCE = 5
CURRENT_TOTAL_ALLOWANCE = CURRENT_COARSE_ALLOWANCE + CURRENT_FINE_ALLOWANCE
BROWSER_BOUNDARY_GUARD = 1
STRESS_TOTAL_ALLOWANCE = 48
SCORE_STRIDE_PX = 1024
GROUP_TIE_STRIDE_PX = 4
CHROME_LAYOUT_LIMIT_PX = 33_554_428


def registration(name: str, initial: int = 0) -> str:
    return (
        f'@property --{name}{{syntax:"<number>";inherits:true;'
        f'initial-value:{initial}}}'
    )


def candidate_markup(html: str) -> str:
    marker = '<span id="fine-stage" class="fine-stage">'
    start = html.index(marker) + len(marker)
    stop = html.index('</span><span class="fine-reader">', start)
    return html[start:stop]


def branch_markup(group: int, candidates: str) -> str:
    return (
        f'<span id="tail-gate-{group}" class="tail-gate tail-gate-{group}">'
        f'<span id="tail-fine-stage-{group}" '
        f'class="fine-stage tail-fine-stage tail-fine-stage-{group}" '
        f'style="--group:{group};anchor-name:--tail-fine-winner-{group}">'
        f'{candidates}</span>'
        f'<span id="tail-fine-reader-{group}" '
        f'class="tail-fine-reader tail-fine-reader-{group}" '
        f'style="--group:{group};position-anchor:--tail-fine-winner-{group}">'
        f'<i id="tail-fine-result-{group}" '
        f'class="tail-fine-result tail-fine-result-{group}">'
        f'<i id="tail-score-carrier-{group}" '
        f'class="tail-score-carrier tail-score-carrier-{group}"></i>'
        f'<i id="tail-token-carrier-{group}" '
        f'class="tail-token-carrier tail-token-carrier-{group}"></i>'
        '</i></span></span>'
    )


def tail_markup(candidates: str) -> str:
    branches = "".join(branch_markup(group, candidates) for group in range(GROUPS))
    token_sources = (
        '<i class="tail-token-source tail-prefix-token-source"></i>'
        + "".join(
            f'<i class="tail-token-source tail-token-source-{group}"></i>'
            for group in range(GROUPS)
        )
    )
    return (
        '<span id="parallel-tail" class="parallel-tail">'
        '<i id="tail-prefix-score" class="tail-prefix-score"></i>'
        '<i id="tail-prefix-token" class="tail-prefix-token"></i>'
        f'{branches}'
        '<i id="tail-score-max" class="tail-score-max"></i>'
        '<span id="tail-score-reader" class="tail-score-reader">'
        '<output id="tail-score-result" class="tail-score-result">'
        f'{token_sources}'
        '<i id="tail-token-max" class="tail-token-max"></i>'
        '<span id="tail-token-reader" class="tail-token-reader">'
        '<output id="tail-final-result" class="tail-final-result"></output>'
        '</span></output></span></span>'
    )


def branch_css(group: int) -> str:
    # Router six has already multiplied every coarse score anchor by the exact
    # six-group unvisited mask. Reusing that permanent source avoids rebuilding
    # the six-way history comparison in every tail gate.
    activation = f"tail-activation-{group}"
    fine_read = f"tail-fine-read-{group}"
    return "".join((
        f'.tail-gate-{group}{{--group:{group};'
        f'position-anchor:--upper-source-6-{group};'
        f'container:{activation}/inline-size;'
        'width:calc('
        f'clamp(0px,anchor-size(--upper-source-6-{group} width) - '
        '(var(--best-bucket-5) - var(--tail-allowance))*4px + 1px,1px) * '
        'calc(1 - var(--done-5)))}}',
        f'.tail-fine-stage-{group}{{--group:{group};'
        f'anchor-name:--tail-fine-winner-{group}}}',
        f'.tail-fine-reader-{group}{{--group:{group};'
        f'position-anchor:--tail-fine-winner-{group};'
        f'width:anchor-size(--tail-fine-winner-{group} width,0px);'
        f'container:{fine_read}/inline-size}}',
        f'@container {activation} (width >= 1px){{'
        f'.tail-fine-stage-{group}{{display:grid}}}}',
        f'@container {fine_read} (width >= 1px){{'
        f'.tail-fine-result-{group}{{'
        f'--tail-bucket-{group}:round(down,100cqi/4px,1);'
        f'--tail-local-{group}:calc(255 - '
        'round(nearest,mod(100cqi,4px)/1px*64,1));'
        f'--tail-winner-{group}:calc({group}*256 + var(--tail-local-{group}));'
        'display:block}'
        f'.tail-score-carrier-{group}{{width:calc('
        f'var(--tail-bucket-{group})*{SCORE_STRIDE_PX}px + '
        f'({GROUPS} - {group})*{GROUP_TIE_STRIDE_PX}px)}}'
        f'.tail-token-carrier-{group}{{'
        f'width:calc(var(--tail-winner-{group})*1px)}}}}',
    ))


def merge_css() -> str:
    score_anchors = ["anchor-size(--tail-prefix-score-anchor width)"] + [
        f"anchor-size(--tail-score-anchor-{group} width)"
        for group in range(GROUPS)
    ]
    token_anchors = ["anchor-size(--tail-prefix-token-source-anchor width)"] + [
        f"anchor-size(--tail-token-source-anchor-{group} width)"
        for group in range(GROUPS)
    ]
    token_rules = "".join(
        f'.tail-token-source-{group}{{'
        f'position-anchor:--tail-token-anchor-{group};'
        f'anchor-name:--tail-token-source-anchor-{group};'
        f'width:calc(anchor-size(--tail-token-anchor-{group} width) * '
        f'(1 - clamp(0,abs(var(--tail-winning-group) - {group}),1)))}}'
        for group in range(GROUPS)
    )
    return "".join((
        '.tail-prefix-score{anchor-name:--tail-prefix-score-anchor;'
        f'width:calc(var(--best-bucket-5)*{SCORE_STRIDE_PX}px + '
        f'({GROUPS} - round(down,var(--best-winner-5)/256,1))*'
        f'{GROUP_TIE_STRIDE_PX}px)}}',
        '.tail-prefix-token{anchor-name:--tail-prefix-token-anchor;'
        'width:calc(var(--best-winner-5)*1px)}',
        *(f'.tail-score-carrier-{group}{{'
          f'anchor-name:--tail-score-anchor-{group}}}'
          f'.tail-token-carrier-{group}{{'
          f'anchor-name:--tail-token-anchor-{group}}}'
          for group in range(GROUPS)),
        '.tail-score-max{position-anchor:--tail-prefix-score-anchor;'
        'anchor-name:--tail-score-max-anchor;'
        f'width:max({",".join(score_anchors)})}}',
        '.tail-score-reader{position-anchor:--tail-score-max-anchor;'
        'width:anchor-size(--tail-score-max-anchor width);'
        'container:tail-score-read/inline-size}',
        '@container tail-score-read (width >= 0px){.tail-score-result{'
        f'--tail-merged-bucket:round(down,100cqi/{SCORE_STRIDE_PX}px,1);'
        f'--tail-winning-group:calc({GROUPS} - round(nearest,'
        f'mod(100cqi,{SCORE_STRIDE_PX}px)/{GROUP_TIE_STRIDE_PX}px,1));'
        'display:block}}',
        '.tail-prefix-token-source{position-anchor:--tail-prefix-token-anchor;'
        'anchor-name:--tail-prefix-token-source-anchor;'
        'width:calc(anchor-size(--tail-prefix-token-anchor width) * '
        '(1 - clamp(0,abs(var(--tail-winning-group) - '
        'round(down,var(--best-winner-5)/256,1)),1)))}',
        token_rules,
        '.tail-token-max{position-anchor:--tail-prefix-token-source-anchor;'
        'anchor-name:--tail-token-max-anchor;'
        f'width:max({",".join(token_anchors)})}}',
        '.tail-token-reader{position-anchor:--tail-token-max-anchor;'
        'width:anchor-size(--tail-token-max-anchor width);'
        'container:tail-token-read/inline-size}',
        '@container tail-token-read (width >= 0px){.tail-final-result{'
        '--tail-final-winner:round(nearest,100cqi/1px,1);'
        'display:block;width:calc(var(--tail-final-winner)*1px)}}',
    ))


def render_tail_css() -> str:
    registrations = [
        # Keep the source page's unrelated default radio fixture from waking a
        # large tail during cold parse. The harness sets the declared positive
        # allowance before every measured evaluation.
        registration("tail-allowance", -100_000),
        registration("tail-merged-bucket"),
        registration("tail-winning-group"),
        registration("tail-final-winner"),
    ]
    for group in range(GROUPS):
        registrations.extend((
            registration(f"tail-bucket-{group}"),
            registration(f"tail-local-{group}"),
            registration(f"tail-winner-{group}"),
        ))
    fixed = (
        'body{anchor-scope:all}'
        '.parallel-tail,.tail-gate,.tail-fine-stage,.tail-fine-reader,'
        '.tail-fine-result,.tail-score-carrier,.tail-token-carrier,'
        '.tail-prefix-score,.tail-prefix-token,.tail-score-max,'
        '.tail-score-reader,.tail-score-result,.tail-token-source,'
        '.tail-token-max,.tail-token-reader,.tail-final-result{'
        'position:fixed;left:0;top:-30000px;height:1px}'
        '.tail-gate{width:0;container-type:inline-size}'
        '.tail-fine-stage{display:none;top:-29000px}'
        '.tail-fine-reader{width:0;top:-28000px}'
        '.tail-score-carrier,.tail-token-carrier,.tail-token-source{width:0}'
    )
    return (
        "".join(registrations)
        + fixed
        + "".join(branch_css(group) for group in range(GROUPS))
        + merge_css()
    )


def compute_fixture_data() -> tuple[dict[str, object], dict[str, object]]:
    saved = np.load(STATES)
    all_hidden = np.asarray(saved["hidden"], dtype=np.float64)
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    # Read the normalized denominator from the fine-head reference, which is
    # the shared source of truth for both exact stages and the tail.
    fine_reference = json.loads(FINE_REFERENCE.read_text())
    input_range = float(fine_reference["inputRange"])
    inside = np.max(np.abs(all_hidden), axis=1) <= input_range
    corpus_indices = np.flatnonzero(inside)
    hidden = all_hidden[inside]

    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(
        tensors.tensor("wte.weight")[: head.VOCABULARY], dtype=np.float64
    )
    row_scales = np.max(np.abs(weights), axis=1) / head.WEIGHT_MAX
    row_scales[row_scales == 0] = 1.0
    coarse_weights = np.rint(weights / row_scales[:, None]) * row_scales[:, None]
    error_norms = np.linalg.norm(weights - coarse_weights, axis=1)
    fine_scale = float(fine_reference["weightScale"])
    fine_codes = np.rint(weights / fine_scale).astype(np.int16)
    fine_weights = fine_codes.astype(np.float64) * fine_scale

    coarse_upper = (
        hidden @ coarse_weights.T
        + np.linalg.norm(hidden, axis=1)[:, None] * error_norms
    )
    fine_scores = hidden @ fine_weights.T
    dense_scores = hidden @ weights.T
    floors = np.floor(np.min(fine_scores, axis=1)).astype(int) - 1
    upper_buckets = np.floor(
        (coarse_upper - floors[:, None]) * head.SCORE_SCALE
    ).astype(int) + 1
    fine_buckets = np.rint(
        (fine_scores - floors[:, None]) * head.SCORE_SCALE
    ).astype(int)

    group_upper = np.full((len(hidden), GROUPS), -1, dtype=int)
    group_fine_winners = np.empty((len(hidden), GROUPS), dtype=int)
    group_fine_buckets = np.empty((len(hidden), GROUPS), dtype=int)
    for group in range(GROUPS):
        start = group * head.GROUP_SIZE
        stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
        group_upper[:, group] = np.max(upper_buckets[:, start:stop], axis=1)
        local = np.argmax(fine_buckets[:, start:stop], axis=1)
        winners = start + local
        group_fine_winners[:, group] = winners
        group_fine_buckets[:, group] = fine_buckets[
            np.arange(len(hidden)), winners
        ]
    order = np.argsort(-group_upper, axis=1, kind="stable")

    def fixture_oracle(position: int, allowance: int, kind: str) -> dict[str, object]:
        groups = order[position, :PREFIX_GROUPS].astype(int)
        winners = group_fine_winners[position, groups]
        buckets = group_fine_buckets[position, groups]
        best_winners: list[int] = []
        best_buckets: list[int] = []
        done: list[bool] = []
        best_winner = -1
        best_bucket = -1
        for stage, (winner, bucket) in enumerate(zip(winners, buckets, strict=True)):
            winner = int(winner)
            bucket = int(bucket)
            if bucket > best_bucket or (
                bucket == best_bucket and (best_winner < 0 or winner < best_winner)
            ):
                best_winner, best_bucket = winner, bucket
            best_winners.append(best_winner)
            best_buckets.append(best_bucket)
            next_group = int(order[position, stage + 1])
            done.append(best_bucket - int(group_upper[position, next_group]) > allowance)
        first_done = next((stage for stage, value in enumerate(done) if value), None)
        visited = set(map(int, groups))
        candidates = [
            group for group in range(GROUPS)
            if group not in visited
            and int(group_upper[position, group]) >= best_bucket - allowance
        ]
        active_winners = [int(group_fine_winners[position, group]) for group in candidates]
        active_buckets = [int(group_fine_buckets[position, group]) for group in candidates]
        merge = [(best_bucket, best_winner, best_winner // head.GROUP_SIZE)] + [
            (bucket, winner, group)
            for group, winner, bucket in zip(
                candidates, active_winners, active_buckets, strict=True
            )
        ]
        merged_bucket, merged_winner, merged_group = min(
            merge, key=lambda value: (-value[0], value[1])
        )
        target_winner = int(np.argmax(fine_scores[position]))
        dense_winner = int(np.argmax(dense_scores[position]))
        fallback = first_done is None
        if fallback and merged_winner != target_winner:
            raise RuntimeError(
                f"parallel closure lost target at corpus state {corpus_indices[position]}"
            )
        if not fallback and candidates:
            raise RuntimeError("certified fixture unexpectedly has tail candidates")
        current_range_fixture = kind != "forced-parallel-stress"
        coarse_allowance = (
            CURRENT_COARSE_ALLOWANCE if current_range_fixture else allowance // 2
        )
        fine_allowance = (
            CURRENT_FINE_ALLOWANCE if current_range_fixture else allowance - allowance // 2
        )
        boundary_guard = allowance - coarse_allowance - fine_allowance
        return {
            "kind": kind,
            "corpusIndex": int(corpus_indices[position]),
            "hiddenVector": hidden[position].tolist(),
            "scoreFloor": int(floors[position]),
            "coarseAllowanceBuckets": coarse_allowance,
            "fineAllowanceBuckets": fine_allowance,
            "browserBoundaryGuardBuckets": boundary_guard,
            "totalAllowanceBuckets": allowance,
            "strictStop": True,
            "prefixGroups": groups.tolist(),
            "prefixFineWinners": winners.tolist(),
            "prefixFineBuckets": buckets.tolist(),
            "prefixBestWinners": best_winners,
            "prefixBestBuckets": best_buckets,
            "prefixDone": done,
            "firstDoneZeroBased": first_done,
            "fallbackExpected": fallback,
            "candidateGroups": candidates,
            "candidateFineWinners": active_winners,
            "candidateFineBuckets": active_buckets,
            "mergedGroup": merged_group,
            "mergedBucket": merged_bucket,
            "mergedWinner": merged_winner,
            "targetWinner": target_winner,
            "denseWinner": dense_winner,
            "targetMatchesDense": target_winner == dense_winner,
        }

    current_oracles = [
        fixture_oracle(position, CURRENT_TOTAL_ALLOWANCE, "screen")
        for position in range(len(hidden))
    ]
    easy = [oracle for oracle in current_oracles if not oracle["fallbackExpected"]]
    hard = [oracle for oracle in current_oracles if oracle["fallbackExpected"]]
    if not easy or not hard:
        raise RuntimeError("expected natural easy and hard fixtures in current range")
    easiest = min(easy, key=lambda value: int(value["firstDoneZeroBased"]))

    stress_oracles = [
        fixture_oracle(position, STRESS_TOTAL_ALLOWANCE, "forced-parallel-stress")
        for position in range(len(hidden))
    ]
    stress = max(
        (oracle for oracle in stress_oracles if oracle["fallbackExpected"]),
        key=lambda value: len(value["candidateGroups"]),
    )
    guarded_hard = []
    for oracle in hard:
        position = int(np.flatnonzero(corpus_indices == oracle["corpusIndex"])[0])
        guarded_hard.append(fixture_oracle(
            position,
            CURRENT_TOTAL_ALLOWANCE + BROWSER_BOUNDARY_GUARD,
            "current-range-hard-plus-one-browser-bucket-guard",
        ))

    chosen: list[dict[str, object]] = []
    for oracle in (easiest, *guarded_hard, stress):
        if oracle["corpusIndex"] not in {item["corpusIndex"] for item in chosen}:
            chosen.append(oracle)

    max_geometry = max(
        int(oracle["mergedBucket"]) * SCORE_STRIDE_PX
        + (GROUPS - int(oracle["mergedGroup"])) * GROUP_TIE_STRIDE_PX
        for oracle in chosen
    )
    if max_geometry >= CHROME_LAYOUT_LIMIT_PX:
        raise RuntimeError("selected score/group geometry exceeds Chrome's layout limit")
    metadata = {
        "corpusStates": int(len(all_hidden)),
        "statesInsideCurrentRange": int(np.sum(inside)),
        "currentInputRange": input_range,
        "naturalEasyStates": len(easy),
        "naturalHardStates": len(hard),
        "currentAllowances": {
            "coarseBuckets": CURRENT_COARSE_ALLOWANCE,
            "fineBuckets": CURRENT_FINE_ALLOWANCE,
            "strictStopGapBuckets": CURRENT_TOTAL_ALLOWANCE,
        },
        "browserBoundaryGuardBucketsOnNaturalHardFixtures": BROWSER_BOUNDARY_GUARD,
        "stressTotalAllowanceBuckets": STRESS_TOTAL_ALLOWANCE,
        "maxFixtureMergeGeometryPixels": max_geometry,
    }
    return {"selected": chosen}, metadata


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    candidates = candidate_markup(html)
    marker = '<output id="remaining-result-6" class="remaining-result-6"></output>'
    if html.count(marker) != 1:
        raise RuntimeError("sixth remaining-result insertion point missing")
    html = html.replace(
        marker,
        '<output id="remaining-result-6" class="remaining-result-6">'
        + tail_markup(candidates)
        + '</output>',
        1,
    ).replace(
        "Certified int10 6-stage unrolled cascade",
        "Certified int10 six-stage plus parallel uncertainty tail",
        1,
    )

    css = (SOURCE / "index.css").read_text()
    for stage in range(PREFIX_GROUPS):
        old = (
            f"--done-{stage}:clamp(0,sign(var(--certificate-gap-{stage}) - "
            "49) + 1,1)"
        )
        new = (
            f"--done-{stage}:clamp(0,sign(var(--certificate-gap-{stage}) - "
            "var(--tail-allowance)),1)"
        )
        if css.count(old) != 1:
            raise RuntimeError(f"stage {stage} stop expression missing")
        css = css.replace(old, new, 1)
    css += render_tail_css() + "\n"

    fixtures, metadata = compute_fixture_data()
    source_reference = json.loads((SOURCE / "reference.json").read_text())
    reference = {
        **source_reference,
        "backend": "certified-int10-six-stage-gated-plus-parallel-tail",
        "source": SOURCE_NAME,
        "prefixExactGroups": PREFIX_GROUPS,
        "fallback": "constant-depth-parallel-uncertainty-closure",
        "fallbackGroupBranches": GROUPS,
        "scoreGeometryPixelsPerBucket": SCORE_STRIDE_PX,
        "groupTiePixelsPerGroup": GROUP_TIE_STRIDE_PX,
        "chromeLayoutLimitPixels": CHROME_LAYOUT_LIMIT_PX,
        "fixtureSelection": metadata,
        "parallelTailFixtures": fixtures,
    }
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "index.css").write_text(css)
    reference["htmlBytes"] = (OUTPUT / "index.html").stat().st_size
    reference["cssBytes"] = (OUTPUT / "index.css").stat().st_size
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "htmlBytes": reference["htmlBytes"],
        "cssBytes": reference["cssBytes"],
        "branches": GROUPS,
        "fixtureCorpusIndices": [
            fixture["corpusIndex"] for fixture in fixtures["selected"]
        ],
        "fixtureKinds": [fixture["kind"] for fixture in fixtures["selected"]],
        "candidateGroupCounts": [
            len(fixture["candidateGroups"]) for fixture in fixtures["selected"]
        ],
        **metadata,
    }, indent=2))


if __name__ == "__main__":
    main()
