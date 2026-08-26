"""Summarize complete saved runs without changing the original demo report."""

import argparse
import itertools
import json
import statistics
from pathlib import Path


def summarize(directory, prefix=""):
    run = json.loads((directory / (prefix + "pipeline-results.json")).read_text())
    numerical_path = directory / (prefix + "numerical-results.json")
    numerical = (
        json.loads(numerical_path.read_text()) if numerical_path.exists() else {}
    )
    rows = {}
    for row in run["samples"]:
        epoch = int(float(row["headEpoch"] or 0))
        if epoch > 0:
            rows.setdefault(epoch, row)
    epochs = sorted(rows)
    intervals = [
        {
            "epoch": right,
            "seconds": (rows[right]["milliseconds"] - rows[left]["milliseconds"])
            / 1000,
        }
        for left, right in itertools.pairwise(epochs)
        if right == left + 1
    ]
    times = [row["seconds"] for row in intervals]
    result = {
        "directory": str(directory),
        "reportPrefix": prefix,
        "complete": run.get("complete", False),
        "manifest": run["manifest"],
        "browserArguments": run.get("browserArguments", []),
        "observedTokenEpochs": epochs,
        "totalSeconds": run.get("totalMilliseconds", 0) / 1000,
        "firstObservedSeconds": rows.get(1, {}).get("milliseconds", 0) / 1000,
        "warmIntervals": intervals,
        "warmMedianSeconds": statistics.median(times) if times else None,
        "warmMinimumSeconds": min(times) if times else None,
        "warmMaximumSeconds": max(times) if times else None,
        "sampledPeak": run.get("sampledPeak"),
        "runtimeJavaScript": run.get("runtimeJavaScript"),
        "harnessJavaScript": run.get("harnessJavaScript"),
        "externalWritesAfterNavigation": run.get("externalWritesAfterNavigation"),
    }
    if 1 in rows and "initialRunClickMilliseconds" in run:
        result["runToFirstSeconds"] = (
            rows[1]["milliseconds"] - run["initialRunClickMilliseconds"]
        ) / 1000
    if len(epochs) > 1:
        first, last = (rows[e]["metrics"] for e in (epochs[0], epochs[-1]))
        duration = last["TaskDuration"] - first["TaskDuration"]
        result["rendererWarmTaskPercentages"] = {
            key: 100 * (last[key] - first[key]) / duration
            for key in (
                "RecalcStyleDuration",
                "LayoutDuration",
                "TaskOtherDuration",
                "DevToolsCommandDuration",
                "ScriptDuration",
                "V8CompileDuration",
            )
            if key in first and key in last and duration > 0
        }
    marks = {
        (m["stage"], m["epoch"]): m["milliseconds"] / 1000
        for m in run.get("milestones", [])
    }
    captured = "capture" if run.get("retainedCaptureObserver") else "head"
    totals = {
        "handoff": 0.0,
        "embedding": 0.0,
        "coreAndKV": 0.0,
        "finalBridgeAndHead": 0.0,
    }
    usable, rejected = [], []
    for epoch in epochs[1:]:
        keys = (
            (captured, epoch - 1),
            ("epoch", epoch),
            ("embedding", epoch),
            ("core", epoch),
            (captured, epoch),
        )
        if not all(key in marks for key in keys):
            rejected.append(epoch)
            continue
        cuts = [marks[key] for key in keys]
        if any(b < a for a, b in itertools.pairwise(cuts)):
            rejected.append(epoch)
            continue
        usable.append(epoch)
        for key, (a, b) in zip(totals, itertools.pairwise(cuts)):
            totals[key] += b - a
    result["coarseMilestones"] = {
        "usableEpochs": usable,
        "missingOrNonmonotonicEpochs": rejected,
        "note": "Observed geometry boundaries, not exclusive operation timings; shared frames and observer delay overlap.",
        "percentages": {
            key: 100 * value / sum(totals.values()) for key, value in totals.items()
        }
        if usable
        else {},
    }
    for key in (
        "tokens",
        "text",
        "tokenAgreement",
        "originalFloatAgreement",
        "finalResidualError",
    ):
        if key in numerical:
            result[key] = numerical[key]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--report-prefix", default="")
    args = parser.parse_args()
    result = summarize(args.directory, args.report_prefix)
    path = args.directory / (args.report_prefix + "scaling-summary.json")
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
