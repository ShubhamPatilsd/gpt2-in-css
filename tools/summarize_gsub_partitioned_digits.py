#!/usr/bin/env python3
"""Summarize completed, exact-font-gated partitioned-digit experiments."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from statistics import median


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gates", type=Path, nargs="+", required=True)
    parser.add_argument("--timings", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    gates = [json.loads(p.read_text()) for p in args.gates]
    timings = [json.loads(p.read_text()) for p in args.timings]
    assert all(r.get("passed") is True for r in gates + timings), "Only complete passing reports can be summarized"
    accepted, gate_hashes = set(), {}
    for gate in gates:
        for row in gate["correctness"]:
            assert row["passed"] and row["mismatches"] == 0
            accepted.add((row["id"], row["n"], row["m"]))
        for key, value in gate["fontSha256"].items():
            assert key not in gate_hashes or gate_hashes[key] == value
            gate_hashes[key] = value
    groups = defaultdict(list)
    checked = 0
    for report in timings:
        for key, value in report["fontSha256"].items():
            assert gate_hashes[key] == value, f"Ungated font {key}"
        for row in report["timings"]:
            assert (row["id"], row["n"], row["m"]) in accepted
            assert row["mismatches"] == 0 and len(row["rawMilliseconds"]) == 25
            samples = row["rawMilliseconds"][5:]
            assert row["medianMilliseconds"] == sorted(samples)[10]
            assert row["checkedOutputs"] == 25 * row["outputs"]
            groups[(row["id"], row["n"], row["m"], row["outputs"])].append(row)
            checked += row["checkedOutputs"]
    summary = []
    for (identifier, n, m, outputs), rows in sorted(groups.items(), key=lambda pair: (pair[0][1:3], pair[0][0])):
        assert len(rows) == 3 and len({row["repetition"] for row in rows}) == 3
        assert len({row["seed"] for row in rows}) == 3
        medians = [row["medianMilliseconds"] for row in sorted(rows, key=lambda row: row["repetition"])]
        center = median(medians)
        summary.append({"id": identifier, "inputs": n, "outputsPerVector": m, "outputsPerBatch": outputs,
                        "runMediansMilliseconds": medians, "medianMilliseconds": center,
                        "minimumRunMedianMilliseconds": min(medians), "maximumRunMedianMilliseconds": max(medians),
                        "millisecondsPerOutput": center / outputs, "millisecondsPerVector": center / (outputs / m)})
    source_files = args.gates + args.timings
    result = {"scope": "Synthetic four-bit integer arithmetic. Repeated coefficient rows in the shared-output test. No model speed claim.",
              "medianConvention": "Upper middle sample of20 measured rounds per repetition; median of3 fresh-browser repetition medians.",
              "correctnessOutputChecks": sum(row["outputChecks"] for gate in gates for row in gate["correctness"]),
              "timedOutputChecksIncludingWarmup": checked,
              "sourceFiles": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in source_files],
              "summarizerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "configurations": summary}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    for row in summary:
        print(f"N{row['inputs']} M{row['outputsPerVector']} {row['id']}: {row['medianMilliseconds']:.3f}ms "
              f"[{row['minimumRunMedianMilliseconds']:.3f},{row['maximumRunMedianMilliseconds']:.3f}] / {row['outputsPerBatch']} outputs")
    print(f"Correctness: {result['correctnessOutputChecks']}; timed: {checked}")


if __name__ == "__main__":
    main()
