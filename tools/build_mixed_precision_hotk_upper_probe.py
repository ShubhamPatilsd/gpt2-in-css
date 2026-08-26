#!/usr/bin/env python3
"""Build only the offline-selected mixed-precision hot-K browser candidates."""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
import build_mixed_precision_hot2_upper_probe as hot2
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-mixed-precision-hotk-sweep"
OFFLINE = OUTPUT / "offline-results.json"
BASELINE = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated"
)
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
COARSE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-certified-upper-int10"
STAGES = 6
HOT_UPPER_ALLOWANCE_BUCKETS = 24
STOP_GAP_BUCKETS = 48
GROUPS = math.ceil(head.VOCABULARY / head.GROUP_SIZE)


def if_branches(hot_groups: tuple[int, ...], value: str, fallback: str) -> str:
    return "if(" + "".join(
        f"style(--group:{group}):{value};" for group in hot_groups
    ) + f"else:{fallback})"


def mixed_stage_css(stage: int, hot_groups: tuple[int, ...]) -> str:
    top = -92_000 + stage * 300
    gate = "display:contents;" if stage == 0 else (
        f"display:if(style(--done-{stage - 1}:1):none;else:contents);"
    )
    group_binding = "" if stage == 0 else f"--group:var(--remaining-group-{stage});"
    selected_group = "var(--group)" if stage == 0 else f"var(--remaining-group-{stage})"
    result_group = (
        "--search-root-group:var(--group);--selected-group-0:var(--group);"
        if stage == 0
        else (
            "--group:var(--search-root-group);"
            f"--selected-group-{stage}:var(--remaining-group-{stage});"
        )
    )
    if stage == 0:
        state = "--best-bucket-0:var(--fine-bucket-0);--best-winner-0:var(--fine-winner-0);"
    else:
        previous = stage - 1
        state = (
            f"--score-delta-{stage}:calc(var(--fine-bucket-{stage}) - "
            f"var(--best-bucket-{previous}));"
            f"--use-stage-{stage}:max(clamp(0,sign(var(--score-delta-{stage})),1),"
            f"calc((1 - abs(sign(var(--score-delta-{stage})))) * "
            f"clamp(0,sign(var(--best-winner-{previous}) - "
            f"var(--fine-winner-{stage})),1)));"
            f"--best-winner-{stage}:calc(var(--best-winner-{previous}) * "
            f"(1 - var(--use-stage-{stage})) + var(--fine-winner-{stage}) * "
            f"var(--use-stage-{stage}));"
            f"--best-bucket-{stage}:max(var(--best-bucket-{previous}),"
            f"var(--fine-bucket-{stage}));"
        )
    choice_width = "if(" + "".join(
        f"style(--group:{group}):anchor-size(--group-{group} width);"
        for group in hot_groups
    ) + f"else:anchor-size(--dynamic-fine-winner-{stage} width))"
    dynamic_display = if_branches(hot_groups, "none", "grid")
    return (
        f".mixed-stage-{stage}{{{gate}}}"
        f".dynamic-fine-stage-{stage}{{{group_binding}top:{top}px;"
        f"anchor-name:--dynamic-fine-winner-{stage};display:{dynamic_display}}}"
        f".mixed-choice-source-{stage}{{{group_binding}position:fixed;left:0;"
        f"top:{top + 100}px;height:1px;anchor-name:--mixed-winner-{stage};"
        f"width:{choice_width}}}"
        f".mixed-final-reader-{stage}{{position:fixed;left:0;top:{top + 200}px;"
        f"height:1px;position-anchor:--mixed-winner-{stage};"
        f"width:anchor-size(--mixed-winner-{stage} width);"
        f"container:mixed-fine-result-{stage}/inline-size}}"
        f"@container mixed-fine-result-{stage} (width >= 0px){{"
        f".mixed-fine-result-{stage}{{{result_group}"
        f"--fine-bucket-{stage}:round(down,(100cqi + .001px)/4px,1);"
        f"--fine-code-{stage}:calc(255 - "
        f"round(nearest,mod(100cqi + .001px,4px)/1px*64,1));"
        f"--fine-local-{stage}:var(--fine-code-{stage});"
        f"--fine-winner-{stage}:calc({selected_group}*256 + "
        f"var(--fine-local-{stage}));{state}display:block;"
        f"width:calc(var(--best-winner-{stage})*1px);height:1px}}}}"
    )


def hot_font_css(hot_groups: tuple[int, ...]) -> tuple[str, list[Path]]:
    first_line = (FINE / "index.css").read_text().split("\n", 1)[0]
    font_css = first_line.replace(
        'url("score-',
        'url("../../gpt2-hvar-grid-output-head-global16-twoplane/score-',
    )
    families = ",".join(
        f"Score{plane}{shard}" for shard in range(6) for plane in ("H", "L")
    )
    allowance_px = HOT_UPPER_ALLOWANCE_BUCKETS * head.SCORE_STRIDE_PX
    selectors = ",".join(
        f".group-wrapper:has(>.group-{group})" for group in hot_groups
    )
    return (
        font_css
        + f".mixed-hot-candidate{{font-family:{families};font-size:100px;"
        "width:calc-size(max-content,calc(round(nearest,"
        "(size - var(--base)*1px) * var(--factor) + var(--score-offset),4px) + "
        "var(--local-tie)/64*1px))}"
        + f"{selectors}{{width:calc-size(max-content,calc(round(down,size,4px) + "
        f"{allowance_px}px))}}",
        sorted(FINE.glob("score-*.woff2")),
    )


def page_html(
    hot_groups: tuple[int, ...], dynamic_candidates: str, static_candidates: list[str]
) -> str:
    hot2.HOT_GROUPS = hot_groups
    html = hot2.build_html(dynamic_candidates, static_candidates)
    # Candidate pages live one directory deeper than the retained hot-2 page.
    html = html.replace('href="../gpt2-', 'href="../../gpt2-')
    return html.replace(
        "Mixed-precision hot-two certified upper head",
        f"Mixed-precision hot-{len(hot_groups)} certified upper head",
    )


def build_candidate(
    k: int,
    baseline: dict[str, object],
    float_weights: np.ndarray,
    fine_weights: np.ndarray,
    dynamic_candidates: str,
    static_candidates: list[str],
    offline_row: dict[str, object],
    coarse_fonts: list[Path],
) -> dict[str, object]:
    hot_groups = tuple(range(k))
    hot2.HOT_GROUPS = hot_groups
    priorities = np.tile(
        np.arange(head.GROUP_SIZE - 1, -1, -1, dtype=np.int64), (k, 1)
    )
    contract, fixture_summary = hot2.fixture_contract(
        baseline, float_weights, fine_weights, priorities
    )
    if fixture_summary["finalExactWinners"] != fixture_summary["fixtures"]:
        raise RuntimeError(f"K={k} fixture contract lost an exact winner")

    directory = OUTPUT / f"k{k}"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.html").write_text(
        page_html(hot_groups, dynamic_candidates, static_candidates)
    )
    font_css, fine_fonts = hot_font_css(hot_groups)
    css = [
        font_css,
        hot2.registrations(),
        "*{box-sizing:border-box}html,body{margin:0;overflow:clip}",
    ]
    selected = ["selected-group-0"]
    for stage in range(1, STAGES + 1):
        css.append(hot2.precomputed.router_css(stage, GROUPS, selected))
        selected.append(f"selected-group-{stage}")
    css.extend(mixed_stage_css(stage, hot_groups) for stage in range(STAGES))
    topology = "".join(css) + "\n"
    (directory / "topology.css").write_text(topology)

    html = (directory / "index.html").read_text()
    checks = {
        "exactHotCandidateCount": len(
            re.findall(r'class="candidate mixed-hot-candidate"', html)
        ),
        "expectedExactHotCandidateCount": k * head.GROUP_SIZE,
        "allHotAnchorsReused": all(
            f"anchor-size(--group-{group} width)" in topology for group in hot_groups
        ),
        "allHotRoutesSuppressDynamicGrid": all(
            f"style(--group:{group}):none;" in topology for group in hot_groups
        ),
        "allowanceAfterGroupMaximum": all(
            f".group-wrapper:has(>.group-{group})" in topology for group in hot_groups
        ) and f"round(down,size,4px) + {HOT_UPPER_ALLOWANCE_BUCKETS * head.SCORE_STRIDE_PX}px" in topology,
        "standardExactTie": "var(--local-tie)/64*1px))}" in topology,
        "rowsAdded": 0,
    }
    if checks["exactHotCandidateCount"] != checks["expectedExactHotCandidateCount"]:
        raise RuntimeError(f"K={k} exact-row replacement count failed: {checks}")
    if not all(
        value for key, value in checks.items()
        if key not in {"exactHotCandidateCount", "expectedExactHotCandidateCount", "rowsAdded"}
    ):
        raise RuntimeError(f"K={k} static transport check failed: {checks}")

    reference = {
        "backend": f"mixed-rowwise-int10-global-int16-hot{k}-upper-six-stage",
        "k": k,
        "hotGroups": list(hot_groups),
        "control": BASELINE.name,
        "groups": GROUPS,
        "groupSize": head.GROUP_SIZE,
        "stages": STAGES,
        "hotUpperAllowanceBuckets": HOT_UPPER_ALLOWANCE_BUCKETS,
        "stopGapBuckets": STOP_GAP_BUCKETS,
        "upperRows": head.VOCABULARY,
        "upperRowsAdded": 0,
        "upperRowsReplacedWithGlobalInt16": k * head.GROUP_SIZE,
        "speculativeParallelFineRows": 0,
        "dynamicFineRowsPerActiveNonHotStage": head.GROUP_SIZE,
        "tieContract": "rounded 1/256 score bucket, then lower token ID",
        "offlineSweep": offline_row,
        "fixtureFeasibility": fixture_summary,
        "certifiedFixtures": contract,
        "staticTransportChecks": checks,
        "assets": {
            "coarseFontFiles": len(coarse_fonts),
            "coarseFontWoff2Bytes": sum(path.stat().st_size for path in coarse_fonts),
            "exactFontFiles": len(fine_fonts),
            "exactFontWoff2Bytes": sum(path.stat().st_size for path in fine_fonts),
            "fontsCopiedOrRebuilt": False,
        },
        "generatedBytes": {},
    }
    reference_path = directory / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    reference["generatedBytes"] = {
        name: (directory / name).stat().st_size
        for name in ("index.html", "topology.css", "reference.json")
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    return {
        "k": k,
        "directory": str(directory.relative_to(ROOT)),
        "hotGroups": list(hot_groups),
        "rowsAdded": 0,
        "rowsReplaced": k * head.GROUP_SIZE,
        "fixtureFinalExactWinners": fixture_summary["finalExactWinners"],
        "fixtureCount": fixture_summary["fixtures"],
        "generatedBytes": reference["generatedBytes"],
        "staticTransportChecks": checks,
    }


def main() -> None:
    started = time.perf_counter()
    if not OFFLINE.exists():
        raise FileNotFoundError("run analyze_mixed_precision_hotk_sweep.py first")
    offline = json.loads(OFFLINE.read_text())
    candidates = [int(k) for k in offline["pareto"]["browserCandidateK"]]
    if not candidates or any(k not in (1, 2, 4, 8, 16, 32) for k in candidates):
        raise RuntimeError(f"invalid offline-selected candidates: {candidates}")
    rows = {int(row["k"]): row for row in offline["policies"]["contiguousLow"]}
    baseline = json.loads((BASELINE / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    coarse_reference = json.loads((COARSE / "reference.json").read_text())
    if baseline["exactStages"] != STAGES or not baseline["stageGating"]:
        raise RuntimeError("baseline is not the gated exact six-stage control")
    if fine_reference["inputRange"] != coarse_reference["inputRange"]:
        raise RuntimeError("coarse and exact coordinate ranges differ")

    float_weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[: head.VOCABULARY],
        dtype=np.float64,
    )
    fine_scale = float(fine_reference["weightScale"])
    fine_weights = (
        np.rint(float_weights / fine_scale).astype(np.int16).astype(np.float64)
        * fine_scale
    )
    dynamic_candidates = hot2.dynamic_exact_candidates()
    static_candidates = hot2.exact_static_candidates()
    coarse_source = ROOT / "experiments" / coarse_reference["source"]
    coarse_fonts = sorted(coarse_source.glob("score-d*.woff2"))
    built = [
        build_candidate(
            k,
            baseline,
            float_weights,
            fine_weights,
            dynamic_candidates,
            static_candidates,
            rows[k],
            coarse_fonts,
        )
        for k in candidates
    ]
    manifest = {
        "status": "prepared-not-run",
        "browserLaunchedByBuilder": False,
        "candidateK": candidates,
        "controlDirectory": BASELINE.name,
        "pairedHarness": "tools/test_mixed_precision_hotk_upper_probe.mjs",
        "candidates": built,
        "buildSeconds": time.perf_counter() - started,
    }
    (OUTPUT / "browser-artifacts.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
