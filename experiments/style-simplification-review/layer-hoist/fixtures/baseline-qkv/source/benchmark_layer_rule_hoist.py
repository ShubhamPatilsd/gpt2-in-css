#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Matched real-layer rule-hoisting screen; never a full-token speed estimate.

Run compile, smoke, and timing under run_unconventional_isolated.py. The smoke
must pass before timing. Each browser has a fresh profile. Source weights,
inputs, demand, receipt protocol, and oracle thresholds are unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import statistics
from unittest.mock import patch

import browser_gpt2_dense_locality as locality
import probe_browser_gpt2_dense_stage_locality as dense

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/style-simplification-review/layer-hoist"
STAGES = ("qkv", "mlp")
VARIANTS = ("baseline", "layer-hoist")
SOURCE_FILES = [
    Path(__file__).name, "probe_browser_gpt2_dense_stage_locality.py",
    "browser_gpt2_dense_locality.py", "browser_gpt2_reused_core.py",
    "browser_gpt2_core.py", "browser_gpt2_runtime.py", "build_gpt2_block_css.py",
    "build_hybrid_twelve_block.py", "profile_hybrid_twelve_block.py",
    "probe_native_value_latch.py", "probe_browser_native_compute.py",
    "benchmark_browser_gpt2_memory.py", "analyze_full_gpt2.py",
    "run_unconventional_isolated.py",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def load(path):
    return json.loads(path.read_text())


def compile_all():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"layers": [0, 11], "cases": {}, "sources": {}}
    for name in SOURCE_FILES:
        manifest["sources"][name] = digest(ROOT / "tools" / name)
    for stage in STAGES:
        for variant in VARIANTS:
            directory = OUT / "fixtures" / f"{variant}-{stage}"
            calls = []
            original = locality.hoist_layer_rules

            def audited_hoist(css, layer, kind, known):
                result, removed = original(css, layer, kind, known)
                calls.append({"layer": layer, "kind": kind, "removed": removed,
                              "beforeSha256": hashlib.sha256(css.encode()).hexdigest(),
                              "afterSha256": hashlib.sha256(result.encode()).hexdigest(),
                              "known": [{"kind": k[0], "selector": k[1], "property": k[2], "value": v}
                                        for k, v in sorted(known.items())]})
                return result, removed

            with patch.object(locality, "hoist_layer_rules", audited_hoist):
                fixture = dense.compile_fixture(directory, variant, stage, [0, 11])
            source_dir = directory / "source"
            source_dir.mkdir()
            for name in SOURCE_FILES:
                shutil.copy2(ROOT / "tools" / name, source_dir / name)
            witnesses = load(directory / "font-witnesses.json")
            fonts = {path: digest(Path(path)) for path in sorted(witnesses)}
            save(directory / "font-hashes.json", fonts)
            save(directory / "hoist-audit.json", {
                "variant": variant,
                "allowedProperties": sorted(locality.HOISTABLE),
                "allOccurrencesMustHaveSameValue": True,
                "nativeReceiptGatesRemainConditional": True,
                "fontSettingsWeightsNumericalRulesRemainConditional": True,
                "calls": calls,
            })
            manifest["cases"][f"{variant}-{stage}"] = {
                "fixtureSamplesHash": object_hash(fixture["fixtureSamples"]),
                "sourceHashes": {n: digest(source_dir / n) for n in SOURCE_FILES},
                "artifactHashes": fixture["artifactHashes"],
                "fontHashes": fonts, "compileStats": fixture["compileStats"],
                "stylesheetBytes": (directory / "component.css").stat().st_size,
            }
            print(json.dumps({"compiled": f"{variant}-{stage}",
                              "stats": fixture["compileStats"]}), flush=True)
    for stage in STAGES:
        a, b = [manifest["cases"][f"{v}-{stage}"] for v in VARIANTS]
        assert a["fixtureSamplesHash"] == b["fixtureSamplesHash"]
        assert a["fontHashes"] == b["fontHashes"]
    assert manifest["sources"] == {n: digest(ROOT / "tools" / n) for n in SOURCE_FILES}, "Source changed during compilation"
    save(OUT / "manifest.json", manifest)


def verify_provenance(manifest):
    # Do not silently run artifacts through a harness that changed after compile.
    for name, sha in manifest["sources"].items():
        if digest(ROOT / "tools" / name) != sha:
            raise ValueError(f"Source changed after compile: {name}")
    checked = set()
    for key, case in manifest["cases"].items():
        directory = OUT / "fixtures" / key
        for name, sha in case["artifactHashes"].items():
            assert digest(directory / name) == sha
        for path, sha in case["fontHashes"].items():
            if path not in checked:
                assert digest(Path(path)) == sha
                checked.add(path)


def deadline(_signal, _frame):
    raise TimeoutError("Layer-hoist case exceeded the predeclared 180-second budget")


def one_case(phase, pair, stage, variant):
    original = OUT / "fixtures" / f"{variant}-{stage}"
    directory = OUT / phase / f"pair{pair}" / f"{variant}-{stage}"
    directory.mkdir(parents=True, exist_ok=False)
    for name in ("index.html", "component.css", "fixture.json", "font-hashes.json"):
        os.link(original / name, directory / name)
    fixture = load(original / "fixture.json")
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(180)
    try:
        result = dense.run_case(directory, fixture)
    finally:
        signal.alarm(0)
    return result


def compare_pair(phase, pair, stage):
    cases = {v: load(OUT / phase / f"pair{pair}" / f"{v}-{stage}" / "results.json") for v in VARIANTS}
    comparisons = []
    for a, b in zip(cases["baseline"]["samples"], cases["layer-hoist"]["samples"], strict=True):
        assert all(a[k] == b[k] for k in ("epoch", "layer", "position", "kind"))
        difference = dense.error(a["actual"], b["actual"])
        comparisons.append({"epoch": a["epoch"], "error": difference,
                            "passed": difference["maximum"] is not None and difference["maximum"] <= 1e-6})
    passed = all(c["passed"] for c in cases.values()) and len(comparisons) == 6 and all(c["passed"] for c in comparisons)
    result = {"phase": phase, "pair": pair, "stage": stage, "passed": passed,
              "maximumBaselineDifferenceLimit": 1e-6, "comparisons": comparisons}
    save(OUT / phase / f"pair{pair}" / f"comparison-{stage}.json", result)
    if not passed:
        raise RuntimeError(f"Preserved failed matched gate: {phase}/pair{pair}/{stage}")
    return result


def run_phase(phase):
    manifest = load(OUT / "manifest.json")
    verify_provenance(manifest)
    if phase == "timing":
        gate = load(OUT / "smoke" / "gate.json")
        assert gate["passed"] and gate["manifestSha256"] == digest(OUT / "manifest.json")
    pairs = [("baseline", "layer-hoist")] if phase == "smoke" else [
        ("baseline", "layer-hoist"), ("layer-hoist", "baseline")]
    comparisons = []
    for pair, order in enumerate(pairs):
        stages = STAGES if pair == 0 else tuple(reversed(STAGES))
        for stage in stages:
            for variant in order:
                result = one_case(phase, pair, stage, variant)
                if not result["passed"]:
                    raise RuntimeError(f"Preserved failed case: {phase}/pair{pair}/{variant}-{stage}")
            comparisons.append(compare_pair(phase, pair, stage))
    verify_provenance(manifest)
    save(OUT / phase / "gate.json", {"passed": all(x["passed"] for x in comparisons),
         "manifestSha256": digest(OUT / "manifest.json"), "pairs": pairs,
         "comparisons": comparisons, "scope": "Fresh isolated dense-stage browser profiles, not token generation"})


def summarize():
    manifest = load(OUT / "manifest.json")
    gate = load(OUT / "timing" / "gate.json")
    assert gate["passed"]
    rows = []
    for stage in STAGES:
        for pair in range(2):
            case_rows = {}
            for variant in VARIANTS:
                result = load(OUT / "timing" / f"pair{pair}" / f"{variant}-{stage}" / "results.json")
                assert result["passed"]
                groups = {"cold": result["samples"][:1], "fresh": result["samples"][1:4],
                          "revisit": result["samples"][4:], "warm": result["samples"][1:]}
                case_rows[variant] = {
                    "groups": {name: {"millisecondsMedian": statistics.median(s["milliseconds"] for s in samples),
                               "millisecondsSum": sum(s["milliseconds"] for s in samples),
                               "sampleCount": len(samples),
                               "rendererTotals": {metric: sum(s["rendererDelta"].get(metric, 0) for s in samples)
                                                  for metric in ("RecalcStyleDuration", "LayoutDuration", "TaskDuration", "RecalcStyleCount", "LayoutCount")}}
                               for name, samples in groups.items()},
                    "maxRmse": max(s["error"]["rmse"] for s in result["samples"]),
                    "maxAbsoluteError": max(s["error"]["maximum"] for s in result["samples"]),
                    "peak": result["sampledPeak"], "browser": result["browser"],
                }
            rows.append({"stage": stage, "pair": pair, "order": gate["pairs"][pair], "cases": case_rows})
    save(OUT / "summary.json", {"passed": True, "rows": rows,
         "compile": {k: {"stylesheetBytes": v["stylesheetBytes"], "stats": v["compileStats"]} for k, v in manifest["cases"].items()},
         "timingIncludes": "External raw input writes, native arithmetic and freshness receipt, weighted all-output CSS geometry consumer, geometry polling",
         "timingExcludes": "Post-timer all-coordinate oracle read, autonomous attention/KV, embeddings, vocabulary, native layer feedback",
         "pollingFloorMilliseconds": 75, "fullTokenExtrapolation": None})
    print(json.dumps(rows, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("compile", "smoke", "timing", "summarize"))
    args = parser.parse_args()
    if args.phase == "compile":
        compile_all()
    elif args.phase == "summarize":
        summarize()
    else:
        run_phase(args.phase)


if __name__ == "__main__":
    main()
