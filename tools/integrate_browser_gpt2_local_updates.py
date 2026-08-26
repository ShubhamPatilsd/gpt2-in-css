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
import math
import platform
import re
import statistics
import subprocess
import sys
import time
import traceback
from contextlib import ExitStack, contextmanager
from itertools import pairwise
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

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
    "browser_gpt2_saved_run.py",
    "browser_gpt2_embedding.py",
    "browser_gpt2_head.py",
    "build_gpt2_block_css.py",
    "analyze_full_gpt2.py",
    "probe_browser_native_compute.py",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def phase_sources(directory, phase, experiment):
    """Archive each execution phase without overwriting compile-time evidence."""
    relative = f"sources-{phase}-{uuid4().hex[:12]}"
    archive = directory / relative
    archive.mkdir()
    for name in (
        "experiment.json",
        "integration-summary.json",
        "numerical-results.json",
    ):
        previous = directory / name
        if previous.exists():
            (archive / ("previous-" + name)).write_bytes(previous.read_bytes())
    paths = {ROOT / "tools" / name for name in SOURCES}
    for module in tuple(sys.modules.values()):
        location = getattr(module, "__file__", None)
        if location:
            source = Path(location).resolve()
            if source.suffix == ".py" and source.parent == ROOT / "tools":
                paths.add(source)
    hashes = {}
    for source in sorted(paths):
        target = archive / source.name
        target.write_bytes(source.read_bytes())
        hashes[source.name] = sha(target)
    compiled = experiment.get("sourceHashes", {})
    record = {
        "archive": relative,
        "sourceHashes": hashes,
        "changedSinceCompilation": {
            name: {"compiled": compiled[name], "phase": value}
            for name, value in hashes.items()
            if name in compiled and compiled[name] != value
        },
        "pythonVersion": sys.version,
        "platform": platform.platform(),
        "scope": "On-disk sources at phase entry, including loaded local modules. Separate compile/run/verify revisions are recorded, not treated as artifact drift.",
    }
    experiment.setdefault("phaseSources", {}).setdefault(phase, []).append(record)
    save(archive / "source-manifest.json", record)
    return record


def vector_is_finite(values, width):
    return (
        isinstance(values, list)
        and len(values) == width
        and all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in values
        )
    )


def verification_shape(actual, manifest, report):
    """Check complete coverage before a verifier can silently accept a subset."""
    from browser_gpt2_font_vector_cache import cache_slot

    tokens = actual.get("tokens", [])
    valid_tokens = (
        vector_is_finite(tokens, len(tokens))
        and 0 < len(tokens) <= manifest["capacity"]
        and all(value == int(value) and 0 <= value < 50257 for value in tokens)
    )
    stopped_correctly = bool(valid_tokens) and (
        len(tokens) == manifest["capacity"]
        if report.get("stopReason") == "token-limit"
        else report.get("stopReason") == "eos" and tokens[-1] == 50256
    )
    slots = manifest.get("kvWindow") or manifest["capacity"]
    positions = {
        cache_slot(position, slots, manifest.get("kvSinks", 0)): position
        for position in range(len(tokens))
    }
    expected = {
        (layer, slot, position)
        for layer in range(manifest["blocks"])
        for slot, position in positions.items()
    }
    caches = actual.get("caches", [])
    observed = [
        (row.get("layer"), row.get("slot"), row.get("position", row.get("slot")))
        for row in caches
    ]
    checks = {
        "validTokenPrefix": bool(valid_tokens),
        "terminationMatchesTokenPrefix": stopped_correctly,
        "finiteResidual768": vector_is_finite(actual.get("finalResidual"), 768),
        "finiteHidden768": vector_is_finite(actual.get("finalHidden"), 768),
        "cacheCoverage": len(observed) == len(expected) and set(observed) == expected,
        "finiteCacheVectors1536": all(
            vector_is_finite(row.get("values"), 1536) for row in caches
        ),
    }
    return {
        "checks": checks,
        "expectedCacheCount": len(expected),
        "observedCacheCount": len(observed),
        "passed": all(checks.values()),
    }


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
            if blocks == 12
            else f"Truncated {blocks}-layer model, native autoregressive feedback, all 50257 vocabulary rows"
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
        phase_sources(directory, "compile", experiment)
        with ExitStack() as stack:
            dense_stats = stack.enter_context(dense_compile_variant(dense))
            owned = (
                stack.enter_context(install_native_attention(value_layout="widths"))
                if attention == "owned"
                else None
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
            "attention": attention,
            "dense": dense,
            "head": head,
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

    with (
        patch.object(observer, "query", cache_query),
        patch.object(observer, "props", cache_props),
    ):
        yield


def run_case(directory, limit, quiet):
    path = directory / "experiment.json"
    experiment = json.loads(path.read_text())
    if (directory / "pipeline-results.json").exists():
        raise FileExistsError(f"Preserving existing measurement: {directory}")
    experiment["measurement"] = {
        "limitSeconds": limit,
        "quietSecondsAfterObserverSetup": quiet,
        "browserArguments": ["--js-flags=--heap-growing-percent=10"],
        "cacheReadback": (
            "After generation: actual own-head fields from all twelve banks per layer"
            if experiment["attention"] == "owned"
            else "After generation: original retained native cache banks"
        ),
    }
    save(path, experiment)
    started = time.perf_counter()
    try:
        phase_sources(directory, "run", experiment)
        for name, expected in experiment["artifactHashes"].items():
            if sha(directory / name) != expected:
                raise ValueError(f"Artifact changed after compilation: {name}")
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
    result = {
        "complete": False,
        "passed": False,
        "totalSeconds": None,
        "lastObservedSampleSeconds": None,
        "timingScope": "Observed native capture intervals; continuing and terminal intervals are separate, with no exclusive stage attribution",
    }
    started = time.perf_counter()
    try:
        phase_sources(directory, "verify", experiment)
        report = json.loads((directory / "pipeline-results.json").read_text())
        manifest = json.loads((directory / "manifest.json").read_text())
        result.update(
            complete=report.get("complete", False),
            sampledPeak=report.get("sampledPeak"),
            externalWritesAfterNavigation=report.get("externalWritesAfterNavigation"),
            stopReason=report.get("stopReason"),
        )
        total = report.get("totalMilliseconds")
        if result["complete"] and total is not None:
            result["totalSeconds"] = total / 1000
        first = {}
        for row in report.get("samples", []):
            epoch = int(float(row.get("headEpoch") or 0))
            if epoch > 0:
                first.setdefault(epoch, row)
        epochs = sorted(first)
        result["observedTokenEpochs"] = epochs
        if first:
            result["lastObservedSampleSeconds"] = (
                max(row["milliseconds"] for row in first.values()) / 1000
            )
        result["warmIntervals"] = []
        for left, right in pairwise(epochs):
            if right != left + 1:
                continue
            terminal = (
                right == manifest["capacity"]
                or float(first[right].get("winner", -1)) == 50256
                or result["complete"]
                and right == epochs[-1]
            )
            result["warmIntervals"].append(
                {
                    "epoch": right,
                    "seconds": (
                        first[right]["milliseconds"] - first[left]["milliseconds"]
                    )
                    / 1000,
                    "terminal": terminal,
                    "kind": "terminal" if terminal else "continuing",
                }
            )
        continuing = [
            row["seconds"] for row in result["warmIntervals"] if not row["terminal"]
        ]
        terminal = [
            row["seconds"] for row in result["warmIntervals"] if row["terminal"]
        ]
        result["warmMedianSeconds"] = (
            statistics.median(continuing) if continuing else None
        )
        result["warmMedianScope"] = (
            "Continuing intervals only; null when no continuing interval was observed"
        )
        result["terminalIntervalsSeconds"] = terminal
        if result["complete"]:
            actual = json.loads((directory / "verification-vectors.json").read_text())
            shape = verification_shape(actual, manifest, report)
            result["verificationCoverage"] = shape
            if not shape["passed"]:
                raise ValueError(
                    f"Incomplete or nonfinite numerical readback: {shape['checks']}"
                )
            verify(directory)
            numerical = json.loads((directory / "numerical-results.json").read_text())
            result["numerical"] = numerical
            cache_errors = numerical["cacheErrors"]
            cache_rmse = [row["error"]["rmse"] for row in cache_errors]
            result["maximumCacheRmse"] = max(cache_rmse, default=None)
            residual = numerical["finalResidualError"]
            expected_count = shape["expectedCacheCount"]
            token_count = len(actual["tokens"])
            checks = {
                "tokenAgreement": len(numerical["tokenAgreement"]) == token_count
                and all(numerical["tokenAgreement"]),
                "headMatchesActualInput": numerical["finalHeadMatchesActualInput"]
                is True,
                "finiteResidualError768": residual.get("finite") == 768
                and isinstance(residual.get("rmse"), (int, float))
                and math.isfinite(residual["rmse"]),
                "cacheErrorCoverage": len(cache_errors) == expected_count,
                "finiteCacheErrors1536": all(
                    row["error"].get("finite") == 1536
                    and isinstance(row["error"].get("rmse"), (int, float))
                    and math.isfinite(row["error"]["rmse"])
                    for row in cache_errors
                ),
                "zeroExternalWrites": result["externalWritesAfterNavigation"] == 0,
            }
            # Predeclared before native runs: the preserved 12-layer baseline
            # has residual RMSE 0.02723 at c2 and 0.01831 at c4. Exact token/head
            # agreement is required separately from these absolute error bounds.
            checks["residualRmseBelow005"] = (
                checks["finiteResidualError768"] and residual["rmse"] < 0.05
            )
            checks["cacheRmseBelow001"] = checks["finiteCacheErrors1536"] and all(
                value < 0.01 for value in cache_rmse
            )
            result["correctnessChecks"] = checks
            result["passed"] = all(checks.values())
    except Exception as exc:  # noqa: BLE001 - Preserve every independent verifier failure.
        result["verificationException"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
        experiment["verifyException"] = result["verificationException"]
    finally:
        result["verificationSeconds"] = time.perf_counter() - started
        save(directory / "integration-summary.json", result)
        experiment["correctness"] = {
            "passed": result["passed"],
            "summary": "integration-summary.json",
            "requiredResidualRmseBelow": 0.05,
            "requiredCacheRmseBelow": 0.01,
            "requiredResidualAndHiddenWidth": 768,
            "requiredCacheVectorWidth": 1536,
            "requiredCacheCoverage": "Every retained position in every model layer, with no duplicates",
        }
        save(path, experiment)
    print(
        json.dumps(
            {
                "case": directory.name,
                "passed": result["passed"],
                "seconds": result["totalSeconds"],
            }
        ),
        flush=True,
    )
    return result["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("compile", "run", "verify", "all"), default="all"
    )
    parser.add_argument(
        "--attention", choices=("baseline", "owned"), default="baseline"
    )
    parser.add_argument("--dense", choices=VARIANTS, default="baseline")
    parser.add_argument("--head", choices=MODES, default="baseline")
    parser.add_argument("--blocks", type=int, choices=range(1, 13), default=12)
    parser.add_argument("--capacity", type=int, default=2)
    parser.add_argument("--label", required=True)
    parser.add_argument("--limit", type=float, default=300)
    parser.add_argument("--quiet", type=float, default=0)
    args = parser.parse_args()
    if (
        args.capacity < 1
        or args.limit <= 0
        or args.quiet < 0
        or not re.fullmatch(r"[A-Za-z0-9_-]+", args.label)
    ):
        parser.error("Require a simple unique label and valid positive bounds")
    directory = OUT / args.label
    if args.phase in ("compile", "all"):
        compile_case(
            directory, args.attention, args.dense, args.head, args.blocks, args.capacity
        )
    if args.phase in ("run", "all"):
        run_case(directory, args.limit, args.quiet)
    if args.phase in ("verify", "all"):
        return int(not verify_case(directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
