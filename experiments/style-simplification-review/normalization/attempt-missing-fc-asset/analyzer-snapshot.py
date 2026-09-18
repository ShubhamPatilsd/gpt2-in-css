#!/usr/bin/env python3
"""Bounded offline gate for LayerNorm rearrangement with unchanged q9 fonts.

Run under run_unconventional_isolated.py with single-thread BLAS settings.
See the predeclared normalization/PROTOCOL.md; no browser or font mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from browser_gpt2_core import layer_matrices, reference_sequence
from build_gpt2_block_css import EPSILON
from build_pretrained_gpt2 import Gpt2Tokenizer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/style-simplification-review/normalization"
PROMPTS = ("The quick brown fox", "Paris is the capital of", "CSS can perform matrix multiplication")
LAYERS = (0, 5, 11)
AXIS_STEPS = 16384


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_sha(array):
    value = np.ascontiguousarray(array)
    return hashlib.sha256(str(value.dtype).encode() + str(value.shape).encode() + value.tobytes()).hexdigest()


def css_constants(array):
    return np.asarray([float(f"{v:.9f}") for v in array], dtype=np.float64)


def stats(error):
    return {"rmse": float(np.sqrt(np.mean(error * error))), "maxError": float(np.max(np.abs(error)))}


def stage_data(tensors, layer, boundary):
    data, matrices, biases = layer_matrices(tensors, layer)
    index, norm = (0, 1) if boundary == "qkv" else (2, 2)
    prefix = f"h.{layer}.{'attn.c_attn' if boundary == 'qkv' else 'mlp.c_fc'}"
    return dict(q=matrices[index], weight=np.asarray(tensors.tensor(prefix + ".weight"), dtype=np.float64).T,
                bias=biases[index], gamma=data[f"ln{norm}_gamma"], beta=data[f"ln{norm}_beta"])


def verify_fonts(layer, boundary, codes):
    if layer == 0:
        directory = ROOT / "experiments/gpt2-block-css"
        stem = "qkv-rowbase" if boundary == "qkv" else "fc-rowbase"
    elif boundary == "fc":
        directory = ROOT / f"experiments/gpt2-flat-12block-chain/layer{layer:02d}"
        stem = f"b{layer}-fc-rowbase"
    else:
        directory = ROOT / "experiments/hybrid-12block-profile/fonts"
        stem = f"b{layer}-qkv"
    verified = []
    for shard in range(3):
        path = directory / f"{stem}-s{shard}.woff2"
        with TTFont(path) as font:
            assert len(font["fvar"].axes) == 256
            assert {(a.minValue, a.defaultValue, a.maxValue) for a in font["fvar"].axes} == {(-1.0, 0.0, 1.0)}
            store = font["HVAR"].table.VarStore
            assert len(store.VarData) == 1
            var = store.VarData[0]
            sub = codes[:, shard * 256:(shard + 1) * 256]
            expected = np.stack((-sub, sub), axis=2).reshape(len(codes), 512)
            actual = np.asarray(var.Item, dtype=np.int16)
            assert actual.shape == (len(codes) + 1, 512)
            assert not np.any(actual[0])
            assert np.array_equal(actual[1:], expected[:, var.VarRegionIndex])
            for region_index, region in enumerate(store.VarRegionList.Region):
                for coordinate, axis in enumerate(region.VarRegionAxis):
                    expected_region = ((-1, -1, 0) if region_index % 2 == 0 else (0, 1, 1)) if coordinate == region_index // 2 else (0, 0, 0)
                    assert (axis.StartCoord, axis.PeakCoord, axis.EndCoord) == expected_region
            bases = np.abs(sub.astype(np.int64)).sum(axis=1) + 32
            assert np.array_equal([font["hmtx"][g][0] for g in font.getGlyphOrder()[1:]], bases)
        verified.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path), "codesAndBasesMatch": True})
    return verified


def gather_cases(tensors):
    cases, provenance = [], []
    for boundary, folder in (("qkv", "baseline-qkv-l0-11-r0"), ("fc", "baseline-mlp-l0-11-r1")):
        path = ROOT / "experiments/browser-gpt2-integration/dense" / folder / "fixture.json"
        fixture = json.loads(path.read_text())
        seen = set()
        for sample in fixture["fixtureSamples"]:
            key = (sample["layer"], sample["position"])
            if key in seen:
                continue
            seen.add(key)
            cases.append(dict(id=f"saved-{boundary}-l{key[0]}-p{key[1]}", layer=key[0], boundary=boundary,
                              position=key[1], prompt="Hello,", tokenIds=[15496, 11],
                              source="saved reference-derived dense fixture", x=np.asarray(sample["input"])))
        provenance.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path), uniqueCases=len(seen)))
    tokenizer = Gpt2Tokenizer(ROOT / "data/gpt2/vocab.json", ROOT / "data/gpt2/merges.txt")
    for prompt_index, prompt in enumerate(PROMPTS):
        tokens = tokenizer.encode(prompt)
        reference = reference_sequence(tokens, 12, quantized=True)
        for layer in LAYERS:
            _data, matrices, biases = layer_matrices(tensors, layer)
            qkv = np.asarray(reference["layers"][layer]["qkv"])
            q, k, v = np.split(qkv, 3, axis=1)
            for position in (0, len(tokens) - 1):
                x = np.asarray(reference["inputs"][position] if layer == 0 else reference["layers"][layer - 1]["out"][position])
                scores = np.einsum("hd,thd->ht", q[position].reshape(12, 64), k[:position + 1].reshape(-1, 12, 64)) / 8
                weights = np.exp(scores - scores.max(axis=1, keepdims=True))
                weights /= weights.sum(axis=1, keepdims=True)
                context = np.einsum("ht,thd->hd", weights, v[:position + 1].reshape(-1, 12, 64)).reshape(768)
                residual = x + matrices[1].reconstructed @ context + biases[1]
                for boundary, vector in (("qkv", x), ("fc", residual)):
                    cases.append(dict(id=f"prompt{prompt_index}-{boundary}-l{layer}-p{position}", layer=layer,
                                      boundary=boundary, position=position, prompt=prompt, tokenIds=tokens,
                                      source="newly saved q9 reference-derived activation", x=vector))
        print(f"Saved prompt activations: {prompt}", flush=True)
    return cases, provenance


def variants(case):
    x = case["x"]
    mean, std = float(x.mean()), float(x.std())
    yield "natural", x
    for multiple in (-64, -8, 8, 64):
        yield f"shift{multiple:+d}std", x + multiple * std
    low = mean + .001 * (x - mean)
    yield "lowvariance", low
    yield "lowvariance-shift+8std", low + 8 * std


def font_dot(inputs, codes, scales, coordinate_mode, advance_mode):
    ranges = np.maximum(1e-6, np.max(np.abs(inputs), axis=1)) * 1.001
    raw_axes = inputs / ranges[:, None]
    clipping = int(np.count_nonzero(np.abs(raw_axes) > 1))
    rounding = np.floor if coordinate_mode == "floor" else lambda x: np.floor(x + .5)
    axes = rounding(raw_axes * AXIS_STEPS) / AXIS_STEPS
    total = np.zeros((len(inputs), len(codes)), dtype=np.float64)
    for shard in range(3):
        sub = codes[:, shard * 256:(shard + 1) * 256].astype(np.float64)
        dot = axes[:, shard * 256:(shard + 1) * 256] @ sub.T
        if advance_mode != "continuous":
            bases = np.abs(sub).sum(axis=1) + 32
            pixels = (dot + bases) * 512 / 1000
            pixels = (np.floor(pixels * 64) if advance_mode == "floor64" else np.floor(pixels * 64 + .5)) / 64
            dot = pixels * 1000 / 512 - bases
        total += dot
    return total * ranges[:, None] * scales[None, :], ranges, clipping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    if (output / "results.json").exists():
        raise FileExistsError("Preserving existing results; choose another --output for a new attempt")
    started = time.monotonic()
    tensors = SafeTensors(MODEL_PATH)
    base_cases, provenance = gather_cases(tensors)
    cases, input_arrays = [], {}
    for case in base_cases:
        for variant, vector in variants(case):
            entry = {key: value for key, value in case.items() if key != "x"}
            entry.update(id=f"{case['id']}-{variant}", baseId=case["id"], variant=variant,
                         mean=float(vector.mean()), std=float(vector.std()), maximumAbsoluteInput=float(np.max(np.abs(vector))))
            cases.append(entry)
            input_arrays[entry["id"]] = vector
    np.savez_compressed(output / "inputs.npz", **input_arrays)
    (output / "inputs.json").write_text(json.dumps({"provenance": provenance, "cases": cases}, indent=2) + "\n")
    source = Path(__file__).resolve()
    shutil.copyfile(source, output / "analyzer-snapshot.py")
    report = dict(protocolSha256=sha(OUT / "PROTOCOL.md"), sourceSha256=sha(source),
                  sources={str(p.relative_to(ROOT)): sha(p) for p in [ROOT / "tools/browser_gpt2_core.py", ROOT / "tools/build_signed_hvar_chain.py", ROOT / "tools/build_hybrid_twelve_block.py", ROOT / "tools/build_gpt2_block_css.py"]},
                  baseCases=len(base_cases), cases=len(cases), matrices=[], rows=[],
                  environment={key: os.environ.get(key) for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")},
                  limitations=["Offline reference-derived inputs, not native browser captures", "Timeline decoding and browser internal float rounding unmodeled", "Per-shard pixel rounding is sensitivity, not a validated browser oracle", "Float reference is the original float matrix applied to the same q9-trajectory input, not an independent float-model trajectory"])
    primary_arrays = {}
    for layer in LAYERS:
        for boundary in ("qkv", "fc"):
            data = stage_data(tensors, layer, boundary)
            q, weight, bias, gamma, beta = [data[key] for key in ("q", "weight", "bias", "gamma", "beta")]
            original_hash = array_sha(q.reconstructed)
            matrix_meta = dict(layer=layer, boundary=boundary, shape=list(weight.shape),
                               codesSha256=array_sha(q.codes), scalesSha256=array_sha(q.scales),
                               reconstructedSha256=original_hash, fonts=verify_fonts(layer, boundary, q.codes))
            selected = [case for case in cases if case["layer"] == layer and case["boundary"] == boundary]
            x = np.stack([input_arrays[case["id"]] for case in selected])
            mu = x.mean(axis=1, keepdims=True)
            sigma = np.sqrt(np.mean((x - mu)**2, axis=1, keepdims=True) + EPSILON)
            normalized = gamma * (x - mu) / sigma + beta
            ideal = normalized @ q.reconstructed.T + bias
            floating = normalized @ weight.T + bias
            algebra = ((x * gamma) @ q.reconstructed.T - mu * (q.reconstructed @ gamma)) / sigma + q.reconstructed @ beta + bias
            matrix_meta["algebraMaximumError"] = float(np.max(np.abs(algebra - ideal)))
            assert matrix_meta["algebraMaximumError"] <= 1e-9
            gamma_css, beta_css, bias_css, scales_css = [css_constants(v) for v in (gamma, beta, bias, q.scales)]
            # Fixed correction constants are emitted with the same CSS formatter.
            c_css = css_constants(q.reconstructed @ gamma)
            d_css = css_constants(q.reconstructed @ beta + bias)
            normalized_css = gamma_css * (x - mu) / sigma + beta_css
            z_css = x * gamma_css
            for coordinate_mode in ("floor", "nearest"):
                for advance_mode in ("continuous", "nearest64", "floor64"):
                    baseline, baseline_range, baseline_clip = font_dot(normalized_css, q.codes, scales_css, coordinate_mode, advance_mode)
                    baseline += bias_css
                    raw, candidate_range, candidate_clip = font_dot(z_css, q.codes, scales_css, coordinate_mode, advance_mode)
                    candidate = (raw - mu * c_css) / sigma + d_css
                    assert baseline_clip == candidate_clip == 0
                    for i, case in enumerate(selected):
                        base_error, cand_error = stats(baseline[i] - floating[i]), stats(candidate[i] - floating[i])
                        cand_q_error = stats(candidate[i] - ideal[i])
                        relative_gate = all(cand_error[key] <= 1.10 * base_error[key] + 1e-5 for key in ("rmse", "maxError"))
                        absolute_gate = cand_q_error["rmse"] < .05
                        row = dict(caseId=case["id"], layer=layer, boundary=boundary, variant=case["variant"],
                                   coordinateMode=coordinate_mode, advanceMode=advance_mode,
                                   baselineVsFloat=base_error, candidateVsFloat=cand_error,
                                   baselineVsIdealQ9=stats(baseline[i] - ideal[i]), candidateVsIdealQ9=cand_q_error,
                                   candidateVsBaseline=stats(candidate[i] - baseline[i]),
                                   baselineRange=float(baseline_range[i]), candidateRange=float(candidate_range[i]),
                                   sigma=float(sigma[i, 0]), candidateRangeOverSigma=float(candidate_range[i] / sigma[i, 0]),
                                   clipping=0, relativeErrorPassed=relative_gate, absoluteErrorPassed=absolute_gate,
                                   passed=relative_gate and absolute_gate)
                        report["rows"].append(row)
                    if coordinate_mode == "floor" and advance_mode == "continuous":
                        prefix = f"l{layer}-{boundary}"
                        primary_arrays.update({prefix + "-baseline": baseline, prefix + "-candidate": candidate,
                                               prefix + "-float": floating, prefix + "-ideal-q9": ideal})
                        matrix_meta["primaryOutputCaseOrder"] = [case["id"] for case in selected]
            assert original_hash == array_sha(q.reconstructed)
            matrix_meta["weightsUnchanged"] = True
            report["matrices"].append(matrix_meta)
            print(f"Screened layer {layer} {boundary}: {len(selected)} cases", flush=True)
    primary = [row for row in report["rows"] if row["coordinateMode"] == "floor" and row["advanceMode"] == "continuous"]
    summaries = []
    for coordinate_mode in ("floor", "nearest"):
        for advance_mode in ("continuous", "nearest64", "floor64"):
            for kind in ("natural", "stress"):
                rows = [r for r in report["rows"] if r["coordinateMode"] == coordinate_mode and r["advanceMode"] == advance_mode and (r["variant"] == "natural") == (kind == "natural")]
                summaries.append(dict(coordinateMode=coordinate_mode, advanceMode=advance_mode, cases=kind,
                                      count=len(rows), passed=sum(r["passed"] for r in rows),
                                      relativeFailures=sum(not r["relativeErrorPassed"] for r in rows),
                                      absoluteFailures=sum(not r["absoluteErrorPassed"] for r in rows),
                                      maximumBaselineFloatRmse=max(r["baselineVsFloat"]["rmse"] for r in rows),
                                      maximumCandidateFloatRmse=max(r["candidateVsFloat"]["rmse"] for r in rows),
                                      maximumCandidateQ9Rmse=max(r["candidateVsIdealQ9"]["rmse"] for r in rows)))
    report.update(summary=summaries, primaryPassed=all(r["passed"] for r in primary),
                  allSensitivityPassed=all(r["passed"] for r in report["rows"]),
                  eligibleForBrowser=all(r["passed"] for r in report["rows"]), elapsedSeconds=time.monotonic() - started)
    np.savez_compressed(output / "primary-outputs.npz", **primary_arrays)
    report["artifactHashes"] = {name: sha(output / name) for name in ("inputs.npz", "inputs.json", "primary-outputs.npz", "analyzer-snapshot.py")}
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("baseCases", "cases", "primaryPassed", "allSensitivityPassed", "eligibleForBrowser", "elapsedSeconds", "summary")}, indent=2))


if __name__ == "__main__":
    main()
