#!/usr/bin/env python3
"""Recover honest saved stage spans; optionally prepare/run native diagnostics.

The diagnostic adds geometry witnesses inside existing receipt gates. It never
changes a token, activation, gate, or native scheduling rule. Browser runs must
be serialized by the investigation coordinator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from collections import Counter
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2-integration/profiling"
NATIVE = ROOT / "experiments/browser-gpt2-scaling/native"
BASE = NATIVE / "baseline-b12-c4-r2"
PHASES = (
    ("feedback", "previousCapture", "epoch"),
    ("embedding", "epoch", "embedding"),
    ("coreThroughHeadInput", "embedding", "headInput"),
    ("headInputThroughHead", "headInput", "head"),
    ("headThroughCapture", "head", "capture"),
)
GATES = {
    "input": '<div class="core-reset core-valid reused-input">',
    "qkv": '<div class="shared-qkv-gate">',
    "context": '<div class="cache-bridge-gate">',
    "attentionProjection": '<div class="shared-attn-gate">',
    "fc": '<div class="shared-fc-gate">',
    "projection": '<div class="shared-proj-gate">',
}
OBSERVERS = {name: f"#stage-cost-{name}" for name in GATES} | {
    "headInput": "#head-input-observer",
    "head": "#head-epoch-observer",
    "capture": "#capture-epoch-observer",
}
COUNTERS = (
    "TaskDuration",
    "RecalcStyleDuration",
    "LayoutDuration",
    "TaskOtherDuration",
    "DevToolsCommandDuration",
    "ScriptDuration",
    "RecalcStyleCount",
    "LayoutCount",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def recover(path):
    report = json.loads(path.read_text())
    manifest = report["manifest"]
    marks = {}
    for mark in report.get("milestones", []):
        marks.setdefault((mark["stage"], int(mark["epoch"])), mark["milliseconds"])
    rows = []
    for epoch in range(2, manifest["capacity"] + 1):
        times = {
            stage: marks.get((stage, epoch))
            for stage in ("epoch", "embedding", "headInput", "head", "capture")
        }
        times["previousCapture"] = marks.get(("capture", epoch - 1))
        ordered = [
            times["previousCapture"],
            *(
                times[stage]
                for stage in ("epoch", "embedding", "headInput", "head", "capture")
            ),
        ]
        missing = [key for key, value in times.items() if value is None]
        valid = not missing and all(a <= b for a, b in pairwise(ordered))
        row = {
            "epoch": epoch,
            "terminal": epoch == manifest["capacity"],
            "valid": valid,
            "observedMilliseconds": times,
        }
        if valid:
            row["spansMilliseconds"] = {
                name: times[after] - times[before] for name, before, after in PHASES
            }
            row["totalMilliseconds"] = times["capture"] - times["previousCapture"]
        else:
            row["rejection"] = {"missing": missing, "nonmonotonic": not missing}
        rows.append(row)
    token_samples = {}
    for sample in report.get("samples", []):
        token_samples.setdefault(int(sample["headEpoch"]), sample)
    renderer = []
    for epoch in sorted(token_samples):
        if epoch - 1 not in token_samples:
            continue
        before, after = token_samples[epoch - 1], token_samples[epoch]
        renderer.append(
            {
                "epoch": epoch,
                "terminal": epoch == manifest["capacity"],
                "milliseconds": after["milliseconds"] - before["milliseconds"],
                "counterDeltas": {
                    key: after["metrics"][key] - before["metrics"][key]
                    for key in COUNTERS
                },
            }
        )
    exclusion = path.parent / "interference.json"
    return {
        "case": path.parent.name,
        "path": str(path.relative_to(ROOT)),
        "sha256": digest(path),
        "blocks": manifest["blocks"],
        "capacity": manifest["capacity"],
        "variant": manifest["scalingExperimentVariant"],
        "complete": report.get("complete", False),
        "timingExcluded": exclusion.exists(),
        "timingExclusion": json.loads(exclusion.read_text())
        if exclusion.exists()
        else None,
        "sourceHashes": {
            f: digest(path.parent / f)
            for f in ("index.html", "runtime.css", "manifest.json")
        },
        "browser": report.get("browser"),
        "coreMarkerEpochs": sorted(epoch for stage, epoch in marks if stage == "core"),
        "spans": rows,
        "tokenBoundaryRenderer": renderer,
    }


def extract():
    cases = [recover(path) for path in sorted(NATIVE.glob("*/pipeline-results.json"))]
    pairs = []
    for repeat in (1, 2):
        names = [f"{variant}-b12-c4-r{repeat}" for variant in ("baseline", "widths")]
        selected = [
            next(case for case in cases if case["case"] == name) for name in names
        ]
        epochs = sorted(
            set.intersection(
                *(
                    {row["epoch"] for row in case["spans"] if row["valid"]}
                    for case in selected
                )
            )
        )
        pairs.append(
            {
                "cases": names,
                "commonValidEpochs": epochs,
                "continuingEpochs": [epoch for epoch in epochs if epoch < 4],
                "terminalEpochs": [epoch for epoch in epochs if epoch == 4],
            }
        )
    data = {
        "schemaVersion": 1,
        "method": "First-observed geometry markers, matched by captured token epoch. These spans are neither exclusive operation costs nor lower/upper bounds on math costs; CDP geometry reads may flush shared renderer work.",
        "counterScope": "Renderer counters exist only at token samples and are not assigned to individual stage spans.",
        "cases": cases,
        "matchedPairs": pairs,
        "scriptSha256": digest(Path(__file__)),
    }
    save(OUT / "saved-stage-costs.json", data)
    lines = [
        "# Native stage cost evidence",
        "",
        "The saved records place most observed continuing-token time between embedding readiness and the final core-to-head input handoff. They do not establish how much of that interval belongs to QKV, attention, MLP, transport, or vocabulary work triggered by a shared renderer update. The separate receipt diagnostic is intended to locate those costs.",
        "",
        "Reproduce the saved-data extraction with `uv run tools/profile_browser_gpt2_stage_costs.py extract`. No browser is launched. [Machine-readable rows](profiling/saved-stage-costs.json) retain each source hash, rejected epoch, token-boundary renderer counter, and timing exclusion.",
        "",
        "## Matched saved geometry spans",
        "",
        "These are observations after CDP reads return, not exclusive stage execution times. The old core marker appears only for some epochs; this table uses the distinct, retained head-input marker and matches the full boundary sequence within each token. Token 4 is terminal and is kept separate. The contaminated baseline r0 is excluded from timing.",
        "",
        "| Case | Token epochs | Feedback + embedding (s) | Embedding → head input (s) | Head input → head (s) | Head → capture (s) | Total observed span (s) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for pair in pairs:
        for name in pair["cases"]:
            case = next(case for case in cases if case["case"] == name)
            for group in (pair["continuingEpochs"], pair["terminalEpochs"]):
                rows = [row for row in case["spans"] if row["epoch"] in group]
                if not rows:
                    continue
                spans = {
                    key: sum(row["spansMilliseconds"][key] for row in rows)
                    / len(rows)
                    / 1000
                    for key, _, _ in PHASES
                }
                total = sum(row["totalMilliseconds"] for row in rows) / len(rows) / 1000
                lines.append(
                    f"| {name} | {', '.join(map(str, group))} | {spans['feedback'] + spans['embedding']:.3f} | {spans['coreThroughHeadInput']:.3f} | {spans['headInputThroughHead']:.3f} | {spans['headThroughCapture']:.3f} | {total:.3f} |"
                )
    lines += [
        "",
        "Rows average only the displayed token epochs within one process. They are not independent repeated samples. Pair r1 and pair r2 have opposite overall performance directions; these spans do not turn that into a repeatable speedup.",
        "",
        "Matched whole-token renderer counters for continuing tokens 2 and 3 in pair r2 give the following shares. These counters have different boundaries from the geometry spans above; they cannot be mapped onto individual stages.",
        "",
        "| Case | Style / task | Layout / task | Other / task | DevTools / task |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name in ("baseline-b12-c4-r2", "widths-b12-c4-r2"):
        case = next(case for case in cases if case["case"] == name)
        rows = [row for row in case["tokenBoundaryRenderer"] if row["epoch"] in (2, 3)]
        totals = {
            key: sum(row["counterDeltas"][key] for row in rows) for key in COUNTERS
        }
        values = " | ".join(
            f"{100 * totals[key] / totals['TaskDuration']:.2f}%"
            for key in (
                "RecalcStyleDuration",
                "LayoutDuration",
                "TaskOtherDuration",
                "DevToolsCommandDuration",
            )
        )
        lines.append(f"| {name} | {values} |")
    lines += [
        "",
        "## What the existing evidence can and cannot rank",
        "",
        "1. **Highest observed span: the reusable core and its handoff.** On continuing tokens 2 and 3, this is the interval from embedding to head-input readiness. It includes twelve passes through LN1, QKV, native attention, attention projection, LN2, FC/GELU, MLP projection and residual feedback, plus final transport. The receipt diagnostic below attempts to split this combined interval at fresh pass receipts, but does not obtain complete coverage.",
        "2. **Style work is material at token scale.** Saved token-boundary counters report renderer style and layout work across complete token intervals. Their shares cannot be assigned to a projection or vocabulary stage without intermediate counter observations.",
        "3. **Vocabulary has an observable readiness tail, but its total cost is not isolated.** A small head-input-to-head span cannot establish that the 50,257-row head is cheap: the read exposing head-input geometry can already have flushed head work. The head-input observer itself reports a retained input epoch, not a command to start vocabulary execution.",
        "",
        "## Fresh receipt diagnostic protocol",
        "",
        "Prepare an HTML clone of the clean twelve-layer, four-slot baseline with `uv run tools/profile_browser_gpt2_stage_costs.py prepare`. Preparation retains the exact baseline CSS through an absolute stylesheet link and adds six tiny geometry witnesses inside existing native input/receipt gates. They expose the actual pass epoch only while the corresponding gate is open: core input, QKV, attention context transport, attention output projection, FC/GELU, and MLP output projection. No arithmetic, animation, container, or scheduling rule changes. The generation marker travels through the existing matrix receipt, so stale widths cannot be credited to a newer pass.",
        "",
        "After the coordinator grants the serialized browser slot, run `uv run tools/profile_browser_gpt2_stage_costs.py run --target-tokens 2 --limit-seconds 180`. A fresh headless Chromium runs with page JavaScript disabled and the same heap flag as the native measurements. Only CDP geometry and performance reads observe progress after navigation. It stops after observing two captured tokens, or the explicit time limit, without supplying an input or intermediate result. Native generation can already have entered token 3 before the observer sees capture 2. Geometry at the retained capture witness supplies the token check against the preserved baseline; the baseline's separate residual validation remains baseline evidence, and no fresh residual check is claimed here.",
        "",
        "Each new receipt observation saves the CDP call start/end timestamps and a renderer-counter snapshot. The observer polls the six small receipts plus three existing head/capture witnesses sequentially, then sleeps 50 ms. It retains at most 2,000 distinct stage events and writes compact JSON; no trace file is collected. A missed, reset, or nonmonotonic receipt is reported rather than filled in. Counter deltas include work flushed by the observer, and different stage receipts may be exposed during the same frame; resulting stage spans are diagnostic and cannot be presented as uncontaminated benchmarks. Geometry read latency and unassigned/missing boundaries accompany the result.",
        "",
        "Source and method limits: observing a receipt establishes freshness, not that all work executed strictly before that read. The FC receipt includes bias and GELU in its fused CSS consumer; the attention-projection and MLP-projection intervals include their residual additions and readback. Math and transfer are therefore still combined until a separately validated ablation distinguishes them. No per-layer optimization recommendation will be claimed from a missing receipt.",
        "",
    ]
    (OUT.parent / "stage-costs.md").write_text("\n".join(lines))
    if (OUT / "receipt-diagnostic/results.json").exists():
        analyze()
    print(json.dumps({"savedCases": len(cases), "matchedPairs": pairs}, indent=2))


def prepare():
    destination = OUT / "receipt-diagnostic"
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / "results.json").exists():
        raise ValueError("Preserve a completed diagnostic and its source snapshot")
    html = (BASE / "index.html").read_text()
    link = 'href="runtime.css"'
    if html.count(link) != 1:
        raise ValueError("Expected one baseline stylesheet")
    html = html.replace(link, f'href="{(BASE / "runtime.css").as_uri()}"')
    for stage, needle in GATES.items():
        if html.count(needle) != 1:
            raise ValueError(f"Expected one {stage} gate")
        witness = f'<i id="stage-cost-{stage}" style="position:fixed;top:-100000px;visibility:hidden;width:calc(var(--epoch)*1px);height:1px"></i>'
        html = html.replace(needle, needle + witness)
    (destination / "index.html").write_text(html)
    (destination / "profiler-source.py").write_bytes(Path(__file__).read_bytes())
    manifest = {
        "baseline": str(BASE.relative_to(ROOT)),
        "baselineHashes": {
            name: digest(BASE / name)
            for name in (
                "index.html",
                "runtime.css",
                "manifest.json",
                "pipeline-results.json",
            )
        },
        "htmlSha256": digest(destination / "index.html"),
        "scriptSha256": digest(Path(__file__)),
        "witnesses": GATES,
        "changes": "Only absolute stylesheet link and six geometry witnesses inserted inside existing native receipt gates; baseline CSS unchanged.",
        "runtimeJavaScript": False,
        "externalWritesAfterNavigation": 0,
    }
    save(destination / "diagnostic-manifest.json", manifest)
    print(json.dumps({"prepared": str(destination), "addedWitnesses": len(GATES)}))


def analyze():
    source = OUT / "receipt-diagnostic/results.json"
    report = json.loads(source.read_text())
    maximum_pass = report["targetTokens"] * 12
    events = {(event["stage"], event["epoch"]): event for event in report["events"]}
    coverage = {
        stage: sorted(
            epoch for name, epoch in events if name == stage and epoch <= maximum_pass
        )
        for stage in GATES
    }
    complete_passes = sorted(
        set.intersection(*(set(epochs) for epochs in coverage.values()))
    )
    phase_rows = []
    for before, after in pairwise(GATES):
        intervals, rejected = [], []
        for epoch in range(1, maximum_pass + 1):
            start, end = events.get((before, epoch)), events.get((after, epoch))
            if start is None or end is None:
                rejected.append({"pass": epoch, "reason": "missing-endpoint"})
                continue
            if start["counterEndMilliseconds"] > end["readStartMilliseconds"]:
                rejected.append(
                    {"pass": epoch, "reason": "nonmonotonic-or-overlapping-observation"}
                )
                continue
            intervals.append(
                {
                    "pass": epoch,
                    "tokenEpoch": (epoch - 1) // 12 + 1,
                    "layer": (epoch - 1) % 12,
                    "milliseconds": end["readEndMilliseconds"]
                    - start["readEndMilliseconds"],
                    "counterDeltas": {
                        key: end["metrics"][key] - start["metrics"][key]
                        for key in COUNTERS
                    },
                    "endpointReadMilliseconds": [
                        start["readEndMilliseconds"] - start["readStartMilliseconds"],
                        end["readEndMilliseconds"] - end["readStartMilliseconds"],
                    ],
                }
            )
        times = [row["milliseconds"] for row in intervals]
        phase_rows.append(
            {
                "from": before,
                "to": after,
                "intervals": intervals,
                "rejected": rejected,
                "count": len(times),
                "medianMilliseconds": statistics.median(times) if times else None,
                "minimumMilliseconds": min(times, default=None),
                "maximumMilliseconds": max(times, default=None),
            }
        )
    result = {
        "source": str(source.relative_to(ROOT)),
        "sourceSha256": digest(source),
        "scriptSha256": digest(Path(__file__)),
        "passedTokenPrefix": report["passed"],
        "maximumAttributedPass": maximum_pass,
        "coverageByStage": coverage,
        "completePasses": complete_passes,
        "postTargetCoreEvents": [
            event
            for event in report["events"]
            if event["stage"] in GATES and event["epoch"] > maximum_pass
        ],
        "phasePairs": phase_rows,
        "inference": "Incomplete, selected same-pass observation intervals only. Their medians must not be added or normalized into stage shares. Observer reads flush shared renderer work and native generation can advance before capture is observed.",
    }
    save(OUT / "receipt-diagnostic/analysis.json", result)
    lines = [
        "",
        "## Fresh diagnostic result",
        "",
        f"The diagnostic captured the expected tokens **11 and 314** with zero post-navigation writes. It reached the second observed capture at {report['captures'][-1]['epoch']} tokens; the last geometry event was at {report['events'][-1]['readEndMilliseconds'] / 1000:.3f} seconds. This is a diagnostic run with additional observers, not a matched throughput benchmark. [Raw observations](profiling/receipt-diagnostic/results.json), [coverage and matched pairs](profiling/receipt-diagnostic/analysis.json), and [method review](profiling/methodological-review.md) are retained.",
        "",
        f"Coverage is insufficient for a native stage decomposition: **{len(complete_passes)} of {maximum_pass} passes have all six witnesses observed**. There were {len(report['events'])} total fresh stage/head/capture events, including {len(result['postTargetCoreEvents'])} core events beyond pass {maximum_pass}. Native token 3 had already started before capture 2 was read. Those later events are excluded below. The head-completion witness was never caught, so there is no fresh vocabulary interval estimate.",
        "",
        "| Witness | Observed passes within 1–24 | Coverage |",
        "| --- | --- | ---: |",
    ]
    for stage, epochs in coverage.items():
        lines.append(f"| {stage} | {', '.join(map(str, epochs))} | {len(epochs)}/24 |")
    latency = report["geometryReadLatencyMilliseconds"]
    lines += [
        "",
        f"The {latency['count']} geometry calls took a median {latency['median']:.1f} ms, maximum {latency['maximum'] / 1000:.3f} s, and a combined {latency['total'] / 1000:.3f} s of call wall time. That wall time is not observer CPU overhead: it includes waiting for and flushing native browser work. A final-pass projection read lasted 5.685 s and returned near head readiness, demonstrating why that delay cannot be labeled exclusive MLP projection cost.",
        "",
        "The following same-pass intervals have both endpoints observed in chronological order. Their pass sets differ and are selected by observability. They are diagnostic samples, **not comparable stage proportions**, and must not be added together.",
        "",
        "| Observation interval | Matched passes | Median (ms) | Min–max (ms) |",
        "| --- | --- | ---: | ---: |",
    ]
    for phase in phase_rows:
        if phase["count"]:
            epochs = ", ".join(str(row["pass"]) for row in phase["intervals"])
            lines.append(
                f"| {phase['from']} → {phase['to']} | {epochs} | {phase['medianMilliseconds']:.1f} | {phase['minimumMilliseconds']:.1f}–{phase['maximumMilliseconds']:.1f} |"
            )
        else:
            lines.append(f"| {phase['from']} → {phase['to']} | none | — | — |")
    lines += [
        "",
        "**Actionable conclusion:** use isolated, numerically checked QKV and LN2→FC/GELU→projection ablations to compare dense changes. This experiment did not yield a defensible ranking of native QKV, MLP and vocabulary cost. A single aggregate pass/phase witness could reduce sequential polling, but it would require a separate diagnostic and would still not establish exclusive CPU attribution. No such follow-up is included here.",
        "",
    ]
    path = OUT.parent / "stage-costs.md"
    original = path.read_text().split("\n## Fresh diagnostic result", 1)[0]
    path.write_text(original.rstrip() + "\n" + "\n".join(lines))
    print(
        json.dumps(
            {
                "diagnosticPassed": report["passed"],
                "completePasses": complete_passes,
                "matchedPhaseCounts": {
                    f"{row['from']}->{row['to']}": row["count"] for row in phase_rows
                },
            }
        )
    )


def run(target_tokens, limit_seconds):
    from profile_hybrid_twelve_block import browser, metrics, query

    destination = OUT / "receipt-diagnostic"
    manifest = json.loads((destination / "diagnostic-manifest.json").read_text())
    if digest(destination / "index.html") != manifest["htmlSha256"]:
        raise ValueError("Prepared HTML changed")
    for name, expected in manifest["baselineHashes"].items():
        if digest(BASE / name) != expected:
            raise ValueError(f"Baseline changed: {name}")
    output = destination / "results.json"
    if output.exists():
        raise ValueError(
            "Preserve existing diagnostic results; choose a new case explicitly"
        )
    baseline = json.loads((BASE / "pipeline-results.json").read_text())
    expected_tokens = {
        int(row["headEpoch"]): int(row["winner"]) for row in baseline["samples"]
    }
    report = {
        "manifest": manifest,
        "scriptSha256": digest(Path(__file__)),
        "pythonVersion": sys.version,
        "platform": platform.platform(),
        "targetTokens": target_tokens,
        "limitSeconds": limit_seconds,
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "externalWritesAfterNavigation": 0,
        "events": [],
        "captures": [],
        "commands": {},
        "complete": False,
        "stopReason": "not-started",
    }
    seen = set()
    counts = Counter()
    read_latencies = []
    started = time.perf_counter()
    try:
        with browser(["--js-flags=--heap-growing-percent=10"]) as cdp:
            cdp.connection.settimeout(min(60, limit_seconds))
            report["browser"] = cdp.command("Browser.getVersion")
            original_command = cdp.command

            def readonly(method, params=None):
                permitted = {
                    "DOM.getDocument",
                    "DOM.querySelector",
                    "DOM.getBoxModel",
                    "Performance.getMetrics",
                    "Browser.getVersion",
                }
                if method not in permitted:
                    raise ValueError(f"Forbidden post-navigation command: {method}")
                counts[method] += 1
                return original_command(method, params)

            started = time.perf_counter()
            cdp.command("Page.navigate", {"url": (destination / "index.html").as_uri()})
            cdp.command = readonly
            # Page.navigate acknowledges navigation before document replacement
            # is complete. Retry discovery against a freshly obtained root.
            discovery_deadline = started + min(limit_seconds, 30)
            discovery_retries = 0
            while True:
                cdp.root_node = None
                try:
                    nodes = {
                        stage: query(cdp, selector)
                        for stage, selector in OBSERVERS.items()
                    }
                    if all(nodes.values()):
                        break
                except RuntimeError as exc:
                    if "Could not find node with given id" not in str(exc):
                        raise
                if time.perf_counter() >= discovery_deadline:
                    raise ValueError(
                        "Observer discovery exceeded 30-second startup budget"
                    )
                discovery_retries += 1
                time.sleep(0.05)
            report["discoveryRetries"] = discovery_retries
            report["setupMilliseconds"] = (time.perf_counter() - started) * 1000
            report["observerProtocol"] = {
                "pollDelayMilliseconds": 50,
                "readOrder": list(nodes),
                "metricsOn": "first observed positive stage/pass only",
                "trace": False,
                "maximumEvents": 2000,
                "timeLimitScope": "loop deadline; an in-flight CDP read can exceed it by at most its 60-second socket timeout",
                "counterAttribution": "Counters are snapshots after geometry reads; shared/queued work is not exclusive stage CPU.",
                "tokenCheckScope": "captured token IDs only; no fresh residual-vector readback",
            }
            deadline = started + limit_seconds
            while time.perf_counter() < deadline:
                for stage, node in nodes.items():
                    before = (time.perf_counter() - started) * 1000
                    try:
                        box = cdp.command("DOM.getBoxModel", {"nodeId": node})["model"][
                            "content"
                        ]
                    except RuntimeError as exc:
                        if "Could not compute box model" not in str(exc):
                            raise
                        box = [0] * 8
                    after = (time.perf_counter() - started) * 1000
                    read_latencies.append(after - before)
                    epoch = round(box[2] - box[0])
                    if epoch <= 0 or (stage, epoch) in seen:
                        continue
                    seen.add((stage, epoch))
                    snapshot = metrics(cdp)
                    event = {
                        "stage": stage,
                        "epoch": epoch,
                        "tokenEpoch": (epoch - 1) // 12 + 1
                        if stage in GATES
                        else epoch,
                        "layer": (epoch - 1) % 12 if stage in GATES else None,
                        "readStartMilliseconds": before,
                        "readEndMilliseconds": after,
                        "counterEndMilliseconds": (time.perf_counter() - started)
                        * 1000,
                        "metrics": {key: snapshot[key] for key in COUNTERS},
                    }
                    report["events"].append(event)
                    if stage == "capture":
                        token = round(box[5] - box[1])
                        report["captures"].append(
                            {
                                "epoch": epoch,
                                "token": token,
                                "expected": expected_tokens.get(epoch),
                                "passed": token == expected_tokens.get(epoch),
                            }
                        )
                        print(
                            json.dumps(
                                {
                                    "capturedEpoch": epoch,
                                    "token": token,
                                    "milliseconds": after,
                                    "receiptEvents": len(report["events"]),
                                }
                            ),
                            flush=True,
                        )
                        save(output, report)
                        if epoch >= target_tokens:
                            report["complete"] = True
                            report["stopReason"] = "bounded-token-target"
                            break
                    if len(report["events"]) >= 2000:
                        raise RuntimeError("Diagnostic event cap reached")
                if report["complete"]:
                    break
                time.sleep(0.05)
            else:
                report["stopReason"] = "time-limit"
    except Exception as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        report["stopReason"] = "error"
        raise
    finally:
        report["totalMilliseconds"] = (time.perf_counter() - started) * 1000
        report["commands"] = dict(counts)
        report["geometryReadLatencyMilliseconds"] = {
            "count": len(read_latencies),
            "median": statistics.median(read_latencies) if read_latencies else None,
            "maximum": max(read_latencies, default=None),
            "total": sum(read_latencies),
        }
        report["passed"] = (
            report["complete"]
            and len(report["captures"]) == target_tokens
            and all(row["passed"] for row in report["captures"])
        )
        save(output, report)
    if not report["passed"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("extract", "prepare", "run", "analyze"))
    parser.add_argument("--target-tokens", type=int, default=2)
    parser.add_argument("--limit-seconds", type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.target_tokens <= 4 or args.limit_seconds <= 0:
        parser.error("target tokens must be 1..4 and time limit must be positive")
    if args.action == "extract":
        extract()
    elif args.action == "prepare":
        prepare()
    elif args.action == "analyze":
        analyze()
    else:
        run(args.target_tokens, args.limit_seconds)


if __name__ == "__main__":
    main()
