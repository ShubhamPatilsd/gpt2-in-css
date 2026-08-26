"""Score retained Chromium hidden states after a teacher-forced native run.

All transformer blocks, embedding lookup, cache retention and greedy vocabulary
selection ran in Chromium. Distribution metrics below use an OFFLINE head and
normalization; this is not a native browser perplexity/softmax implementation.
Nothing computed here is returned to the browser.
"""

import argparse
import json
from pathlib import Path

import build_gpt2_block_css as block
import numpy as np
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from browser_gpt2_core import reference_sequence
from browser_gpt2_saved_run import completed_run
from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS, WEIGHT_SCALE, R


def log_probs(logits):
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    return shifted - np.log(np.sum(np.exp(shifted), axis=-1, keepdims=True))


def distribution_metrics(actual, reference, targets):
    rows = np.arange(len(targets))
    nll = -actual[rows, targets]
    reference_nll = -reference[rows, targets]
    return {
        "predictions": len(targets),
        "perplexity": float(np.exp(nll.mean())),
        "referencePerplexity": float(np.exp(reference_nll.mean())),
        "perplexityRatio": float(np.exp((nll - reference_nll).mean())),
        "meanKLReferenceToActual": float(
            np.mean(np.sum(np.exp(reference) * (reference - actual), axis=-1))
        ),
        "meanTotalVariation": float(
            np.mean(np.sum(np.abs(np.exp(reference) - np.exp(actual)), axis=-1)) / 2
        ),
        "top1Agreement": float(np.mean(actual.argmax(-1) == reference.argmax(-1))),
    }


def evaluate(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    run = completed_run(directory)
    inputs, targets = (
        manifest.get("teacherForcedInputs"),
        manifest.get("teacherForcedTargets"),
    )
    samples = sorted(run.get("qualitySamples", []), key=lambda row: row["position"])
    if not inputs or not targets or not samples:
        raise ValueError("Require teacher-forced inputs/targets and --quality-readback")
    if [row["position"] for row in samples] != list(range(1, len(inputs) + 1)):
        raise ValueError(
            "Missing native head-input captures; do not report partial rows as a complete eval"
        )
    if len(targets) != len(inputs) or not run.get("complete"):
        raise ValueError("Require a completed run and one target for every input")
    hidden = np.asarray([row["hidden"] for row in samples])
    if hidden.shape != (len(inputs), 768) or not np.all(np.isfinite(hidden)):
        raise ValueError("Invalid Chromium hidden-state capture")
    tensors = SafeTensors(MODEL_PATH)
    weight = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    reference = reference_sequence(inputs, manifest["blocks"], quantized=False)
    reference_hidden = np.stack(
        [block.layer_norm(np.asarray(row), gamma, beta) for row in reference["outputs"]]
    )
    reference_probs = log_probs(reference_hidden @ weight.T)
    q9_reference = reference_sequence(inputs, manifest["blocks"], quantized=True)
    q9_hidden = np.stack(
        [
            block.layer_norm(np.asarray(row), gamma, beta)
            for row in q9_reference["outputs"]
        ]
    )
    q9_probs = log_probs(q9_hidden @ weight.T)
    if manifest.get("kvWindow", len(inputs)) < len(inputs):
        runtime_reference = reference_sequence(
            inputs,
            manifest["blocks"],
            quantized=True,
            kv_window=manifest["kvWindow"],
            kv_sinks=manifest.get("kvSinks", 0),
        )
        runtime_hidden = np.stack(
            [
                block.layer_norm(np.asarray(row), gamma, beta)
                for row in runtime_reference["outputs"]
            ]
        )
        runtime_probs = log_probs(runtime_hidden @ weight.T)
    else:
        runtime_probs = q9_probs
    browser_probs = log_probs(hidden @ weight.T)
    rounded_hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    rounded_weight = np.rint(weight / WEIGHT_SCALE) * WEIGHT_SCALE
    q16_probs = log_probs(rounded_hidden @ rounded_weight.T)
    report = {
        "scope": "Actual Chromium transformer/embedding/KV/greedy head; distribution metrics scored offline from captured hidden states",
        "blocks": manifest["blocks"],
        "attentionMask": manifest.get("attentionMask", "full causal"),
        "referenceAttentionMask": "full causal",
        "referenceArithmetic": "Float64 evaluation of the original FP32 checkpoint",
        "kvWindow": manifest.get("kvWindow", manifest["capacity"]),
        "kvSinks": manifest.get("kvSinks", 0),
        "runtimeJavaScript": False,
        "externalWritesAfterNavigation": run["externalWritesAfterNavigation"],
        "floatHeadDistribution": distribution_metrics(
            browser_probs, reference_probs, np.asarray(targets)
        ),
        "idealQ9FullAttentionDistribution": distribution_metrics(
            q9_probs, reference_probs, np.asarray(targets)
        ),
        "idealQ9RuntimeAttentionDistribution": distribution_metrics(
            runtime_probs, reference_probs, np.asarray(targets)
        ),
        "nativeVsIdealQ9RuntimeAttention": distribution_metrics(
            browser_probs, runtime_probs, np.asarray(targets)
        ),
        "q16HeadDistribution": distribution_metrics(
            q16_probs, reference_probs, np.asarray(targets)
        ),
        "nativeGreedyVsOfflineQ16Agreement": float(
            np.mean(
                np.asarray([r["nativeWinner"] for r in samples]) == q16_probs.argmax(-1)
            )
        ),
        "nativeGreedyVsFP32Agreement": float(
            np.mean(
                np.asarray([r["nativeWinner"] for r in samples])
                == reference_probs.argmax(-1)
            )
        ),
        "note": "A short held-out screen, not broad task-quality certification or a native probability-normalization implementation"
        if manifest["blocks"] == 12
        else "Integration smoke test with fewer than 12 blocks; NOT a GPT-2 quality result",
    }
    (directory / "quality-results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    evaluate(parser.parse_args().directory.resolve())
