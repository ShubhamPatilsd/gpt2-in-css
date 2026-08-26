#!/usr/bin/env python3
"""Profile the script-free two-token attention reducer variants in Chromium.

The fixtures contain HTML/CSS/fonts only.  This harness uses the Chrome
DevTools Protocol's DOM, CSS, and Performance domains directly; it never
enables Runtime or evaluates JavaScript in the page.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

from probe_browser_native_compute import CdpSocket, chrome_path, metric_map


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-block-css"
VARIANTS = {
    "css": "view-timeline-attention-2token",
    "css-fused": "view-timeline-attention-2token-css-fused",
    "css-typed-staged": "view-timeline-attention-2token-css-typed-staged",
    "flex-prob": "view-timeline-attention-2token-flex-prob",
    "flex-anchor": "view-timeline-attention-2token-flex-anchor",
}


def summarize(actual: list[float], expected: list[float]) -> dict[str, float]:
    errors = [a - b for a, b in zip(actual, expected, strict=True)]
    return {
        "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "maximumAbsoluteError": max(abs(error) for error in errors),
    }


def median(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def launch(variant: str, rounds: int) -> dict:
    stem = VARIANTS[variant]
    html_path = OUT / f"{stem}.html"
    reference_path = OUT / f"{stem}-reference.json"
    html = html_path.read_text(encoding="utf-8")
    if "<script" in html.lower():
        raise RuntimeError(f"{html_path.name} unexpectedly contains a script element")
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    expected_context = [value for row in reference["context"] for value in row]
    expected_residual = [value for row in reference["residual"] for value in row]

    chrome = chrome_path()
    with tempfile.TemporaryDirectory(prefix=f"attention-{variant}-") as profile:
        process = subprocess.Popen(
            [
                str(chrome),
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
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            port_file = Path(profile) / "DevToolsActivePort"
            deadline = time.perf_counter() + 30
            while not port_file.exists() and time.perf_counter() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Chromium exited before opening its debugging port")
                time.sleep(0.02)
            if not port_file.exists():
                raise RuntimeError("Chromium did not open its debugging port")
            port = int(port_file.read_text().splitlines()[0])
            targets = json.load(
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=10)
            )
            target = next(item for item in targets if item.get("type") == "page")
            cdp = CdpSocket(target["webSocketDebuggerUrl"])
            cdp.connection.settimeout(240)
            try:
                cdp.command("Page.enable")
                cdp.command("DOM.enable")
                cdp.command("CSS.enable")
                cdp.command("Performance.enable")
                started = time.perf_counter()
                cdp.command("Page.navigate", {"url": html_path.resolve().as_uri()})

                result_node = 0
                body_node = 0
                while time.perf_counter() - started < 180:
                    try:
                        root = cdp.command("DOM.getDocument", {"depth": 1})["root"][
                            "nodeId"
                        ]
                        body_node = cdp.command(
                            "DOM.querySelector", {"nodeId": root, "selector": "body"}
                        )["nodeId"]
                        result_node = cdp.command(
                            "DOM.querySelector",
                            {"nodeId": root, "selector": "#attention-result"},
                        )["nodeId"]
                    except RuntimeError as error:
                        if "Could not find node with given id" not in str(error):
                            raise
                        body_node = 0
                        result_node = 0
                    if body_node and result_node:
                        break
                    time.sleep(0.02)
                if not result_node:
                    raise RuntimeError(f"{variant} did not produce #attention-result")

                settle_deadline = time.perf_counter() + 10
                while True:
                    computed_response = cdp.command(
                        "CSS.getComputedStyleForNode", {"nodeId": result_node}
                    )
                    computed = {
                        item["name"]: item["value"]
                        for item in computed_response["computedStyle"]
                    }
                    try:
                        settle_residual = [
                            float(computed[f"--r1-{token}-{index:03d}"])
                            for token in range(2)
                            for index in range(768)
                        ]
                    except (KeyError, ValueError):
                        settle_residual = []
                    if settle_residual and summarize(
                        settle_residual, expected_residual
                    )["rmse"] < 0.1:
                        break
                    if time.perf_counter() >= settle_deadline:
                        raise RuntimeError(f"{variant} did not settle to a valid residual")
                    cdp.command("Page.getLayoutMetrics")
                    time.sleep(0.02)
                navigation_ms = (time.perf_counter() - started) * 1000

                context = [
                    float(computed[f"--context-{token}-{index:03d}"])
                    for token in range(2)
                    for index in range(768)
                ]
                residual = [
                    float(computed[f"--r1-{token}-{index:03d}"])
                    for token in range(2)
                    for index in range(768)
                ]
                report = {
                    "navigationAndFirstReadMilliseconds": navigation_ms,
                    "context": summarize(context, expected_context),
                    "residual": summarize(residual, expected_residual),
                    "htmlBytes": html_path.stat().st_size,
                    "cssBytes": (OUT / f"{stem}.css").stat().st_size,
                    "containsScriptElement": False,
                }

                if variant not in ("css", "css-fused", "css-typed-staged"):
                    flex_nodes = cdp.command(
                        "DOM.querySelectorAll",
                        {"nodeId": root, "selector": ".flex-normalizer>i"},
                    )["nodeIds"]
                    widths = []
                    for node_id in flex_nodes:
                        quad = cdp.command("DOM.getBoxModel", {"nodeId": node_id})[
                            "model"
                        ]["border"]
                        widths.append(max(quad[0::2]) - min(quad[0::2]))
                    expected_widths = [
                        reference["probabilities"][1][head][source] * 65_536
                        for head in range(12)
                        for source in range(2)
                    ]
                    report["flexProbabilityWidthPixels"] = summarize(
                        widths, expected_widths
                    )
                    report["flexProbabilityWidthPixels"]["actual"] = widths
                    report["flexProbabilityWidthPixels"]["expected"] = expected_widths
                    reader_nodes = cdp.command(
                        "DOM.querySelectorAll",
                        {"nodeId": root, "selector": ".flex-reader"},
                    )["nodeIds"]
                    reader_widths = []
                    for node_id in reader_nodes:
                        quad = cdp.command("DOM.getBoxModel", {"nodeId": node_id})[
                            "model"
                        ]["border"]
                        reader_widths.append(max(quad[0::2]) - min(quad[0::2]))
                    if variant == "flex-prob":
                        reader_expected = expected_widths
                    else:
                        reader_expected = [
                            65_536
                            * (
                                reference["flex_value_offsets"][index // 64]
                                + reference["context"][1][index]
                            )
                            for index in range(768)
                        ]
                    report["readerWidthPixels"] = summarize(
                        reader_widths, reader_expected
                    )
                    if variant == "flex-prob":
                        decoded = [
                            float(computed[f"--prob-{head}-{source}"])
                            for head in range(12)
                            for source in range(2)
                        ]
                        expected = [
                            reference["probabilities"][1][head][source]
                            for head in range(12)
                            for source in range(2)
                        ]
                        report["decodedProbabilities"] = summarize(decoded, expected)
                        report["decodedProbabilities"]["actual"] = decoded
                        report["decodedProbabilities"]["expected"] = expected

                warm_samples = []
                for round_index in range(rounds):
                    before = metric_map(cdp.command("Performance.getMetrics"))
                    mutation_started = time.perf_counter()
                    if round_index % 2:
                        cdp.command(
                            "DOM.removeAttribute", {"nodeId": body_node, "name": "class"}
                        )
                    else:
                        cdp.command(
                            "DOM.setAttributeValue",
                            {
                                "nodeId": body_node,
                                "name": "class",
                                "value": "alternate",
                            },
                        )
                    forced = cdp.command(
                        "CSS.getComputedStyleForNode", {"nodeId": result_node}
                    )
                    elapsed = time.perf_counter() - mutation_started
                    after = metric_map(cdp.command("Performance.getMetrics"))
                    forced_map = {
                        item["name"]: item["value"] for item in forced["computedStyle"]
                    }
                    warm_samples.append(
                        {
                            "wallClockMilliseconds": elapsed * 1000,
                            "recalcStyleMilliseconds": 1000
                            * (
                                after.get("RecalcStyleDuration", 0)
                                - before.get("RecalcStyleDuration", 0)
                            ),
                            "layoutMilliseconds": 1000
                            * (
                                after.get("LayoutDuration", 0)
                                - before.get("LayoutDuration", 0)
                            ),
                            "taskMilliseconds": 1000
                            * (
                                after.get("TaskDuration", 0)
                                - before.get("TaskDuration", 0)
                            ),
                            "finiteProbe": math.isfinite(
                                float(forced_map["--r1-1-000"])
                            ),
                            "probe": float(forced_map["--r1-1-000"]),
                        }
                    )
                report["warmMutation"] = {
                    "rounds": rounds,
                    "median": {
                        key: median([sample[key] for sample in warm_samples])
                        for key in (
                            "wallClockMilliseconds",
                            "recalcStyleMilliseconds",
                            "layoutMilliseconds",
                            "taskMilliseconds",
                        )
                    },
                    "samples": warm_samples,
                }
                return report
            finally:
                cdp.close()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


def main() -> None:
    rounds = 7
    chrome = chrome_path()
    version = subprocess.run(
        [str(chrome), "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    report = {
        "browser": version,
        "runtimeJavaScript": False,
        "harnessJavaScriptEvaluation": False,
        "variants": {
            variant: launch(variant, rounds) for variant in VARIANTS
        },
    }
    baseline = report["variants"]["css"]["warmMutation"]["median"]
    for variant in ("flex-prob", "flex-anchor"):
        current = report["variants"][variant]["warmMutation"]["median"]
        current["wallClockRelativeToCss"] = (
            current["wallClockMilliseconds"] / baseline["wallClockMilliseconds"]
        )
        current["recalcStyleRelativeToCss"] = (
            current["recalcStyleMilliseconds"] / baseline["recalcStyleMilliseconds"]
        )
    destination = OUT / "view-timeline-attention-flex-reducers-chromium.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
