#!/usr/bin/env python3
"""Offline feasibility gate for activation codebooks on GPT-2's block-0 MLP.

This learns product codebooks on real contextual activations, then checks the
complete FC -> GELU -> projection output on isolated held-out contexts. It is
not browser inference and does not claim the original checkpoint is preserved.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import time

import numpy as np

from analyze_css_native_grouped_mlp import (
    Config, evaluate_corpus, gelu, load_weights, make_corpus,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "learned-glyph-code-screen"
SEED = 20260917


def errors(pred, target):
    residual = np.asarray(pred, dtype=np.float64) - target
    rms = float(np.sqrt(np.mean(residual ** 2)))
    target_rms = float(np.sqrt(np.mean(np.asarray(target, dtype=np.float64) ** 2)))
    return {"rmse": rms, "relativeRmsError": rms / max(target_rms, 1e-12),
            "maxAbsoluteError": float(np.max(np.abs(residual)))}


def nearest(x, centers):
    distances = (np.sum(x*x, axis=1)[:, None] + np.sum(centers*centers, axis=1)[None, :]
                 - 2 * x @ centers.T)
    return np.argmin(distances, axis=1)


def train_codebooks(x, weight, group_width, count, seed):
    """Output-sensitive k-means: group distance equals squared FC contribution error."""
    rng = np.random.default_rng(seed)
    books = []
    metrics = []
    for start in range(0, x.shape[1], group_width):
        block = x[:, start:start+group_width].astype(np.float64)
        w = weight[start:start+group_width].astype(np.float64)
        # d @ (w @ w.T) @ d.T is the group's exact squared preactivation error.
        metric = np.linalg.cholesky(w @ w.T + np.eye(group_width) * 1e-9)
        transformed = block @ metric
        chosen = [int(rng.integers(len(x)))]
        minimum = np.sum((transformed - transformed[chosen[0]])**2, axis=1)
        for _ in range(1, count):
            total = float(minimum.sum())
            index = int(rng.choice(len(x), p=minimum/total)) if total else int(rng.integers(len(x)))
            chosen.append(index)
            minimum = np.minimum(minimum, np.sum((transformed-transformed[index])**2, axis=1))
        centers = block[chosen].copy()
        old_labels = None
        for _ in range(24):
            labels = nearest(transformed, centers @ metric)
            if old_labels is not None and np.array_equal(labels, old_labels):
                break
            old_labels = labels
            for k in range(count):
                mask = labels == k
                if np.any(mask):
                    centers[k] = block[mask].mean(axis=0)
        books.append(centers.astype(np.float32))
        metrics.append(metric.astype(np.float32))
    return np.stack(books), np.stack(metrics)


def reconstruct(x, books, metrics):
    width = books.shape[2]
    result = np.empty_like(x)
    codes = []
    for group, (centers, metric) in enumerate(zip(books, metrics)):
        start = group * width
        indices = nearest(x[:, start:start+width] @ metric, centers @ metric)
        result[:, start:start+width] = centers[indices]
        codes.append(indices)
    return result, np.stack(codes, axis=1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    began = time.perf_counter()
    samples = int(os.environ.get("GLYPH_CODE_SAMPLES", "384"))
    config = Config(False, samples, 0, 16, 8, (8, 16), 0.0, SEED, "cpu", 0)
    records, corpus_report = make_corpus(config)
    weights = load_weights()
    corpus = evaluate_corpus(records, weights, config.corpus_batch_size)
    # Match evaluate_corpus's ordering exactly for per-context provenance.
    ordered = [r for length in sorted({len(r.tokens) for r in records})
               for r in records if len(r.tokens) == length]
    references = {}
    for split in corpus:
        x = corpus[split]["inputs"]
        pre = x @ weights.fc_weight + weights.fc_bias
        references[split] = {"pre": pre, "hidden": gelu(pre)}
    candidates = []
    selected = None
    selected_books = None
    for width in (4, 8, 16):
        for count in (16, 64):
            tick = time.perf_counter()
            books, metrics = train_codebooks(corpus["train"]["inputs"], weights.fc_weight,
                                             width, count, SEED + width*100 + count)
            report = {"groupWidth": width, "centroids": count, "groups": 768//width,
                      "codesPerInput": 768//width, "codeBits": int(np.log2(count)),
                      "tableContributions": (768//width)*count*3072,
                      "float32TableBytes": (768//width)*count*3072*4,
                      "naiveDistanceCoordinateTerms": 768*count,
                      "selectedAdvanceContributions": (768//width)*3072,
                      "evaluation": {}}
            for split, arrays in corpus.items():
                reconstructed, codes = reconstruct(arrays["inputs"], books, metrics)
                pre = reconstructed @ weights.fc_weight + weights.fc_bias
                hidden = gelu(pre)
                result = hidden @ weights.proj_weight + weights.proj_bias
                # One-row explicit table sum verifies the lookup formulation rather
                # than silently assuming reconstructed matrix multiplication is it.
                from_tables = weights.fc_bias.astype(np.float64).copy()
                for group in range(len(books)):
                    start = group*width
                    from_tables += books[group, codes[0, group]].astype(np.float64) @ weights.fc_weight[start:start+width]
                table_error = float(np.max(np.abs(from_tables - pre[0])))
                if table_error > 0.002:
                    raise AssertionError(f"lookup-sum equivalence failed: {table_error}")
                evaluation = {"inputs": errors(reconstructed, arrays["inputs"]),
                              "preactivation": errors(pre, references[split]["pre"]),
                              "gelu": errors(hidden, references[split]["hidden"]),
                              "mlpOutput": errors(result, arrays["targets"]),
                              "explicitLookupSumMaxError": table_error, "byKind": {}}
                split_records = [r for r in ordered if r.split == split]
                for kind in ("local-text", "uniform-random"):
                    mask = np.array([r.kind == kind for r in split_records])
                    evaluation["byKind"][kind] = errors(result[mask], arrays["targets"][mask])
                report["evaluation"][split] = evaluation
            report["trainingAndEvaluationSeconds"] = time.perf_counter() - tick
            score = report["evaluation"]["validation"]["mlpOutput"]["relativeRmsError"]
            if selected is None or score < selected[0]:
                selected = (score, len(candidates))
                selected_books = (books, metrics)
            candidates.append(report)
            print(json.dumps({"width":width,"centroids":count,"validationOutputRelativeRms":score}), flush=True)
    winner = candidates[selected[1]]
    test_error = winner["evaluation"]["test"]["mlpOutput"]["relativeRmsError"]
    passed = test_error <= 0.05
    report = {"scope":"offline learned activation codebooks; original block-0 FC, GELU and projection retained",
              "runtime":"Python oracle/training only; no browser speed measured",
              "seed":SEED,"numpy":np.__version__,"platform":platform.platform(),
              "corpus":corpus_report, "candidates":candidates,"selectedByValidationIndex":selected[1],
              "gate":{"maximumHeldOutMlpRelativeRmsError":0.05,"passed":passed,
                      "note":"A screening threshold, not a proof of generation quality. Failure rejects these trained configurations only."},
              "elapsedSeconds":time.perf_counter()-began,
              "trainingContextHashes":[r.token_hash for r in records if r.split=="train"],
              "testContextHashes":[r.token_hash for r in records if r.split=="test"]}
    (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
    np.savez_compressed(OUT/"selected-codebooks.npz",centers=selected_books[0],metrics=selected_books[1])
    rows=[]
    for c in candidates:
        rows.append(f"| {c['groupWidth']} | {c['centroids']} | {c['codesPerInput']} | "
                    f"{100*c['evaluation']['validation']['mlpOutput']['relativeRmsError']:.2f}% | "
                    f"{100*c['evaluation']['test']['mlpOutput']['relativeRmsError']:.2f}% | "
                    f"{c['float32TableBytes']/2**20:.1f} MiB |")
    (OUT/"RESULTS.md").write_text(
        "# Learned glyph-code feasibility screen\n\n"
        "This is an offline model-change experiment, not a browser speedup. It learns output-sensitive "
        "product codebooks on contextual GPT-2-small block-0 LayerNorm outputs. Each group uses k-means++ "
        "initialization and up to 24 Lloyd iterations in the FC-induced metric. Original full 768→3072 "
        "FC weights, GELU and 3072→768 projection are retained. Lookup contributions are algebraically "
        "equivalent to multiplying the reconstructed activation; explicit sums checked each split.\n\n"
        f"There are {samples} contexts split by token hashes and local source files; lengths 8 and 16. "
        "Half are local text and half random-token stress inputs. Codebooks see training data only. "
        "The candidate is selected by validation error; test data does not tune its parameters.\n\n"
        "| Group width | Codes/group | Codes/input | Validation MLP relative RMS error | Test error | Float table storage |\n"
        "|---|---|---|---|---|---|\n"+"\n".join(rows)+"\n\n"
        f"Selected candidate: width {winner['groupWidth']}, {winner['centroids']} codes; held-out MLP "
        f"relative RMS error **{test_error:.2%}**. The predeclared 5% screening gate "
        f"**{'passes' if passed else 'fails'}**. "
        "The gate does not establish next-token correctness, perplexity, or full-layer equivalence. "
        "Per-kind, input, preactivation and GELU errors are in results.json.\n\n"
        "A failed screen means these modest learned codebooks are not ready to compile into browser fonts. "
        "It does not rule out end-to-end distillation, larger training corpora or stages trained to emit codes directly. "
        "Nearest-center encoding and table summation costs remain unmeasured in the browser. Table storage here "
        "is numeric float32 storage, not a measured font size. No original model or compiler was changed.\n\n"
        "Reproduce:\n\n```sh\npython3 tools/run_unconventional_isolated.py --label learned-codes -- "
        "env OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 tools/screen_learned_glyph_codes.py\n```\n")
    print(json.dumps({"selected":selected[1],"testError":test_error,"gatePassed":passed,
                      "elapsedSeconds":report["elapsedSeconds"]}),flush=True)


if __name__ == "__main__":
    main()
