#!/usr/bin/env python3
"""Build dynamic Q·K attention-score probes with two-lane CSS SWAR."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "anchor-swar-attention"
HEAD_WIDTH = 64
RADIX = 4_096
HALF_RADIX = RADIX // 2
SCALAR_BASE = 64
PAIR_BASE = 131_072
OUTPUT_BASE = 70_000
CASES = 2


def balanced_sum(terms: list[str]) -> str:
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return f"({balanced_sum(terms[:middle])} + {balanced_sum(terms[middle:])})"


def scalar_term(head: int, token: int, index: int) -> str:
    q = f"(anchor-size(--q-{head}-{index} width) / 1px - {SCALAR_BASE})"
    k = f"(anchor-size(--k-{head}-{token}-{index} width) / 1px - {SCALAR_BASE})"
    return f"1px * ({q} * {k})"


def pair_term(head: int, token: int, packet: int) -> str:
    q = f"(anchor-size(--qp-{head}-{packet} width) / 1px - {PAIR_BASE})"
    k = f"(anchor-size(--kp-{head}-{token}-{packet} width) / 1px - {PAIR_BASE})"
    return (
        "1px * (mod("
        f"round(nearest,({q} * {k}) / {RADIX},1) + {HALF_RADIX},"
        f"{RADIX}) - {HALF_RADIX})"
    )


def scalar_sources(prefix: str, values: np.ndarray) -> str:
    if prefix == "q":
        return "".join(
            f'<i class="q source" data-head="{head}" data-index="{index}" '
            f'style="width:{SCALAR_BASE + int(values[0, head, index])}px;'
            f'anchor-name:--q-{head}-{index}"></i>'
            for head in range(values.shape[1])
            for index in range(HEAD_WIDTH)
        )
    return "".join(
        f'<i class="k source" data-head="{head}" data-token="{token}" '
        f'data-index="{index}" '
        f'style="width:{SCALAR_BASE + int(values[0, head, token, index])}px;'
        f'anchor-name:--k-{head}-{token}-{index}"></i>'
        for head in range(values.shape[1])
        for token in range(values.shape[2])
        for index in range(HEAD_WIDTH)
    )


def paired(values: np.ndarray, *, reverse: bool = False) -> np.ndarray:
    if reverse:
        return values[..., 1::2] + RADIX * values[..., 0::2]
    return values[..., 0::2] + RADIX * values[..., 1::2]


def pair_sources(prefix: str, values: np.ndarray) -> str:
    packed = paired(values, reverse=prefix == "k")
    if prefix == "q":
        return "".join(
            f'<i class="q source" data-head="{head}" data-index="{packet}" '
            f'style="width:{PAIR_BASE + int(packed[0, head, packet])}px;'
            f'anchor-name:--qp-{head}-{packet}"></i>'
            for head in range(packed.shape[1])
            for packet in range(HEAD_WIDTH // 2)
        )
    return "".join(
        f'<i class="k source" data-head="{head}" data-token="{token}" '
        f'data-index="{packet}" '
        f'style="width:{PAIR_BASE + int(packed[0, head, token, packet])}px;'
        f'anchor-name:--kp-{head}-{token}-{packet}"></i>'
        for head in range(packed.shape[1])
        for token in range(packed.shape[2])
        for packet in range(HEAD_WIDTH // 2)
    )


def build(heads: int, tokens: int, seed: int) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    q = rng.integers(-31, 32, size=(CASES, heads, HEAD_WIDTH), dtype=np.int64)
    k = rng.integers(-31, 32, size=(CASES, heads, tokens, HEAD_WIDTH), dtype=np.int64)
    initial = np.einsum("hwd,hd->hw", k[0], q[0])
    query_only = np.einsum("hwd,hd->hw", k[0], q[1])
    full = np.einsum("hwd,hd->hw", k[1], q[1])

    output_markup = "".join(
        f'<i class="output o-{head}-{token}" data-head="{head}" '
        f'data-token="{token}"></i>'
        for head in range(heads)
        for token in range(tokens)
    )
    common = (
        "html,body{margin:0}.stage{position:fixed;inset:0;contain:layout style;"
        "anchor-scope:all}.source,.output{position:fixed;left:0;top:0;height:1px;"
        "display:block;visibility:hidden}"
    )
    pages = {}
    for variant in ("scalar", "pair"):
        rules = []
        for head in range(heads):
            for token in range(tokens):
                terms = (
                    [scalar_term(head, token, index) for index in range(HEAD_WIDTH)]
                    if variant == "scalar"
                    else [pair_term(head, token, packet) for packet in range(HEAD_WIDTH // 2)]
                )
                rules.append(
                    f".o-{head}-{token}{{width:calc({OUTPUT_BASE}px + "
                    f"{balanced_sum(terms)})}}"
                )
        sources = (
            scalar_sources("q", q) + scalar_sources("k", k)
            if variant == "scalar"
            else pair_sources("q", q) + pair_sources("k", k)
        )
        html = (
            "<!doctype html><meta charset=\"utf-8\"><title>"
            f"{variant} SWAR attention {heads} heads x {tokens} tokens</title>"
            f"<style>{common}{''.join(rules)}</style><main class=\"stage\">"
            f"{sources}{output_markup}</main>"
        )
        name = f"h{heads}-t{tokens}-{variant}.html"
        (OUT / name).write_text(html)
        pages[variant] = {"page": name, "bytes": len(html.encode())}

    reference = {
        "heads": heads,
        "tokens": tokens,
        "headWidth": HEAD_WIDTH,
        "radix": RADIX,
        "scalarBase": SCALAR_BASE,
        "pairBase": PAIR_BASE,
        "outputBase": OUTPUT_BASE,
        "q": q.tolist(),
        "k": k.tolist(),
        "pairedQ": paired(q).tolist(),
        "pairedK": paired(k, reverse=True).tolist(),
        "expectedInitial": initial.reshape(-1).tolist(),
        "expectedQueryOnly": query_only.reshape(-1).tolist(),
        "expectedFull": full.reshape(-1).tolist(),
        "pages": pages,
        "scalarTerms": heads * tokens * HEAD_WIDTH,
        "pairTerms": heads * tokens * HEAD_WIDTH // 2,
        "scalarSources": heads * HEAD_WIDTH * (tokens + 1),
        "pairSources": heads * HEAD_WIDTH * (tokens + 1) // 2,
    }
    name = f"h{heads}-t{tokens}.json"
    (OUT / name).write_text(json.dumps(reference) + "\n")
    return {"reference": name, **reference}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shapes", default="1x4,1x16,1x64,12x4,12x16,12x64")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    shapes = [
        tuple(int(value) for value in item.split("x", maxsplit=1))
        for item in args.shapes.split(",")
        if item
    ]
    manifest = [
        build(heads, tokens, 0xA77E + heads * 1009 + tokens)
        for heads, tokens in shapes
    ]
    (OUT / "manifest.json").write_text(json.dumps(manifest) + "\n")
    print(json.dumps([
        {
            "shape": f"{item['heads']}x{item['tokens']}",
            "scalarBytes": item["pages"]["scalar"]["bytes"],
            "pairBytes": item["pages"]["pair"]["bytes"],
            "scalarSources": item["scalarSources"],
            "pairSources": item["pairSources"],
        }
        for item in manifest
    ], indent=2))


if __name__ == "__main__":
    main()
