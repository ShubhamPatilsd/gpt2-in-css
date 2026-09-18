#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Reproducible native-attention ablations; never an autonomous timing claim."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import statistics
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
from benchmark_browser_gpt2_memory import MemorySampler
from browser_gpt2_scaling_variants import VARIANTS, replacement
from probe_browser_gpt2_geometry_attention import compile_fixture
from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, error, metrics, query, read_vector
from test_browser_gpt2_components import wait_fonts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2-scaling"


def oracle(qkv, history):
    q = np.split(qkv, 3)[0]
    keys = np.array([x[0] for x in history]).reshape(-1, 12, 64)
    values = np.array([x[1] for x in history]).reshape(-1, 12, 64)
    scores = np.einsum("hd,thd->ht", q.reshape(12, 64), keys) / 8
    weights = np.exp(scores - scores.max(axis=1, keepdims=True))
    weights /= weights.sum(axis=1, keepdims=True)
    return np.einsum("ht,thd->hd", weights, values).reshape(768).tolist()


def delta(after, before):
    return {
        k: after[k] - before.get(k, 0)
        for k in after
        if k.endswith(("Duration", "Count"))
    }


def settled(cdp, node, receipt, epoch, limit=30):
    previous, stable, reads = None, 0, 0
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        state = props(cdp, receipt)
        values = read_vector(cdp, node, "x", 768)
        reads += 1
        ready = (
            state.get("--bridge-ready") == "1"
            and float(state.get("--epoch", 0)) == epoch
        )
        if (
            ready
            and previous is not None
            and np.isfinite(values).all()
            and np.max(np.abs(np.array(values) - previous)) < 1e-7
        ):
            stable += 1
        else:
            stable = 0
        if stable >= 3:
            return values, reads
        previous = np.array(values)
        time.sleep(0.025)
    raise TimeoutError(
        f"No fresh stable context at epoch {epoch}; readiness={state.get('--bridge-ready')}"
    )


def run_case(name, capacity, layers, positions, repeat, query_updates=3, trace=False):
    directory = OUT / "runs" / f"{name}-c{capacity}-l{layers}-p{positions}-r{repeat}"
    directory.mkdir(parents=True, exist_ok=True)
    replace = replacement(name)

    def attention(*args, **kwargs):
        args = list(args)
        args[1] = layers
        kwargs["write_epoch"] = "--position"
        return replace(*args, **kwargs)

    with patch("browser_gpt2_font_vector_cache.attention", attention):
        inputs, _ = compile_fixture(
            directory, capacity, 12, 64, None, backend="font-vector"
        )
    css_path = directory / "attention.css"
    css = (
        css_path.read_text()
        + 'body{--position:1}@property --position{syntax:"<number>";inherits:true;initial-value:1}'
    )
    css_path.write_text(css)
    report = {
        "variant": name,
        "options": asdict(VARIANTS[name]),
        "capacity": capacity,
        "layers": layers,
        "positions": positions,
        "repeat": repeat,
        "queryUpdates": query_updates,
        "traceRequested": trace,
        "startedAtUTC": datetime.now(timezone.utc).isoformat(),
        "pythonVersion": platform.python_version(),
        "platform": platform.platform(),
        "fixtureSeed": 7391,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "fonttools", "brotli", "pillow")
        },
        "scope": "Externally supplied QKV attention component with native KV retention; excludes projections, MLP and vocabulary head",
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "externalWritesAfterNavigation": 0,
        "samples": [],
        "browserArguments": ["--js-flags=--heap-growing-percent=10"],
        "sourceHashes": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                Path(__file__),
                ROOT / "tools/browser_gpt2_scaling_variants.py",
                ROOT / "tools/browser_gpt2_font_vector_cache.py",
                ROOT / "tools/probe_browser_gpt2_geometry_attention.py",
                ROOT / "tools/build_hybrid_twelve_block.py",
                ROOT / "tools/profile_hybrid_twelve_block.py",
                ROOT / "tools/probe_native_value_latch.py",
                ROOT / "tools/benchmark_browser_gpt2_memory.py",
                ROOT / "tools/test_browser_gpt2_components.py",
                css_path,
                directory / "index.html",
            )
        },
        "settleProtocol": "Three unchanged finite vector reads plus matching native generation receipt; 25ms polling. Timing includes CDP writes/reads and settling floor.",
    }
    snapshots = directory / "sources"
    snapshots.mkdir(exist_ok=True)
    for filename in report["sourceHashes"]:
        if filename.endswith(".py"):
            (snapshots / filename).write_bytes((ROOT / "tools" / filename).read_bytes())
    history = [[] for _ in range(layers)]
    steps = []
    for pos in range(positions):
        for layer in range(layers):
            vector = inputs[pos] * (1 + 0.07 * layer) + 0.1 * layer
            history[layer].append(tuple(np.split(vector, 3)[1:]))
            steps.append(
                (pos + 1, layer, vector, oracle(vector, history[layer]), "append")
            )
    # Revisit all layers with fixed K/V and change ONLY head zero's query. These
    # are valid recomputations at the current position, not generated tokens.
    for update in range(query_updates):
        for layer in range(layers):
            vector = (inputs[positions - 1] * (1 + 0.07 * layer) + 0.1 * layer).copy()
            vector[:64] += (update + 1) * 0.31
            kind = "query-only" if layers == 1 else "query+layer-switch"
            steps.append(
                (positions, layer, vector, oracle(vector, history[layer]), kind)
            )
    try:
        with (
            browser(report["browserArguments"]) as cdp,
            MemorySampler(cdp.browser_pid) as memory,
        ):
            cdp.connection.settimeout(60)
            report["browser"] = cdp.command("Browser.getVersion")
            node = navigate(cdp, directory / "index.html", "#result", limit=60)
            body = query(cdp, "body")
            receipt = query(cdp, ".b100-bridge-receipt")
            wait_fonts(cdp, ".fvs-score-0-0", 1)
            wait_fonts(cdp, ".fvs-v-0-0", 1)
            for index, (position, layer, vector, expected, kind) in enumerate(steps):
                epoch = index + 1
                before = metrics(cdp)
                begin = time.perf_counter()
                if index:
                    attribute(
                        cdp,
                        body,
                        "style",
                        f"--epoch:{epoch};--position:{position};--layer:{layer};"
                        + ";".join(
                            f"--qkv-{i:03d}:{v:.12g}" for i, v in enumerate(vector)
                        ),
                    )
                    report["externalWritesAfterNavigation"] += 1
                actual, reads = settled(cdp, node, receipt, epoch)
                duration = (time.perf_counter() - begin) * 1000
                measured = error(actual, expected)
                row = {
                    "epoch": epoch,
                    "position": position,
                    "layer": layer,
                    "kind": kind,
                    "milliseconds": duration,
                    "error": measured,
                    "reads": reads,
                    "rendererDelta": delta(metrics(cdp), before),
                    "passed": measured["rmse"] is not None and measured["rmse"] < 0.005,
                    "unchangedHeadsMaximumError": float(
                        np.max(np.abs(np.array(actual[64:]) - expected[64:]))
                    ),
                }
                report["samples"].append(row)
                (directory / "results.json").write_text(json.dumps(report, indent=2))
                print(
                    json.dumps(
                        {
                            "case": directory.name,
                            **{
                                k: row[k]
                                for k in (
                                    "epoch",
                                    "kind",
                                    "milliseconds",
                                    "error",
                                    "passed",
                                )
                            },
                        }
                    ),
                    flush=True,
                )
                if not row["passed"]:
                    report["failureDiagnostics"] = {}
                    for selector in (
                        ".fvs-query",
                        ".fvs-bank-0",
                        ".fvs-score-0-0",
                        ".fvs-score-reader",
                        ".fvs-v-0-0",
                        ".fvs-value-row",
                    ):
                        state = props(cdp, query(cdp, selector))
                        report["failureDiagnostics"][selector] = {
                            k: v
                            for k, v in state.items()
                            if k.startswith(
                                (
                                    "--fr-",
                                    "--fc-",
                                    "--fqs-",
                                    "--fs-",
                                    "--fd-",
                                    "--fe-",
                                    "--fb-",
                                )
                            )
                            or k in ("width", "font-variation-settings", "display")
                        }
                    break
            report["sampledPeak"] = {
                k: max(s[k] for s in memory.samples)
                for k in ("rendererRssMiB", "browserTreeRssMiB")
            }
            report["rendererFinal"] = metrics(cdp)
            report["domCounters"] = cdp.command("Memory.getDOMCounters")
            if trace and all(row["passed"] for row in report["samples"]):
                # A separate diagnostic update: tracing is excluded from timings.
                report["traceKind"] = (
                    "query-only; same selected layer, position and K/V as the final timed sample"
                )
                cdp.command(
                    "Tracing.start",
                    {
                        "categories": "devtools.timeline,blink,disabled-by-default-devtools.timeline.invalidationTracking",
                        "transferMode": "ReportEvents",
                    },
                )
                last = steps[-1]
                vector = last[2].copy()
                vector[:64] += 0.27
                epoch = len(steps) + 1
                attribute(
                    cdp,
                    body,
                    "style",
                    f"--epoch:{epoch};--position:{last[0]};--layer:{last[1]};"
                    + ";".join(f"--qkv-{i:03d}:{v:.12g}" for i, v in enumerate(vector)),
                )
                report["externalWritesAfterNavigation"] += 1
                actual, _ = settled(cdp, node, receipt, epoch)
                report["traceValidation"] = error(
                    actual, oracle(vector, history[last[1]])
                )
                cdp.command("Tracing.end")
                deadline = time.monotonic() + 30
                while not cdp.trace_complete and time.monotonic() < deadline:
                    cdp.command("Browser.getVersion")
                    time.sleep(0.05)
                report["traceComplete"] = cdp.trace_complete
                report["tracePassed"] = (
                    cdp.trace_complete
                    and report["traceValidation"]["rmse"] is not None
                    and report["traceValidation"]["rmse"] < 0.005
                )
                (directory / "trace.json").write_text(json.dumps(cdp.events))
                report["traceTotals"] = [
                    {
                        "pid": k[0],
                        "tid": k[1],
                        "event": k[2],
                        "microsecondsInclusive": v,
                        "count": cdp.event_counts[k],
                    }
                    for k, v in cdp.event_totals.items()
                ]
    except Exception as exc:  # noqa: BLE001 -- preserve failed experimental runs
        report["exception"] = f"{type(exc).__name__}: {exc}"
        print(
            json.dumps({"case": directory.name, "exception": report["exception"]}),
            flush=True,
        )
    report["passed"] = (
        "exception" not in report
        and len(report["samples"]) == len(steps)
        and all(r["passed"] for r in report["samples"])
    )
    for kind in ("append", "query-only", "query+layer-switch"):
        samples = [r for r in report["samples"][1:] if r["kind"] == kind]
        if samples:
            report[kind] = {
                "medianMilliseconds": statistics.median(
                    r["milliseconds"] for r in samples
                ),
                "meanStyleMilliseconds": statistics.mean(
                    r["rendererDelta"].get("RecalcStyleDuration", 0) * 1000
                    for r in samples
                ),
                "meanLayoutMilliseconds": statistics.mean(
                    r["rendererDelta"].get("LayoutDuration", 0) * 1000 for r in samples
                ),
            }
    (directory / "results.json").write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS)
    )
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--layers", type=int, default=1)
    parser.add_argument("--positions", type=int)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--query-updates", type=int, default=3)
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    positions = args.capacity if args.positions is None else args.positions
    if not 1 <= positions <= args.capacity or not 1 <= args.layers <= 12:
        parser.error("Require 1 <= positions <= capacity and 1 <= layers <= 12")
    if args.repeats < 1 or args.query_updates < 0:
        parser.error("Require repeats >= 1 and query-updates >= 0")
    failures = 0
    for repeat in range(args.repeats):
        names = args.variants if repeat % 2 == 0 else args.variants[::-1]
        for name in names:
            path = (
                OUT
                / "runs"
                / f"{name}-c{args.capacity}-l{args.layers}-p{positions}-r{repeat}"
                / "results.json"
            )
            if path.exists():
                saved = json.loads(path.read_text())
                requested = saved.get(
                    "queryUpdates",
                    sum(
                        row.get("kind") in ("query-only", "query+layer-switch")
                        for row in saved.get("samples", [])
                    )
                    // args.layers,
                )
                traced = saved.get("traceRequested", "traceValidation" in saved)
                if requested != args.query_updates or traced != args.trace:
                    parser.error(
                        f"Existing run {path} has different query/trace settings. Preserve/archive it explicitly before reusing this configuration."
                    )
                print(
                    f"Preserving existing run {path}; choose a different configuration or archive it explicitly",
                    flush=True,
                )
                failures += (
                    not saved.get("passed", False) or saved.get("tracePassed") is False
                )
                continue
            try:
                result = run_case(
                    name,
                    args.capacity,
                    args.layers,
                    positions,
                    repeat,
                    args.query_updates,
                    args.trace,
                )
            except Exception as exc:  # noqa: BLE001 -- preserve compiler failures too
                result = {
                    "variant": name,
                    "capacity": args.capacity,
                    "layers": args.layers,
                    "positions": positions,
                    "repeat": repeat,
                    "queryUpdates": args.query_updates,
                    "traceRequested": args.trace,
                    "passed": False,
                    "samples": [],
                    "failurePhase": "compilation or report construction",
                    "exception": f"{type(exc).__name__}: {exc}",
                }
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(result, indent=2))
                print(json.dumps(result), flush=True)
            failures += (
                not result.get("passed", False) or result.get("tracePassed") is False
            )
    if failures:
        raise SystemExit(
            f"{failures} cases failed; all available evidence was preserved"
        )


if __name__ == "__main__":
    main()
