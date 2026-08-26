#!/usr/bin/env python3
# /// script
# dependencies = ["numpy==2.5.3"]
# ///
"""Render the reproducible offline comparison and all uncurated continuations."""

import argparse
import json
from pathlib import Path

import numpy as np

LABELS = {
    "fp32": "FP32",
    "w8a8": "Naive dynamic W8A8",
    "smoothquant_w8a8": "SmoothQuant-style W8A8",
    "svg": "SVG-like 8-bit surfaces",
    "svg_float_probabilities": "SVG-like, FP32 attention probabilities (diagnostic)",
    "svg_legacy_ranges": "SVG-like, old short-prompt calibration (control)",
}


def paired_interval(values, seed=20260916):
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, (10000, len(values))).mean(axis=1)
    return np.quantile(draws, [0.025, 0.975]).tolist()


def summarize(out):
    result = json.loads((out / "results.json").read_text())
    manifest = json.loads((out / "manifest.json").read_text())
    baseline = result["variants"]["fp32"]["overall"]
    base_nll = np.load(out / "fp32-metrics.npz")["nll"]
    lines = [
        "# GPT-2 quantization quality: matched held-out comparison",
        "",
        "**Offline numerical screening, not a Chromium quality or speed benchmark.** No browser/runtime files were modified. No JavaScript was used.",
        "",
        f"{baseline['tokens']:,} teacher-forced next-token predictions: {manifest['context']}-token windows from {len(manifest['evaluation'])} distinct WikiText-2 **test** articles. Main calibration: {len(manifest['calibration']) * manifest['context']:,} tokens from {len(manifest['calibration'])} distinct **train** articles; the separately labeled old-range control uses the original short prompts. Same checkpoint, tokenizer, test tokens and generation prompts for every variant. No test-set scale fitting.",
        "",
        "Lower perplexity is better. Relative perplexity measures ground-truth predictive likelihood, not a percentage of intelligence or task accuracy. Exact token agreement is only a diagnostic.",
        "",
        "| Numerical recipe | Perplexity | Change vs FP32 | ΔNLL, nats/token (95% paired CI) | KL(FP32‖variant) | Top-1 agreement |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    analysis = {}
    for name, row in result["variants"].items():
        metrics = row["overall"]
        nll = np.load(out / f"{name}-metrics.npz")["nll"]
        delta = (nll - base_nll).mean(axis=1)
        ci = paired_interval(delta)
        ratio = metrics["perplexity"] / baseline["perplexity"]
        analysis[name] = {
            "ppl_ratio": ratio,
            "delta_nll": float(delta.mean()),
            "delta_nll_paired_article_bootstrap_95pct": ci,
            "ppl_ratio_paired_article_bootstrap_95pct": np.exp(ci).tolist(),
            "windows_with_higher_nll": int(np.count_nonzero(delta > 0)),
        }
        lines.append(
            f"| {LABELS[name]} | {metrics['perplexity']:.2f} | {(ratio - 1) * 100:+.1f}% | {delta.mean():+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}] | {metrics['kl']:.4f} | {metrics['agreement'] * 100:.1f}% |"
        )
    if "svg" in analysis:
        lines += [
            "",
            "## What this means",
            "",
            f"The SVG-like approximation has a {(analysis['svg']['ppl_ratio'] - 1) * 100:.1f}% perplexity increase on this sample. Its top-1 disagreement is **not** an equivalent percentage loss of model quality. This makes a calibrated SVG route worth investigating, but does not establish production acceptability or commercial-provider equivalence.",
        ]
        if "svg_legacy_ranges" in analysis:
            old = result["variants"]["svg_legacy_ranges"]["overall"]["perplexity"]
            new = result["variants"]["svg"]["overall"]["perplexity"]
            lines += [
                "",
                f"**Range calibration is a major part of the old failure:** holding the SVG approximation and evaluation text fixed, replacing the old short-prompt ranges with train-corpus ranges changes perplexity from **{old:.2f} to {new:.2f}**. No additional activation bits, extra planes or model finetuning were used. This isolates calibration as a large effect in the simulator; it does not prove that recalibration will repair Chromium's omitted arithmetic errors.",
            ]
        if "svg_float_probabilities" in analysis:
            svg_nll = np.load(out / "svg-metrics.npz")["nll"]
            float_nll = np.load(out / "svg_float_probabilities-metrics.npz")["nll"]
            difference = (svg_nll - float_nll).mean(axis=1)
            interval = paired_interval(difference)
            analysis["probability_rounding_effect"] = {
                "delta_nll_svg_minus_float_probability": float(difference.mean()),
                "paired_article_bootstrap_95pct": interval,
            }
            lines += [
                "",
                f"Removing attention-probability rounding only changes PPL from {result['variants']['svg']['overall']['perplexity']:.2f} to {result['variants']['svg_float_probabilities']['overall']['perplexity']:.2f}. Its paired ΔNLL interval is [{interval[0]:+.4f}, {interval[1]:+.4f}] nats/token; this run does not establish it as the dominant error source. Longer contexts than {manifest['context']} tokens remain untested.",
            ]
        lines += [
            "",
            "**Next acceptance test:** apply train-only calibration to the actual Chromium SVG graph and measure held-out next-token likelihoods using a Python-only diagnostic harness. Validate the graph's product/reduction and nonlinear rounding, then full cached decoding. Keep the working font/CSS pipeline unchanged until that test passes. Do not replace that acceptance test with another simplified simulator result.",
        ]
    lines += [
        "",
        "Intervals resample the paired article/windows (10,000 bootstrap draws); they cover sampling uncertainty on this small corpus, not systematic simulator error. This is **not** published full-WikiText perplexity: each window starts with an empty cache and position zero.",
        "",
        "## Recipes",
        "",
        "- **FP32:** original checkpoint, full 12-block causal attention and 50,257-token output head.",
        "- **Naive dynamic W8A8:** signed INT8 weights, per-output-channel scale; signed INT8 linear inputs, dynamic per-token scale. Q/DQ simulation with FP32 accumulation, bias, nonlinearities, residuals, attention and KV storage. An intentionally simple baseline, not a provider-quality implementation.",
        "- **SmoothQuant-style W8A8:** same quantizer, with calibration-derived input-channel scaling `s = sqrt(max_abs_activation / max_abs_weight)`, then `x / s` and `s * W` before Q/DQ (alpha 0.5). Applied to all linear layers including the output head. This implements the numerical reparameterization, not an official library's kernels. No finetuning.",
        "- **SVG-like:** existing fixed 32 log-range groups, 10% headroom, 8-bit materialization at input, normalized activations, QKV/cache, context, attention outputs, both residuals, FC, GELU, projection and final hidden vector. Attention scores use per-head calibrated surfaces; probabilities round to multiples of 1/255 without renormalization. Weights use the legacy **signed-magnitude ±255** recipe, not ordinary signed INT8. Input embeddings stay FP32 in all variants.",
        "- **FP32-probability diagnostic:** identical SVG approximation except probability rounding is removed. This is an error-isolation experiment, **not** an implemented SVG workaround or a browser-feasible precision claim.",
        "",
        "- **Old-range control (when present):** same SVG approximation and identical evaluation tokens, but ranges come from the original eight short calibration prompts plus eight FP32 generated tokens each. This deliberately changes calibration, not precision or arithmetic, to test the effect of range selection.",
        "",
        "The SVG screen still uses FP32 dot-product accumulation, exact FP32 layernorm/GELU/softmax followed by the listed rounding, and an FP32-accumulated output-head dot product. It omits Chromium product/reduction/filter-boundary rounding, approximation tables and readback. Thus its error is **not** certified browser error, and it is not a proven upper or lower bound.",
        "",
        "## Context-position breakdown",
        "",
        "Every row below uses the same windows; early positions have less context. Do not interpret naturally falling perplexity with context as improving numerical fidelity—compare relative degradation.",
        "",
        "| Available context | FP32 PPL | SmoothQuant-style PPL | SVG-like PPL | SVG / FP32 | SVG KL |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for bucket, base in result["variants"]["fp32"]["context_buckets"].items():
        sq = (
            result["variants"]
            .get("smoothquant_w8a8", {})
            .get("context_buckets", {})
            .get(bucket, {})
        )
        svg = (
            result["variants"].get("svg", {}).get("context_buckets", {}).get(bucket, {})
        )
        if sq and svg:
            lines.append(
                f"| {bucket} tokens | {base['perplexity']:.2f} | {sq['perplexity']:.2f} | {svg['perplexity']:.2f} | {svg['perplexity'] / base['perplexity']:.2f}× | {svg['kl']:.4f} |"
            )
    lines += ["", "## Clipping and attention probability rounding", ""]
    for name, row in result["variants"].items():
        stats = row["teacher_forced_surface_stats"]
        surface = {k: v for k, v in stats.items() if "clipped" in v}
        if not surface:
            continue
        clipped = sum(v["clipped"] for v in surface.values())
        elements = sum(v["elements"] for v in surface.values())
        analysis[name]["clipped_elements"] = clipped
        analysis[name]["materialized_elements"] = elements
        lines += [
            f"### {LABELS[name]}",
            "",
            f"{clipped:,} / {elements:,} materialized values outside calibrated bounds ({100 * clipped / elements:.5f}%). Low clipping does not imply low rounding error.",
            "",
            "| Surface | Clipped values | Percent of that surface |",
            "|---|---:|---:|",
        ]
        for key, stat in sorted(
            surface.items(), key=lambda item: item[1]["clipped"], reverse=True
        )[:8]:
            lines.append(
                f"| {key} | {stat['clipped']:,} | {100 * stat['clipped'] / stat['elements']:.5f}% |"
            )
        probability = [v for k, v in stats.items() if k.endswith(".probabilities")]
        if probability:
            zero = sum(v["rounded_to_zero"] for v in probability)
            total = sum(v["elements"] for v in probability)
            rows = sum(v["rows"] for v in probability)
            lost = sum(v["lost_mass"] for v in probability) / rows
            row_error = sum(v["row_sum_abs_error"] for v in probability) / rows
            analysis[name]["attention_probabilities"] = {
                "rounded_to_zero_fraction": zero / total,
                "mean_mass_lost_to_zero": lost,
                "mean_abs_row_sum_error": row_error,
            }
            lines += [
                "",
                f"Of valid attention entries, {100 * zero / total:.2f}% round from positive to zero. Mean probability mass lost to those zeros: {100 * lost:.3f}% per attention row; mean absolute row-sum error: {100 * row_error:.3f}%. These are measured approximation effects, not by themselves a quality score.",
            ]
        lines.append("")
    lines += [
        "## Longer greedy continuations",
        "",
        f"{len(manifest['prompts'])} fixed prompts, up to {manifest['generated_tokens']} newly generated tokens each; stop on EOS. No sampling, repetition penalty or prompt-dependent tuning. All outputs are saved in `CONTINUATIONS.md`, not cherry-picked.",
        "",
        "| Recipe | Mean repeated 4-gram fraction | EOS within budget |",
        "|---|---:|---:|",
    ]
    for name, row in result["variants"].items():
        eos = sum(r["eos"] for r in row["continuations"])
        lines.append(
            f"| {LABELS[name]} | {100 * row['mean_repeated_4gram_fraction']:.1f}% | {eos}/{len(manifest['prompts'])} |"
        )
    lines += [
        "",
        "Repetition is `(total 4-grams − unique 4-grams) / total 4-grams`, computed on generated tokens only. This tiny greedy sample is **not a coherence benchmark**; GPT-2 itself can repeat or hallucinate. Divergent continuations alone are not proof of worse quality.",
        "",
        "## Validation, provenance and limits",
        "",
        f"- Batched FP32 vs existing scalar implementation, max logit error: {result['checks']['scalar_max_logit_error']:.8f}; cached vs full: {result['checks']['cache_max_logit_error']:.8f}; left padding: {result['checks']['left_padding_max_logit_error']:.8f}.",
        "- Known eight-token `Hello` continuation reproduced exactly. Unit/integration tests additionally cover quantizer bounds, calibration equivalence, metrics, causality and SVG-vs-legacy simulation agreement.",
        "- Rust `tokenizers` byte-level GPT-2 BPE uses the checkpoint vocab/merges, including Unicode splitting. The older ASCII-only helper is not used for this corpus.",
        f"- [WikiText-2 dataset](https://huggingface.co/datasets/Salesforce/wikitext), revision `{manifest['revision']}`. Dataset card: CC-BY-SA 3.0 / GFDL. `manifest.json` records source hashes, checkpoint/tokenizer hashes, article selections, exact token windows and seed.",
        "- Numerical baseline informed by [SmoothQuant](https://arxiv.org/abs/2211.10438) and its [official implementation](https://github.com/mit-han-lab/smoothquant). This test does not measure any commercial inference provider, FP8 model, INT4 model, or GPU kernel.",
        "- Earlier **actual Chromium** one-token SVG-core tests achieved 61/84 (four GELU bands) or 63/84 (32 bands) held-out winner agreement. Those are a different workload without corpus likelihoods; see `../svg-filter-bias-correction/RESULTS.md`. They cannot be substituted for this evaluation or combined into an end-to-end speed claim.",
        "- No matched browser perplexity run or complete SVG decoding latency was measured here. JSON execution durations are evaluator costs, **not inference speeds**. The working native font/CSS demo remains unchanged.",
        "",
        "## Reproduce",
        "",
        "```sh",
        "VECLIB_MAXIMUM_THREADS=4 uv run tools/evaluate_gpt2_quantization_quality.py --variants fp32 w8a8 smoothquant_w8a8 svg svg_float_probabilities",
        "VECLIB_MAXIMUM_THREADS=4 uv run tools/evaluate_gpt2_quantization_quality.py --variants svg_legacy_ranges --append",
        "VECLIB_MAXIMUM_THREADS=4 uv run --with numpy==2.5.3 python -m unittest discover -s tools -p test_gpt2_quantization_quality.py -v",
        "uv run tools/report_gpt2_quantization_quality.py",
        "```",
        "",
    ]
    (out / "RESULTS.md").write_text("\n".join(lines))
    (out / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n")
    continuations = [
        "# All greedy continuations",
        "",
        "Uncurated fixed-prompt outputs. Numbers in the quality report are corpus-based; these are inspection samples.",
        "",
    ]
    for index, prompt in enumerate(manifest["prompts"]):
        continuations += [f"## {index + 1}. {prompt}", ""]
        for name, row in result["variants"].items():
            output = row["continuations"][index]
            continuations += [
                f"### {LABELS[name]}",
                "",
                "```text",
                output["text"],
                "```",
                "",
            ]
    (out / "CONTINUATIONS.md").write_text("\n".join(continuations))
    print(json.dumps(analysis, indent=2))
    print(out / "RESULTS.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "experiments/gpt2-quantization-quality",
    )
    summarize(parser.parse_args().out)
