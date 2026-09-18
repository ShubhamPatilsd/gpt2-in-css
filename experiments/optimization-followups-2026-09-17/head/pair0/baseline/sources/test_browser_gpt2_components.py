#!/usr/bin/env python3
"""Python/CDP-only numerical checks of the native GPT-2 head and lookup."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from probe_native_value_latch import attribute, error, navigate, props
from profile_hybrid_twelve_block import (
    browser,
    load,
    metrics,
    query,
    read_vector,
    settle,
)

OUT = Path(__file__).resolve().parents[1] / "experiments/browser-gpt2"


def wait_fonts(cdp, selector, glyphs, limit=180):
    node = query(cdp, selector)
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        fonts = cdp.command("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
        if sum(f["glyphCount"] for f in fonts if f["isCustomFont"]) >= glyphs:
            return fonts
        time.sleep(0.1)
    raise TimeoutError("Custom fonts did not become active")


def read_winner(cdp, node, limit=60):
    deadline = time.monotonic() + limit
    previous, stable = None, 0
    while time.monotonic() < deadline:
        value = props(cdp, node).get("--winner", "-1")
        if value == previous:
            stable += 1
        else:
            stable = 0
        if stable >= 4:
            return float(value)
        previous = value
        time.sleep(0.03)
    raise TimeoutError("Head did not settle")


def head_test(cdp, count, directory=None):
    directory = directory or OUT / "head"
    reference = json.loads((directory / "reference.json").read_text())
    started = time.perf_counter()
    node = navigate(cdp, directory / "index.html", "#head-result")
    wait_fonts(cdp, '.head-row[data-token="0"]', 6)
    initial = read_winner(cdp, node)
    cold = (time.perf_counter() - started) * 1000
    print("head loaded", round(cold), "ms; initial", initial, flush=True)
    body = query(cdp, "body")
    rows = []
    for state, hidden in enumerate(reference["hidden"][:count]):
        before = metrics(cdp)
        started = time.perf_counter()
        if state:
            attribute(
                cdp,
                body,
                "style",
                ";".join(f"--h{i}:{v:.12g}" for i, v in enumerate(hidden)),
            )
        winner = read_winner(cdp, node)
        elapsed = (time.perf_counter() - started) * 1000
        after = metrics(cdp)
        expected = reference["fixtures"][state]["q16BucketWinner"]
        row = {
            "state": reference["sourceStates"][state],
            "winner": winner,
            "expected": expected,
            "milliseconds": elapsed,
            "taskMilliseconds": (after["TaskDuration"] - before["TaskDuration"]) * 1000,
            "passed": winner == expected,
        }
        if not row["passed"]:
            wanted_group = expected // 256
            row["geometry"] = {}
            for selector in (
                f'.head-row[data-token="{expected}"]',
                f".head-group:nth-child({wanted_group + 1})",
                f".head-score-{wanted_group}",
                ".head-max-1-0",
                f".head-match-{wanted_group}",
                ".head-choice-1-0",
                ".head-reader",
            ):
                match = query(cdp, selector)
                row["geometry"][selector] = (
                    props(cdp, match).get("width") if match else None
                )
        rows.append(row)
        print("head", row, flush=True)
        (directory / "browser-results.json").write_text(
            json.dumps(
                {
                    "coldMilliseconds": cold,
                    "samples": rows,
                    "runtimeJavaScript": False,
                    "harnessJavaScript": False,
                },
                indent=2,
            )
        )
        if not row["passed"]:
            break


def embedding_test(cdp, count, directory=None):
    directory = directory or OUT / "embedding"
    reference = json.loads((directory / "reference.json").read_text())
    started = time.perf_counter()
    node = navigate(cdp, directory / "index.html", "#embedding-result")
    wait_fonts(cdp, ".embedding-metric", 1)
    _initial, _ = settle(cdp, node, "embed", 768, limit=60)
    cold = (time.perf_counter() - started) * 1000
    body = query(cdp, "body")
    rows = []
    for state, token in enumerate(reference["tokens"][:count]):
        started = time.perf_counter()
        before = metrics(cdp)
        if state:
            attribute(cdp, body, "style", f"--token:{token}")
        values, reads = settle(cdp, node, "embed", 768, limit=60)
        after = metrics(cdp)
        row = {
            "token": token,
            "milliseconds": (time.perf_counter() - started) * 1000,
            "taskMilliseconds": (after["TaskDuration"] - before["TaskDuration"]) * 1000,
            "error": error(values, reference["embeddings"][state]),
            "reads": reads,
        }
        row["passed"] = (
            row["error"]["maximum"] is not None and row["error"]["maximum"] < 0.002
        )
        print("embedding", row, flush=True)
        rows.append(row)
        (directory / "browser-results.json").write_text(
            json.dumps(
                {
                    "coldMilliseconds": cold,
                    "samples": rows,
                    "runtimeJavaScript": False,
                    "harnessJavaScript": False,
                },
                indent=2,
            )
        )
        if not row["passed"]:
            break


def core_test(cdp, count, directory=None):
    directory = directory or OUT / "core"
    reference = json.loads((directory / "reference.json").read_text())
    node, _initial, cold, _ = load(
        cdp, directory / "index.html", "#core-result", "x", 768
    )
    body = query(cdp, "body")
    stored = {}
    rows = []
    for state, inputs in enumerate(reference["inputs"][:count]):
        started = time.perf_counter()
        before = metrics(cdp)
        if state:
            attribute(
                cdp,
                body,
                "style",
                f"--epoch:{state + 1};"
                + ";".join(f"--x-{i:03d}:{v:.12g}" for i, v in enumerate(inputs)),
            )
        settle(
            cdp, node, "x", 768, geometry_node=cdp.geometry_node, generation=state + 1
        )
        elapsed = (time.perf_counter() - started) * 1000
        after = metrics(cdp)
        values = read_vector(cdp, node, "x", 768)
        caches = []
        for layer in range(reference["blocks"]):
            for slot in range(state + 1):
                bank = query(cdp, f'.kv-slot-{slot}[data-layer="{layer}"]')
                entries = props(cdp, bank)
                actual = [
                    float(entries[f"--kv-{kind}{slot}-{i:03d}"])
                    for kind in ("k", "v")
                    for i in range(768)
                ]
                key = (layer, slot)
                if slot == state:
                    stored[key] = actual
                caches.append(
                    {
                        "layer": layer,
                        "slot": slot,
                        "retentionError": error(actual, stored[key]),
                        "referenceError": error(
                            actual, reference["layers"][layer]["qkv"][slot][768:]
                        ),
                    }
                )
        row = {
            "epoch": state + 1,
            "milliseconds": elapsed,
            "taskMilliseconds": (after["TaskDuration"] - before["TaskDuration"]) * 1000,
            "error": error(values, reference["outputs"][state]),
            "caches": caches,
        }
        row["passed"] = (
            row["error"]["rmse"] is not None
            and row["error"]["rmse"] < 0.02
            and all(c["retentionError"]["maximum"] == 0 for c in caches)
        )
        rows.append(row)
        print(
            "core",
            {k: v for k, v in row.items() if k != "caches"},
            "cache retention",
            max(c["retentionError"]["maximum"] or 0 for c in caches),
            flush=True,
        )
        (directory / "browser-results.json").write_text(
            json.dumps(
                {
                    "coldMilliseconds": cold,
                    "samples": rows,
                    "runtimeJavaScript": False,
                    "harnessJavaScript": False,
                },
                indent=2,
                allow_nan=False,
            )
        )
        if not row["passed"]:
            break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("component", choices=("head", "embedding", "core"))
    parser.add_argument("--states", type=int, default=38)
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    if args.directory:
        args.directory = args.directory.resolve()
    with browser() as cdp:
        {"head": head_test, "embedding": embedding_test, "core": core_test}[
            args.component
        ](cdp, args.states, args.directory)


if __name__ == "__main__":
    main()
