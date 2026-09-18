"""Audit-only offline screen; reuse the prior gate's inputs and error policy.

Run from repo root with PYTHONPATH=tools and numpy/fonttools/pillow/brotli.
No browser, font generation, production changes, or timing claim.
"""
from pathlib import Path
import hashlib
import json
import time

import numpy as np
import analyze_preserved_weight_normalization as prior


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    started = time.monotonic()
    out = DEST
    destination = out / "centered-normalization-results.json"
    if destination.exists():
        raise FileExistsError(destination)
    inputs = prior.OUT / "inputs.npz"
    metadata = prior.OUT / "inputs.json"
    cases = json.loads(metadata.read_text())["cases"]
    tensors = prior.SafeTensors(prior.MODEL_PATH)
    rows, matrices = [], []
    with np.load(inputs) as vectors:
        for layer in prior.LAYERS:
            for boundary in ("qkv", "fc"):
                d = prior.stage_data(tensors, layer, boundary)
                q, weight, bias, gamma, beta = [d[k] for k in ("q", "weight", "bias", "gamma", "beta")]
                selected = [c for c in cases if c["layer"] == layer and c["boundary"] == boundary]
                x = np.stack([vectors[c["id"]] for c in selected])
                mu = x.mean(axis=1, keepdims=True)
                sigma = np.sqrt(np.mean((x - mu)**2, axis=1, keepdims=True) + prior.EPSILON)
                normalized = gamma * (x - mu) / sigma + beta
                ideal = normalized @ q.reconstructed.T + bias
                floating = normalized @ weight.T + bias
                algebra = ((x - mu) * gamma) @ q.reconstructed.T / sigma + q.reconstructed @ beta + bias
                algebra_error = float(np.max(np.abs(algebra - ideal)))
                assert algebra_error < 1e-9
                gamma_css, beta_css, bias_css, scales_css = [prior.css_constants(v) for v in (gamma, beta, bias, q.scales)]
                normalized_css = gamma_css * (x - mu) / sigma + beta_css
                centered_css = gamma_css * (x - mu)
                constant = prior.css_constants(q.reconstructed @ beta + bias)
                matrices.append(dict(layer=layer, boundary=boundary,
                    codesSha256=prior.array_sha(q.codes), scalesSha256=prior.array_sha(q.scales),
                    algebraMaximumError=algebra_error))
                for coordinate in ("floor", "nearest"):
                    for advance in ("continuous", "nearest64", "floor64"):
                        baseline, _, bc = prior.font_dot(normalized_css, q.codes, scales_css, coordinate, advance)
                        baseline += bias_css
                        raw, _, cc = prior.font_dot(centered_css, q.codes, scales_css, coordinate, advance)
                        candidate = np.where(sigma < 0.125, baseline, raw / sigma + constant)
                        assert bc == cc == 0
                        for i, c in enumerate(selected):
                            base = prior.stats(baseline[i] - floating[i])
                            cand = prior.stats(candidate[i] - floating[i])
                            cand_q = prior.stats(candidate[i] - ideal[i])
                            relative = all(cand[k] <= 1.10 * base[k] + 1e-5 for k in ("rmse", "maxError"))
                            absolute = cand_q["rmse"] < .05
                            rows.append(dict(caseId=c["id"], layer=layer, boundary=boundary,
                                variant=c["variant"], sigma=float(sigma[i,0]), legacyFallback=bool(sigma[i,0] < .125), coordinateMode=coordinate, advanceMode=advance,
                                baselineVsFloat=base, candidateVsFloat=cand, candidateVsIdealQ9=cand_q,
                                relativeErrorPassed=relative, absoluteErrorPassed=absolute,
                                passed=relative and absolute))
                print(f"Screened layer {layer} {boundary}", flush=True)
    summaries = []
    for coordinate in ("floor", "nearest"):
        for advance in ("continuous", "nearest64", "floor64"):
            for kind in ("natural", "stress"):
                selected = [r for r in rows if r["coordinateMode"] == coordinate and r["advanceMode"] == advance
                    and (r["variant"] == "natural") == (kind == "natural")]
                summaries.append(dict(coordinateMode=coordinate, advanceMode=advance, cases=kind,
                    count=len(selected), passed=sum(r["passed"] for r in selected),
                    relativeFailures=sum(not r["relativeErrorPassed"] for r in selected),
                    absoluteFailures=sum(not r["absoluteErrorPassed"] for r in selected),
                    maximumCandidateQ9Rmse=max(r["candidateVsIdealQ9"]["rmse"] for r in selected)))
    report = dict(scope="Offline screen only; same 308 reference-derived inputs and prior gate policy",
        formula="legacy if sigma < 1/8, otherwise Q @ (gamma * (x - mean)) / sigma + Q @ beta + bias",
        inputSha256=digest(inputs), metadataSha256=digest(metadata),
        sourceSha256=digest(Path(__file__)), priorAnalyzerSha256=digest(Path(prior.__file__)),
        policy="candidate float RMSE and max <= 1.10 * baseline + 1e-5; candidate ideal-q9 RMSE < .05",
        limitations=["No browser transport, CSS internal float rounding, or timeline decode model",
            "Pixel-rounding alternatives are sensitivity models, not measured browser oracles",
            "No speed, native token agreement, or novel held-out quality claim"],
        matrices=matrices, rows=rows, summary=summaries,
        allSensitivityPassed=all(r["passed"] for r in rows), elapsedSeconds=time.monotonic() - started)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k:report[k] for k in ("summary", "allSensitivityPassed", "elapsedSeconds")}, indent=2))


if __name__ == "__main__":
    main()
