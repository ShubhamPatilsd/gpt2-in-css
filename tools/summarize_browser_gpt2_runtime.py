"""Summarize saved complete-pipeline measurements, never isolated-stage sums."""

import itertools
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2"


def main():
    run = json.loads((OUT / "demo/pipeline-results.json").read_text())
    numerical = json.loads((OUT / "demo/numerical-results.json").read_text())
    actual = json.loads((OUT / "demo/verification-vectors.json").read_text())
    baseline = json.loads((OUT / "full-runtime/verification-vectors.json").read_text())
    assert run["complete"]
    samples = {}
    for row in run["samples"]:
        epoch = int(float(row["headEpoch"]))
        if epoch > 0:
            samples.setdefault(epoch, row)
    times = [samples[i]["milliseconds"] / 1000 for i in range(1, 9)]
    deltas = [b - a for a, b in itertools.pairwise(times)]
    marks = {
        (m["stage"], m["epoch"]): m["milliseconds"] / 1000 for m in run["milestones"]
    }
    phases = {
        "Handoff / observer boundary": 0.0,
        "Embedding handoff": 0.0,
        "12-block core + KV": 0.0,
        "Final bridge, norm and full head": 0.0,
    }
    for i in range(2, 9):
        cuts = [
            marks["head", i - 1],
            marks["epoch", i],
            marks["embedding", i],
            marks["core", i],
            marks["head", i],
        ]
        for name, a, b in zip(phases, cuts, cuts[1:]):
            assert b >= a
            phases[name] += b - a
    phase_total = sum(phases.values())
    current = {(c["layer"], c["slot"]): c["values"] for c in actual["caches"]}
    old = {(c["layer"], c["slot"]): c["values"] for c in baseline["caches"]}
    mismatches = sum(a != b for key in current for a, b in zip(current[key], old[key]))
    comparison = {
        "cacheSlots": len(current),
        "cacheCoordinates": sum(map(len, current.values())),
        "differingCoordinates": mismatches,
        "finalResidualIdentical": actual["finalResidual"] == baseline["finalResidual"],
        "finalHiddenIdentical": actual["finalHidden"] == baseline["finalHidden"],
    }
    first, last = samples[1]["metrics"], samples[8]["metrics"]
    task = last["TaskDuration"] - first["TaskDuration"]
    renderer = {
        name: 100 * (last[field] - first[field]) / task
        for name, field in [
            ("Style recalculation", "RecalcStyleDuration"),
            ("Layout", "LayoutDuration"),
            ("Other renderer tasks", "TaskOtherDuration"),
            ("CDP command handling", "DevToolsCommandDuration"),
        ]
    }
    summary = {
        "totalSeconds": run["totalMilliseconds"] / 1000,
        "firstObservedSeconds": times[0],
        "runToFirstSeconds": times[0] - run["initialRunClickMilliseconds"] / 1000,
        "medianFollowupSeconds": statistics.median(deltas),
        "minimumFollowupSeconds": min(deltas),
        "maximumFollowupSeconds": max(deltas),
        "followupSeconds": deltas,
        "coarseMilestonePercentages": {
            k: 100 * v / phase_total for k, v in phases.items()
        },
        "rendererWarmPercentages": renderer,
        "comparisonToNestedBaseline": comparison,
    }
    (OUT / "demo/timing-summary.json").write_text(json.dumps(summary, indent=2))
    total = summary["totalSeconds"]
    lines = [
        "# Complete Chromium pipeline results",
        "",
        "Measured September 16, 2026, on Apple M2 Pro / 16 GB RAM, Chrome 153.0.8010.48.",
        "Fresh headless Chromium profile, ordinary static HTTP delivery, scripts disabled.",
        "One initial native Run click; no further input mutations, stage scheduling, or intermediate-vector transfers.",
        "",
        "Scope: one selected prompt token, browser-owned prefill and K/V, all twelve blocks, full vocabulary selection, token feedback, and eight generated tokens.",
        "",
        "## Actual end-to-end times",
        "",
        "| Measurement | Seconds |",
        "| --- | ---: |",
        f"| Page navigation → first result observed | {times[0]:.3f} |",
        f"| Initial Run click → first result observed | {summary['runToFirstSeconds']:.3f} |",
        f"| Subsequent result interval, median | {summary['medianFollowupSeconds']:.3f} |",
        f"| Subsequent result interval, min–max | {min(deltas):.3f}–{max(deltas):.3f} |",
        f"| Page navigation → all eight tokens captured | {total:.3f} ({int(total // 60)} min {total % 60:.1f} s) |",
        "",
        "The follow-up intervals were: "
        + ", ".join(f"{v:.3f}" for v in deltas)
        + " seconds.",
        "These are complete recurrent intervals, not sums of separate matrix benchmarks. This is **not 13 seconds/token**.",
        "The initial click occurred after {:.3f} s of loading/initial layout. Page-level startup and native font readiness are included; disk caches were not globally flushed.".format(
            run["initialRunClickMilliseconds"] / 1000
        ),
        "",
        "## Where the warm interval goes",
        "",
        "| Observed boundary interval | Share |",
        "| --- | ---: |",
    ]
    lines += [
        f"| {name} | {100 * value / phase_total:.1f}% |"
        for name, value in phases.items()
    ]
    lines += [
        "",
        "These coarse native-geometry milestones span shared rendering frames. In particular, the handoff bucket includes observation/queue delay, and the final-head bucket cannot cleanly separate work performed in the same frame. Do not interpret them as an exclusive mathematical-operation profiler.",
        "",
        "Renderer counters across the seven warm intervals: "
        + ", ".join(f"{k} {v:.1f}%" for k, v in renderer.items())
        + ". Script execution and V8 compilation time were zero.",
        "",
        "## Optimizations retained and rejected",
        "",
        "- Retained a flat per-layer cache: only the active slot declares live sources. The four-state sequence had zero retention error; its three fresh-input comparisons were approximately 11–22% faster than the same states with a nested bank. This was a small screen, not a randomized multi-run benchmark.",
        "- Isolated the scorer from core scratch/cache inheritance, and delayed its initial layout until the first real hidden vector. Subsequent token feedback stays alive.",
        "- Replaced the fragile large-width fractional token decoder with an integer second pass and bounded 16-way reduction trees. All 50,257 candidates are scored; there is no shortlist or search timeout.",
        "- Rejected every-matrix and whole-block retirement. In the two-block screen they were much slower than keeping the live timelines.",
        "- The earlier full nested-cache run took 789.316 s. It used local-file delivery and a different readout harness, so the difference is an observed system-level comparison, not a clean isolated cache-speedup claim.",
        "",
        "## Correctness and limits",
        "",
        f"- Produced `{numerical['text']}`.",
        f"- {sum(numerical['tokenAgreement'])}/8 decisions matched the independent q9/q16 reference; {sum(numerical['originalFloatAgreement'])}/8 also matched the original floating-point checkpoint on the generated context.",
        f"- {comparison['cacheCoordinates']:,} K/V coordinates across {comparison['cacheSlots']} slots: {mismatches} differing CSS readbacks versus the completed nested-cache baseline. Final residual and normalized hidden readbacks are also identical.",
        f"- Final residual versus the continuous-activation q9 reference: RMSE {numerical['finalResidualError']['rmse']:.6f}, max error {numerical['finalResidualError']['maximum']:.6f}. The font/core path is therefore not advertised as exact float32 arithmetic.",
        "- Head-only screen: 38/38 difficult fixtures. Embedding lookup: 16/16 fixtures, including vocabulary/group boundaries.",
        "- Unobserved full-model progression passed: after the initial Run click, 180 seconds without DOM/style/layout observations produced two correct tokens. The harness is not required to advance the loop.",
        "- Native control fixtures passed pause/prompt locking, resume, form reset, and end-of-text stopping. A separate font-readiness fixture passed both available-font and deliberately blocked-font cases. These are focused control fixtures, not additional full-model continuations.",
        "- This is a bounded implementation, not broad held-out model certification. The planned 128-position / 16-continuation expansion has not been run; no further quantization is promoted on these results.",
        "- Context is eight positions, no eviction. Storage uses a 24-hour delayed-transition horizon. Prompt input is a fixed one-token picker, not arbitrary text tokenization.",
        "",
        "Raw evidence: `demo/pipeline-results.json`, `demo/timing-summary.json`, `demo/numerical-results.json`, `demo/verification-vectors.json`, `demo/screenshot.png`, `demo/unobserved-results.json`, `controls/results.json`, and `font-barrier-probe/results.json`.",
        "",
        "Remaining performance priority: reduce core animation/style propagation and native handoff cost. A faster head alone cannot remove the dominant core cost. Broader context, arbitrary text input, and stronger numerical coverage remain separate follow-ups.",
        "",
    ]
    (OUT / "RESULTS.md").write_text("\n".join(lines))
    print(summary, flush=True)


if __name__ == "__main__":
    main()
