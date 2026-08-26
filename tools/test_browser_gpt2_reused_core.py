"""Observe native layer/token loops. No inputs or intermediate writes after load."""

import argparse
import json
import time
from pathlib import Path

from benchmark_browser_gpt2_memory import MemorySampler
from probe_native_value_latch import navigate, props
from profile_hybrid_twelve_block import browser, error, metrics, query, read_vector


def run(
    directory, limit=300, quiet=0, heap_growth_percent=0, report_name="results.json"
):
    reference = json.loads((directory / "reference.json").read_text())
    steps = reference["blocks"] * reference["capacity"]
    report = {
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "externalWritesAfterNavigation": 0,
        "scope": "teacher-forced native core; excludes vocabulary head",
        "milestones": [],
        "completed": False,
    }
    flags = (
        [f"--js-flags=--heap-growing-percent={heap_growth_percent}"]
        if heap_growth_percent
        else []
    )
    report["browserArguments"] = flags
    with browser(flags) as cdp, MemorySampler(cdp.browser_pid) as memory:
        report["browser"] = cdp.command("Browser.getVersion")
        started = time.perf_counter()
        observer = navigate(cdp, directory / "index.html", "#measurement")
        if quiet:
            time.sleep(quiet)
        deadline = time.monotonic() + limit
        seen = 0
        completed = False
        while time.monotonic() < deadline:
            box = cdp.command("DOM.getBoxModel", {"nodeId": observer})["model"][
                "content"
            ]
            step = round((box[2] - box[0]) / 64)
            if step != seen:
                row = {
                    "pass": step,
                    "milliseconds": (time.perf_counter() - started) * 1000,
                    "memory": memory.snapshot(),
                }
                report["milestones"].append(row)
                (directory / "progress.json").write_text(json.dumps(report, indent=2))
                print(row, flush=True)
                seen = step
                if step > 0 and step % reference["blocks"] == 0:
                    # Read the native retained bank, not a live producer that
                    # may already be starting the next pass. Reads never feed back.
                    bank = (step - 1) % 2
                    values = props(cdp, query(cdp, f".loop-bank-{bank}"))
                    if float(values[f"--saved-{bank}-768"]) == step:
                        actual = [
                            float(values[f"--saved-{bank}-{i}"]) for i in range(768)
                        ]
                        report.setdefault("tokenOutputs", []).append(
                            {
                                "position": step // reference["blocks"],
                                "values": actual,
                                "error": error(
                                    actual,
                                    reference["outputs"][
                                        step // reference["blocks"] - 1
                                    ],
                                ),
                            }
                        )
            if step == steps and query(cdp, f"#loop-captured-{steps}.done"):
                completed = True
                break
            time.sleep(0.05)
        report["completed"] = completed
        report["totalMilliseconds"] = (time.perf_counter() - started) * 1000
        report["rendererCounters"] = metrics(cdp)
        report["sampledPeak"] = {
            key: max(row[key] for row in memory.samples)
            for key in ("rendererRssMiB", "browserTreeRssMiB")
        }
        report["memorySamples"] = memory.samples
        output = query(cdp, "#reused-result")
        actual = read_vector(cdp, output, "out", 768)
        report["finalValues"] = actual
        report["finalError"] = error(actual, reference["outputs"][-1])
        report["passed"] = (
            completed
            and report["finalError"]["rmse"] is not None
            and report["finalError"]["rmse"] < 0.05
        )
        report["diagnostics"] = {}
        for selector in (
            "body",
            ".font-status",
            "#fonts-loaded",
            ".font-ready-gate",
            ".loop-input",
            ".reused-input",
            ".shared-qkv-receipt",
            ".cache-bridge-receipt",
            ".shared-attn-receipt",
            ".shared-fc-receipt",
            ".shared-proj-receipt",
            "#reused-result",
        ):
            node = query(cdp, selector)
            if node:
                values = props(cdp, node)
                report["diagnostics"][selector] = {
                    k: v
                    for k, v in values.items()
                    if k
                    in (
                        "--pass",
                        "--position",
                        "--layer",
                        "--epoch",
                        "--loop-ready",
                        "--loop-ack",
                        "--bridge-ready",
                        "--gate-qkv",
                        "--gate-attn",
                        "--gate-fc",
                        "--gate-proj",
                        "content-visibility",
                        "font-family",
                        "width",
                        "height",
                    )
                }
        if not completed:
            report["fontProofFailures"] = []
            for index in range(reference["fontFaces"]):
                proof = props(cdp, query(cdp, f".font-proof-{index}"))
                if proof["width"] != "1px":
                    report["fontProofFailures"].append(
                        {"index": index, "width": proof["width"]}
                    )
            print("font proofs", report["fontProofFailures"], flush=True)
        print(
            {
                k: v
                for k, v in report.items()
                if k
                in (
                    "completed",
                    "totalMilliseconds",
                    "sampledPeak",
                    "finalError",
                    "passed",
                    "diagnostics",
                )
            },
            flush=True,
        )
    (directory / report_name).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--limit", type=float, default=300)
    parser.add_argument("--quiet", type=float, default=0)
    parser.add_argument(
        "--heap-growth-percent", type=int, choices=(0, 10, 25, 50, 100), default=0
    )
    parser.add_argument("--report-name", default="results.json")
    args = parser.parse_args()
    run(
        args.directory.resolve(),
        args.limit,
        args.quiet,
        args.heap_growth_percent,
        args.report_name,
    )
