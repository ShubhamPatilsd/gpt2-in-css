#!/usr/bin/env python3
"""OFFLINE accuracy check only: this is never part of timed browser inference."""

import argparse
import json
from pathlib import Path
import numpy as np
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    reference = json.loads((args.report.parent / "reference.json").read_text())
    tensors = SafeTensors(MODEL_PATH)
    embedding = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)

    def logits(vector):
        v = np.asarray(vector)
        return embedding @ ((v - v.mean()) / np.sqrt(v.var() + 1e-5) * gamma + beta)

    rows = []
    for connected in report["connected"]:
        if connected["blocks"] != 12:
            continue
        states = [(0, connected["initialOutput"])] + [
            (s["state"], s["output"]) for s in connected["samples"]
        ]
        for state, actual in states:
            predicted = logits(actual)
            expected = logits(reference["layers"][11]["proj"][state])
            order = np.argsort(expected)[-2:][::-1]
            row = dict(
                state=state,
                referenceWinner=int(order[0]),
                browserResidualWinner=int(predicted.argmax()),
                referenceWinnerMargin=float(expected[order[0]] - expected[order[1]]),
                maximumLogitError=float(np.max(np.abs(predicted - expected))),
            )
            row["winnerMatches"] = (
                row["referenceWinner"] == row["browserResidualWinner"]
            )
            rows.append(row)
    result = {
        "offlineCheckOnly": True,
        "includedInBrowserTiming": False,
        "checks": rows,
    }
    path = args.report.with_name(args.report.stem + "-offline-head-check.json")
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
