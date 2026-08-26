#!/usr/bin/env python3
"""Measure direct-CSS versus flex/anchor attention reduction in Chromium.

Every generated page is HTML/CSS only.  The Python harness uses CDP DOM,
CSS, and Performance commands and never evaluates JavaScript.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random
import subprocess
import tempfile
import time
import urllib.request

from probe_browser_native_compute import CdpSocket, chrome_path, metric_map


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "flex-anchor-attention-scaling"
HEADS = 12
HEAD_WIDTH = 64
WIDTH = HEADS * HEAD_WIDTH
GEOMETRY_SCALE = 65_536
LENGTHS = (2, 8, 16, 32, 64)


def number(value: float) -> str:
    return f"{value:.10g}"


def fixture(length: int, backend: str) -> tuple[str, list[float]]:
    rng = random.Random(0xF1E0A + length)
    scores = [
        [rng.uniform(-4.0, 4.0) for _ in range(length)] for _ in range(HEADS)
    ]
    alternate_scores = [
        [rng.uniform(-4.0, 4.0) for _ in range(length)] for _ in range(HEADS)
    ]
    values = [
        [rng.uniform(-1.4, 1.4) for _ in range(WIDTH)] for _ in range(length)
    ]
    alternate_values = [
        [rng.uniform(-1.4, 1.4) for _ in range(WIDTH)] for _ in range(length)
    ]
    offsets = []
    for head in range(HEADS):
        start = head * HEAD_WIDTH
        stop = start + HEAD_WIDTH
        bound = max(
            abs(value)
            for state in (values, alternate_values)
            for source in state
            for value in source[start:stop]
        )
        offsets.append(bound + 0.01)

    variables = []
    alternate_variables = []
    for head in range(HEADS):
        for source in range(length):
            variables.append(f"--s-{head}-{source}:{number(scores[head][source])}")
            alternate_variables.append(
                f"--s-{head}-{source}:{number(alternate_scores[head][source])}"
            )
    for source in range(length):
        for index in range(WIDTH):
            variables.append(f"--v-{source}-{index}:{number(values[source][index])}")
            alternate_variables.append(
                f"--v-{source}-{index}:{number(alternate_values[source][index])}"
            )

    reducer_declarations = []
    registrations = []
    for head in range(HEADS):
        score_names = [f"var(--s-{head}-{source})" for source in range(length)]
        if backend == "css-typed-staged":
            registrations.append(
                f'@property --m-{head}'
                '{syntax:"<number>";inherits:true;initial-value:0}'
            )
        reducer_declarations.append(f"--m-{head}:max({','.join(score_names)})")
        if backend == "css-typed-staged":
            registrations.append(
                f'@property --d-{head}'
                '{syntax:"<number>";inherits:true;initial-value:1}'
            )
            for source in range(length):
                registrations.extend(
                    (
                        f'@property --e-{head}-{source}'
                        '{syntax:"<number>";inherits:true;initial-value:1}',
                        f'@property --p-{head}-{source}'
                        '{syntax:"<number>";inherits:true;initial-value:0}',
                    )
                )
                reducer_declarations.append(
                    f"--e-{head}-{source}:exp(var(--s-{head}-{source}) - "
                    f"var(--m-{head}))"
                )
            reducer_declarations.append(
                f"--d-{head}:calc("
                + " + ".join(
                    f"var(--e-{head}-{source})" for source in range(length)
                )
                + ")"
            )
            for source in range(length):
                reducer_declarations.append(
                    f"--p-{head}-{source}:calc(var(--e-{head}-{source})/"
                    f"var(--d-{head}))"
                )
        elif backend in ("css-prob", "css-typed-prob", "css-fused"):
            exponentials = [
                f"exp(var(--s-{head}-{source}) - var(--m-{head}))"
                for source in range(length)
            ]
            reducer_declarations.append(
                f"--d-{head}:calc({' + '.join(exponentials)})"
            )
            if backend in ("css-prob", "css-typed-prob"):
                for source, exponential in enumerate(exponentials):
                    if backend == "css-typed-prob":
                        registrations.append(
                            f'@property --p-{head}-{source}'
                            '{syntax:"<number>";inherits:true;initial-value:0}'
                        )
                    reducer_declarations.append(
                        f"--p-{head}-{source}:calc({exponential}/var(--d-{head}))"
                    )

    normalizers = []
    if backend == "flex-anchor":
        for head in range(HEADS):
            items = "".join(
                f'<i style="anchor-name:--p-{head}-{source};'
                f'flex-grow:exp(var(--s-{head}-{source}) - var(--m-{head}))"></i>'
                for source in range(length)
            )
            normalizers.append(f'<div class="normalizer">{items}</div>')

    readers = []
    expected = []
    for index in range(WIDTH):
        head = index // HEAD_WIDTH
        shifted = [score - max(scores[head]) for score in scores[head]]
        weights = [math.exp(score) for score in shifted]
        denominator = sum(weights)
        probabilities = [weight / denominator for weight in weights]
        context = sum(
            probabilities[source] * values[source][index]
            for source in range(length)
        )
        expected.append(GEOMETRY_SCALE * (offsets[head] + context))
        if backend in ("css-prob", "css-typed-prob", "css-typed-staged"):
            terms = " + ".join(
                f"var(--p-{head}-{source})*var(--v-{source}-{index})"
                for source in range(length)
            )
            width = (
                f"calc({GEOMETRY_SCALE}px*({number(offsets[head])} + {terms}))"
            )
        elif backend == "css-fused":
            terms = " + ".join(
                f"exp(var(--s-{head}-{source}) - var(--m-{head}))*"
                f"var(--v-{source}-{index})"
                for source in range(length)
            )
            width = (
                f"calc({GEOMETRY_SCALE}px*({number(offsets[head])} + "
                f"({terms})/var(--d-{head})))"
            )
        else:
            terms = " + ".join(
                f"({number(offsets[head])} + var(--v-{source}-{index}))*"
                f"anchor-size(--p-{head}-{source} width)"
                for source in range(length)
            )
            width = f"calc({terms})"
        readers.append(f'<i class="reader" style="width:{width}"></i>')

    html = f"""<!doctype html>
<meta charset="utf-8">
<style>
{''.join(registrations)}
html,body{{margin:0}}
body{{{';'.join(variables)}}}
body.alternate{{{';'.join(alternate_variables)}}}
.reducer{{position:relative;anchor-scope:all;{';'.join(reducer_declarations)}}}
.normalizer{{position:absolute;left:0;top:0;display:flex;width:{GEOMETRY_SCALE}px;height:1px}}
.normalizer>i{{display:block;flex-basis:0;flex-shrink:1;min-width:0;height:1px}}
.reader{{position:absolute;left:0;top:2px;display:block;height:1px}}
</style>
<div class="reducer">{''.join(normalizers)}{''.join(readers)}</div>
"""
    return html, expected


def median(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def summarize(actual: list[float], expected: list[float]) -> dict[str, float]:
    errors = [a - b for a, b in zip(actual, expected, strict=True)]
    decoded = [error / GEOMETRY_SCALE for error in errors]
    return {
        "maximumWidthErrorPixels": max(abs(error) for error in errors),
        "decodedRmse": math.sqrt(
            sum(error * error for error in decoded) / len(decoded)
        ),
        "decodedMaximumAbsoluteError": max(abs(error) for error in decoded),
    }


def profile(html_path: Path, expected: list[float], rounds: int = 5) -> dict:
    chrome = chrome_path()
    with tempfile.TemporaryDirectory(prefix="flex-attention-scale-") as profile_dir:
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
                "--remote-debugging-port=0",
                "--remote-allow-origins=*",
                f"--user-data-dir={profile_dir}",
                "--window-size=900,300",
                html_path.resolve().as_uri(),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            port_file = Path(profile_dir) / "DevToolsActivePort"
            deadline = time.perf_counter() + 30
            while not port_file.exists() and time.perf_counter() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Chromium exited before CDP became available")
                time.sleep(0.02)
            port = int(port_file.read_text().splitlines()[0])
            targets = json.load(
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=10)
            )
            target = next(item for item in targets if item.get("type") == "page")
            cdp = CdpSocket(target["webSocketDebuggerUrl"])
            cdp.connection.settimeout(240)
            try:
                cdp.command("DOM.enable")
                cdp.command("CSS.enable")
                cdp.command("Performance.enable")
                root = cdp.command("DOM.getDocument", {"depth": 1})["root"]["nodeId"]
                body = cdp.command(
                    "DOM.querySelector", {"nodeId": root, "selector": "body"}
                )["nodeId"]
                nodes = cdp.command(
                    "DOM.querySelectorAll", {"nodeId": root, "selector": ".reader"}
                )["nodeIds"]
                deadline = time.perf_counter() + 30
                while len(nodes) != WIDTH and time.perf_counter() < deadline:
                    time.sleep(0.02)
                    root = cdp.command("DOM.getDocument", {"depth": 1})["root"]["nodeId"]
                    body = cdp.command(
                        "DOM.querySelector", {"nodeId": root, "selector": "body"}
                    )["nodeId"]
                    nodes = cdp.command(
                        "DOM.querySelectorAll",
                        {"nodeId": root, "selector": ".reader"},
                    )["nodeIds"]
                if len(nodes) != WIDTH:
                    raise RuntimeError(f"expected {WIDTH} readers, found {len(nodes)}")
                widths = []
                for node in nodes:
                    quad = cdp.command("DOM.getBoxModel", {"nodeId": node})["model"][
                        "border"
                    ]
                    widths.append(max(quad[0::2]) - min(quad[0::2]))

                samples = []
                for round_index in range(rounds):
                    before = metric_map(cdp.command("Performance.getMetrics"))
                    started = time.perf_counter()
                    if round_index % 2:
                        cdp.command(
                            "DOM.removeAttribute", {"nodeId": body, "name": "class"}
                        )
                    else:
                        cdp.command(
                            "DOM.setAttributeValue",
                            {"nodeId": body, "name": "class", "value": "alternate"},
                        )
                    cdp.command("Page.getLayoutMetrics")
                    elapsed = (time.perf_counter() - started) * 1000
                    after = metric_map(cdp.command("Performance.getMetrics"))
                    samples.append(
                        {
                            "wallClockMilliseconds": elapsed,
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
                        }
                    )
                keys = (
                    "wallClockMilliseconds",
                    "recalcStyleMilliseconds",
                    "layoutMilliseconds",
                    "taskMilliseconds",
                )
                return {
                    "accuracy": summarize(widths, expected),
                    "warmMutationMedian": {
                        key: median([sample[key] for sample in samples]) for key in keys
                    },
                    "samples": samples,
                }
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backend",
        action="append",
        choices=(
            "css-prob",
            "css-typed-prob",
            "css-typed-staged",
            "css-fused",
            "flex-anchor",
        ),
        help="rerun only this backend and merge it into an existing results file",
    )
    parser.add_argument(
        "--length",
        action="append",
        type=int,
        choices=LENGTHS,
        help="rerun only this context length and merge it into existing results",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    chrome = chrome_path()
    version = subprocess.run(
        [str(chrome), "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    destination = OUT / "results.json"
    partial = args.backend is not None or args.length is not None
    report = json.loads(destination.read_text()) if partial and destination.exists() else {
        "browser": version,
        "runtimeJavaScript": False,
        "harnessJavaScriptEvaluation": False,
        "geometryScale": GEOMETRY_SCALE,
        "dimensions": WIDTH,
        "heads": HEADS,
        "results": {},
    }
    report["browser"] = version
    selected_lengths = tuple(args.length) if args.length else LENGTHS
    selected_backends = (
        tuple(args.backend)
        if args.backend
        else (
            "css-prob",
            "css-typed-prob",
            "css-typed-staged",
            "css-fused",
            "flex-anchor",
        )
    )
    for length in selected_lengths:
        report["results"].setdefault(str(length), {})
        for backend in selected_backends:
            html, expected = fixture(length, backend)
            html_path = OUT / f"attention-{length}-{backend}.html"
            html_path.write_text(html, encoding="utf-8")
            if "<script" in html.lower():
                raise RuntimeError(f"{html_path.name} contains a script element")
            result = profile(html_path, expected)
            result["htmlBytes"] = html_path.stat().st_size
            report["results"][str(length)][backend] = result
        if not all(
            backend in report["results"][str(length)]
            for backend in (
                "css-prob",
                "css-typed-prob",
                "css-typed-staged",
                "css-fused",
                "flex-anchor",
            )
        ):
            continue
        css_prob_time = report["results"][str(length)]["css-prob"][
            "warmMutationMedian"
        ]
        css_fused_time = report["results"][str(length)]["css-fused"][
            "warmMutationMedian"
        ]
        css_typed_time = report["results"][str(length)]["css-typed-prob"][
            "warmMutationMedian"
        ]
        css_staged_time = report["results"][str(length)]["css-typed-staged"][
            "warmMutationMedian"
        ]
        flex_time = report["results"][str(length)]["flex-anchor"][
            "warmMutationMedian"
        ]
        flex_time["wallClockRelativeToCssProb"] = (
            flex_time["wallClockMilliseconds"]
            / css_prob_time["wallClockMilliseconds"]
        )
        flex_time["recalcStyleRelativeToCssProb"] = (
            flex_time["recalcStyleMilliseconds"]
            / css_prob_time["recalcStyleMilliseconds"]
        )
        flex_time["wallClockRelativeToCssFused"] = (
            flex_time["wallClockMilliseconds"]
            / css_fused_time["wallClockMilliseconds"]
        )
        flex_time["recalcStyleRelativeToCssFused"] = (
            flex_time["recalcStyleMilliseconds"]
            / css_fused_time["recalcStyleMilliseconds"]
        )
        flex_time["wallClockRelativeToCssTypedProb"] = (
            flex_time["wallClockMilliseconds"]
            / css_typed_time["wallClockMilliseconds"]
        )
        flex_time["recalcStyleRelativeToCssTypedProb"] = (
            flex_time["recalcStyleMilliseconds"]
            / css_typed_time["recalcStyleMilliseconds"]
        )
        flex_time["wallClockRelativeToCssTypedStaged"] = (
            flex_time["wallClockMilliseconds"]
            / css_staged_time["wallClockMilliseconds"]
        )
        flex_time["recalcStyleRelativeToCssTypedStaged"] = (
            flex_time["recalcStyleMilliseconds"]
            / css_staged_time["recalcStyleMilliseconds"]
        )
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
