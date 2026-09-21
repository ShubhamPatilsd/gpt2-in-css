#!/usr/bin/env python3
"""Build a full-vocabulary GPT-2-small native token-to-embedding lookup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_hvar_token_embedding_lookup as lookup
import numpy as np
import r2c_hoist as r2c
from analyze_full_gpt2 import MODEL_PATH, SafeTensors

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2/embedding"
TOKENS = [
    15496,
    0,
    255,
    256,
    50256,
    995,
    11,
    13,
    262,
    314,
    382,
    37848,
    4101,
    9999,
    20000,
    40000,
]


TOKEN_GROUP = "round(down,calc(var(--token) / 256),1)"
TOKEN_LOCAL = "mod(var(--token),256)"
if r2c.HOIST_EMBEDDING:
    # R2C: the two token-derived axis values as typed numbers on the same element.
    TOKEN_SETTINGS = '"GRUP" var(--fq-token-group),"LOCL" var(--fq-token-local)'
    TOKEN_HOIST = r2c.private_regs(["--fq-token-group", "--fq-token-local"]) + (
        f".embedding-source{{--fq-token-group:{TOKEN_GROUP};--fq-token-local:{TOKEN_LOCAL}}}"
    )
else:
    TOKEN_SETTINGS = f'"GRUP" {TOKEN_GROUP},"LOCL" {TOKEN_LOCAL}'
    TOKEN_HOIST = ""


def compile_embedding(directory=OUT, with_epoch=False):
    properties = "".join(
        f'@property --embed-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}'
        f'@property --embedp-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}'
        f"@keyframes embedk{i}{{from{{--embedp-{i:03d}:0}}to{{--embedp-{i:03d}:1}}}}"
        for i in range(768)
    )
    css = properties + TOKEN_HOIST + (
        '@property --token{syntax:"<number>";inherits:true;initial-value:15496}'
        f'@font-face{{font-family:EmbeddingLookup;src:url("{(directory / "embedding-lookup.woff2").resolve().as_uri()}") format("woff2")}}'
        ".embedding-source{font:1000px EmbeddingLookup;font-kerning:none;"
        f"font-variation-settings:{TOKEN_SETTINGS};"
        "timeline-scope:" + ",".join(f"--embed-t{i}" for i in range(768)) + "}"
        ".embedding-scroller{position:fixed;left:0;top:-50000px;width:65536px;height:1px;overflow-x:scroll;overflow-y:hidden}"
        ".embedding-track{position:relative;width:196608px;height:1px}"
        ".embedding-metric{position:absolute;left:0;top:0;display:block;width:max-content;height:1px;white-space:pre;font-style:normal}"
    )
    metrics = "".join(
        f'<i class="embedding-metric" style="view-timeline:--embed-t{i} inline">&#x{0xE000 + i:X};</i>'
        for i in range(768)
    )
    child = '<div id="embedding-result">{child}</div>'
    for start in reversed(range(0, 768, 256)):
        css += (
            f".embedding-consumer-{start}{{animation-name:"
            + ",".join(f"embedk{i}" for i in range(start, start + 256))
            + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
            + ",".join(f"--embed-t{i}" for i in range(start, start + 256))
            + ";"
            + ";".join(
                f"--embed-{i:03d}:calc((65536 / var(--embedp-{i:03d}) - 65536 - 20000) / 4096)"
                for i in range(start, start + 256)
            )
            + "}"
        )
        child = f'<div class="embedding-consumer-{start}">{child}</div>'
    html = f'<div class="embedding-source"><div class="embedding-scroller"><div class="embedding-track">{metrics}</div></div>{child}</div>'
    if with_epoch:
        css += (
            '@property --embed-stamp{syntax:"<number>";inherits:true;initial-value:0}'
            '@property --embed-ready{syntax:"<number>";inherits:true;initial-value:0}'
            "@keyframes embedstamp{from{--embed-stamp:0}to{--embed-stamp:1}}"
            ".embedding-source{timeline-scope:"
            + ",".join(f"--embed-t{i}" for i in range(768))
            + ",--embed-epoch}"
            ".embedding-receipt{container-name:embeddingreceipt;animation:embedstamp 1s linear both;animation-timeline:--embed-epoch;"
            "--embed-ready:calc(1 - min(1,abs(round(nearest,(65536 / var(--embed-stamp) - 65536 - 20000) / 1024,1) - var(--epoch))))}"
        )
        marker = '<i class="embedding-metric" style="width:calc(20000px + var(--epoch)*1024px);view-timeline:--embed-epoch inline"></i>'
        html = html.replace(metrics, metrics + marker)
        html = html.replace(
            '<div id="embedding-result">{child}</div>',
            '<div class="embedding-receipt"><div id="embedding-result">{child}</div></div>',
        )
    return html, css


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    embedding = SafeTensors(MODEL_PATH).tensor("wte.weight")
    if not (args.output / "embedding-lookup.woff2").exists():
        lookup.FONT_PATH = args.output / "embedding-lookup.ttf"
        lookup.build_font(np.asarray(embedding, dtype=np.float64))
    html, css = compile_embedding(args.output)
    (args.output / "embedding.css").write_text(css)
    (args.output / "embedding-body.html").write_text(html)
    page = (
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><link rel="stylesheet" href="embedding.css"><body>'
        + html.replace("{child}", "")
        + "</body>"
    )
    (args.output / "index.html").write_text(page)
    reference = {
        "tokens": TOKENS,
        "embeddings": np.asarray(embedding[TOKENS], dtype=np.float64).tolist(),
        "width": 768,
        "vocabulary": 50257,
        "scale": 4096,
        "runtimeJavaScript": False,
    }
    (args.output / "reference.json").write_text(json.dumps(reference))
    print(
        {
            "fontBytes": (args.output / "embedding-lookup.woff2").stat().st_size,
            "vocabulary": 50257,
            "width": 768,
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
