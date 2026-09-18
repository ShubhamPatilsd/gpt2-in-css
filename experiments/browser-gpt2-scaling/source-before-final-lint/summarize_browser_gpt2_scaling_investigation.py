#!/usr/bin/env python3
"""Summarize saved scaling experiments without launching or modifying a browser.

Only the Python standard library is needed. Independent browser runs, rather
than repeated updates within one process, are the unit of replication. Invalid
or incomplete runs are listed but do not supply speedup estimates. The JSON
retains per-position/layer statistics that should not be collapsed into a token
throughput claim.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "experiments/browser-gpt2-scaling"
GENERATED_HASHES = {"attention.css", "index.html", "style.css"}
KINDS = ("append", "query-only", "query+layer-switch")


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def maximum(values):
    values = [v for v in values if v is not None]
    return max(values) if values else None


def span(values):
    values = [v for v in values if v is not None]
    return [min(values), max(values)] if values else None


def text_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def number(value, digits=1):
    return "—" if value is None else f"{value:.{digits}f}"


def extent(values):
    return "—" if values is None else f"{number(values[0])}–{number(values[1])}"


def table(headers, rows):
    return "\n".join([
        "| " + " | ".join(map(text_cell, headers)) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(map(text_cell, row)) + " |" for row in rows],
    ])


def source_revision(report):
    hashes = {k: v for k, v in report.get("sourceHashes", {}).items()
              if Path(k).name not in GENERATED_HASHES}
    if not hashes:
        return "unrecorded", {}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return digest[:12], hashes


def sample_stats(samples):
    def counter(name):
        return [r.get("rendererDelta", {}).get(name) for r in samples]
    def duration(name):
        values = counter(name)
        return mean([v * 1000 if v is not None else None for v in values])
    return {
        "sampleCount": len(samples),
        "medianMilliseconds": median([r.get("milliseconds") for r in samples]),
        "meanStyleMilliseconds": duration("RecalcStyleDuration"),
        "meanLayoutMilliseconds": duration("LayoutDuration"),
        "meanRendererTaskMilliseconds": duration("TaskDuration"),
        "meanDevToolsCommandMilliseconds": duration("DevToolsCommandDuration"),
        "meanStyleCount": mean(counter("RecalcStyleCount")),
        "meanLayoutCount": mean(counter("LayoutCount")),
        "maximumRmse": maximum([r.get("error", {}).get("rmse") for r in samples]),
        "maximumAbsoluteError": maximum([r.get("error", {}).get("maximum") for r in samples]),
        "minimumFiniteCoordinates": min((r.get("error", {}).get("finite", 0)
                                          for r in samples), default=None),
    }


def read_run(path, root):
    report = json.loads(path.read_text())
    revision, sources = source_revision(report)
    samples = report.get("samples", [])
    layers = report["layers"]
    query_count = sum(r.get("kind") in KINDS[1:] for r in samples)
    # Older files omit the requested update count; infer it only for a completed
    # successful run. A failed run's observed count is not its intended design.
    requested = report.get("queryUpdates")
    if requested is None and report.get("passed") is True and query_count % layers == 0:
        requested = query_count // layers
    state = "passed" if report.get("passed") is True else (
        "failed" if report.get("passed") is False or "exception" in report else "incomplete")
    if state == "passed" and (not samples or any(r.get("passed") is not True for r in samples)):
        state = "inconsistent-pass-flag"
    expected_samples = layers * (report["positions"] + requested) if requested is not None else None
    if state == "passed" and expected_samples != len(samples):
        state = "inconsistent-pass-flag"
    browser = report.get("browser", {})
    warm = samples[1:]
    by_position = defaultdict(list)
    position_updates = defaultdict(list)
    for row in warm:
        by_position[(row.get("kind"), row.get("position"), row.get("layer"))].append(row)
        position_updates[(row.get("kind"), row.get("position"))].append(row)
    return {
        "path": path.relative_to(root).as_posix(),
        "name": path.parent.name,
        "resultSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "variant": report["variant"], "options": report.get("options", {}),
        "capacity": report["capacity"], "positions": report["positions"],
        "layers": layers, "repeat": report["repeat"], "queryUpdates": requested,
        "expectedSampleCount": expected_samples,
        "observedQuerySamples": query_count, "status": state,
        "exception": report.get("exception"), "failurePhase": report.get("failurePhase"),
        "sourceRevision": revision,
        "sourceHashes": sources, "generatedSourceHashes": {
            k: v for k, v in report.get("sourceHashes", {}).items() if Path(k).name in GENERATED_HASHES},
        "browserProduct": browser.get("product", "unrecorded"),
        "browserRevision": browser.get("revision", "unrecorded"),
        "browserArguments": report.get("browserArguments", []),
        "environment": {k: report.get(k) for k in ("pythonVersion", "platform", "packages", "fixtureSeed")},
        "externalWritesAfterNavigation": report.get("externalWritesAfterNavigation"),
        "sampledPeak": report.get("sampledPeak", {}),
        "domCounters": report.get("domCounters", {}),
        "layoutObjects": report.get("rendererFinal", {}).get("LayoutObjects"),
        "allSampleStatistics": sample_stats(samples),
        "append": sample_stats([r for r in warm if r.get("kind") == "append"]),
        "query-only": sample_stats([r for r in warm if r.get("kind") == "query-only"]),
        "query+layer-switch": sample_stats([r for r in warm if r.get("kind") == "query+layer-switch"]),
        "byPositionLayer": [{"kind": k[0], "position": k[1], "layer": k[2],
                             **sample_stats(v)} for k, v in sorted(by_position.items())],
        "byPosition": [{"kind": k[0], "position": k[1], **sample_stats(v)}
                       for k, v in sorted(position_updates.items())],
        "tracePresent": (path.parent / "trace.json").exists(),
        "traceComplete": report.get("traceComplete"),
        "traceRequested": report.get("traceRequested"),
        "traceKind": report.get("traceKind"),
        "tracePassed": report.get("tracePassed"),
        "traceValidation": report.get("traceValidation"),
    }


def configuration(run):
    return (run["capacity"], run["positions"], run["layers"], run["queryUpdates"],
            run["sourceRevision"], run["browserProduct"], run["browserRevision"],
            json.dumps(run["browserArguments"], sort_keys=True))


def summarize_group(runs):
    first = runs[0]
    valid = [r for r in runs if r["status"] == "passed"]
    result = {k: first[k] for k in (
        "variant", "options", "capacity", "positions", "layers", "queryUpdates",
        "sourceRevision", "browserProduct", "browserRevision", "browserArguments")}
    result.update({"runCount": len(runs), "passingRunCount": len(valid),
                   "repeatIds": [r["repeat"] for r in runs],
                   "paths": [r["path"] for r in runs],
                   "maximumRmse": maximum([r["allSampleStatistics"]["maximumRmse"] for r in runs]),
                   "maximumAbsoluteError": maximum([r["allSampleStatistics"]["maximumAbsoluteError"] for r in runs]),
                   "peakRendererMiBRange": span([r["sampledPeak"].get("rendererRssMiB") for r in valid]),
                   "peakBrowserTreeMiBRange": span([r["sampledPeak"].get("browserTreeRssMiB") for r in valid]),
                   "nodesRange": span([r["domCounters"].get("nodes") for r in valid]),
                   "layoutObjectsRange": span([r.get("layoutObjects") for r in valid])})
    for kind in KINDS:
        result[kind] = {"samplesPerRun": [r[kind]["sampleCount"] for r in valid]}
        for key in ("medianMilliseconds", "meanStyleMilliseconds", "meanLayoutMilliseconds",
                    "meanRendererTaskMilliseconds", "meanDevToolsCommandMilliseconds",
                    "meanStyleCount", "meanLayoutCount"):
            values = [r[kind][key] for r in valid]
            result[kind][key] = median(values)
            result[kind][key + "Range"] = span(values)
    position_rows = defaultdict(list)
    for run in valid:
        for row in run["byPosition"]:
            if row["kind"] == "append":
                position_rows[row["position"]].append(row)
    result["appendByPosition"] = []
    for position, rows in sorted(position_rows.items()):
        result["appendByPosition"].append({
            "position": position, "runCount": len(rows),
            "samplesPerRun": [r["sampleCount"] for r in rows],
            "medianMilliseconds": median([r["medianMilliseconds"] for r in rows]),
            "medianMillisecondsRange": span([r["medianMilliseconds"] for r in rows]),
            "meanStyleMilliseconds": median([r["meanStyleMilliseconds"] for r in rows]),
            "meanLayoutMilliseconds": median([r["meanLayoutMilliseconds"] for r in rows]),
        })
    return result


def comparisons(runs):
    # Pair only like-for-like designs and repeat IDs. In particular, code changes
    # and a different number of query updates cannot silently become a control.
    controls = {(configuration(r), r["repeat"]): r for r in runs
                if r["variant"] == "baseline" and r["status"] == "passed"}
    grouped = defaultdict(list)
    for run in runs:
        if run["variant"] == "baseline" or run["status"] != "passed":
            continue
        control = controls.get((configuration(run), run["repeat"]))
        if control is None:
            continue
        for kind in KINDS:
            a, b = run[kind]["medianMilliseconds"], control[kind]["medianMilliseconds"]
            if a is not None and b:
                grouped[(configuration(run), run["variant"], kind)].append({
                    "repeat": run["repeat"], "variantPath": run["path"],
                    "baselinePath": control["path"], "wallTimeRatio": a / b,
                    "wallTimeReductionPercent": (1 - a / b) * 100})
    result = []
    for (config, variant, kind), pairs in sorted(grouped.items(), key=lambda x: str(x[0])):
        result.append({"capacity": config[0], "positions": config[1], "layers": config[2],
                       "queryUpdates": config[3], "sourceRevision": config[4],
                       "variant": variant, "kind": kind, "pairCount": len(pairs),
                       "medianWallTimeReductionPercent": median([p["wallTimeReductionPercent"] for p in pairs]),
                       "wallTimeReductionPercentRange": span([p["wallTimeReductionPercent"] for p in pairs]),
                       "pairs": pairs})
    return result


def read_locality(path, root):
    report = json.loads(path.read_text())
    revision, hashes = source_revision(report)
    errors = [report.get("initialError", {}), *report.get("initialHeadErrors", []),
              *report.get("unrelatedHeadErrors", []),
              *[r.get("error", {}) for r in report.get("samples", [])],
              *[e for r in report.get("samples", []) for e in r.get("unrelatedHeadErrors", [])]]
    return {
        "path": path.relative_to(root).as_posix(),
        "resultSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        **{k: report.get(k) for k in ("heads", "slots", "spectatorsPerHead", "mode", "repeat", "passed", "exception")},
        "sourceRevision": revision, "sourceHashes": hashes,
        "browserProduct": report.get("browser", {}).get("product", "unrecorded"),
        "sampledPeakRendererMiB": report.get("sampledPeakRendererMiB"),
        "domCounters": report.get("domCounters", {}),
        "statistics": sample_stats(report.get("samples", [])),
        "maximumRmse": maximum([e.get("rmse") for e in errors]),
        "maximumAbsoluteError": maximum([e.get("maximum") for e in errors]),
        "unrelatedMaximumOutputChange": maximum([r.get("unrelatedMaximumOutputChange") for r in report.get("samples", [])]),
    }


def read_locality_trace(path, root):
    report = json.loads(path.read_text())
    revision, hashes = source_revision(report)
    return {
        "path": path.relative_to(root).as_posix(),
        "resultSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        **{k: report.get(k) for k in ("heads", "slots", "spectatorsPerHead", "mode", "passed", "exception", "traceComplete", "error", "unrelatedMaximumOutputChange")},
        "sourceRevision": revision, "sourceHashes": hashes,
        "updateLayoutTreeElementCounts": [e.get("args", {}).get("elementCount") for e in report.get("updateLayoutTreeEvents", [])],
        "layoutDirtyObjectCounts": [e.get("args", {}).get("beginData", {}).get("dirtyObjects") for e in report.get("layoutEvents", [])],
        "layoutTotalObjectCounts": [e.get("args", {}).get("beginData", {}).get("totalObjects") for e in report.get("layoutEvents", [])],
    }


def read_native_commit(path, root):
    report = json.loads(path.read_text())
    revision, hashes = source_revision(report)
    commits = report.get("commits", [])
    return {
        "path": path.relative_to(root).as_posix(),
        "resultSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sourceRevision": revision, "sourceHashes": hashes,
        "scope": report.get("scope"), "passed": report.get("passed"),
        "completed": report.get("completed"), "exception": report.get("exception"),
        "browserProduct": report.get("browser", {}).get("product", "unrecorded"),
        "externalWritesAfterNavigation": report.get("externalWritesAfterNavigation"),
        "observeAfterSeconds": report.get("observeAfterSeconds"),
        "completedBeforeFirstComputedStyleRead": report.get("completedBeforeFirstComputedStyleRead"),
        "commitCount": len(commits), "passingCommitCount": sum(c.get("passed") is True for c in commits),
        "maximumInputRmse": maximum([c.get("inputError", {}).get("rmse") for c in commits]),
        "maximumOutputRmse": maximum([c.get("outputError", {}).get("rmse") for c in commits]),
        "maximumOutputAbsoluteError": maximum([c.get("outputError", {}).get("maximum") for c in commits]),
        "maximumPoisonRmse": maximum([c.get("poisonError", {}).get("rmse") for c in commits]),
        "commits": commits,
        "unrelatedError": report.get("unrelatedError"),
        "unrelatedObservedValidSamples": report.get("unrelatedObservedValidSamples"),
        "unrelatedMaximumObservedOutputChange": report.get("unrelatedMaximumObservedOutputChange"),
    }


def read_archived_failure(path, root):
    report = json.loads(path.read_text())
    revision, hashes = source_revision(report)
    return {
        "path": path.relative_to(root).as_posix(),
        "resultSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sourceRevision": revision, "sourceHashes": hashes,
        "scope": report.get("scope"), "passed": report.get("passed"),
        "exception": report.get("exception"), "failurePhase": report.get("failurePhase"),
        "sampleCount": len(report.get("samples", [])),
        "replacementResult": (path.parent / "results.json").relative_to(root).as_posix()
                             if (path.parent / "results.json").exists() else None,
    }


def collect(root):
    runs, locality, locality_traces, native_commits, archived_failures, unreadable = [], [], [], [], [], []
    for folder, destination, reader in (("runs", runs, read_run), ("locality", locality, read_locality),
                                        ("native-local-commits", native_commits, read_native_commit)):
        for path in sorted((root / folder).glob("*/results.json")):
            try:
                if folder == "locality" and path.parent.name.startswith("trace-"):
                    locality_traces.append(read_locality_trace(path, root))
                else:
                    destination.append(reader(path, root))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                unreadable.append({"path": path.relative_to(root).as_posix(), "exception": str(exc)})
    for path in sorted(root.rglob("*failure*.json")):
        try:
            archived_failures.append(read_archived_failure(path, root))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            unreadable.append({"path": path.relative_to(root).as_posix(), "exception": str(exc)})
    groups = defaultdict(list)
    for run in runs:
        groups[(configuration(run), run["variant"], json.dumps(run["options"], sort_keys=True))].append(run)
    revisions = {}
    for run in [*runs, *locality, *locality_traces, *native_commits, *archived_failures]:
        revisions[run["sourceRevision"]] = run["sourceHashes"]
    figure_path = root / "plots/scaling-investigation.png"
    figure = {"path": figure_path.relative_to(root).as_posix(),
              "sha256": hashlib.sha256(figure_path.read_bytes()).hexdigest(),
              "dataPath": "plots/scaling-data.json", "manifestPath": "plots/render-manifest.json"} if figure_path.exists() else None
    return {
        "schemaVersion": 1,
        "scope": "Externally driven attention component and separate structural-locality diagnostic; no autonomous throughput inference",
        "aggregation": "Median of per-process medians for wall time; median of per-process mean renderer metrics; ranges across independent processes; no confidence interval",
        "firstSamplePolicy": "Exclude only the first append sample of each attention process. Initial visits to later layers remain included. Locality initial settling is separate from its timed updates.",
        "comparisonPolicy": "Match capacity, populated positions, layers, query update count, recorded source hashes, browser version/arguments and repeat ID; only complete passing runs contribute timing estimates",
        "runs": runs,
        "groups": [summarize_group(v) for _, v in sorted(groups.items(), key=lambda x: str(x[0]))],
        "pairedComparisons": comparisons(runs), "localityRuns": locality, "localityTraces": locality_traces,
        "nativeCommitRuns": native_commits, "archivedFailedAttempts": archived_failures,
        "figure": figure,
        "sourceRevisions": revisions, "unreadableFiles": unreadable,
        "inventory": {"attentionRuns": len(runs), "passingAttentionRuns": sum(r["status"] == "passed" for r in runs),
                      "localityRuns": len(locality), "passingLocalityRuns": sum(r["passed"] is True for r in locality),
                      "localityTraces": len(locality_traces), "passingLocalityTraces": sum(r["passed"] is True for r in locality_traces),
                      "nativeCommitRuns": len(native_commits), "passingNativeCommitRuns": sum(r["passed"] is True for r in native_commits),
                      "nativeCommits": sum(r["commitCount"] for r in native_commits),
                      "passingNativeCommits": sum(r["passingCommitCount"] for r in native_commits),
                      "archivedFailedAttempts": len(archived_failures),
                      "unreadableFiles": len(unreadable)},
    }


def render(summary):
    inventory = summary["inventory"]
    lines = ["# Saved scaling measurements", "",
        "Generated by `python3 tools/summarize_browser_gpt2_scaling_investigation.py`. "
        "This report uses saved files only. Rerun after new browser measurements finish. "
        "Every source result and its SHA-256 are listed in [investigation.json](investigation.json).", "",
        "The [architecture review](ARCHITECTURE.md) covers the production graph and remaining "
        "design work. [Native pipeline experiments](native-report.md) report integration evidence "
        "separately from the attention and locality measurements below. "
        "The [locality report](locality-report.md) interprets the independent head-ownership curves.", "",
        f"Snapshot: **{inventory['passingAttentionRuns']}/{inventory['attentionRuns']} passing attention cases**; "
        f"**{inventory['passingLocalityRuns']}/{inventory['localityRuns']} passing locality cases**; "
        f"**{inventory['passingLocalityTraces']}/{inventory['localityTraces']} passing locality traces**; "
        f"**{inventory['passingNativeCommitRuns']}/{inventory['nativeCommitRuns']} passing native-commit cases** "
        f"({inventory['passingNativeCommits']}/{inventory['nativeCommits']} commits); "
        f"**{inventory['archivedFailedAttempts']} separately preserved failed attempts**; "
        f"{inventory['unreadableFiles']} unreadable files.", "",
        "## What the numbers mean", "",
        "These attention runs supply QKV, position, layer and generation controls externally through CDP. "
        "The browser retains KV and computes attention without page JavaScript. They omit embedding, "
        "QKV/output projection, MLP, vocabulary scoring and autonomous scheduling. Milliseconds below "
        "are per component update, never per generated token.", "",
        "Capacity is allocated cache slots; populated positions are how far the run appends before "
        "query probes. Each append summary mixes positions 2 through that final position for one "
        "layer. For multiple layers it also includes the initial visits to layers after layer 0. "
        "Query probes use the final populated position. An early-prefix append average is not a "
        "full-context latency. The per-position/layer JSON preserves this distinction.", "",
        "Wall values are medians of independent process medians. Renderer values are medians of "
        "per-process means. Wall ranges show process medians, not individual-update extremes. "
        "Repeated updates inside one browser process are not independent repetitions. With one "
        "or two processes, these are descriptive ranges rather than confidence intervals.", "",
        "Configuration pass counts and archived failed-attempt counts are distinct: a successful "
        "retry does not turn its earlier failure into a passing attempt. Native pipeline runs "
        "remain in the separate native report rather than this inventory. "
        "Only complete passing runs contribute aggregate timings and baseline comparisons. All "
        "failures and incomplete files remain in the inventory below. Correctness uses a deterministic "
        "synthetic fixture and a 768-coordinate reference, RMSE < 0.005; maximum error is retained. "
        "It does not establish full-model quality or behavior on other prompts.", "",
        "Wall time includes writing a complete inline style attribute, two computed-style reads per "
        "settling poll, and at least three 25 ms sleeps. Those reads can force browser work. Renderer "
        "style/layout totals help distinguish work reduction from polling and protocol cost, but "
        "are not pure isolated algorithm timings. RSS is a 0.5 s sampled process sum and can miss "
        "short peaks; it is not macOS physical footprint, and sums can double-count shared memory.", "",
        "`query-only` means only 64 query numbers change numerically for a **single selected layer**, "
        "while K/V and position stay fixed. The harness still rewrites all input declarations and "
        "advances the global generation marker. With multiple layers, these rows also switch the "
        "active layer and expose that layer's K/V: interpret them as **query plus layer switch**. "
        "They do not establish head-local invalidation in the production graph.", "",
        "## Attention cases, separated by design and recorded revision", ""]
    if summary.get("figure"):
        figure = summary["figure"]
        at = lines.index("## Attention cases, separated by design and recorded revision")
        lines[at:at] = ["## Scaling figure", "",
                       f"![Matched full-capacity attention append curves and separate structural-locality style-time curve]({figure['path']})", "",
                       "The panels show different component workloads and metrics. Lines are medians; "
                       "bands/error bars are ranges across two independent processes. "
                       f"[PNG]({figure['path']}), [SVG](plots/scaling-investigation.svg), "
                       f"[source data and input hashes]({figure['dataPath']}), "
                       f"[render manifest]({figure['manifestPath']}).", ""]
    configs = defaultdict(list)
    for group in summary["groups"]:
        configs[configuration(group)].append(group)
    for config, groups in sorted(configs.items(), key=lambda x: str(x[0])):
        capacity, positions, layers, updates, revision, product, _, _ = config
        lines.extend([f"### Capacity {capacity}; populated {positions}; layers {layers}; query updates/layer {updates}; source `{revision}`", "",
                      f"Browser: `{product}`. Population is {positions}/{capacity} slots. "
                      + ("Query rows include layer selection changes." if layers > 1 else "Query rows retain the same active layer."), ""])
        for kind in KINDS:
            if not any(g[kind]["samplesPerRun"] and any(g[kind]["samplesPerRun"]) for g in groups):
                continue
            lines.extend([f"**{kind}**", ""])
            rows = []
            for group in sorted(groups, key=lambda g: (g["variant"] != "baseline", g["variant"])):
                stats = group[kind]
                rows.append([group["variant"], f"{group['passingRunCount']}/{group['runCount']}",
                             ", ".join(map(str, group["repeatIds"])),
                             ", ".join(map(str, stats["samplesPerRun"])),
                             number(stats["medianMilliseconds"]), extent(stats["medianMillisecondsRange"]),
                             number(stats["meanStyleMilliseconds"]), number(stats["meanLayoutMilliseconds"]),
                             number(stats["meanRendererTaskMilliseconds"]),
                             extent(group["peakRendererMiBRange"]),
                             number(group["maximumRmse"], 6)])
            lines.extend([table(["Variant", "Pass/runs", "Repeats", "Updates/run", "Wall ms", "Wall range ms", "Style ms", "Layout ms", "Task ms", "Peak renderer MiB", "Worst RMSE"], rows), ""])
        pairs = [p for p in summary["pairedComparisons"] if
                 (p["capacity"], p["positions"], p["layers"], p["queryUpdates"], p["sourceRevision"]) == config[:5]]
        if pairs:
            lines.extend(["Matched baseline comparisons: positive reduction means less wall time; negative means slower. "
                          "Pairs use the same repeat ID and recorded source revision. No significance test is implied.", "",
                          table(["Variant", "Update", "Pairs", "Median reduction %", "Pair range %"],
                                [[p["variant"], p["kind"], p["pairCount"], number(p["medianWallTimeReductionPercent"]), extent(p["wallTimeReductionPercentRange"])] for p in pairs]), ""])
        checkpoints = {2, 4, 8, 16, 32, positions}
        curve_rows = []
        for group in sorted(groups, key=lambda g: (g["variant"] != "baseline", g["variant"])):
            for row in group["appendByPosition"]:
                if row["position"] in checkpoints:
                    curve_rows.append([group["variant"], row["position"], row["runCount"],
                                       ", ".join(map(str, row["samplesPerRun"])), number(row["medianMilliseconds"]),
                                       extent(row["medianMillisecondsRange"]), number(row["meanStyleMilliseconds"]),
                                       number(row["meanLayoutMilliseconds"])])
        if curve_rows:
            lines.extend(["**Append checkpoints within this fixed-capacity run**", "",
                          "These rows keep population fixed rather than mixing the growing prefix. "
                          "For multiple layers, wall time is the per-process median across that "
                          "position's layer updates, then the median across processes; renderer "
                          "values are the corresponding process means. They are still per-layer "
                          "component updates, not token latency. Every position and individual "
                          "layer is retained in JSON.", "",
                          table(["Variant", "Populated position", "Runs", "Layer updates/run", "Wall ms", "Wall range ms", "Style ms", "Layout ms"], curve_rows), ""])
    lines.extend(["## Exact runs and correctness", "",
        table(["Saved result", "Status", "Observed/planned samples", "Worst RMSE", "Maximum abs. error", "External writes", "Exception"],
              [[f"[{r['name']}]({r['path']})", r["status"], f"{r['allSampleStatistics']['sampleCount']}/{r['expectedSampleCount'] if r['expectedSampleCount'] is not None else '?'}",
                number(r["allSampleStatistics"]["maximumRmse"], 6),
                number(r["allSampleStatistics"]["maximumAbsoluteError"], 6),
                r["externalWritesAfterNavigation"], r["exception"] or "—"] for r in summary["runs"]]), ""])
    attention_traces = [r for r in summary["runs"] if r["traceRequested"] or r["tracePresent"] or r["traceKind"]]
    if attention_traces:
        lines.extend(["**Separate attention traces**", "",
                      "Timed-sample status and diagnostic trace status are distinct. The trace is a "
                      "same-selected-layer query mutation after the last timed sample; it does not "
                      "trace a layer switch. Missing validation/completion stays unknown. No trace "
                      "duration enters the timing estimates.", "",
                      table(["Run", "Requested", "Complete", "Trace passed", "RMSE", "Operation"],
                            [[f"[{r['name']}]({r['path']})", r["traceRequested"], r["traceComplete"], r["tracePassed"],
                              number((r["traceValidation"] or {}).get("rmse"), 6), r["traceKind"] or "unrecorded"] for r in attention_traces]), ""])
    lines.extend(["## Structural locality diagnostic", "",
        "This is a separate prototype: K/V are immutable fixture inputs, QK uses real font metrics, "
        "and softmax/weighted V use CSS arithmetic. It compares a body mutation with a mutation "
        "inside head 0 on otherwise equivalent pages. Extra spectator elements are synthetic "
        "unrelated storage, not useful neural computation. Passing here supports a locality "
        "mechanism; it does not validate native KV storage or the complete production head barrier.", ""])
    if summary["localityRuns"]:
        lines.extend([table(["Run", "Heads", "Slots/head", "Spectators/head", "Mode", "Pass", "Wall ms", "Style ms", "Layout ms", "Peak MiB", "Worst RMSE"],
            [[f"[{Path(r['path']).parent.name}]({r['path']})", r["heads"], r["slots"], r["spectatorsPerHead"], r["mode"], r["passed"],
              number(r["statistics"]["medianMilliseconds"]), number(r["statistics"]["meanStyleMilliseconds"]),
              number(r["statistics"]["meanLayoutMilliseconds"]), number(r["sampledPeakRendererMiB"]), number(r["maximumRmse"], 6)] for r in summary["localityRuns"]]), ""])
    else:
        lines.extend(["No completed locality result files existed when this report was generated.", ""])
    if summary["localityTraces"]:
        lines.extend(["**Separate diagnostic traces**", "",
                      "Each row is one separately traced mutation. Element counts are reported per "
                      "`UpdateLayoutTree` event; they are not unique nodes across events and must not "
                      "be added into an affected-node total. Layout dirty/total object counts likewise "
                      "describe each event. Traced timings are excluded from the timing tables.", "",
                      table(["Trace", "Heads", "Spectators/head", "Pass/complete", "Style event element counts", "Layout dirty objects", "Layout total objects", "Unrelated output change"],
                            [[f"[{Path(r['path']).parent.name}]({r['path']})", r["heads"], r["spectatorsPerHead"],
                              f"{r['passed']}/{r['traceComplete']}", ", ".join(map(str, r["updateLayoutTreeElementCounts"])),
                              ", ".join(map(str, r["layoutDirtyObjectCounts"])), ", ".join(map(str, r["layoutTotalObjectCounts"])),
                              number(r["unrelatedMaximumOutputChange"], 7)] for r in summary["localityTraces"]]), ""])
    if summary["nativeCommitRuns"]:
        lines.extend(["## Native local input commits: separate mechanism evidence", "",
                      "These cases use two 64-coordinate attention heads, eight static K/V positions, "
                      "a reusable local query register and an A → B → A capture sequence. The upstream "
                      "source is poisoned after capture; retained input/output and opposite signed "
                      "source/held tags are audited. They do not write a native KV cache, select "
                      "layers, join twelve heads or generate tokens. Their errors and elapsed "
                      "observations are never pooled with the attention timing experiments.", "",
                      "The delayed-observation cases test progress before observation. The stronger "
                      "DOM marker check records completion before the first computed-style read. "
                      "A missing marker field means that check was not recorded, not that it failed. "
                      "Observed unchanged-output differences cover only the samples actually read; "
                      "one observed valid sample cannot establish continuous invariance during "
                      "the unobserved interval. See [native local commits](native-local-commits.md).", "",
                      table(["Case", "Pass/complete", "Passing commits", "External writes", "Observe after s", "Done before first style read", "Worst output RMSE", "Worst output abs. error", "Observed head-1 samples"],
                            [[f"[{Path(r['path']).parent.name}]({r['path']})", f"{r['passed']}/{r['completed']}",
                              f"{r['passingCommitCount']}/{r['commitCount']}", r["externalWritesAfterNavigation"],
                              r["observeAfterSeconds"], r["completedBeforeFirstComputedStyleRead"] if r["completedBeforeFirstComputedStyleRead"] is not None else "unrecorded",
                              number(r["maximumOutputRmse"], 8), number(r["maximumOutputAbsoluteError"], 8), r["unrelatedObservedValidSamples"]]
                             for r in summary["nativeCommitRuns"]]), ""])
    if summary["archivedFailedAttempts"]:
        lines.extend(["## Separately preserved failed attempts", "",
                      "These files retain attempts that were followed by a distinct successful "
                      "result for the same configuration. They contribute no performance samples. "
                      "They are counted separately from the current per-configuration results.", "",
                      table(["Archived attempt", "Samples", "Exception", "Subsequent configuration result"],
                            [[f"[{r['path']}]({r['path']})", r["sampleCount"], r["exception"] or "unrecorded",
                              f"[result]({r['replacementResult']})" if r["replacementResult"] else "—"]
                             for r in summary["archivedFailedAttempts"]]), ""])
    lines.extend(["## Recorded source revisions", "",
        "The grouping key hashes recorded source hashes (excluding generated CSS/HTML). A different "
        "revision is kept separate even when the change might be unrelated to one variant. The "
        "recorded hashes are not a complete build manifest: helper compilers, imported measurement "
        "code and font assets may be absent. A matching key therefore means matching recorded "
        "sources, not proof that every dependency was byte-for-byte identical.", ""])
    for revision, hashes in sorted(summary["sourceRevisions"].items()):
        lines.extend([f"**`{revision}`**", ""])
        lines.extend([table(["Source", "SHA-256"], [[name, f"`{digest}`"] for name, digest in sorted(hashes.items())]) if hashes else "No source hashes recorded.", ""])
    lines.extend(["## Interpretation limits and next evidence", "",
        "- Selective non-inheriting cache fields still traverse a shared spine. Explicit forwarding can "
        "cost more than it saves; a slower `fields` case is a valid negative result, not an implementation "
        "to silently discard. `combined` includes that cost; `lean` omits it.",
        "- Hiding empty glyphs reduces rendering of unpopulated slots, while their DOM/CSS still exist. "
        "At full occupancy, every slot is active. Early-prefix gains cannot be extrapolated to a full cache.",
        "- Width reuse should be assessed separately when K/V stay fixed, when a slot is appended, and "
        "when layer selection replaces the active V. A component improvement is not an end-to-end gain.",
        "- `timelines` changes visibility scope of attention score timelines; it does not implement "
        "a new local stage-version protocol or independent all-head completion barrier.",
        "- `materialize` stops forwarding raw QKV after their last intended consumer. It does not "
        "remove a geometry bridge or fuse transformer operators. Deeper fusion is still separate work.",
        "- Style counts count recalculation events, not elements invalidated. A claim that update cost "
        "is constant as unrelated state grows needs the locality curve and, ideally, affected-element "
        "trace counts. Inclusive nested trace durations cannot be summed as wall time.",
        "- Native multi-layer feedback and full-model runs are required before promoting a variant. "
        "These tables alone cannot explain the previous 52-minute autonomous run or establish its fix.", "",
        "See [methodological-review.md](methodological-review.md) for the code review and proposed controls.", ""])
    if summary["unreadableFiles"]:
        lines.extend(["## Unreadable or concurrently changing files", "",
                      table(["Path", "Error"], [[r["path"], r["exception"]] for r in summary["unreadableFiles"]]), ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT)
    args = parser.parse_args()
    root = args.root.resolve()
    summary = collect(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "investigation.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    (root / "MEASUREMENTS.md").write_text(render(summary))
    print(json.dumps(summary["inventory"], sort_keys=True))


if __name__ == "__main__":
    main()
