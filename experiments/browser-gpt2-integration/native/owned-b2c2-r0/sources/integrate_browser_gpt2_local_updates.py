#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Compile and verify opt-in locality changes in the autonomous full pipeline.

All model arithmetic and the complete vocabulary remain browser-native. Each
case preserves its exact compiler sources and artifacts, including failures.
The owned-attention observer reads actual per-head banks after generation;
it supplies no activations, expected answers, or scheduling ticks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import statistics
import subprocess
import time
import traceback
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

import test_browser_gpt2_runtime as observer
from browser_gpt2_dense_locality import VARIANTS, dense_compile_variant
from browser_gpt2_head_locality import MODES, transform_head
from browser_gpt2_owned_attention import collect_cache_layer, install_native_attention
from browser_gpt2_runtime import compile_runtime
from verify_browser_gpt2_runtime import verify

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2-integration/native"
SOURCES = (
    "integrate_browser_gpt2_local_updates.py",
    "browser_gpt2_owned_attention.py",
    "browser_gpt2_dense_locality.py",
    "browser_gpt2_head_locality.py",
    "browser_gpt2_runtime.py",
    "browser_gpt2_reused_core.py",
    "browser_gpt2_reused_adapter.py",
    "browser_gpt2_font_vector_cache.py",
    "browser_gpt2_core.py",
    "browser_gpt2_head_receipts.py",
    "build_hybrid_twelve_block.py",
    "build_gpt2_groupwise_production_q16_sixfont.py",
    "test_browser_gpt2_runtime.py",
    "verify_browser_gpt2_runtime.py",
    "profile_hybrid_twelve_block.py",
    "probe_native_value_latch.py",
    "benchmark_browser_gpt2_memory.py",
    "decode_css_cache_diagnostic.py",
    "probe_native_reused_loop.py",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def compile_case(directory, attention, dense, head, blocks, capacity):
    if directory.exists():
        raise FileExistsError(f"Preserving existing case: {directory}")
    directory.mkdir(parents=True)
    archive = directory / "sources"
    archive.mkdir()
    for name in SOURCES:
        (archive / name).write_bytes((ROOT / "tools" / name).read_bytes())
    configuration = {
        "autostart": True,
        "isolate_head": True,
        "cache_layout": "flat",
        "cache_codec": "font-vector",
        "scoped_state": True,
        "reuse_core": True,
        "detached_output": True,
    }
    experiment = {
        "attention": attention,
        "dense": dense,
        "head": head,
        "blocks": blocks,
        "capacity": capacity,
        "configuration": configuration,
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "scope": (
            "Complete 12-layer GPT-2, native autoregressive feedback, all 50257 vocabulary rows"
            if blocks == 12 else
            f"Truncated {blocks}-layer model, native autoregressive feedback, all 50257 vocabulary rows"
        ),
        "sourceHashes": {name: sha(archive / name) for name in SOURCES},
        "gitHead": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "platform": platform.platform(),
        "notes": [
            "All changes are opt-in scoped compiler patches; original compilers are unchanged.",
            "Model fonts are referenced in place, not regenerated or copied.",
            "No post-navigation writes; independent reference evaluation follows browser exit.",
            "Wall time includes font loading and observer overhead; it is not an exclusive stage timing.",
        ],
        "compiled": False,
    }
    path = directory / "experiment.json"
    save(path, experiment)
    started = time.perf_counter()
    try:
        with ExitStack() as stack:
            dense_stats = stack.enter_context(dense_compile_variant(dense))
            owned = (
                stack.enter_context(install_native_attention(value_layout="widths"))
                if attention == "owned" else None
            )
            compile_runtime(directory, blocks, capacity, **configuration)
        experiment["denseRewrite"] = dense_stats
        if owned:
            if owned.artifact is None:
                raise ValueError("Owned attention was requested but never compiled")
            experiment["attentionRewrite"] = owned.artifact.metadata
        html_path, css_path = directory / "index.html", directory / "runtime.css"
        html, css, metadata = transform_head(
            html_path.read_text(), css_path.read_text(), head
        )
        if "<script" in html.lower() or "script-src 'none'" not in html:
            raise ValueError("Generated artifact failed the no-script guard")
        html_path.write_text(html)
        css_path.write_text(css)
        experiment["headRewrite"] = metadata
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["localUpdateExperiment"] = {
            "attention": attention, "dense": dense, "head": head,
        }
        if owned:
            manifest["valueLayout"] = "widths"
            manifest["attentionOwnership"] = owned.artifact.metadata
        save(manifest_path, manifest)
        experiment["artifactHashes"] = {
            name: sha(directory / name)
            for name in ("index.html", "runtime.css", "manifest.json")
        }
        experiment["artifactBytes"] = {
            name: (directory / name).stat().st_size
            for name in experiment["artifactHashes"]
        }
        experiment["compiled"] = True
    except Exception as exc:
        experiment["compileException"] = f"{type(exc).__name__}: {exc}"
        experiment["traceback"] = traceback.format_exc()
        raise
    finally:
        experiment["compileSeconds"] = time.perf_counter() - started
        save(path, experiment)


@contextmanager
def owned_cache_readback(capacity):
    """Adapt only the post-generation verification reads to split cache banks."""
    original_query, original_props = observer.query, observer.props
    bank_nodes = {}

    def cache_query(cdp, selector):
        match = re.fullmatch(r'\.fvs-bank\[data-layer="(\d+)"\]', selector)
        if match:
            layer = int(match[1])
            node = original_query(cdp, f".oa-bank-0-{layer}")
            if not node:
                raise ValueError(f"Missing actual owned cache bank for layer {layer}")
            bank_nodes[node] = layer
            return node
        return original_query(cdp, selector)

    def cache_props(cdp, node):
        if node in bank_nodes:
            return collect_cache_layer(cdp, bank_nodes[node], capacity)
        return original_props(cdp, node)

    with patch.object(observer, "query", cache_query), patch.object(observer, "props", cache_props):
        yield


def run_case(directory, limit, quiet):
    path = directory / "experiment.json"
    experiment = json.loads(path.read_text())
    if (directory / "pipeline-results.json").exists():
        raise FileExistsError(f"Preserving existing measurement: {directory}")
    for name, expected in experiment["artifactHashes"].items():
        if sha(directory / name) != expected:
            raise ValueError(f"Artifact changed after compilation: {name}")
    experiment["measurement"] = {
        "limitSeconds": limit,
        "quietSecondsAfterObserverSetup": quiet,
        "browserArguments": ["--js-flags=--heap-growing-percent=10"],
        "cacheReadback": (
            "After generation: actual own-head fields from all twelve banks per layer"
            if experiment["attention"] == "owned" else
            "After generation: original retained native cache banks"
        ),
    }
    save(path, experiment)
    started = time.perf_counter()
    try:
        with ExitStack() as stack:
            if experiment["attention"] == "owned":
                stack.enter_context(owned_cache_readback(experiment["capacity"]))
            observer.run(directory, limit=limit, quiet=quiet, heap_growth_percent=10)
        report = json.loads((directory / "pipeline-results.json").read_text())
        experiment["complete"] = report.get("complete", False)
        if report.get("externalWritesAfterNavigation") != 0:
            raise ValueError("Native execution unexpectedly received external writes")
    except Exception as exc:
        experiment["runException"] = f"{type(exc).__name__}: {exc}"
        experiment["traceback"] = traceback.format_exc()
        raise
    finally:
        experiment["harnessSecondsIncludingReadback"] = time.perf_counter() - started
        save(path, experiment)


def verify_case(directory):
    path = directory / "experiment.json"
    experiment = json.loads(path.read_text())
    report = json.loads((directory / "pipeline-results.json").read_text())
    result = {
        "complete": report.get("complete", False),
        "passed": False,
        "totalSeconds": report.get("totalMilliseconds", 0) / 1000,
        "sampledPeak": report.get("sampledPeak"),
        "externalWritesAfterNavigation": report.get("externalWritesAfterNavigation"),
        "timingScope": "Observed native token throughput; no exclusive stage attribution",
    }
    first = {}
    for row in report.get("samples", []):
        epoch = int(float(row.get("headEpoch") or 0))
        if epoch > 0:
            first.setdefault(epoch, row)
    epochs = sorted(first)
    result["warmIntervals"] = [
        {"epoch": right, "seconds": (first[right]["milliseconds"] - first[left]["milliseconds"]) / 1000}
        for left, right in zip(epochs, epochs[1:]) if right == left + 1
    ]
    intervals = [row["seconds"] for row in result["warmIntervals"]]
    result["warmMedianSeconds"] = statistics.median(intervals) if intervals else None
    if result["complete"]:
        verify(directory)
        numerical = json.loads((directory / "numerical-results.json").read_text())
        result["numerical"] = numerical
        cache_rmse = [row["error"]["rmse"] for row in numerical["cacheErrors"]]
        result["maximumCacheRmse"] = max(cache_rmse, default=None)
        result["passed"] = (
            bool(numerical["tokenAgreement"])
            and all(numerical["tokenAgreement"])
            and numerical["finalHeadMatchesActualInput"]
            # Predeclared before native runs: the preserved 12-layer baseline
            # has residual RMSE 0.02723 at c2 and 0.01831 at c4. Keep a separate
            # bounded error check; exact token/head agreement remains required.
            and numerical["finalResidualError"]["rmse"] < 0.05
            and bool(cache_rmse)
            and all(value is not None and value < 0.01 for value in cache_rmse)
            and result["externalWritesAfterNavigation"] == 0
        )
    save(directory / "integration-summary.json", result)
    experiment["correctness"] = {
        "passed": result["passed"],
        "summary": "integration-summary.json",
        "requiredResidualRmseBelow": 0.05,
        "requiredCacheRmseBelow": 0.01,
    }
    save(path, experiment)
    print(json.dumps({"case": directory.name, "passed": result["passed"], "seconds": result["totalSeconds"]}), flush=True)
    return result["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("compile", "run", "verify", "all"), default="all")
    parser.add_argument("--attention", choices=("baseline", "owned"), default="baseline")
    parser.add_argument("--dense", choices=VARIANTS, default="baseline")
    parser.add_argument("--head", choices=MODES, default="baseline")
    parser.add_argument("--blocks", type=int, choices=range(1, 13), default=12)
    parser.add_argument("--capacity", type=int, default=2)
    parser.add_argument("--label", required=True)
    parser.add_argument("--limit", type=float, default=300)
    parser.add_argument("--quiet", type=float, default=0)
    args = parser.parse_args()
    if args.capacity < 1 or args.limit <= 0 or args.quiet < 0 or not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        parser.error("Require a simple unique label and valid positive bounds")
    directory = OUT / args.label
    if args.phase in ("compile", "all"):
        compile_case(directory, args.attention, args.dense, args.head, args.blocks, args.capacity)
    if args.phase in ("run", "all"):
        run_case(directory, args.limit, args.quiet)
    if args.phase in ("verify", "all"):
        return int(not verify_case(directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
