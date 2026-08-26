#!/usr/bin/env python3
"""Connect projected-KV attention to the matching real block-0 LN2/MLP tail."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np

from build_geometry_streaming_full_tail import extract_div
from build_gpt2_block_css import QUANT_BITS, gelu_new, layer_norm, model_data
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-block-css"
TAIL_SOURCE = OUT / "view-timeline-block-hybrid-packed4-chain-channel89asym-h15.html"
TAIL_CSS = "view-timeline-block-hybrid-packed4-chain-channel89asym-h15.css"
ATTENTION_PREFIX_CSS = "view-timeline-attention-prefix.css"
DIRECT_ATTENTION_PREFIX_CSS = "view-timeline-attention-prefix-tail-only.css"
SAFE_TAIL_SOURCE = OUT / "view-timeline-block-hybrid-packed4-chain.html"
SAFE_TAIL_CSS = "view-timeline-block-hybrid-packed4-chain.css"
MULTITOKEN_TAIL_SOURCE = (
    OUT / "view-timeline-block-hybrid-packed4-chain-channel89-h15.html"
)
MULTITOKEN_TAIL_CSS = "view-timeline-block-hybrid-packed4-chain-multitoken.css"
LEAF = '<output id="attention-result"></output>'
PACKET_LEAF = '<output class="geometry-projection-result" id="attention-result"></output>'
WIDTH = 768


def aliases(destination: str, source: str) -> str:
    return ";".join(
        f"--{destination}-{index:03d}:var(--{source}-{index:03d})"
        for index in range(WIDTH)
    )


def numeric_reference(residual: np.ndarray) -> dict[str, list[float]]:
    data = model_data(0, input_vector=residual)
    normalized = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    hidden = gelu_new(fc.reconstructed @ normalized + data["fc_bias"])
    projection = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
    final = residual + projection.reconstructed @ hidden + data["mlp_proj_bias"]
    importance = np.linalg.norm(projection.reconstructed, axis=0)
    ranked = np.argsort(importance)
    low = ranked[: len(hidden) // 2]
    high = ranked[len(hidden) // 2 :]
    groups = np.asarray([
        (low[group * 2], high[group * 2], low[group * 2 + 1], high[group * 2 + 1])
        for group in range(len(hidden) // 4)
    ], dtype=np.int64)
    packed_minimum = -0.25
    packed_maximum = 15.75
    packed_span = packed_maximum - packed_minimum
    levels = np.full(len(hidden), 511, dtype=np.int64)
    levels[low] = 255
    encoded = np.rint(
        np.sqrt(
            (np.clip(hidden, packed_minimum, packed_maximum) - packed_minimum)
            / packed_span
        ) * levels
    )
    packed_hidden = (encoded / levels) ** 2 * packed_span + packed_minimum
    packed_final = (
        residual
        + projection.reconstructed @ packed_hidden
        + data["mlp_proj_bias"]
    )
    return {
        "normalized": normalized.tolist(),
        "hidden": hidden.tolist(),
        "fullPrecisionPackedWeightReference": final.tolist(),
        "packedHidden": packed_hidden.tolist(),
        "packedReference": packed_final.tolist(),
        "packedGroups": groups.tolist(),
        "packedMinimum": packed_minimum,
        "packedMaximum": packed_maximum,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contexts", type=int, nargs="+", default=[16, 32])
    parser.add_argument(
        "--projection-transports",
        choices=("timeline", "packet6", "packet8", "packet12"),
        nargs="+",
        default=["timeline"],
    )
    parser.add_argument(
        "--score-backends",
        choices=("css-kv", "feature-kv", "bilinear-kv", "bilinear-sum-kv"),
        nargs="+",
        default=["feature-kv"],
    )
    args = parser.parse_args()
    source_tail = TAIL_SOURCE.read_text()
    prefix_css = (OUT / ATTENTION_PREFIX_CSS).read_text()
    direct_prefix_css, removed_r1 = re.subn(
        r"--r1-\d{3}:[^;}]+(?:;|(?=}))",
        "",
        prefix_css,
    )
    if removed_r1 != WIDTH:
        raise ValueError(f"expected to remove {WIDTH} stale residual declarations")
    (OUT / DIRECT_ATTENTION_PREFIX_CSS).write_text(direct_prefix_css)
    tail = extract_div(
        source_tail,
        '<div class="after-attn hybrid-packed4-mlp-stage"',
    )
    if tail.count('id="final"') != 1:
        raise ValueError("expected exactly one block-0 packed MLP output")
    tail = tail.replace(
        '<div class="after-attn hybrid-packed4-mlp-stage"',
        '<div class="after-attn hybrid-packed4-mlp-stage" style="'
        + aliases("r1", "attention-r1")
        + '"',
        1,
    )
    links = (
        f'<link rel="stylesheet" href="{TAIL_CSS}">'
        f'<link rel="stylesheet" href="{ATTENTION_PREFIX_CSS}">'
    )
    safe_tail_source = SAFE_TAIL_SOURCE.read_text()
    safe_tail = extract_div(
        safe_tail_source,
        '<div class="after-attn hybrid-packed4-mlp-stage"',
    ).replace(
        '<div class="after-attn hybrid-packed4-mlp-stage"',
        '<div class="after-attn hybrid-packed4-mlp-stage" style="'
        + aliases("r1", "attention-r1")
        + '"',
        1,
    )
    safe_links = (
        f'<link rel="stylesheet" href="{SAFE_TAIL_CSS}">'
        f'<link rel="stylesheet" href="{ATTENTION_PREFIX_CSS}">'
    )
    multitoken_tail_source = MULTITOKEN_TAIL_SOURCE.read_text()
    multitoken_direct_tail = extract_div(
        multitoken_tail_source,
        '<div class="after-attn hybrid-packed4-mlp-stage"',
    )
    multitoken_tail = multitoken_direct_tail.replace(
        '<div class="after-attn hybrid-packed4-mlp-stage"',
        '<div class="after-attn hybrid-packed4-mlp-stage" style="'
        + aliases("r1", "attention-r1")
        + '"',
        1,
    )
    multitoken_links = (
        f'<link rel="stylesheet" href="{MULTITOKEN_TAIL_CSS}">'
        f'<link rel="stylesheet" href="{ATTENTION_PREFIX_CSS}">'
    )
    direct_links = (
        f'<link rel="stylesheet" href="{MULTITOKEN_TAIL_CSS}">'
        f'<link rel="stylesheet" href="{DIRECT_ATTENTION_PREFIX_CSS}">'
    )
    generated = []
    jobs = [
        (context, transport, score_backend)
        for context in args.contexts
        for transport in args.projection_transports
        for score_backend in args.score_backends
    ]
    for context, projection_transport, score_backend in jobs:
        score_stem = {
            "css-kv": "css-kv-score",
            "feature-kv": "projected-kv-score",
            "bilinear-kv": "bilinear-kv-score",
            "bilinear-sum-kv": "bilinear-sum-kv-score",
        }[score_backend]
        source_stem = (
            f"attention-context-{context}-geometry-streaming-flat-"
            f"{score_stem}-cached-value-live-current-kv-siblings-"
            + (
                "projected"
                if projection_transport == "timeline"
                else f"projection-{projection_transport}"
            )
        )
        source_path = OUT / f"{source_stem}.html"
        reference_path = OUT / f"{source_stem}-reference.json"
        source = source_path.read_text()
        reference = json.loads(reference_path.read_text())
        residual = np.asarray(reference["residual"], dtype=np.float64)
        leaf = LEAF if projection_transport == "timeline" else PACKET_LEAF
        if source.count(leaf) != 1:
            raise ValueError(f"expected exactly one attention leaf in {source_path.name}")
        bridge = (
            '<div id="attention-result" style="'
            + aliases("attention-r1", "r1")
            + '">'
            + tail
            + "</div>"
        )
        connected = source.replace("</title>", f"</title>{links}", 1).replace(
            leaf, bridge, 1
        )
        output_path = OUT / f"{source_stem}-full-block0.html"
        output_path.write_text(connected)

        isolated_values = ";".join(
            f"--attention-r1-{index:03d}:{value:.12g}"
            for index, value in enumerate(residual)
        )
        isolated = (
            '<!doctype html><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f"<title>Isolated block-0 MLP, context {context}</title>{links}"
            f'<div id="attention-isolated" style="{isolated_values}">{tail}</div>'
        )
        isolated_path = OUT / f"{source_stem}-full-block0-isolated.html"
        isolated_path.write_text(isolated)
        safe_bridge = (
            '<div id="attention-result" style="'
            + aliases("attention-r1", "r1")
            + '">'
            + safe_tail
            + "</div>"
        )
        safe_connected = source.replace(
            "</title>", f"</title>{safe_links}", 1
        ).replace(leaf, safe_bridge, 1)
        safe_output_path = OUT / f"{source_stem}-full-block0-safe.html"
        safe_output_path.write_text(safe_connected)
        safe_isolated = (
            '<!doctype html><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f"<title>Isolated safe block-0 MLP, context {context}</title>{safe_links}"
            f'<div id="attention-isolated" style="{isolated_values}">{safe_tail}</div>'
        )
        safe_isolated_path = OUT / f"{source_stem}-full-block0-safe-isolated.html"
        safe_isolated_path.write_text(safe_isolated)
        multitoken_bridge = (
            '<div id="attention-result" style="'
            + aliases("attention-r1", "r1")
            + '">'
            + multitoken_tail
            + "</div>"
        )
        multitoken_connected = source.replace(
            "</title>", f"</title>{multitoken_links}", 1
        ).replace(leaf, multitoken_bridge, 1)
        multitoken_output_path = OUT / f"{source_stem}-full-block0-multitoken.html"
        multitoken_output_path.write_text(multitoken_connected)
        multitoken_isolated = (
            '<!doctype html><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f"<title>Isolated multitoken-calibrated block-0 MLP, context {context}</title>"
            f"{multitoken_links}"
            f'<div id="attention-isolated" style="{isolated_values}">'
            f"{multitoken_tail}</div>"
        )
        multitoken_isolated_path = (
            OUT / f"{source_stem}-full-block0-multitoken-isolated.html"
        )
        multitoken_isolated_path.write_text(multitoken_isolated)
        direct_bridge = (
            '<div id="attention-result">'
            + multitoken_direct_tail
            + "</div>"
        )
        direct_connected = source.replace(
            "</title>", f"</title>{direct_links}", 1
        ).replace(leaf, direct_bridge, 1)
        direct_output_path = (
            OUT / f"{source_stem}-full-block0-multitoken-direct.html"
        )
        direct_output_path.write_text(direct_connected)
        direct_isolated_values = ";".join(
            f"--r1-{index:03d}:{value:.12g}"
            for index, value in enumerate(residual)
        )
        direct_isolated = (
            '<!doctype html><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f"<title>Isolated direct multitoken block-0 MLP, context {context}</title>"
            f"{direct_links}"
            f'<div id="attention-isolated" style="{direct_isolated_values}">'
            f"{multitoken_direct_tail}</div>"
        )
        direct_isolated_path = (
            OUT / f"{source_stem}-full-block0-multitoken-direct-isolated.html"
        )
        direct_isolated_path.write_text(direct_isolated)
        output_reference = {
            "context": context,
            "attentionResidual": residual.tolist(),
            **numeric_reference(residual),
            "runtimeJavaScript": False,
        }
        full_reference_path = OUT / f"{source_stem}-full-block0-reference.json"
        full_reference_path.write_text(json.dumps(output_reference, indent=2) + "\n")
        generated.extend((
            output_path.name,
            isolated_path.name,
            safe_output_path.name,
            safe_isolated_path.name,
            multitoken_output_path.name,
            multitoken_isolated_path.name,
            direct_output_path.name,
            direct_isolated_path.name,
            full_reference_path.name,
        ))
    (OUT / "projected-kv-full-block0-manifest.json").write_text(
        json.dumps({
            "contexts": args.contexts,
            "projectionTransports": args.projection_transports,
            "scoreBackends": args.score_backends,
            "attention": "live current-token QKV with projected past KV cache",
            "tail": "matching real GPT-2 block-0 LN2, MLP, projection, and residual",
            "runtimeJavaScript": False,
            "generated": generated,
        }, indent=2) + "\n"
    )
    print({"contexts": args.contexts, "generated": len(generated)})


if __name__ == "__main__":
    main()
