#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Compile, run, and verify isolated native-pipeline attention ablations.

The generated artifact uses native feedback, real model layers and the entire
vocabulary head. Python compiles, observes, and verifies; it never supplies
activations or scheduling ticks. Existing output directories are preserved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from browser_gpt2_runtime import compile_runtime
from browser_gpt2_scaling_variants import VARIANTS, replacement
from summarize_browser_gpt2_scaling import summarize
from test_browser_gpt2_runtime import run
from verify_browser_gpt2_runtime import verify

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2-scaling/native"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def compile_case(directory, variant, blocks, capacity):
    if directory.exists():
        raise FileExistsError(f"Preserving existing case: {directory}")
    directory.mkdir(parents=True)
    provenance = {
        "variant": variant,
        "options": asdict(VARIANTS[variant]),
        "blocks": blocks,
        "capacity": capacity,
        "scope": (
            "12-layer GPT-2 with native autoregressive feedback and full vocabulary head"
            if blocks == 12 else
            f"Truncated {blocks}-layer GPT-2 with native autoregressive feedback and full vocabulary head; not the full model"
        ),
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "sourceHashes": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in sorted((ROOT / "tools").glob("*.py"))
        },
        "gitHead": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "configuration": {
            "autostart": True,
            "isolate_head": True,
            "cache_layout": "flat",
            "cache_codec": "font-vector",
            "scoped_state": True,
            "reuse_core": True,
            "detached_output": True,
        },
        "notes": [
            "The attention compiler is replaced only inside a scoped unittest.mock.patch.",
            "Original compiler sources and previously generated demos are not modified.",
            "All existing model fonts are referenced in place; font assets are not copied.",
            "Capacity is both allocated KV capacity and native generated-token limit.",
            "Autoregressive input starts at prompt token 15496 (Hello).",
        ],
    }
    write_json(directory / "experiment.json", provenance)
    started = time.perf_counter()
    try:
        with patch("browser_gpt2_font_vector_cache.attention", replacement(variant)):
            compile_runtime(
                directory, blocks, capacity, **provenance["configuration"]
            )
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["scalingExperimentVariant"] = variant
        manifest["scalingExperimentOptions"] = asdict(VARIANTS[variant])
        # The patch changes this argument internally; record the effective value.
        manifest["valueLayout"] = "widths" if VARIANTS[variant].widths else "runs"
        write_json(manifest_path, manifest)
        markup = (directory / "index.html").read_text()
        if "<script" in markup.lower() or "script-src 'none'" not in markup:
            raise ValueError("Generated artifact did not pass the no-script check")
        provenance["compiled"] = True
        provenance["artifactHashes"] = {
            name: sha256(directory / name)
            for name in ("index.html", "runtime.css", "manifest.json")
        }
        provenance["artifactBytes"] = {
            name: (directory / name).stat().st_size
            for name in ("index.html", "runtime.css", "manifest.json")
        }
    except Exception as exc:
        provenance["compiled"] = False
        provenance["compileException"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        provenance["compileSeconds"] = time.perf_counter() - started
        write_json(directory / "experiment.json", provenance)
    return provenance


def run_case(directory, limit, quiet):
    path = directory / "experiment.json"
    experiment = json.loads(path.read_text())
    if (directory / "pipeline-results.json").exists():
        raise FileExistsError(f"Preserving existing measurement: {directory}")
    for name, expected in experiment["artifactHashes"].items():
        if sha256(directory / name) != expected:
            raise ValueError(f"Artifact changed since compile: {name}")
    experiment["measurement"] = {
        "limitSeconds": limit,
        "quietSecondsAfterObserverSetup": quiet,
        "browserArguments": ["--js-flags=--heap-growing-percent=10"],
        "observer": "Existing native runtime harness: small geometry observers via CDP, approximately 100ms polling, no JavaScript domains",
        "quietInterval": (
            "After navigation and resolving observer nodes, the harness sleeps without CDP calls. OS RSS sampling continues. The first observation after this interval only gives an upper bound on completion time."
            if quiet else "None; normal observation run"
        ),
        "timingCaveat": "Wall time includes navigation, font loading and CDP observation. Warm intervals are single-sequence token intervals, not an isolated stage timing.",
    }
    write_json(path, experiment)
    started = time.perf_counter()
    try:
        run(directory, limit=limit, quiet=quiet, heap_growth_percent=10)
        saved = json.loads((directory / "pipeline-results.json").read_text())
        experiment["completed"] = saved.get("complete", False)
    except Exception as exc:
        experiment["completed"] = False
        experiment["runException"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        experiment["harnessSecondsIncludingReadback"] = time.perf_counter() - started
        write_json(path, experiment)


def verify_case(directory):
    path = directory / "experiment.json"
    experiment = json.loads(path.read_text())
    saved = json.loads((directory / "pipeline-results.json").read_text())
    if saved.get("complete"):
        verify(directory)
        numerical = json.loads((directory / "numerical-results.json").read_text())
        experiment["correctness"] = {
            "completed": True,
            "allTokenIdsMatchQuantizedReference": all(numerical["tokenAgreement"]),
            "finalHeadMatchesActualInput": numerical["finalHeadMatchesActualInput"],
            "finalResidualError": numerical["finalResidualError"],
            "originalFloatAgreement": numerical.get("originalFloatAgreement"),
            "cacheSlotCountChecked": len(numerical["cacheErrors"]),
            "maximumCacheRmse": max(
                (row["error"]["rmse"] for row in numerical["cacheErrors"]),
                default=None,
            ),
            "caveat": "Reference is evaluated independently after the browser exits. Truncated-layer results cannot establish full-model quality; a short sequence cannot establish general model accuracy.",
        }
    else:
        experiment["correctness"] = {"completed": False, "verified": False}
    result = summarize(directory)
    result["experiment"] = {
        key: experiment[key] for key in ("variant", "scope", "measurement")
    }
    write_json(directory / "scaling-summary.json", result)
    write_json(path, experiment)
    print(json.dumps({"case": directory.name, "summary": result}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("compile", "run", "verify", "all"), default="all")
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=["baseline", "lean"])
    parser.add_argument("--blocks", type=int, choices=range(1, 13), default=2)
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--repeat", type=int, default=0)
    parser.add_argument("--limit", type=int, default=900)
    parser.add_argument("--quiet", type=float, default=0)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if args.capacity < 1 or args.repeat < 0 or args.quiet < 0:
        parser.error("capacity must be positive; repeat and quiet must be nonnegative")
    names = args.variants if args.repeat % 2 == 0 else args.variants[::-1]
    for variant in names:
        suffix = f"-quiet{args.quiet:g}" if args.quiet else ""
        directory = args.out.resolve() / f"{variant}-b{args.blocks}-c{args.capacity}-r{args.repeat}{suffix}"
        if args.phase in ("compile", "all"):
            compile_case(directory, variant, args.blocks, args.capacity)
        if args.phase in ("run", "all"):
            run_case(directory, args.limit, args.quiet)
        if args.phase in ("verify", "all"):
            verify_case(directory)


if __name__ == "__main__":
    main()
