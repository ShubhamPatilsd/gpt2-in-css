#!/usr/bin/env python3
"""Observe autonomous native generation. No JavaScript, vector writes, or ticks."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import threading
import time
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import build_hybrid_twelve_block as hybrid
from benchmark_browser_gpt2_memory import MemorySampler
from browser_gpt2_runtime import OUT, feedback
from decode_css_cache_diagnostic import decode_cache
from probe_native_value_latch import navigate, props
from profile_hybrid_twelve_block import browser, metrics, query, read_vector


def synthetic(directory):
    capacity = 4
    front, output, css, timelines = feedback(capacity, synthetic=True)
    css += hybrid.regs(["--epoch", "--token", "--winner", "--head-output-epoch"])
    css += (
        "html{timeline-scope:"
        + ",".join(timelines)
        + "}.fake-metric{position:fixed;width:calc(var(--token)*1px);height:calc(var(--epoch)*1px);anchor-name:--fake}.fake-reader{position:fixed;width:anchor-size(--fake width,0px);height:anchor-size(--fake height,0px);container-type:size}.fake-result{--winner:calc(round(nearest,100cqi/1px,1) + 1);--head-output-epoch:round(nearest,100cqb/1px,1)}"
    )
    model = front.replace(
        "{child}",
        '<i class="fake-metric"></i><div class="fake-reader"><div class="fake-result">'
        + output
        + "</div></div>",
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.html").write_text(
        '<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><style>'
        + css
        + '</style><body><input id="run" type="checkbox" checked>'
        + model
        + "</body>"
    )
    (directory / "manifest.json").write_text(
        json.dumps({"capacity": capacity, "synthetic": True})
    )


@contextmanager
def static_url(directory, enabled):
    if not enabled:
        yield None
        return
    root = Path(__file__).resolve().parents[1]

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(root))
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/" + str(
            (directory / "index.html").relative_to(root)
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def run(
    directory,
    limit=900,
    quiet=0,
    http=False,
    start=False,
    heap_growth_percent=0,
    report_prefix="",
    quality_readback=False,
):
    def artifact(name):
        return directory / (report_prefix + name)

    manifest = json.loads((directory / "manifest.json").read_text())
    start = start or not manifest.get("autostart", True)
    capacity = manifest["capacity"]
    report = {
        "manifest": manifest,
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "externalWritesAfterNavigation": 0,
        "samples": [],
        "qualityReadback": quality_readback,
        "artifactSha256": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ("index.html", "runtime.css", "manifest.json")
            if (directory / name).is_file()
        },
        "scope": "teacher-forced native forward passes"
        if manifest.get("teacherForcedInputs")
        else "autonomous native generation",
    }
    flags = (
        [f"--js-flags=--heap-growing-percent={heap_growth_percent}"]
        if heap_growth_percent
        else []
    )
    report["browserArguments"] = flags
    with (
        static_url(directory, http) as url,
        browser(flags) as cdp,
        MemorySampler(cdp.browser_pid) as memory,
    ):
        report["browser"] = cdp.command("Browser.getVersion")
        started = time.perf_counter()
        node = navigate(cdp, directory / "index.html", "#tokens", url=url, limit=180)
        if start:
            button = query(cdp, "#run")
            box = cdp.command("DOM.getBoxModel", {"nodeId": button})["model"]["content"]
            point = {
                "x": (box[0] + box[2]) / 2,
                "y": (box[1] + box[5]) / 2,
                "button": "left",
                "clickCount": 1,
            }
            report["initialRunClickMilliseconds"] = (
                time.perf_counter() - started
            ) * 1000
            cdp.command("Input.dispatchMouseEvent", {"type": "mousePressed", **point})
            cdp.command("Input.dispatchMouseEvent", {"type": "mouseReleased", **point})
            report["externalWritesAfterNavigation"] = 1
            report["externalWritePurpose"] = (
                "Initial user Run click only; no token scheduling or intermediate data writes"
            )
        observer_selectors = {
            "epoch": "#runtime-epoch-observer",
            "embedding": "#embedding-epoch-observer",
            "core": "#core-epoch-observer",
            "headInput": "#head-input-observer",
            "head": "#head-epoch-observer",
        }
        observers = {
            name: query(cdp, selector) for name, selector in observer_selectors.items()
        }
        compact = all(observers.values())
        capture = query(cdp, "#capture-epoch-observer")
        if capture:
            observers["capture"] = capture
        report["retainedCaptureObserver"] = bool(capture)
        report["observer"] = (
            "small native geometry" if compact else "computed properties"
        )
        report["milestones"] = []
        seen = set()
        if quiet:
            time.sleep(quiet)
        deadline = time.monotonic() + limit
        previous = None
        while time.monotonic() < deadline:
            if compact:
                heads = [0, 0]
                input_ready = False
                for name, n in observers.items():
                    if name == "head" and not input_ready:
                        continue
                    try:
                        box = cdp.command("DOM.getBoxModel", {"nodeId": n})["model"][
                            "content"
                        ]
                        epoch = round((box[2] - box[0]) / (64 if name == "core" else 1))
                    except RuntimeError as exc:
                        if "Could not compute box model" not in str(exc):
                            raise
                        epoch = 0
                        box = [0] * 8
                    if epoch and (name, epoch) not in seen:
                        seen.add((name, epoch))
                        report["milestones"].append(
                            {
                                "stage": name,
                                "epoch": epoch,
                                "milliseconds": (time.perf_counter() - started) * 1000,
                            }
                        )
                    if name == "headInput":
                        input_ready = epoch > 0
                    if name == ("capture" if capture else "head"):
                        heads = [epoch, round(box[5] - box[1])]
                if not input_ready and not (capture and heads[0] > 0):
                    time.sleep(0.1)
                    continue
                # Do not enumerate tens of thousands of inherited properties
                # while a long core calculation is still in flight.
                if (
                    previous
                    and str(heads[0]) == previous["headEpoch"]
                    and str(heads[1]) == previous["winner"]
                    and heads[0] < capacity
                    and heads[1] != 50256
                ):
                    time.sleep(0.1)
                    continue
            values = props(cdp, node)
            tokens = [
                float(values.get(f"--saved-token-{i}", -999))
                for i in range(1, capacity + 1)
            ]
            state = {
                "epoch": values.get("--epoch"),
                "headEpoch": str(heads[0])
                if compact and capture
                else values.get("--head-output-epoch"),
                "winner": str(heads[1])
                if compact and capture
                else values.get("--winner"),
                "tokens": tokens,
            }
            eos = query(cdp, "#eos-done.done") != 0
            completed = query(cdp, f"#token-{capacity}-captured.done") != 0 or eos
            if state != previous or completed:
                if (
                    quality_readback
                    and heads[0] > 0
                    and not any(
                        row["position"] == heads[0]
                        for row in report.get("qualitySamples", [])
                    )
                ):
                    held = props(cdp, query(cdp, ".head-input-bank"))
                    if round(float(held["--head-input-epoch"])) == heads[0]:
                        report.setdefault("qualitySamples", []).append(
                            {
                                "position": heads[0],
                                "nativeWinner": heads[1],
                                "hidden": [float(held[f"--h{i}"]) for i in range(768)],
                            }
                        )
                state["milliseconds"] = (time.perf_counter() - started) * 1000
                state["metrics"] = metrics(cdp)
                report["samples"].append(state)
                print({k: v for k, v in state.items() if k != "metrics"}, flush=True)
                previous = {
                    k: v
                    for k, v in state.items()
                    if k not in ("milliseconds", "metrics")
                }
                artifact("pipeline-results.json").write_text(
                    json.dumps(report, indent=2)
                )
            if completed:
                report["complete"] = True
                report["totalMilliseconds"] = (time.perf_counter() - started) * 1000
                report["stopReason"] = "eos" if eos else "token-limit"
                break
            time.sleep(0.1)
        else:
            report["complete"] = False
        # Freeze the timing-window memory report before numerical readbacks.
        report["memorySamples"] = list(memory.samples)
        report["sampledPeak"] = {
            key: max(row[key] for row in memory.samples)
            for key in ("rendererRssMiB", "browserTreeRssMiB")
        }
        selectors = [
            "body",
            ".feedback-select",
            ".embedding-receipt",
            "#block-0",
            ".input-ready",
            "#core-result",
            ".head-input-bank",
            ".head-group-state",
            "#head-result",
            ".font-status",
            "#fonts-loaded",
            ".loop-input",
            ".core-controller",
            ".reused-input",
            ".shared-qkv-receipt",
            ".shared-proj-receipt",
        ]
        report["diagnostics"] = {}
        for selector in selectors:
            n = query(cdp, selector)
            if n:
                p = props(cdp, n)
                report["diagnostics"][selector] = {
                    k: v
                    for k, v in p.items()
                    if k
                    in (
                        "width",
                        "height",
                        "content-visibility",
                        "--epoch",
                        "--token",
                        "--bridge-ready",
                        "--embed-ready",
                        "--head-input-epoch",
                        "--head-output-epoch",
                        "--winner",
                        "--head-group-index",
                        "--head-max-score",
                        "--pass",
                        "--native-pass",
                        "--position",
                        "--layer",
                        "--loop-ready",
                        "--loop-ack",
                        "--gate-qkv",
                        "--gate-proj",
                        "container-name",
                    )
                }
        artifact("pipeline-results.json").write_text(json.dumps(report, indent=2))
        if report["complete"] and not manifest.get("synthetic"):
            screenshot = cdp.command("Page.captureScreenshot", {"format": "png"})
            artifact("screenshot.png").write_bytes(base64.b64decode(screenshot["data"]))
            verification = {
                "tokens": tokens[
                    : next(
                        (i for i, token in enumerate(tokens) if token < 0), len(tokens)
                    )
                ],
                "prompt": round(
                    float(props(cdp, query(cdp, ".feedback-reader"))["--frozen-prompt"])
                ),
                "finalResidual": read_vector(cdp, query(cdp, "#core-result"), "x", 768),
            }
            values = props(cdp, query(cdp, ".head-input-bank"))
            verification["finalHidden"] = [float(values[f"--h{i}"]) for i in range(768)]
            verification["caches"] = []
            # Inactive geometry banks have no layout boxes. Do not awaken or
            # replay them for readback: component retention tests are separate.
            geometry_cache = manifest.get("cacheCodec") == "geometry"
            verification["cacheReadbackScope"] = (
                "not read: inactive remembered-layout banks have no boxes"
                if geometry_cache
                else "all retained native cache slots"
            )
            for layer in range(0 if geometry_cache else manifest["blocks"]):
                from browser_gpt2_font_vector_cache import cache_slot

                bank_class = (
                    "fvs-bank"
                    if manifest.get("cacheCodec") == "font-vector"
                    else "kv-bank"
                )
                bank = query(cdp, f'.{bank_class}[data-layer="{layer}"]')
                bank_values = props(cdp, bank) if bank else None
                slots = manifest.get("kvWindow", capacity)
                retained_positions = {
                    cache_slot(p, slots, manifest.get("kvSinks", 0)): p
                    for p in range(len(verification["tokens"]))
                }
                for slot, position in sorted(retained_positions.items()):
                    values = (
                        bank_values
                        if bank_values is not None
                        else props(
                            cdp, query(cdp, f'.kv-slot-{slot}[data-layer="{layer}"]')
                        )
                    )
                    verification["caches"].append(
                        {
                            "layer": layer,
                            "slot": slot,
                            "position": position,
                            "values": decode_cache(
                                values,
                                slot,
                                manifest.get("cacheCodec", "scalar"),
                                active=slot == len(verification["tokens"]) - 1
                                and (
                                    manifest.get("coreBackend") != "reused"
                                    or layer == manifest["blocks"] - 1
                                ),
                            ),
                        }
                    )
            artifact("verification-vectors.json").write_text(json.dumps(verification))
    print("Complete:", report["complete"], flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=OUT)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--limit", type=int, default=900)
    parser.add_argument("--quiet-seconds", type=int, default=0)
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--report-prefix", default="")
    parser.add_argument(
        "--quality-readback",
        action="store_true",
        help="Read retained head inputs after each token for offline quality scoring; never feeds inference",
    )
    parser.add_argument(
        "--heap-growth-percent", type=int, choices=(0, 10, 25, 50, 100), default=0
    )
    args = parser.parse_args()
    directory = args.directory.resolve()
    if args.synthetic:
        synthetic(directory)
    run(
        directory,
        args.limit,
        args.quiet_seconds,
        args.http,
        args.start,
        args.heap_growth_percent,
        args.report_prefix,
        args.quality_readback,
    )


if __name__ == "__main__":
    main()
