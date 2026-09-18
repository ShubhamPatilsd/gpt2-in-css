#!/usr/bin/env python3
"""Rebuild summary.json from retained untraced runs and independent traces."""

import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent
runs = [json.loads(p.read_text()) for p in sorted(ROOT.glob("*-r*/results.json"))]
traces = [json.loads(p.read_text()) for p in sorted(ROOT.glob("trace-*/results.json"))]
summary = {
    "benchmarkCases": len(runs),
    "benchmarkMutations": sum(len(r["samples"]) for r in runs),
    "traceCases": len(traces),
    "allPassed": all(r["passed"] for r in runs + traces),
    "activeInputHashes": sorted({r["activeInputHash"] for r in runs}),
    "browserVersions": sorted({r["browser"]["product"] for r in runs + traces}),
    "unrelatedMaximumOutputChange": max(s["unrelatedMaximumOutputChange"] for r in runs for s in r["samples"]),
    "groups": [],
    "traces": [],
}
for spectators in sorted({r["spectatorsPerHead"] for r in runs}):
    for heads in sorted({r["heads"] for r in runs}):
        for mode in ("broadcast", "local"):
            selected = [r for r in runs if (r["spectatorsPerHead"], r["heads"], r["mode"]) == (spectators, heads, mode)]
            samples = [s for r in selected for s in r["samples"]]
            errors = [e for r in selected for e in r["initialHeadErrors"]]
            errors += [s["error"] for s in samples]
            errors += [e for s in samples for e in s["unrelatedHeadErrors"]]
            summary["groups"].append({
                "spectatorsPerHead": spectators, "heads": heads, "mode": mode,
                "runs": len(selected), "mutations": len(samples),
                "meanStyleMilliseconds": statistics.mean(s["rendererDelta"]["RecalcStyleDuration"] * 1000 for s in samples),
                "runMeanStyleMilliseconds": [r["meanStyleMilliseconds"] for r in selected],
                "meanLayoutMilliseconds": statistics.mean(s["rendererDelta"]["LayoutDuration"] * 1000 for s in samples),
                "medianWallMilliseconds": statistics.median(s["milliseconds"] for s in samples),
                "meanSampledPeakRendererMiB": statistics.mean(r["sampledPeakRendererMiB"] for r in selected),
                "allHeadMaximumError": max(e["maximum"] for e in errors),
                "allHeadMaximumRMSE": max(e["rmse"] for e in errors),
                "maxActiveOutputError": max(s["error"]["maximum"] for s in samples),
                "domNodes": [r["domCounters"]["nodes"] for r in selected],
            })
for trace in traces:
    summary["traces"].append({
        **{k: trace[k] for k in ("spectatorsPerHead", "heads", "mode", "passed")},
        "styleElementCounts": [e["args"].get("elementCount") for e in trace["updateLayoutTreeEvents"]],
        "layoutDirtyObjects": [e["args"]["beginData"].get("dirtyObjects") for e in trace["layoutEvents"]],
        "shapeTextCount": sum(e["count"] for e in trace["traceTotals"] if e["event"] == "InlineNode::ShapeTextIncludingFirstLine"),
    })
(ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({k: v for k, v in summary.items() if k not in ("groups", "traces")}, indent=2))
