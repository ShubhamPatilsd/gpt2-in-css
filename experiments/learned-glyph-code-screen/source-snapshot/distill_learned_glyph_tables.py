#!/usr/bin/env python3
"""Fit table corrections after the learned-code screen; no browser inference."""
import json
import time

import numpy as np

from screen_learned_glyph_codes import (
    OUT, SEED, Config, errors, evaluate_corpus, gelu, load_weights, make_corpus, reconstruct,
)


def kernel(a, b):
    # Normalized dot product of group-specific one-hot code identities.
    return np.mean(a[:, None, :] == b[None, :, :], axis=2, dtype=np.float64)


def main():
    began = time.perf_counter()
    screen = json.loads((OUT / "results.json").read_text())
    best = screen["candidates"][screen["selectedByValidationIndex"]]
    saved = np.load(OUT / "selected-codebooks.npz")
    config = Config(False, screen["corpus"]["totalSamples"], 0, 16, 8, (8,16), 0.0, SEED, "cpu", 0)
    records, corpus_report = make_corpus(config)
    weights = load_weights()
    corpus = evaluate_corpus(records, weights, config.corpus_batch_size)
    data = {}
    for split, arrays in corpus.items():
        xhat, codes = reconstruct(arrays["inputs"], saved["centers"], saved["metrics"])
        pre = xhat @ weights.fc_weight + weights.fc_bias
        target = arrays["inputs"] @ weights.fc_weight + weights.fc_bias
        data[split] = {"codes": codes, "pre": pre, "target": target}
    train = data["train"]
    kernels = {s: kernel(d["codes"], train["codes"]) for s,d in data.items()}
    residual = train["target"].astype(np.float64) - train["pre"]
    candidates=[]
    best_fit=None
    for penalty in (0.001,0.01,0.1,1.0,10.0):
        coefficients=np.linalg.solve(kernels["train"]+np.eye(len(residual))*penalty,residual)
        evaluation={}
        for split, d in data.items():
            pre=d["pre"]+kernels[split]@coefficients
            result=gelu(pre)@weights.proj_weight+weights.proj_bias
            evaluation[split]={"preactivation":errors(pre,d["target"]),
                               "mlpOutput":errors(result,corpus[split]["targets"])}
        candidates.append({"ridgePenalty":penalty,"evaluation":evaluation})
        score=evaluation["validation"]["mlpOutput"]["relativeRmsError"]
        if best_fit is None or score<best_fit[0]:
            best_fit=(score,len(candidates)-1,coefficients.copy())
    selected=candidates[best_fit[1]]
    # Reify the fitted kernel into finite per-group/per-code contributions.
    groups, count, _ = saved["centers"].shape
    corrections=np.zeros((groups,count,3072),dtype=np.float32)
    for g in range(groups):
        np.add.at(corrections[g],train["codes"][:,g],best_fit[2]/groups)
    lookup=np.zeros(3072,dtype=np.float64)
    for g in range(groups):
        lookup+=corrections[g,data["test"]["codes"][0,g]]
    equivalent=kernels["test"][0]@best_fit[2]
    max_error=float(np.max(np.abs(lookup-equivalent)))
    if max_error>0.002:
        raise AssertionError(f"learned table/kernel equivalence failed: {max_error}")
    report={"scope":"supervised additive lookup-table distillation on fixed learned activation codes",
            "baseCandidate":{"groupWidth":best["groupWidth"],"centroids":best["centroids"]},
            "training":"Ridge fit to FC preactivation residuals; validation selects penalty; test does not fit tables.",
            "candidates":candidates,"selectedByValidationIndex":best_fit[1],
            "testMlpRelativeRmsError":selected["evaluation"]["test"]["mlpOutput"]["relativeRmsError"],
            "explicitLearnedTableVsKernelMaxError":max_error,"correctionTableBytes":corrections.nbytes,
            "elapsedSeconds":time.perf_counter()-began,"corpusIsolation":corpus_report["isolation"],
            "browserMeasured":False}
    (OUT/"distillation.json").write_text(json.dumps(report,indent=2)+"\n")
    np.savez_compressed(OUT/"distillation-coefficients.npz",coefficients=best_fit[2],trainingCodes=train["codes"])
    rows=[]
    for c in candidates:
        rows.append(f"| {c['ridgePenalty']} | {c['evaluation']['validation']['mlpOutput']['relativeRmsError']:.2%} | "
                    f"{c['evaluation']['test']['mlpOutput']['relativeRmsError']:.2%} |")
    (OUT/"DISTILLATION.md").write_text(
        "# Supervised lookup-table follow-up\n\n"
        "The centroid-only screen failed, so this follow-up learns table values themselves. "
        "It keeps the activation codes of the candidate selected on validation data and fits additive "
        "per-group/per-code corrections to the real FC preactivations by ridge regression. "
        "Original GELU and projection are applied afterward. This is a small supervised distillation "
        "experiment, not full end-to-end training or browser inference.\n\n"
        "The normalized same-code kernel is exactly equivalent to finite additive contribution tables; "
        "an explicit held-out table sum is checked against that kernel. No pairwise comparison with the "
        "training corpus is required at runtime: its learned contribution is compiled into each code's table. "
        "Train/validation/test isolation is inherited from the first screen.\n\n"
        "| Ridge penalty | Validation MLP relative RMS error | Test error |\n|---|---|---|\n"+
        "\n".join(rows)+"\n\n"+
        f"Validation selects penalty {selected['ridgePenalty']}; test relative RMS error is "
        f"**{report['testMlpRelativeRmsError']:.2%}**. "
        "The 5% screening threshold and requirements for full-model quality remain unchanged. "
        "This does not measure the native encoding/lookup/reduction cost or demonstrate a token speedup.\n\n"
        "Reproduce after the base screen:\n\n```sh\npython3 tools/run_unconventional_isolated.py --label glyph-table-distillation -- "
        "env OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 tools/distill_learned_glyph_tables.py\n```\n")
    print(json.dumps({"selectedPenalty":selected["ridgePenalty"],"testError":report["testMlpRelativeRmsError"],
                      "elapsedSeconds":report["elapsedSeconds"]}),flush=True)


if __name__=="__main__":
    main()
