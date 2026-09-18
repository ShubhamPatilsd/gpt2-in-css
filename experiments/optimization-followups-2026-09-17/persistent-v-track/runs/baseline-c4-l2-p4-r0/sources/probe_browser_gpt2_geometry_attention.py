"""Chromium remembered-KV attention against independent numeric references.

QKV inputs are externally supplied component fixtures. All cache retention,
dot products, stable softmax, and weighted V sums are computed in Chromium.
This is not an autonomous full-model timing.
"""

import argparse
import json
import re
import time
from pathlib import Path

import build_hybrid_twelve_block as hybrid
import numpy as np
from benchmark_browser_gpt2_memory import MemorySampler
from browser_gpt2_geometry_cache import attention, context_source, in_plane
from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, error, query, read_vector, settle
from test_browser_gpt2_components import wait_fonts

ROOT = Path(__file__).resolve().parents[1]


def compile_fixture(
    directory,
    capacity,
    heads,
    head_width,
    real_inputs,
    containment="strict",
    balanced=False,
    backend="geometry",
    kv_window=None,
    kv_sinks=0,
    font_backend="original",
    value_layout="runs",
    prewarm_values=False,
):
    width = heads * head_width
    if real_inputs:
        if (heads, head_width) != (12, 64):
            raise ValueError("Real model fixtures require 12 heads of width 64")
        ref = json.loads(real_inputs.read_text())
        inputs = np.asarray(ref["layers"][0]["qkv"][:capacity])
    else:
        inputs = np.random.default_rng(7391).normal(size=(capacity, 3 * width))
        inputs[:, width : 2 * width] *= 3
        inputs[:, 2 * width :] *= 5
    if len(inputs) != capacity:
        raise ValueError("Insufficient QKV input fixtures")
    references = []
    q, k, v = np.split(inputs, 3, axis=1)
    from browser_gpt2_core import attention_positions

    for position in range(capacity):
        retained = attention_positions(position, kv_window, kv_sinks)
        scores = np.einsum(
            "hd,thd->ht",
            q[position].reshape(heads, head_width),
            k[retained].reshape(-1, heads, head_width),
        ) / np.sqrt(head_width)
        weights = np.exp(scores - scores.max(axis=1, keepdims=True))
        weights /= weights.sum(axis=1, keepdims=True)
        references.append(
            np.einsum("ht,thd->hd", weights, v[retained].reshape(-1, heads, head_width))
            .reshape(width)
            .tolist()
        )
    source, receiver, bridge_css, _ = hybrid.bridge(100, 768)
    if backend == "font-vector":
        from browser_gpt2_font_vector_cache import attention as font_attention

        if (heads, head_width) != (12, 64):
            raise ValueError("Font-vector operator requires 12 heads of width 64")
        source, css, _ = font_attention(
            capacity,
            1,
            source,
            kv_window=kv_window,
            kv_sinks=kv_sinks,
            value_layout=value_layout,
            prewarm_values=prewarm_values,
        )
    else:
        if kv_window is not None or kv_sinks:
            raise ValueError("Bounded KV requires the font-vector backend")
        html, css, expressions = attention(
            capacity, heads, head_width, balanced=balanced
        )
        source = in_plane(
            context_source(source, expressions + ["0"] * (768 - width)), html
        )
    css += bridge_css
    if font_backend == "fontations":
        from browser_gpt2_font_backend import fontations_stylesheet

        css = fontations_stylesheet(css)
    css += hybrid.regs(
        hybrid.names("qkv", 3 * width)
        + hybrid.names("x", 768)
        + hybrid.names("bridge-p", 768)
        + ["--epoch", "--bridge-stamp", "--bridge-ready"]
    )
    css += "".join(
        f"@keyframes bridgek{i}{{from{{--bridge-p-{i:03d}:-2}}to{{--bridge-p-{i:03d}:1}}}}"
        for i in range(768)
    )
    css += "@keyframes bridgestamp{from{--bridge-stamp:0}to{--bridge-stamp:1}}"
    css = re.sub(r"524288 / var\((--bridge-p-\d+)\)", r"1572864 / (var(\1) + 2)", css)
    css += (
        "body{--epoch:1;--layer:0;container-name:runtime}"
        ".scroller{position:fixed;left:0;top:-60000px;height:1px;overflow-x:scroll;overflow-y:hidden;contain:strict;visibility:hidden}"
        ".track{position:relative;height:1px}.metric{position:absolute;left:0;top:0;height:1px}"
        "body{"
        + ";".join(f"--qkv-{i:03d}:{value:.12g}" for i, value in enumerate(inputs[0]))
        + "}"
    )
    css += f".scroller{{contain:{containment}}}"
    scopes = re.findall(r"html\{timeline-scope:([^}]+)\}", css)
    css += (
        "html{timeline-scope:"
        + ",".join(dict.fromkeys(t for group in scopes for t in group.split(",")))
        + "}"
    )
    page = (
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><link rel="stylesheet" href="attention.css"><body>'
        + source
        + receiver.replace(
            "{child}",
            '<div id="result"><i id="attention-ready" style="display:block;'
            'width:calc(var(--epoch)*64px);height:1px"></i></div>',
        )
        + "</body>"
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "attention.css").write_text(css)
    (directory / "index.html").write_text(page)
    return inputs, references


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--heads", type=int, default=1)
    parser.add_argument("--head-width", type=int, default=8)
    parser.add_argument("--real-inputs", type=Path)
    parser.add_argument("--balanced", action="store_true")
    parser.add_argument("--kv-window", type=int)
    parser.add_argument("--kv-sinks", type=int, default=0)
    parser.add_argument(
        "--value-layout", choices=("runs", "fallback", "widths"), default="runs"
    )
    parser.add_argument("--prewarm-values", action="store_true")
    parser.add_argument(
        "--font-backend", choices=("original", "fontations"), default="original"
    )
    parser.add_argument(
        "--backend", choices=("geometry", "font-vector"), default="geometry"
    )
    parser.add_argument(
        "--positions",
        type=int,
        help="Run only this many inputs while keeping the compiled capacity",
    )
    parser.add_argument(
        "--source-containment",
        choices=("strict", "none", "size", "layout", "paint"),
        default="strict",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments/browser-gpt2/geometry-attention-small",
    )
    args = parser.parse_args()
    width = args.heads * args.head_width
    if not 1 <= width <= 768:
        parser.error("Require 1–768 coordinates")
    if args.prewarm_values and (
        args.backend != "font-vector" or args.value_layout != "widths"
    ):
        parser.error("--prewarm-values requires --backend font-vector --value-layout widths")
    directory = args.output.resolve()
    inputs, reference = compile_fixture(
        directory,
        args.capacity,
        args.heads,
        args.head_width,
        args.real_inputs,
        args.source_containment,
        args.balanced,
        args.backend,
        args.kv_window,
        args.kv_sinks,
        args.font_backend,
        args.value_layout,
        args.prewarm_values,
    )
    report = {
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "scope": "Externally supplied QKV component test, not autonomous inference",
        "samples": [],
    }
    with (
        browser(["--js-flags=--heap-growing-percent=10"]) as cdp,
        MemorySampler(cdp.browser_pid) as memory,
    ):
        node = navigate(cdp, directory / "index.html", "#result", limit=180)
        report["browser"] = cdp.command("Browser.getVersion")
        body = query(cdp, "body")
        ready_node = query(cdp, "#attention-ready")
        cdp.external_observer = True
        if args.backend == "font-vector":
            wait_fonts(cdp, ".fvs-score-0-0", 1)
            wait_fonts(
                cdp,
                ".fvs-value-row" if args.value_layout == "fallback" else ".fvs-v-0-0",
                (args.kv_window or args.capacity)
                if args.value_layout == "fallback"
                else 1,
            )
        for position, qkv in enumerate(inputs[: args.positions]):
            begin = time.perf_counter()
            if position:
                attribute(
                    cdp,
                    body,
                    "style",
                    f"--epoch:{position + 1};"
                    + ";".join(
                        f"--qkv-{i:03d}:{value:.12g}" for i, value in enumerate(qkv)
                    ),
                )
            settle(
                cdp, node, "x", 768, limit=60,
                geometry_node=ready_node, generation=position + 1,
            )
            settle(cdp, node, "x", 768, limit=60)
            actual = read_vector(cdp, node, "x", width)
            row = {
                "position": position + 1,
                "milliseconds": (time.perf_counter() - begin) * 1000,
                "error": error(actual, reference[position]),
                "values": actual,
            }
            row["passed"] = (
                row["error"]["rmse"] is not None and row["error"]["rmse"] < 0.005
            )
            report["samples"].append(row)
            (directory / "progress.json").write_text(json.dumps(report, indent=2))
            print({k: v for k, v in row.items() if k != "values"}, flush=True)
            if not row["passed"]:
                report["diagnostics"] = {}
                for selector in (
                    ".geo-bank",
                    ".geo-slot-0",
                    ".geo-slot-0 .geo-latch",
                    ".geo-arithmetic",
                    '[style^="anchor-name:--geo-max-0;"]',
                    '[style^="anchor-name:--geo-weight-0-0;"]',
                    '[style^="anchor-name:--geo-den-0;"]',
                    ".b100-bridge-source .metric",
                    ".b100-bridge-c0",
                    ".b100-bridge-receipt",
                ):
                    found = query(cdp, selector)
                    if found:
                        report["diagnostics"][selector] = props(cdp, found)
                if args.backend == "font-vector":
                    for selector in (
                        ".fvs-bank",
                        ".fvs-score-0-0",
                        ".fvs-score-reader",
                        ".fvs-score-receipt",
                        ".fvs-softmax",
                        ".fvs-v-0-0",
                        ".fvs-value-row",
                        ".fvs-value-head-0",
                    ):
                        found = query(cdp, selector)
                        if found:
                            report["diagnostics"][selector] = props(cdp, found)
                break
        report["sampledPeak"] = {
            key: max(row[key] for row in memory.samples)
            for key in ("rendererRssMiB", "browserTreeRssMiB")
        }
        report["capacity"] = args.capacity
        report["kvWindow"] = args.kv_window or args.capacity
        report["kvSinks"] = args.kv_sinks
        report["testedPositions"] = args.positions or args.capacity
        report["balancedSums"] = args.balanced
        report["backend"] = args.backend
        report["fontBackend"] = args.font_backend
        report["valueLayout"] = args.value_layout
        report["prewarmValues"] = args.prewarm_values
        report["freshOutputGeometryRequired"] = True
        try:
            report["fontInstantiationHistogram"] = cdp.command(
                "Browser.getHistogram", {"name": "Blink.Fonts.VariableFontsRatio"}
            )
        except RuntimeError as exc:
            report["fontInstantiationHistogramUnavailable"] = str(exc)
        report["passed"] = len(report["samples"]) == (
            args.positions or args.capacity
        ) and all(row["passed"] for row in report["samples"])
    (directory / "results.json").write_text(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit("Native attention check failed; see results.json")


if __name__ == "__main__":
    main()
