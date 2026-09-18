#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Real-weight, externally driven dense components; no runtime JavaScript."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

import browser_gpt2_reused_core as reused
import build_gpt2_block_css as block
import build_hybrid_twelve_block as hybrid
import numpy as np
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from benchmark_browser_gpt2_memory import MemorySampler
from browser_gpt2_core import layer_matrices, reference_sequence
from browser_gpt2_dense_locality import (
    VARIANTS,
    dense_compile_variant,
    private_registrations,
)
from browser_gpt2_runtime import font_barrier
from probe_native_value_latch import attribute, navigate
from profile_hybrid_twelve_block import browser, error, metrics, query, read_vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2-integration/dense"
W = 768
FIXTURE_CACHE = {}


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def fixtures(layers):
    """Reference-derived INPUTS for components; never full native inference."""
    key = tuple(layers)
    if key in FIXTURE_CACHE:
        return FIXTURE_CACHE[key]
    reference = reference_sequence([15496, 11], max(layers) + 1)
    tensors = SafeTensors(MODEL_PATH)
    result = {}
    for layer in layers:
        data, matrices, biases = layer_matrices(tensors, layer)
        qkv = np.asarray(reference["layers"][layer]["qkv"])
        q, k, v = np.split(qkv, 3, axis=1)
        cases = []
        for position in (0, 1):
            x = np.asarray(
                reference["inputs"][position]
                if layer == 0
                else reference["layers"][layer - 1]["out"][position]
            )
            scores = np.einsum(
                "hd,thd->ht",
                q[position].reshape(12, 64),
                k[: position + 1].reshape(-1, 12, 64),
            ) / 8
            weights = np.exp(scores - scores.max(axis=1, keepdims=True))
            weights /= weights.sum(axis=1, keepdims=True)
            context = np.einsum(
                "ht,thd->hd", weights, v[: position + 1].reshape(-1, 12, 64)
            ).reshape(W)
            residual = x + matrices[1].reconstructed @ context + biases[1]
            cases.append({"x": x, "r": residual})
        result[layer] = {"data": data, "matrices": matrices, "biases": biases, "cases": cases}
    FIXTURE_CACHE[key] = result
    return result


def oracle(stage, fixture, source):
    data, matrices, bias = fixture["data"], fixture["matrices"], fixture["biases"]
    if stage == "qkv":
        normalized = block.layer_norm(source, data["ln1_gamma"], data["ln1_beta"])
        return (matrices[0].reconstructed @ normalized + bias[0]).tolist()
    normalized = block.layer_norm(source, data["ln2_gamma"], data["ln2_beta"])
    hidden = block.gelu_new(matrices[2].reconstructed @ normalized + bias[2])
    return (source + matrices[3].reconstructed @ hidden + bias[3]).tolist()


def compile_fixture(directory, variant, stage, layers):
    if directory.exists():
        raise FileExistsError(f"Preserving existing fixture {directory}")
    directory.mkdir(parents=True)
    reference = fixtures(layers)
    source_stem, target_stem, count = ("x", "qkv", 3 * W) if stage == "qkv" else ("r", "out", W)
    kinds = ("ln1", "qkv") if stage == "qkv" else ("ln2", "fc", "proj")
    layouts = {}
    with dense_compile_variant(variant) as compile_stats:
        css = reused.shared_css(0, "flat", False)
        css += '@property --layer{syntax:"<number>";inherits:false;initial-value:0}'
        # Match the native reused core's private dense progress/receipt fields.
        progress = set()
        for kind, size in (("qkv", 3 * W), ("attn", W), ("fc", 4 * W), ("proj", W)):
            progress.update(hybrid.names(kind + "p", size))
            progress.update((f"--stamp-{kind}", f"--gate-{kind}"))
        css = private_registrations(css, progress)
        for layer in layers:
            data = reference[layer]["data"]
            matrices, biases = reference[layer]["matrices"], reference[layer]["biases"]
            for kind in kinds:
                if kind in ("ln1", "ln2"):
                    n = 1 if kind == "ln1" else 2
                    html, rule = hybrid.wrapper(
                        f"b{layer}-{kind}",
                        ";".join(block.norm_declarations(
                            "x" if n == 1 else "r", f"n{n}",
                            data[f"ln{n}_gamma"], data[f"ln{n}_beta"],
                            f"mean{n}", f"var{n}",
                        )),
                    )
                else:
                    index = ("qkv", "attn", "fc", "proj").index(kind)
                    stem, size = (("n1", W), ("ctx", W), ("n2", W), ("hidden", 4 * W))[index]
                    target = ("qkv", "r", "hidden", "out")[index]
                    html, rule = hybrid.matvec(
                        layer, kind, matrices[index], biases[index],
                        hybrid.names(stem, size), hybrid.names(target, len(biases[index])),
                        1, 512, compact=True, gated=True, dynamic_range=True,
                    )
                html, rule = reused.specialize(html, rule, layer, kind)
                if kind in layouts and layouts[kind] != html:
                    raise ValueError(f"Non-reusable {kind} layout")
                layouts[kind] = html
                css += rule
    receipt_kind = "qkv" if stage == "qkv" else "proj"
    checksum = " + ".join(f"var(--{target_stem}-{i:03d}) * {i % 11 + 1}" for i in range(count))
    inner = (
        '<div id="dense-result"><i id="dense-result-geometry" style="position:fixed;'
        f'left:0;top:-100px;width:calc(1048576px + ({checksum}) * 16px)"></i></div>'
    )
    for kind in reversed(kinds):
        inner = layouts[kind].replace("{child}", inner)
    css += (
        "@keyframes native-handshake{from{opacity:.99}to{opacity:1}}"
        ".fixture-model{content-visibility:hidden;contain-intrinsic-size:0px 0px}"
        "body:has(#fonts-loaded.done) .fixture-model{content-visibility:visible}"
        "#dense-result-geometry{height:0px}"
        f"@container shared-{receipt_kind}-receipt style(--gate-{receipt_kind}:1){{"
        "#dense-result-geometry{height:calc(var(--epoch)*64px)}}"
    )
    css = css.replace("-gate{display:none}", "-gate{content-visibility:hidden;contain-intrinsic-size:0px 0px}")
    css = css.replace("-gate{display:block}", "-gate{content-visibility:visible}")
    witnesses, witness_css, face_count = font_barrier(css, directory)
    css += witness_css
    sequence = [(p, layer) for p in (0, 1) for layer in layers] + [(1, layer) for layer in layers]
    samples = []
    for index, (position, layer) in enumerate(sequence):
        source = reference[layer]["cases"][position][source_stem]
        samples.append({
            "epoch": index + 1, "layer": layer, "position": position,
            "kind": "layer-revisit" if index >= 2 * len(layers) else "fresh-input",
            "input": source.tolist(), "expected": oracle(stage, reference[layer], source),
        })
    first = samples[0]
    initial = f"--epoch:1;--layer:{first['layer']};" + ";".join(
        f"--{source_stem}-{i:03d}:{value:.12g}" for i, value in enumerate(first["input"])
    )
    (directory / "component.css").write_text(css)
    (directory / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
        'content="script-src \'none\';object-src \'none\'"><link rel="stylesheet" href="component.css">'
        f'<body style="{initial}">{witnesses}<div class="fixture-model">{inner}</div></body>'
    )
    report = {
        "variant": variant, "stage": stage, "layers": layers,
        "sourceStem": source_stem, "targetStem": target_stem, "outputCount": count,
        "fontFaces": face_count, "compileStats": dict(compile_stats),
        "scope": "Externally supplied real reference-derived stage inputs; native dense arithmetic and receipts. Excludes autonomous embedding, attention/cache runtime and vocabulary feedback.",
        "inputSource": "Quantized GPT-2 reference inputs at tokens 15496 and 11, including actual token 2 causal attention for MLP residual inputs; repeated selected layers revisit their own inputs.",
        "sourceHashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            Path(__file__), ROOT / "tools/browser_gpt2_dense_locality.py",
            ROOT / "tools/build_hybrid_twelve_block.py", ROOT / "tools/browser_gpt2_reused_core.py",
            ROOT / "tools/browser_gpt2_core.py",
        ]},
        "artifactHashes": {n: hashlib.sha256((directory / n).read_bytes()).hexdigest() for n in ("index.html", "component.css")},
        "fixtureSamples": samples,
    }
    save(directory / "fixture.json", report)
    return report


def settle_geometry(cdp, node, epoch, limit=120):
    previous, stable, reads = None, 0, 0
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        try:
            box = cdp.command("DOM.getBoxModel", {"nodeId": node})["model"]["content"]
            current = (box[2] - box[0], box[5] - box[1])
        except RuntimeError as exc:
            if "Could not compute box model" not in str(exc):
                raise
            current = (float("nan"), 0)
        reads += 1
        ready = np.isfinite(current).all() and abs(current[1] - epoch * 64) < 0.01
        stable = stable + 1 if ready and previous == current else 0
        if stable >= 3:
            return reads
        previous = current
        time.sleep(0.025)
    raise TimeoutError(f"No stable native dense receipt at epoch {epoch}")


def run_case(directory, fixture):
    result = {**{k: v for k, v in fixture.items() if k != "fixtureSamples"},
              "samples": [], "runtimeJavaScript": False, "harnessJavaScript": False,
              "externalWritesAfterNavigation": 0,
              "measurementProtocol": "One checksum/fresh-epoch geometry box per poll, three stable25ms intervals; vector readback occurs after timing. Wall time includes CDP write/geometry reads, renderer counters captured before vector readback.",
              "oracleRmseLimit": 0.05, "baselineMaximumDifferenceLimit": 0.000001}
    baseline_path = directory.parent / directory.name.replace(fixture["variant"] + "-", "baseline-", 1) / "results.json"
    baseline = json.loads(baseline_path.read_text()) if fixture["variant"] != "baseline" and baseline_path.exists() else None
    try:
        with browser(["--js-flags=--heap-growing-percent=10"]) as cdp, MemorySampler(cdp.browser_pid) as memory:
            result["browser"] = cdp.command("Browser.getVersion")
            before = metrics(cdp)
            started = time.perf_counter()
            node = navigate(cdp, directory / "index.html", "#dense-result", limit=120)
            geometry = query(cdp, "#dense-result-geometry")
            body = query(cdp, "body")
            deadline = time.monotonic() + 120
            while not query(cdp, "#fonts-loaded.done"):
                if time.monotonic() > deadline:
                    raise TimeoutError("Native font barrier did not complete")
                time.sleep(0.05)
            for index, sample in enumerate(fixture["fixtureSamples"]):
                if index:
                    before = metrics(cdp)
                    started = time.perf_counter()
                    attribute(cdp, body, "style", f"--epoch:{sample['epoch']};--layer:{sample['layer']};" + ";".join(
                        f"--{fixture['sourceStem']}-{i:03d}:{value:.12g}" for i, value in enumerate(sample["input"])
                    ))
                    result["externalWritesAfterNavigation"] += 1
                reads = settle_geometry(cdp, geometry, sample["epoch"])
                elapsed = (time.perf_counter() - started) * 1000
                after = metrics(cdp)
                actual = read_vector(cdp, node, fixture["targetStem"], fixture["outputCount"])
                measured = error(actual, sample["expected"])
                row = {k: sample[k] for k in ("epoch", "layer", "position", "kind")}
                row.update(milliseconds=elapsed, reads=reads, error=measured, actual=actual,
                           rendererDelta={k: after[k] - before.get(k, 0) for k in after if k.endswith(("Duration", "Count"))})
                row["passed"] = measured["rmse"] is not None and measured["rmse"] < 0.05
                if baseline and len(baseline["samples"]) > index:
                    row["baselineError"] = error(actual, baseline["samples"][index]["actual"])
                    row["baselineEquivalent"] = row["baselineError"]["maximum"] is not None and row["baselineError"]["maximum"] <= 0.000001
                    row["passed"] = row["passed"] and row["baselineEquivalent"]
                result["samples"].append(row)
                save(directory / "results.json", result)
                print(json.dumps({"case": directory.name, **{k: v for k, v in row.items() if k not in ("actual", "rendererDelta")}}), flush=True)
                if not row["passed"]:
                    break
            result["sampledPeak"] = {k: max(s[k] for s in memory.samples) for k in ("rendererRssMiB", "browserTreeRssMiB")}
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        result["exception"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps({"case": directory.name, "exception": result["exception"]}), flush=True)
    result["passed"] = "exception" not in result and len(result["samples"]) == len(fixture["fixtureSamples"]) and all(s["passed"] for s in result["samples"])
    result["baselineComparisonAvailable"] = baseline is not None
    if len(result["samples"]) > 1:
        result["warmMedianMilliseconds"] = statistics.median(s["milliseconds"] for s in result["samples"][1:])
    save(directory / "results.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    component_variants = [name for name in VARIANTS if name not in ("loop-selective", "combined-loop")]
    parser.add_argument("--variants", nargs="+", choices=component_variants, default=component_variants)
    parser.add_argument("--stages", nargs="+", choices=("qkv", "mlp"), default=["qkv", "mlp"])
    parser.add_argument("--layers", nargs="+", type=int, default=[0, 11])
    parser.add_argument("--repeat", type=int, default=0)
    args = parser.parse_args()
    if not args.layers or min(args.layers) < 0 or max(args.layers) > 11:
        parser.error("Layers must be in 0..11")
    for stage in args.stages:
        for variant in args.variants:
            if stage == "qkv" and variant == "proj-settings":
                continue
            directory = OUT / f"{variant}-{stage}-l{'-'.join(map(str,args.layers))}-r{args.repeat}"
            try:
                fixture = compile_fixture(directory, variant, stage, args.layers)
            except (OSError, RuntimeError, ValueError) as exc:
                if directory.exists():
                    save(directory / "compile-failure.json", {
                        "variant": variant, "stage": stage, "layers": args.layers,
                        "exception": f"{type(exc).__name__}: {exc}",
                    })
                raise
            result = run_case(directory, fixture)
            if variant == "baseline" and not result["passed"]:
                raise SystemExit("Baseline component failed; preserve evidence and repair before continuing")


if __name__ == "__main__":
    main()
