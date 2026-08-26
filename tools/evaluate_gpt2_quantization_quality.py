#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy==2.5.3", "tokenizers==0.22.2", "pyarrow==23.0.1"]
# ///
"""Offline quality screening, NOT a Chromium implementation or speed benchmark.

Compare the local GPT-2 checkpoint with defined W8A8 Q/DQ recipes and the
existing SVG-like surface approximation. Calibration uses WikiText-2 TRAIN;
quality uses distinct TEST articles. No JavaScript, browser changes, or training.

Run: VECLIB_MAXIMUM_THREADS=4 uv run tools/evaluate_gpt2_quantization_quality.py
The SVG approximation deliberately does not model every filter boundary,
per-product rounding, browser layernorm/GELU approximation, or output readback.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import platform
import re
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from analyze_svg_quantization_strategies import gelu_new
from build_pretrained_gpt2 import Gpt2Tokenizer
from evaluate_svg_w8a8_generation import (
    CALIBRATION_PROMPTS,
    EVALUATION_PROMPTS,
    Runner,
    SurfacePlan,
    apply_surface,
    fit_surface,
    load_model,
    quantize_output_rows,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gpt2-quantization-quality"
REVISION = "b08601e04326c79dfdd32d625aee71d232d685c3"
VARIANTS = (
    "fp32",
    "w8a8",
    "smoothquant_w8a8",
    "svg",
    "svg_float_probabilities",
    "svg_legacy_ranges",
)
PROMPTS = list(EVALUATION_PROMPTS) + [
    "The purpose of the experiment was to",
    "After three days at sea, the crew",
    "To make a cup of tea, first",
    "The report found that the number of",
    "When the train arrived at the station,",
    "A computer program is a set of",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def log_probabilities(logits: np.ndarray) -> np.ndarray:
    # Use float64 for metrics, not model arithmetic.
    shifted = logits.astype(np.float64) - logits.max(axis=-1, keepdims=True)
    return shifted - np.log(np.exp(shifted).sum(axis=-1, keepdims=True))


def dynamic_int8(value: np.ndarray, axis: int) -> np.ndarray:
    step = np.maximum(np.max(np.abs(value), axis=axis, keepdims=True), 1e-12) / 127
    return (np.clip(np.rint(value / step), -127, 127) * step).astype(np.float32)


def norm(value: np.ndarray, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
    mean = value.mean(axis=-1, keepdims=True)
    variance = ((value - mean) ** 2).mean(axis=-1, keepdims=True)
    return (value - mean) / np.sqrt(variance + 1e-5) * gamma + beta


class Calibration:
    def __init__(self):
        self.surfaces: dict[str, np.ndarray] = {}
        self.linear_inputs: dict[str, np.ndarray] = {}

    @staticmethod
    def record(target: dict, name: str, value: np.ndarray):
        maximum = np.abs(value.reshape(-1, value.shape[-1])).max(axis=0)
        target[name] = np.maximum(target.get(name, 0), maximum)

    def plans(self) -> dict[str, SurfacePlan]:
        # fit_surface only needs channel maxima: exactly the existing 32-group
        # log-range recipe, with 10% headroom and zero code 128.
        return {name: fit_surface(value[None]) for name, value in self.surfaces.items()}


class Model:
    """Batched causal FP32 arithmetic with explicit Q/DQ/materialization sites."""

    def __init__(self, checkpoint, variant="fp32", calibration=None):
        self.embedding, self.position, self.blocks, self.gamma, self.beta = checkpoint
        self.variant = variant
        self.svg = variant.startswith("svg")
        self.calibration = calibration
        self.trace: Calibration | None = None
        self.plans = calibration.plans() if self.svg else {}
        self.weights: dict[str, np.ndarray] = {}
        self.scales: dict[str, np.ndarray] = {}
        self.reset_stats()
        for index, block in enumerate(self.blocks):
            for label, weight in (
                ("qkv", block.qkv_weight),
                ("attention", block.attention_projection_weight),
                ("fc", block.fc_weight),
                ("projection", block.mlp_projection_weight),
            ):
                self.prepare(f"b{index}.{label}", weight)
        # Input token embeddings stay FP32 in every recipe. Quantize the tied
        # output head independently, just as the legacy SVG simulator does.
        self.prepare("head", self.embedding.T)

    def reset_stats(self):
        self.stats: dict[str, dict] = {}

    def prepare(self, name, weight):
        if self.variant == "fp32":
            self.weights[name] = weight
        elif self.svg:
            # Legacy SVG uses +/-255 signed magnitudes, NOT signed INT8 weights.
            self.weights[name] = quantize_output_rows(weight)
        else:
            scale = np.ones(weight.shape[0], dtype=np.float32)
            if self.variant == "smoothquant_w8a8":
                activation = np.maximum(self.calibration.linear_inputs[name], 1e-5)
                weight_max = np.maximum(np.abs(weight).max(axis=1), 1e-5)
                scale = np.sqrt(activation / weight_max).astype(np.float32)
            self.scales[name] = scale
            self.weights[name] = dynamic_int8(weight * scale[:, None], axis=0)

    def linear(self, name, value, bias=None):
        if self.trace is not None:
            Calibration.record(self.trace.linear_inputs, name, value)
        if not self.svg and self.variant != "fp32":
            value = dynamic_int8(value / self.scales[name], axis=-1)
        shape = value.shape[:-1]
        result = (value.reshape(-1, value.shape[-1]) @ self.weights[name]).reshape(
            *shape, self.weights[name].shape[-1]
        )
        return result if bias is None else result + bias

    def surface(self, name, value, valid=None):
        if self.trace is not None:
            Calibration.record(
                self.trace.surfaces, name, value if valid is None else value[valid]
            )
        if not self.svg:
            return value
        plan = self.plans[name]
        measured = value if valid is None else value[valid]
        raw = plan.zero + measured / plan.step
        stat = self.stats.setdefault(name, {"elements": 0, "clipped": 0})
        stat["elements"] += measured.size
        stat["clipped"] += int(np.count_nonzero((raw < 0) | (raw > 255)))
        return apply_surface(value, plan)[0]

    def hidden(self, tokens, cache=None, valid=None):
        tokens = np.asarray(tokens, dtype=np.int64)
        batch, length = tokens.shape
        if valid is None:
            valid = np.ones_like(tokens, dtype=bool)
        else:
            valid = np.asarray(valid, dtype=bool)
        previous_valid = cache[1] if cache is not None else np.zeros((batch, 0), bool)
        all_valid = np.concatenate([previous_valid, valid], axis=1)
        offset = previous_valid.shape[1]
        positions = np.maximum(all_valid.cumsum(axis=1)[:, offset:] - 1, 0)
        if positions.max() >= self.position.shape[0]:
            raise ValueError("Context exceeds the checkpoint's positional embeddings")
        state = self.surface("input", self.embedding[tokens] + self.position[positions])
        causal = (
            np.arange(offset + length)[None, :] <= (offset + np.arange(length))[:, None]
        )
        allowed = causal[None] & all_valid[:, None, :]
        # Dummy pad queries must remain finite; valid queries never attend pads.
        allowed |= (~valid)[:, :, None] & (np.arange(offset + length) == 0)[
            None, None, :
        ]
        new_cache = []
        for index, block in enumerate(self.blocks):
            prefix = f"b{index}"
            normalized = self.surface(
                f"{prefix}.ln1", norm(state, block.ln1_gamma, block.ln1_beta)
            )
            qkv = self.surface(
                f"{prefix}.qkv",
                self.linear(f"{prefix}.qkv", normalized, block.qkv_bias),
            )
            q, k, v = [
                part.reshape(batch, length, 12, 64).transpose(0, 2, 1, 3)
                for part in np.split(qkv, 3, axis=-1)
            ]
            if cache is not None:
                old_k, old_v = cache[0][index]
                k = np.concatenate([old_k, k], axis=2)
                v = np.concatenate([old_v, v], axis=2)
            new_cache.append((k, v))
            scores = (q @ k.swapaxes(-1, -2)) / 8.0
            scores = self.surface(
                f"{prefix}.scores", scores.transpose(0, 2, 3, 1), allowed
            ).transpose(0, 3, 1, 2)
            scores = np.where(allowed[:, None], scores, -np.inf)
            probability = np.exp(scores - scores.max(axis=-1, keepdims=True))
            probability /= probability.sum(axis=-1, keepdims=True)
            if self.svg and self.variant != "svg_float_probabilities":
                rounded = np.rint(probability * 255) / 255
                stat = self.stats.setdefault(
                    f"{prefix}.probabilities",
                    {
                        "elements": 0,
                        "rounded_to_zero": 0,
                        "lost_mass": 0.0,
                        "rows": 0,
                        "row_sum_abs_error": 0.0,
                    },
                )
                p = probability.transpose(0, 2, 3, 1)[allowed]
                r = rounded.transpose(0, 2, 3, 1)[allowed]
                stat["elements"] += p.size
                stat["rounded_to_zero"] += int(np.count_nonzero((p > 0) & (r == 0)))
                stat["lost_mass"] += float(p[r == 0].sum(dtype=np.float64))
                stat["rows"] += batch * length * 12
                stat["row_sum_abs_error"] += float(
                    np.abs(rounded.sum(axis=-1) - 1).sum()
                )
                probability = rounded  # No renormalization in the legacy SVG recipe.
            context = self.surface(
                f"{prefix}.context",
                (probability @ v).transpose(0, 2, 1, 3).reshape(batch, length, 768),
            )
            learned = self.surface(
                f"{prefix}.attention",
                self.linear(
                    f"{prefix}.attention", context, block.attention_projection_bias
                ),
            )
            state = self.surface(f"{prefix}.residual1", state + learned)
            normalized = self.surface(
                f"{prefix}.ln2", norm(state, block.ln2_gamma, block.ln2_beta)
            )
            pre = self.surface(
                f"{prefix}.fc", self.linear(f"{prefix}.fc", normalized, block.fc_bias)
            )
            hidden = self.surface(f"{prefix}.gelu", gelu_new(pre))
            projected = self.surface(
                f"{prefix}.projection",
                self.linear(f"{prefix}.projection", hidden, block.mlp_projection_bias),
            )
            state = self.surface(f"{prefix}.residual2", state + projected)
        final = self.surface("final", norm(state, self.gamma, self.beta))
        if self.trace is not None:
            Calibration.record(self.trace.linear_inputs, "head", final)
        return final, (new_cache, all_valid)


def get_tokenizer():
    from tokenizers import ByteLevelBPETokenizer

    return ByteLevelBPETokenizer(
        str(ROOT / "data/gpt2/vocab.json"), str(ROOT / "data/gpt2/merges.txt")
    )


def corpus_windows(split, count, length, seed, tokenizer, out):
    import pyarrow.parquet as pq

    path = out / "data" / f"{split}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/datasets/Salesforce/wikitext/resolve/{REVISION}/wikitext-2-raw-v1/{split}-00000-of-00001.parquet"
    if not path.exists():
        print(f"Downloading pinned WikiText-2 {split}", flush=True)
        urllib.request.urlretrieve(url, path)
    texts = pq.read_table(path, columns=["text"])["text"].to_pylist()
    articles, current = [], []
    for text in texts:
        if re.match(r"^\s*= [^=].*[^=] =\s*$", text) and current:
            articles.append("".join(current))
            current = []
        current.append(text)
    if current:
        articles.append("".join(current))
    rng = np.random.default_rng(seed)
    samples = []
    for article_id in rng.permutation(len(articles)):
        article = articles[article_id]
        ids = tokenizer.encode(article).ids
        if len(ids) < length + 1:
            continue
        start = int(rng.integers(0, len(ids) - length))
        selected = ids[start : start + length + 1]
        samples.append(
            {
                "article_id": int(article_id),
                "title": article.strip().splitlines()[0],
                "article_sha256": hashlib.sha256(article.encode()).hexdigest(),
                "token_offset": start,
                "tokens": selected,
            }
        )
        if len(samples) == count:
            break
    if len(samples) != count:
        raise ValueError(
            f"Only found {len(samples)} articles for requested {count} windows"
        )
    return samples, {"url": url, "sha256": sha256(path), "articles": len(articles)}


def metrics(logits, reference, targets):
    lp = log_probabilities(logits)
    rp = log_probabilities(reference)
    probability = np.exp(rp)
    return {
        "nll": -lp[np.arange(len(targets)), targets],
        "kl": np.maximum((probability * (rp - lp)).sum(axis=-1), 0),
        "tv": np.abs(probability - np.exp(lp)).sum(axis=-1) / 2,
        "agreement": (logits.argmax(axis=-1) == reference.argmax(axis=-1)).astype(
            float
        ),
    }


def metric_summary(arrays):
    result = {name: float(np.mean(value)) for name, value in arrays.items()}
    result["perplexity"] = math.exp(result["nll"])
    result["tokens"] = int(np.size(arrays["nll"]))
    return result


def repetition(tokens):
    grams = [tuple(tokens[i : i + 4]) for i in range(max(0, len(tokens) - 3))]
    count = Counter(grams)
    longest, run, previous = 0, 0, None
    for token in tokens:
        run = run + 1 if token == previous else 1
        longest = max(longest, run)
        previous = token
    return {
        "repeated_4gram_fraction": sum(n - 1 for n in count.values())
        / max(1, len(grams)),
        "longest_identical_token_run": longest,
        "generated_tokens": len(tokens),
    }


def generate(model, tokenizer, prompts, count):
    encoded = [tokenizer.encode(prompt).ids for prompt in prompts]
    width = max(map(len, encoded))
    ids = np.full((len(encoded), width), 50256, np.int64)
    valid = np.zeros_like(ids, bool)
    for row, tokens in enumerate(encoded):
        ids[row, -len(tokens) :] = tokens
        valid[row, -len(tokens) :] = True
    state, cache = model.hidden(ids, valid=valid)
    outputs = [[] for _ in prompts]
    stopped = np.zeros(len(prompts), bool)
    for step in range(count):
        logits = model.linear("head", state[:, -1:])[:, 0]
        chosen = logits.argmax(axis=-1)
        for row, token in enumerate(chosen):
            if not stopped[row]:
                outputs[row].append(int(token))
                stopped[row] = token == 50256
        if stopped.all() or step == count - 1:
            break
        state, cache = model.hidden(chosen[:, None], cache=cache)
    return [
        {
            "prompt": prompt,
            "tokens": tokens,
            "continuation": tokenizer.decode(tokens),
            "text": prompt + tokenizer.decode(tokens),
            "eos": bool(tokens and tokens[-1] == 50256),
            **repetition(tokens),
        }
        for prompt, tokens in zip(prompts, outputs)
    ]


def verify_reference(checkpoint, tokenizer):
    ids = tokenizer.encode("Hello, my name is").ids
    model = Model(checkpoint)
    hidden, _ = model.hidden([ids])
    full = model.linear("head", hidden)[0]
    scalar = Runner(*checkpoint)
    expected = np.stack([scalar.token(token) for token in ids])
    cache, cached = None, []
    for token in ids:
        hidden, cache = model.hidden([[token]], cache=cache)
        cached.append(model.linear("head", hidden)[0, 0])
    error = float(np.max(np.abs(full - expected)))
    cache_error = float(np.max(np.abs(full - np.stack(cached))))
    if error > 0.002 or cache_error > 0.002:
        raise AssertionError(f"Reference mismatch: scalar={error}, cache={cache_error}")
    # Left padding must not change any valid token's positions or attention.
    padded, _ = model.hidden(
        [[50256, 50256, *ids]], valid=[[False, False, *([True] * len(ids))]]
    )
    padding_error = float(np.max(np.abs(model.linear("head", padded)[0, 2:] - full)))
    if padding_error > 0.002:
        raise AssertionError(f"Padding mismatch: {padding_error}")
    greedy = generate(model, tokenizer, ["Hello"], 8)[0]["tokens"]
    if greedy != [11, 314, 1101, 7926, 11, 475, 314, 1101]:
        raise AssertionError(f"Known reference continuation mismatch: {greedy}")
    return {
        "scalar_max_logit_error": error,
        "cache_max_logit_error": cache_error,
        "left_padding_max_logit_error": padding_error,
        "known_hello_tokens": greedy,
    }


def legacy_calibration(checkpoint):
    """Reproduce the old eight short prompts + eight FP32 generated tokens.

    Reuse its original tokenizer/Runner here only, to isolate range selection
    from the approximation arithmetic on the new identical test corpus.
    """
    tokenizer = Gpt2Tokenizer(
        ROOT / "data/gpt2/vocab.json", ROOT / "data/gpt2/merges.txt"
    )
    trace = defaultdict(list)
    for prompt in CALIBRATION_PROMPTS:
        runner = Runner(*checkpoint, trace=trace)
        logits = None
        for token in tokenizer.encode(prompt):
            logits = runner.token(token)
        for _ in range(8):
            logits = runner.token(int(np.argmax(logits)))
    calibration = Calibration()
    for name, parts in trace.items():
        if not name.endswith(".probabilities"):
            for value in parts:
                Calibration.record(calibration.surfaces, name, value)
    return calibration


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--calibration-windows", type=int, default=16)
    parser.add_argument("--test-windows", type=int, default=24)
    parser.add_argument("--context", type=int, default=256)
    parser.add_argument("--generated-tokens", type=int, default=64)
    parser.add_argument(
        "--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS[:4])
    )
    parser.add_argument("--seed", type=int, default=20260916)
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append new variants only after checking the exact saved manifest",
    )
    args = parser.parse_args()
    if (
        min(
            args.calibration_windows,
            args.test_windows,
            args.context,
            args.generated_tokens,
        )
        < 1
    ):
        parser.error("Counts must be positive")
    args.out.mkdir(parents=True, exist_ok=True)
    tokenizer = get_tokenizer()
    started = time.perf_counter()
    checkpoint = load_model()
    checks = verify_reference(checkpoint, tokenizer)
    print(f"Reference checks passed: {checks}", flush=True)
    train, train_source = corpus_windows(
        "train", args.calibration_windows, args.context, args.seed, tokenizer, args.out
    )
    test, test_source = corpus_windows(
        "test", args.test_windows, args.context, args.seed + 1, tokenizer, args.out
    )
    assert not (
        {item["article_sha256"] for item in train}
        & {item["article_sha256"] for item in test}
    )
    manifest = {
        "revision": REVISION,
        "seed": args.seed,
        "context": args.context,
        "sources": {"train": train_source, "test": test_source},
        "calibration": train,
        "evaluation": test,
        "prompts": PROMPTS,
        "generated_tokens": args.generated_tokens,
        "model_sha256": sha256(ROOT / "data/gpt2/model.safetensors"),
        "tokenizer_sha256": {
            p: sha256(ROOT / "data/gpt2" / p) for p in ("vocab.json", "merges.txt")
        },
    }
    if (
        args.append
        and (args.out / "manifest.json").exists()
        and json.loads((args.out / "manifest.json").read_text()) != manifest
    ):
        raise ValueError("Cannot append: saved corpus/model/protocol differs")
    save_json(args.out / "manifest.json", manifest)
    reference = Model(checkpoint)
    calibration = Calibration()
    reference.trace = calibration
    for index, sample in enumerate(train):
        reference.hidden([sample["tokens"][:-1]])
        print(f"Calibrated train window {index + 1}/{len(train)}", flush=True)
    reference.trace = None
    np.savez_compressed(
        args.out / "calibration.npz",
        **{
            **{f"surface.{k}": v for k, v in calibration.surfaces.items()},
            **{f"linear.{k}": v for k, v in calibration.linear_inputs.items()},
        },
    )
    reference_hidden = [
        reference.hidden([sample["tokens"][:-1]])[0][0] for sample in test
    ]
    result = {
        "kind": "offline_numerical_screening_not_browser",
        "checks": checks,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "context": args.context,
        "test_windows": len(test),
        "variants": {},
    }
    if args.append and (args.out / "results.json").exists():
        result = json.loads((args.out / "results.json").read_text())
    for variant in args.variants:
        if args.append and variant in result["variants"]:
            raise ValueError(f"Variant {variant} already exists; refusing to overwrite")
        print(f"Starting {variant}", flush=True)
        variant_start = time.perf_counter()
        chosen_calibration = (
            legacy_calibration(checkpoint)
            if variant == "svg_legacy_ranges"
            else calibration
        )
        model = (
            reference
            if variant == "fp32"
            else Model(checkpoint, variant, chosen_calibration)
        )
        arrays = {key: [] for key in ("nll", "kl", "tv", "agreement")}
        per_window = []
        for index, sample in enumerate(test):
            hidden = (
                reference_hidden[index]
                if variant == "fp32"
                else model.hidden([sample["tokens"][:-1]])[0][0]
            )
            window = {key: [] for key in arrays}
            # Bound full-vocabulary metric RAM to 32 rows per chunk.
            for start in range(0, args.context, 32):
                stop = min(start + 32, args.context)
                ref_logits = reference.linear(
                    "head", reference_hidden[index][start:stop]
                )
                logits = (
                    ref_logits
                    if variant == "fp32"
                    else model.linear("head", hidden[start:stop])
                )
                measured = metrics(
                    logits, ref_logits, sample["tokens"][start + 1 : stop + 1]
                )
                for key, value in measured.items():
                    window[key].extend(value.tolist())
            for key, values in arrays.items():
                values.append(window[key])
            per_window.append(
                {"article_id": sample["article_id"], **metric_summary(window)}
            )
            print(
                f"{variant} test {index + 1}/{len(test)}: PPL={per_window[-1]['perplexity']:.3f}",
                flush=True,
            )
        arrays = {key: np.asarray(value) for key, value in arrays.items()}
        np.savez_compressed(args.out / f"{variant}-metrics.npz", **arrays)
        teacher_stats = model.stats
        model.reset_stats()
        continuations = generate(model, tokenizer, PROMPTS, args.generated_tokens)
        buckets = {}
        for first, last in (
            (1, 16),
            (17, 64),
            (65, 128),
            (129, 256),
            (257, 512),
            (513, 1024),
        ):
            if first <= args.context:
                buckets[f"{first}-{min(last, args.context)}"] = metric_summary(
                    {
                        key: value[:, first - 1 : min(last, args.context)]
                        for key, value in arrays.items()
                    }
                )
        result["variants"][variant] = {
            "overall": metric_summary(arrays),
            "per_window": per_window,
            "context_buckets": buckets,
            "teacher_forced_surface_stats": teacher_stats,
            "continuations": continuations,
            "mean_repeated_4gram_fraction": float(
                np.mean([r["repeated_4gram_fraction"] for r in continuations])
            ),
            "offline_evaluation_seconds_NOT_inference_timing": time.perf_counter()
            - variant_start,
        }
        save_json(args.out / "results.json", result)
        print(
            f"FINISHED {variant}: {result['variants'][variant]['overall']}", flush=True
        )
        if model is not reference:
            del model
            gc.collect()
    result["offline_total_seconds_NOT_inference_timing"] = (
        result.get("offline_total_seconds_NOT_inference_timing", 0)
        + time.perf_counter()
        - started
    )
    save_json(args.out / "results.json", result)
    print(f"Results: {args.out / 'results.json'}", flush=True)


if __name__ == "__main__":
    main()
