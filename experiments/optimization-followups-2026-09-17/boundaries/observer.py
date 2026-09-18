#!/usr/bin/env python3
"""Observe K continuing native tokens without shrinking the compiled graph.

Scaffold only: this new runner has not yet been exercised against the full native
model. The external observer never supplies token IDs or intermediate values.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def bounded(command, seconds):
    """Kill only this newly created process group if the work budget expires."""
    process = subprocess.Popen(command, start_new_session=True)
    try:
        return process.wait(timeout=seconds), False
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        return process.wait(), True


def describe(args):
    directory = args.directory.resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    if not 1 <= args.tokens <= manifest["capacity"] or args.tokens >= manifest.get("generatedTokenLimit", manifest["capacity"]):
        raise ValueError("Observe at least1 token, within capacity and strictly below the compiled generation limit")
    if args.wall_seconds <= 0:
        raise ValueError("Wall budget must be positive")
    return {"schemaVersion":1, "scope":"full-native-token-pipeline", "directory": str(directory),
            "blocks":manifest["blocks"], "allocatedCapacity": manifest["capacity"],
            "compiledGenerationLimit": manifest.get("generatedTokenLimit", manifest["capacity"]),
            "observedTokenTarget": args.tokens, "wallBudgetSeconds": args.wall_seconds,
            "sourceSha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                             for name in ("index.html", "runtime.css", "manifest.json") if (directory / name).exists()},
            "compiledGraphModified": False, "runnerBrowserValidated": False,
            "browserArguments":[f"--js-flags=--heap-growing-percent={args.heap_growth_percent}"] if args.heap_growth_percent else [],
            "runnerSha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "numericalVerificationPerformed":False,
            "verificationScope":"Native capture epochs and retained token IDs only; no independent numerical or token-reference validation",
            "authorJavaScript": False, "observerJavaScript": False,
            "limitations": ["Observation times include layout reads and polling delay.",
                            "The next native token may begin before the observer closes the browser.",
                            "A short prefix does not identify long-context latency growth.",
                            "No numerical-quality verification is performed by this timing scaffold."],
            "samples": [], "completedObservedPrefix": False, "manifest": manifest}


def observe(args):
    from benchmark_browser_gpt2_memory import MemorySampler
    from probe_native_value_latch import navigate, props
    from profile_hybrid_twelve_block import browser, query
    from test_browser_gpt2_runtime import static_url
    output = args.output.resolve() / "prefix-results.json"
    report = describe(args)
    launch_started = time.monotonic()
    atomic_json(output, report)
    with static_url(args.directory.resolve(), True) as url, browser(report["browserArguments"]) as cdp, MemorySampler(cdp.browser_pid) as memory:
        report["browser"] = cdp.command("Browser.getVersion")
        report["browserLaunchMilliseconds"] = (time.monotonic() - launch_started) * 1000
        started = time.monotonic()  # Same navigation boundary as the historical runtime observer.
        node = navigate(cdp, args.directory.resolve() / "index.html", "#tokens", url=url, limit=min(180, args.wall_seconds))
        if not report["manifest"].get("autostart", True):
            button = query(cdp, "#run")
            box = cdp.command("DOM.getBoxModel", {"nodeId": button})["model"]["content"]
            point = {"x": (box[0] + box[2]) / 2, "y": (box[1] + box[5]) / 2, "button": "left", "clickCount": 1}
            cdp.command("Input.dispatchMouseEvent", {"type": "mousePressed", **point})
            cdp.command("Input.dispatchMouseEvent", {"type": "mouseReleased", **point})
        capture = query(cdp, "#capture-epoch-observer")
        if not capture:
            raise RuntimeError("This runner requires the native retained-capture observer")
        report["setupMilliseconds"] = (time.monotonic() - started) * 1000
        previous = 0
        boundary_seen = set()
        report["boundaryObservations"] = []
        while True:
            from probe_audit_native_boundaries import collect
            collect(cdp, report, boundary_seen, started)
            try:
                box = cdp.command("DOM.getBoxModel", {"nodeId": capture})["model"]["content"]
                epoch, winner = round(box[2] - box[0]), round(box[5] - box[1])
            except RuntimeError as error:
                if "Could not compute box model" not in str(error):
                    raise
                epoch, winner = 0, -1
            if epoch > previous:
                report["samples"].append({"capturedTokenCount": epoch, "winner": winner,
                                          "milliseconds": (time.monotonic() - started) * 1000,
                                          "skippedObservationCount": max(0, epoch - previous - 1)})
                previous = epoch
                report["sampledMemory"] = list(memory.samples)
                atomic_json(output, report)
            if epoch >= args.tokens or (epoch > 0 and winner == 50256):
                report["completedObservedPrefix"] = epoch == args.tokens and winner != 50256
                report["stopReason"] = "eos" if winner == 50256 else "observed-prefix" if epoch == args.tokens else "missed-prefix-boundary"
                report["timingWindowMilliseconds"] = (time.monotonic() - started) * 1000
                atomic_json(output, report)
                values = props(cdp, node)
                report["retainedTokens"] = [float(values.get(f"--saved-token-{i}", -1)) for i in range(1, min(epoch, args.tokens) + 1)]
                collect(cdp, report, boundary_seen, started)
                from probe_audit_native_prefix import capture
                report["numericalReadback"] = capture(cdp, report)
                atomic_json(output, report)
                break
            time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh directory; never an existing results directory")
    parser.add_argument("--tokens", type=int, default=4)
    parser.add_argument("--wall-seconds", type=float, default=480)
    parser.add_argument("--heap-growth-percent", type=int, choices=(0,10,25,50,100), default=10)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        observe(args)
        return
    plan = describe(args)
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return
    args.output.resolve().mkdir(parents=True, exist_ok=False)
    output = args.output.resolve() / "prefix-results.json"
    atomic_json(output, plan)
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--worker"]
    status, expired = bounded(command, args.wall_seconds)
    report = json.loads(output.read_text())
    report.update(workerExitStatus=status, wallBudgetExpired=expired)
    if expired:
        report["targetCapturedBeforeDeadline"] = report["completedObservedPrefix"]
        report["completedObservedPrefix"] = False
        report["stopReason"] = "wall-budget"
    report["sourceUnchangedAfterRun"] = describe(args)["sourceSha256"] == plan["sourceSha256"]
    atomic_json(output, report)
    if expired or status != 0 or not report["completedObservedPrefix"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
