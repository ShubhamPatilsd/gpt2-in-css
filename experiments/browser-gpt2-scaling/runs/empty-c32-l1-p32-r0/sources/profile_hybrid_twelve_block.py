#!/usr/bin/env python3
"""Python/CDP-only numerical validation and fresh-input timing of the hybrid.

No Runtime domain, page JavaScript, external intermediate transfers, or JS
profilers. Isolated stage percentages are diagnostic shares, explicitly not
an exclusive breakdown of connected wall-clock latency.
"""

from __future__ import annotations

import argparse
import collections
from contextlib import contextmanager
import json
import math
from pathlib import Path
import statistics
import subprocess
import tempfile
import time
import urllib.request

from probe_browser_native_compute import CdpSocket, chrome_path, metric_map

OUT = Path(__file__).resolve().parents[1] / "experiments/hybrid-12block-profile"
STAGES = ("ln1", "qkv", "mix", "attn", "ln2", "fc", "proj")
OUTPUT_STEM = dict(zip(STAGES, ("n1", "qkv", "ctx", "r", "n2", "hidden", "out")))


class Recorder(CdpSocket):
    def __init__(self, url):
        super().__init__(url)
        self.events = []
        self.trace_complete = False
        self.event_totals = collections.Counter()
        self.event_counts = collections.Counter()

    def _receive_frame(self):
        opcode, payload = super()._receive_frame()
        if opcode == 1:
            message = json.loads(payload)
            if message.get("method") == "Tracing.dataCollected":
                retained = {
                    "thread_name",
                    "RunTask",
                    "UpdateLayoutTree",
                    "Layout",
                    "InlineNode::ShapeTextIncludingFirstLine",
                    "PrePaint",
                    "LocalFrameView::RunPaintLifecyclePhase",
                    "LocalFrameView::RunStyleAndLayoutLifecyclePhases",
                    "Blink.CompositingInputs.UpdateTime",
                    "Paint",
                    "AnimationTimeline::serviceAnimations",
                    "PageAnimator::serviceScriptedAnimations",
                }
                self.events.extend(
                    e for e in message["params"]["value"] if e.get("name") in retained
                )
                for event in message["params"]["value"]:
                    if event.get("ph") == "X":
                        key = (event.get("pid"), event.get("tid"), event.get("name"))
                        self.event_totals[key] += event.get("dur", 0)
                        self.event_counts[key] += 1
            elif message.get("method") == "Tracing.tracingComplete":
                self.trace_complete = True
                self.trace_completion = message.get("params", {})
        return opcode, payload

    def command(self, method, params=None):
        if method.startswith(("Runtime.", "Debugger.", "Profiler.")):
            raise RuntimeError("JavaScript execution/profiling domains prohibited")
        return super().command(method, params)


@contextmanager
def browser(extra_args=()):
    with tempfile.TemporaryDirectory(prefix="hybrid12-profile-") as profile:
        process = subprocess.Popen(
            [
                str(chrome_path()),
                "--headless=new",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-component-update",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--allow-file-access-from-files",
                "--remote-debugging-port=0",
                "--remote-allow-origins=*",
                f"--user-data-dir={profile}",
                "--window-size=900,300",
                *extra_args,
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cdp = None
        try:
            port_file = Path(profile) / "DevToolsActivePort"
            deadline = time.monotonic() + 30
            while not port_file.exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Chromium launch failed")
                time.sleep(0.02)
            port = int(port_file.read_text().splitlines()[0])
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
            cdp = Recorder(
                next(t["webSocketDebuggerUrl"] for t in targets if t["type"] == "page")
            )
            cdp.browser_pid = process.pid
            cdp.extra_browser_arguments = list(extra_args)
            cdp.connection.settimeout(300)
            for domain in ("Page", "DOM", "CSS", "Performance"):
                cdp.command(f"{domain}.enable")
            cdp.command("Emulation.setScriptExecutionDisabled", {"value": True})
            yield cdp
        finally:
            if cdp:
                cdp.close()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def query(cdp, selector):
    if not getattr(cdp, "root_node", None):
        cdp.root_node = cdp.command("DOM.getDocument", {"depth": 1})["root"]["nodeId"]
    root = cdp.root_node
    return cdp.command("DOM.querySelector", {"nodeId": root, "selector": selector})[
        "nodeId"
    ]


def read_vector(cdp, node, stem, count):
    computed = {
        p["name"]: p["value"]
        for p in cdp.command("CSS.getComputedStyleForNode", {"nodeId": node})[
            "computedStyle"
        ]
    }
    try:
        return [float(computed[f"--{stem}-{i:03d}"]) for i in range(count)]
    except (ValueError, KeyError):
        return [float("nan")] * count


def error(actual, expected):
    finite = sum(math.isfinite(v) for v in actual)
    if finite != len(expected):
        return {"finite": finite, "rmse": None, "maximum": None}
    diffs = [a - b for a, b in zip(actual, expected, strict=True)]
    return {
        "finite": finite,
        "rmse": math.sqrt(sum(d * d for d in diffs) / len(diffs)),
        "maximum": max(map(abs, diffs)),
    }


def settle(cdp, node, stem, count, limit=240, geometry_node=0, generation=1):
    deadline = time.monotonic() + limit
    previous, stable, reads = None, 0, 0
    while time.monotonic() < deadline:
        try:
            values = (
                cdp.command("DOM.getBoxModel", {"nodeId": geometry_node})["model"][
                    "content"
                ]
                if geometry_node
                else read_vector(cdp, node, stem, count)
            )
        except RuntimeError as exc:
            if "Could not compute box model" not in str(exc):
                raise
            values = [float("nan")]
        reads += 1
        generation_matches = not (
            geometry_node and getattr(cdp, "external_observer", False)
        ) or (len(values) == 8 and abs(values[2] - values[0] - generation * 64) < 0.01)
        if (
            generation_matches
            and previous is not None
            and all(
                math.isfinite(a) and abs(a - b) <= 1e-7
                for a, b in zip(values, previous)
            )
        ):
            stable += 1
        else:
            stable = 0
        if stable >= 3:
            return (None if geometry_node else values), reads
        previous = values
        time.sleep(0.025)
    raise TimeoutError(f"{stem} failed to settle after {reads} reads")


def load(cdp, path, selector, stem, count):
    if "<script" in path.read_text().lower():
        raise RuntimeError("script element in fixture")
    started = time.perf_counter()
    cdp.command("Page.navigate", {"url": path.as_uri()})
    cdp.root_node = None
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        try:
            node = query(cdp, selector)
            if node:
                # A navigation response can precede the DOM replacement; ensure
                # this node belongs to the requested document, not its predecessor.
                root_doc = cdp.command("DOM.describeNode", {"nodeId": cdp.root_node})[
                    "node"
                ]
                if root_doc.get("documentURL") == path.as_uri():
                    break
                cdp.root_node = None
        except RuntimeError:
            cdp.root_node = None
        time.sleep(0.05)
    else:
        raise TimeoutError(f"missing {selector}")
    probe_selector = (
        "#final-probe"
        if selector == "#final"
        else selector.replace("-result", "-probe")
    )
    observer = query(cdp, "#measurement")
    cdp.external_observer = bool(observer) and not getattr(
        cdp, "full_style_settle", False
    )
    cdp.geometry_node = (
        0
        if getattr(cdp, "full_style_settle", False)
        else (observer or query(cdp, probe_selector))
    )
    values, reads = settle(cdp, node, stem, count, geometry_node=cdp.geometry_node)
    cold = (time.perf_counter() - started) * 1000
    if values is None:
        values = read_vector(cdp, node, stem, count)
    return node, values, cold, reads


def metrics(cdp):
    return metric_map(cdp.command("Performance.getMetrics"))


def run(cdp, path, selector, stem, expected, input_styles, trace=False):
    node, initial, cold, reads = load(cdp, path, selector, stem, len(expected[0]))
    body = query(cdp, "body")
    report = {
        "path": path.name,
        "coldMilliseconds": cold,
        "coldReads": reads,
        "initialError": error(initial, expected[0]),
        "initialOutput": initial,
        "samples": [],
    }
    report["settlingReadback"] = (
        "geometry checksum" if cdp.geometry_node else "full computed style"
    )
    if cdp.external_observer:
        report["settlingReadback"] = "external anchor observer with generation check"

    def checkpoint():
        (OUT / f"{path.stem}-latest-measurement.json").write_text(
            json.dumps(report, indent=2, allow_nan=False)
        )

    checkpoint()
    print(path.name, "cold", round(cold), "ms", report["initialError"], flush=True)
    if trace:
        cdp.events = []
        cdp.event_totals.clear()
        cdp.event_counts.clear()
        cdp.trace_complete = False
        # rail + benchmark expose frame and paint phases without blink's
        # millions of per-timeline leaf events filling the trace buffer.
        cdp.command(
            "Tracing.start",
            {
                "categories": "devtools.timeline,rail,benchmark,cc,disabled-by-default-devtools.timeline",
                "transferMode": "ReportEvents",
            },
        )
    for state in range(1, len(input_styles)):
        before = metrics(cdp)
        started = time.perf_counter()
        cdp.command(
            "DOM.setAttributeValue",
            {"nodeId": body, "name": "style", "value": input_styles[state]},
        )
        values, reads = settle(
            cdp,
            node,
            stem,
            len(expected[state]),
            geometry_node=cdp.geometry_node,
            generation=state + 1,
        )
        elapsed = (time.perf_counter() - started) * 1000
        after = metrics(cdp)
        if values is None:
            values = read_vector(cdp, node, stem, len(expected[state]))
        delta = {
            k: (after[k] - before.get(k, 0)) * 1000
            for k in (
                "TaskDuration",
                "RecalcStyleDuration",
                "LayoutDuration",
                "ScriptDuration",
            )
        }
        sample = {
            "state": state,
            "milliseconds": elapsed,
            "reads": reads,
            "browser": delta,
            "error": error(values, expected[state]),
            "output": values,
        }
        report["samples"].append(sample)
        checkpoint()
        print(
            " state",
            state,
            round(elapsed, 1),
            "ms task",
            round(delta["TaskDuration"], 1),
            sample["error"],
            flush=True,
        )
    if trace:
        cdp.command("Tracing.end")
        deadline = time.monotonic() + 60
        while not cdp.trace_complete and time.monotonic() < deadline:
            cdp.command("Browser.getVersion")
            time.sleep(0.01)
        totals = [
            dict(
                pid=k[0], tid=k[1], name=k[2], microseconds=v, count=cdp.event_counts[k]
            )
            for k, v in cdp.event_totals.most_common()
        ]
        (OUT / f"{path.stem}-trace.json").write_text(
            json.dumps(
                {
                    "traceEvents": cdp.events,
                    "inclusiveEventTotals": totals,
                    "completion": getattr(cdp, "trace_completion", {}),
                }
            )
        )
        report["traceEventCount"] = len(cdp.events)
    if report["samples"]:
        report["medianMilliseconds"] = statistics.median(
            s["milliseconds"] for s in report["samples"]
        )
        report["medianBrowserTaskMilliseconds"] = statistics.median(
            s["browser"]["TaskDuration"] for s in report["samples"]
        )
    return report


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocks", type=int, nargs="+", default=[1, 2, 12])
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--layers", type=int, nargs="+")
    parser.add_argument("--stages", nargs="+", default=list(STAGES))
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--report", default="browser-results.json")
    parser.add_argument("--only-isolated", action="store_true")
    parser.add_argument("--directory", type=Path, default=OUT)
    parser.add_argument("--states", type=int, default=4)
    parser.add_argument("--full-style-settle", action="store_true")
    args = parser.parse_args()
    OUT = args.directory.resolve()
    ref = json.loads((OUT / "reference.json").read_text())
    report = {
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "scriptExecutionDisabled": True,
        "context": ref["context"],
        "chunk": ref["chunk"],
        "excludes": ref["excludes"],
        "connected": [],
        "isolated": [],
    }
    report.update(
        resetScratch=ref.get("resetScratch", False), contain=ref.get("contain", False)
    )
    report["compactMetrics"] = ref.get("compactMetrics", False)
    report["generationGates"] = ref.get("generationGates", False)
    report["siblingBlocks"] = ref.get("siblingBlocks", False)
    report["contentGates"] = ref.get("contentGates", False)
    report["fcEasingStops"] = ref.get("fcEasingStops")

    def save():
        (OUT / args.report).write_text(json.dumps(report, indent=2, allow_nan=False))

    with browser() as cdp:
        cdp.full_style_settle = args.full_style_settle
        report["browser"] = cdp.command("Browser.getVersion")
        for blocks in [] if args.only_isolated else args.blocks:
            styles = [
                f"--epoch:{s + 1};"
                + ";".join(f"--x-{i:03d}:{v:.12g}" for i, v in enumerate(row))
                for s, row in enumerate(ref["inputs"][: args.states])
            ]
            result = run(
                cdp,
                OUT / f"connected-{blocks}.html",
                "#final",
                "out",
                ref["layers"][blocks - 1]["proj"][: args.states],
                styles,
                args.trace,
            )
            result["blocks"] = blocks
            result["checkpoints"] = []
            for layer in range(blocks):
                node = query(cdp, f"#b{layer}-proj-result")
                values = read_vector(cdp, node, "out", 768)
                result["checkpoints"].append(
                    error(
                        values,
                        ref["layers"][layer]["proj"][
                            min(args.states, len(ref["inputs"])) - 1
                        ],
                    )
                )
            report["connected"].append(result)
            save()
        if args.isolated:
            for layer in (
                args.layers if args.layers is not None else range(ref["blocks"])
            ):
                for stage in args.stages:
                    result = run(
                        cdp,
                        OUT / f"b{layer}-{stage}.html",
                        f"#b{layer}-{stage}-result",
                        OUTPUT_STEM[stage],
                        ref["layers"][layer][stage][: args.states],
                        ref["layers"][layer]["stageInputStyles"][stage][: args.states],
                        args.trace,
                    )
                    result.update(layer=layer, stage=stage)
                    report["isolated"].append(result)
                    save()


if __name__ == "__main__":
    main()
