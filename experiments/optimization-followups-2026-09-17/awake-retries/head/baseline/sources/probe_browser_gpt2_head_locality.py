#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Full-vocabulary locality ablations with externally supplied real head inputs.

Every vocabulary row is retained. Expected winners are used only by Python's
post-update checks and never appear in generated HTML/CSS. This is a component
experiment; native model integration is separate.
"""

import argparse
import hashlib
import json
import platform
import re
import statistics
import sys
import time
import traceback
from pathlib import Path
from urllib.parse import unquote, urlparse

from benchmark_browser_gpt2_memory import MemorySampler
from browser_gpt2_head_locality import MODES, transform_head
from browser_gpt2_head_receipts import split_head_receipt
from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, error, metrics, query
from test_browser_gpt2_components import wait_fonts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/browser-gpt2/head-two-pass"
OUT = ROOT / "experiments/browser-gpt2-integration/head"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def input_style(epoch, hidden):
    return f"--head-input-epoch:{epoch};" + ";".join(
        f"--h{i}:{float(value):.12g}" for i, value in enumerate(hidden)
    )


def compile_fixture(directory, mode):
    reference = json.loads((SOURCE / "reference.json").read_text())
    html, css = split_head_receipt(
        (SOURCE / "head-body.html").read_text(), (SOURCE / "head.css").read_text()
    )

    def asset(match):
        url = match[1]
        if urlparse(url).scheme:
            return match[0]
        return f'url("{(SOURCE / unquote(url)).resolve().as_uri()}")'

    css = re.sub(r'url\("([^\"]+)"\)', asset, css)
    html, css, metadata = transform_head(html, css, mode)
    css += (
        "#local-head-observer{position:fixed;left:-60000px;top:-60000px;"
        "display:block;width:calc(var(--head-output-epoch)*1px);"
        "height:calc(var(--winner)*1px)}"
    )
    if html.count("{child}") != 1:
        raise ValueError("Expected one head result child for the geometry observer")
    # A component input owner corresponds to the real runtime's retained bank.
    # Here Python supplies hidden vectors; no reference winner is embedded.
    html = (
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
        'content="script-src \'none\'"><link rel="stylesheet" href="head.css"><body>'
        '<div class="head-input-bank" style="'
        + input_style(1, reference["hidden"][0])
        + '">'
        + html.replace("{child}", '<i id="local-head-observer"></i>')
        + "</div></body>"
    )
    if "<script" in html.lower():
        raise ValueError("Unexpected page script")
    (directory / "index.html").write_text(html)
    (directory / "head.css").write_text(css)
    save(directory / "reference.json", reference)
    return reference, metadata


def settle_winner(cdp, node, epoch, limit):
    started = time.perf_counter()
    previous = None
    stable = 0
    reads = 0
    while time.perf_counter() - started < limit:
        box = cdp.command("DOM.getBoxModel", {"nodeId": node})["model"]["content"]
        actual = (round(box[2] - box[0]), round(box[5] - box[1]))
        reads += 1
        stable = stable + 1 if actual == previous else 0
        if actual[0] == epoch and stable >= 3:
            return actual, reads
        previous = actual
        time.sleep(0.03)
    raise TimeoutError(f"Head did not settle at epoch {epoch}; last result {previous}")


def run_case(directory, mode, repeat, limit):
    if directory.exists():
        raise FileExistsError(f"Preserving existing evidence: {directory}")
    directory.mkdir(parents=True)
    report = {
        "mode": mode,
        "repeat": repeat,
        "scope": "Externally supplied real hidden vectors, full 50257-row head; not native token throughput",
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "externalInputWrites": True,
        "externalInputWriteCount": 0,
        "timedObserver": "Two-number geometry witness; full style reads occur after timing",
        "browserArguments": ["--js-flags=--heap-growing-percent=10"],
        "pythonVersion": sys.version,
        "platform": platform.platform(),
        "samples": [],
        "passed": False,
    }
    save(directory / "results.json", report)
    try:
        reference, metadata = compile_fixture(directory, mode)
        report["rewrite"] = metadata
        sequence = [*range(1, len(reference["hidden"])), 0]
        report["requestedUpdates"] = len(sequence)
        sources = (
            Path(__file__),
            ROOT / "tools/browser_gpt2_head_locality.py",
            ROOT / "tools/browser_gpt2_head_receipts.py",
            ROOT / "tools/build_gpt2_groupwise_production_q16_sixfont.py",
            ROOT / "tools/profile_hybrid_twelve_block.py",
            ROOT / "tools/probe_native_value_latch.py",
            ROOT / "tools/benchmark_browser_gpt2_memory.py",
            ROOT / "tools/test_browser_gpt2_components.py",
        )
        (directory / "sources").mkdir()
        for path in sources:
            (directory / "sources" / path.name).write_bytes(path.read_bytes())
        report["sourceHashes"] = {
            str(path.relative_to(ROOT)): sha(path) for path in sources
        }
        report["sourceHeadHashes"] = {
            name: sha(SOURCE / name)
            for name in ("head-body.html", "head.css", "reference.json")
        }
        report["artifactHashes"] = {
            name: sha(directory / name)
            for name in ("index.html", "head.css", "reference.json")
        }
        with (
            browser(report["browserArguments"]) as cdp,
            MemorySampler(cdp.browser_pid) as memory,
        ):
            report["browser"] = cdp.command("Browser.getVersion")
            node = navigate(
                cdp, directory / "index.html", "#local-head-observer", limit=180
            )
            wait_fonts(cdp, '.head-row[data-token="0"]', 6)
            owner = query(cdp, ".head-input-bank")
            coarse_row = query(cdp, '.head-row[data-token="0"]')
            initial, _ = settle_winner(cdp, node, 1, limit)
            expected_first = reference["fixtures"][0]["q16BucketWinner"]
            report["initialCheck"] = {
                "actual": initial,
                "expected": [1, expected_first],
                "passed": initial == (1, expected_first),
            }
            if initial != (1, expected_first):
                raise ValueError(
                    f"Initial winner mismatch: {initial}, expected {expected_first}"
                )
            # All supplied fixture inputs, then a revisit of the first vector.
            for epoch, source_index in enumerate(sequence, start=2):
                hidden = reference["hidden"][source_index]
                before = metrics(cdp)
                started = time.perf_counter()
                attribute(cdp, owner, "style", input_style(epoch, hidden))
                report["externalInputWriteCount"] += 1
                actual, reads = settle_winner(cdp, node, epoch, limit)
                elapsed = (time.perf_counter() - started) * 1000
                after = metrics(cdp)
                retained = props(cdp, owner)
                received = [float(retained[f"--h{i}"]) for i in range(768)]
                row_state = props(cdp, coarse_row)
                leaked = [float(row_state[f"--h{i}"]) for i in range(768)]
                input_error = error(received, hidden)
                expected = reference["fixtures"][source_index]["q16BucketWinner"]
                correct = actual == (epoch, expected)
                row = {
                    "sourceIndex": source_index,
                    "epoch": epoch,
                    "winner": actual[1],
                    "actualEpoch": actual[0],
                    "expectedWinner": expected,
                    "milliseconds": elapsed,
                    "settlingReads": reads,
                    "rendererDelta": {
                        key: after[key] - value
                        for key, value in before.items()
                        if key in after
                    },
                    "inputError": input_error,
                    "rowRawInputMaximum": max(map(abs, leaked)),
                    "passed": correct
                    and input_error["rmse"] is not None
                    and input_error["rmse"] < 0.0001,
                }
                if mode == "private-inputs":
                    row["passed"] = row["passed"] and row["rowRawInputMaximum"] == 0
                report["samples"].append(row)
                save(directory / "results.json", report)
                print(
                    json.dumps(
                        {
                            "case": directory.name,
                            "epoch": epoch,
                            "ms": elapsed,
                            "passed": row["passed"],
                        }
                    ),
                    flush=True,
                )
                if not row["passed"]:
                    raise ValueError(
                        f"Head component validation failed at epoch {epoch}"
                    )
            report["memorySamples"] = list(memory.samples)
            report["peakRendererRssMiB"] = max(
                row["rendererRssMiB"] for row in report["memorySamples"]
            )
            report["domCounters"] = cdp.command("Memory.getDOMCounters")
            report["passed"] = len(report["samples"]) == report[
                "requestedUpdates"
            ] and all(row["passed"] for row in report["samples"])
            report["medianMilliseconds"] = statistics.median(
                row["milliseconds"] for row in report["samples"]
            )
    except Exception as exc:  # noqa: BLE001 - Preserve every compile/browser/numerical failure.
        report["exception"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
    save(directory / "results.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--repeat", type=int, default=0)
    parser.add_argument("--limit", type=float, default=120)
    parser.add_argument("--label", default="screen")
    args = parser.parse_args()
    if (
        args.repeat < 0
        or args.limit <= 0
        or not re.fullmatch(r"[a-zA-Z0-9_-]+", args.label)
    ):
        parser.error("Require nonnegative repeat, positive limit and a simple label")
    modes = args.modes if args.repeat % 2 == 0 else args.modes[::-1]
    failed = False
    for mode in modes:
        result = run_case(
            OUT / f"{args.label}-{mode}-r{args.repeat}", mode, args.repeat, args.limit
        )
        failed |= not result["passed"]
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
