#!/usr/bin/env python3
"""Independent post-run checks. Nothing in this file feeds the browser."""

import argparse
import json
from pathlib import Path

import build_gpt2_block_css as b
import numpy as np
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from browser_gpt2_core import reference_sequence
from browser_gpt2_saved_run import completed_run
from build_gpt2_groupwise_production_q16_sixfont import (
    AXIS_STEPS,
    SCORE_GAIN,
    WEIGHT_SCALE,
    R,
)
from build_pretrained_gpt2 import Gpt2Tokenizer
from profile_hybrid_twelve_block import error


def verify(directory, prefix=""):
    completed_run(directory, prefix)
    manifest = json.loads((directory / "manifest.json").read_text())
    actual = json.loads(
        (directory / (prefix + "verification-vectors.json")).read_text()
    )
    outputs = [int(t) for t in actual["tokens"]]
    prompt = actual.get("prompt", 15496)
    teacher_forced = manifest.get("teacherForcedInputs")
    tokens = (
        teacher_forced[: len(outputs)] if teacher_forced else [prompt] + outputs[:-1]
    )
    reference = reference_sequence(
        tokens,
        manifest["blocks"],
        kv_window=manifest.get("kvWindow"),
        kv_sinks=manifest.get("kvSinks", 0),
    )
    tensors = SafeTensors(MODEL_PATH)
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    weights = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    qweights = np.rint(weights / WEIGHT_SCALE) * WEIGHT_SCALE

    def scores(rows, rounded):
        hidden = np.stack([b.layer_norm(np.asarray(x), gamma, beta) for x in rows])
        if rounded:
            hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
            return np.rint(hidden @ qweights.T * SCORE_GAIN * 256)
        return hidden @ weights.T

    q_scores = scores(reference["outputs"], True)
    expected = q_scores.argmax(1).tolist()
    report = {
        "tokens": outputs,
        "referenceQ9Q16": expected,
        "referenceAttentionMask": manifest.get("attentionMask", "full causal"),
        "tokenAgreement": [a == b for a, b in zip(outputs, expected)],
        "finalResidualError": error(actual["finalResidual"], reference["outputs"][-1]),
        "cacheErrors": [],
    }
    for cache in actual["caches"]:
        layer, slot = cache["layer"], cache["slot"]
        position = cache.get("position", slot)
        report["cacheErrors"].append(
            {
                "layer": layer,
                "slot": slot,
                "position": position,
                "error": error(
                    cache["values"], reference["layers"][layer]["qkv"][position][768:]
                ),
            }
        )
    hidden = np.asarray(actual["finalHidden"])
    hidden = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    report["finalHeadActualInputWinner"] = int(
        np.rint(hidden @ qweights.T * SCORE_GAIN * 256).argmax()
    )
    report["finalHeadMatchesActualInput"] = (
        report["finalHeadActualInputWinner"] == outputs[-1]
    )
    if manifest["blocks"] == 12:
        original = reference_sequence(tokens, 12, quantized=False)
        float_scores = scores(original["outputs"], False)
        report["originalFloatWinners"] = float_scores.argmax(1).tolist()
        report["originalFloatAgreement"] = [
            a == b for a, b in zip(outputs, report["originalFloatWinners"])
        ]
    root = Path(__file__).resolve().parents[1]
    codec = Gpt2Tokenizer(root / "data/gpt2/vocab.json", root / "data/gpt2/merges.txt")
    report["text"] = codec.decode_token(prompt) + "".join(
        codec.decode_token(t) for t in outputs
    )
    if teacher_forced:
        report["text"] = "".join(codec.decode_token(t) for t in tokens)
        report["textKind"] = "evaluation input; predictions are not a continuation"
    (directory / (prefix + "numerical-results.json")).write_text(
        json.dumps(report, indent=2)
    )
    print({k: v for k, v in report.items() if k != "cacheErrors"}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--report-prefix", default="")
    args = parser.parse_args()
    verify(args.directory.resolve(), args.report_prefix)
