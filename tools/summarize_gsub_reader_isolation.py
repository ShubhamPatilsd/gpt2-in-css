#!/usr/bin/env python3
"""Summarize independent browser repetitions; do not pool them as one run."""
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-reader-isolation"
data = json.loads((OUT / "results.json").read_text())
assert data.get("passed") is True and not data["smoke"]
summary = {"source": "results.json", "repetitions": data["repetitions"],
           "batch": data["batch"], "rows": [], "profiles": []}
for width in data["widths"]:
    for kind in ("sequential", "tree", "hvar", "precomputed-font", "precomputed-css", "direct-css"):
        selected = [t for t in data["timings"] if t["width"] == width and t["kind"] == kind]
        row = {"width": width, "kind": kind}
        if kind == "direct-css":
            values = [t["statistics"]["median"] for t in selected]
            assert len(values) == data["repetitions"]
            row.update(medianMilliseconds=median(values), runMedianRange=[min(values), max(values)], runMedians=values)
        else:
            runs = []
            for rep in range(data["repetitions"]):
                pair = {t["endpoint"]: t for t in selected if t["rep"] == rep}
                source, full = pair["source"], pair["full"]
                warmup = data["warmup"]
                deltas = [f-s for s, f in zip(source["rawMilliseconds"][warmup:], full["rawMilliseconds"][warmup:])]
                runs.append({"rep": rep, "sourceMedian": source["statistics"]["median"],
                             "fullMedian": full["statistics"]["median"], "pairedDeltaMedian": median(deltas)})
            row["runs"] = runs
            for key in ("sourceMedian", "fullMedian", "pairedDeltaMedian"):
                values = [r[key] for r in runs]
                row[key] = median(values)
                row[key+"Range"] = [min(values), max(values)]
        summary["rows"].append(row)
for profile in data["profiles"]:
    rounds = profile["rounds"]
    summary["profiles"].append({"kind": profile["kind"], "endpoint": profile["endpoint"],
        "elapsedPerBatchMs": profile["elapsedMilliseconds"]/rounds,
        "stylePerBatchMs": profile["metrics"]["RecalcStyleDuration"]*1000/rounds,
        "layoutPerBatchMs": profile["metrics"]["LayoutDuration"]*1000/rounds,
        "styleEvents": profile["metrics"]["RecalcStyleCount"], "layoutEvents": profile["metrics"]["LayoutCount"]})
(OUT / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
for row in summary["rows"]:
    if row["kind"] == "direct-css":
        print(row["width"], row["kind"], round(row["medianMilliseconds"], 3), row["runMedianRange"])
    else:
        print(row["width"], row["kind"], "source", round(row["sourceMedian"], 3), "full", round(row["fullMedian"], 3),
              "paired delta", round(row["pairedDeltaMedian"], 3), "delta range", row["pairedDeltaMedianRange"])
