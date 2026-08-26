#!/usr/bin/env python3
"""Build a CSS-only exact hierarchical argmax over real TinyStories logits."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import build_output_head_benchmark as output_head


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "grid-hierarchical-output-head"
VOCABULARY = 50_257
GROUP_SIZE = 256
LAYOUT_UNITS_PER_PX = 64
SCORE_SCALE = 1_024
SCORE_STRIDE_PX = GROUP_SIZE // LAYOUT_UNITS_PER_PX


def render_css(hidden_vectors: np.ndarray, floor: int, groups: int) -> str:
    dot_terms = [
        f"var(--h{dimension})*attr(a{dimension} type(<number>))"
        for dimension in range(hidden_vectors.shape[1])
    ]
    group_rules = [
        f".group-{group}{{anchor-name:--group-{group}}}"
        for group in range(groups)
    ]
    carrier_rules = [
        f".carrier-{group}{{--flag:clamp(0,1 - abs(var(--group) - {group}),1);"
        f"position-anchor:--group-{group};anchor-name:--carrier-{group};"
        f"width:calc(anchor-size(--group-{group} width) * var(--flag))}}"
        for group in range(groups)
    ]
    carrier_sizes = ",".join(
        f"anchor-size(--carrier-{group} width)" for group in range(groups)
    )
    return "\n".join(
        [
            '@property --score{syntax:"<number>";inherits:false;initial-value:0}',
            '@property --bucket{syntax:"<number>";inherits:true;initial-value:0}',
            '@property --group{syntax:"<number>";inherits:true;initial-value:0}',
            '@property --local{syntax:"<number>";inherits:true;initial-value:0}',
            '@property --winner{syntax:"<number>";inherits:true;initial-value:0}',
            '@property --flag{syntax:"<number>";inherits:true;initial-value:0}',
            output_head.query_rules(hidden_vectors),
            "*{box-sizing:border-box}html,body{margin:0;overflow:clip}body{anchor-scope:all}",
            ".model{position:fixed;inset:0 auto auto 0;display:grid;"
            "grid-template-columns:max-content;grid-template-rows:1px;"
            "width:max-content;height:1px;anchor-name:--outer-winner}",
            ".group-wrapper{grid-area:1/1;display:block;"
            f"width:calc-size(max-content,calc(round(down,size,{SCORE_STRIDE_PX}px) + "
            f"var(--group-tie)/{LAYOUT_UNITS_PER_PX}*1px))}}",
            ".group-grid{display:grid;grid-template-columns:max-content;"
            "grid-template-rows:1px;width:max-content;height:1px}",
            ".candidate{grid-area:1/1;display:block;justify-self:start;height:1px;"
            f"--score:calc({' + '.join(dot_terms)});"
            f"--bucket:round(nearest,clamp(0,(var(--score) - {floor})*{SCORE_SCALE},65535),1);"
            f"width:calc(var(--bucket)*{SCORE_STRIDE_PX}px + var(--local-tie)/{LAYOUT_UNITS_PER_PX}*1px)}}",
            "".join(group_rules),
            ".outer-reader{position:fixed;position-anchor:--outer-winner;"
            "inset:2px auto auto 0;width:anchor-size(--outer-winner width);height:1px;"
            "container:outer-result/inline-size}",
            "@container outer-result (width >= 0px){.selection{"
            f"--group:calc({GROUP_SIZE - 1} - round(nearest,"
            f"mod(100cqi,{SCORE_STRIDE_PX}px)/1px*{LAYOUT_UNITS_PER_PX},1));"
            f"--bucket:round(down,100cqi/{SCORE_STRIDE_PX}px,1)}}",
            ".carrier,.selected,.selected-reader{position:fixed;height:1px}",
            "".join(carrier_rules),
            ".selected{position-anchor:--carrier-0;anchor-name:--selected-group;"
            f"width:max({carrier_sizes})}}",
            ".selected-reader{position-anchor:--selected-group;"
            "width:anchor-size(--selected-group width);container:selected-result/inline-size}",
            "@container selected-result (width >= 0px){.result{"
            f"--local:calc({GROUP_SIZE - 1} - round(nearest,"
            f"mod(100cqi,{SCORE_STRIDE_PX}px)/1px*{LAYOUT_UNITS_PER_PX},1));"
            f"--winner:calc(var(--group)*{GROUP_SIZE} + var(--local));"
            "display:block;width:calc(var(--winner)*1px);height:1px}}",
        ]
    ) + "\n"


def render_html(embeddings: np.ndarray, groups: int) -> str:
    group_markup = []
    for group in range(groups):
        start = group * GROUP_SIZE
        stop = min(len(embeddings), start + GROUP_SIZE)
        items = []
        for token in range(start, stop):
            attributes = " ".join(
                f"a{dimension}={output_head.css_number(weight)}"
                for dimension, weight in enumerate(embeddings[token])
            )
            items.append(
                f'<i class="candidate" style="--local-tie:{GROUP_SIZE - 1 - token % GROUP_SIZE}" '
                f"{attributes}></i>"
            )
        group_markup.append(
            f'<section class="group-wrapper" style="--group-tie:{GROUP_SIZE - 1 - group}">'
            f'<div class="group-grid group-{group}">{"".join(items)}</div></section>'
        )
    carriers = "".join(
        f'<i class="carrier carrier-{group}"></i>' for group in range(groups)
    )
    controls = "".join(
        f'<input type="radio" name="query" id="q{query}"{(" checked" if query == 0 else "")}>'
        for query in range(len(output_head.PROMPTS))
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Hierarchical Grid TinyStories output head</title>
<link rel="stylesheet" href="index.css">
{controls}
<main id="model" class="model">{"".join(group_markup)}</main>
<div class="outer-reader"><div class="selection">
{carriers}<i class="selected"></i>
<div class="selected-reader"><output id="result" class="result"></output></div>
</div></div>
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    state = output_head.load_torch_zip(output_head.download_checkpoint())
    tokenizer = output_head.BUILDER.Gpt2Tokenizer(
        ROOT / "data" / "tiny-gpt2" / "vocab.json",
        ROOT / "data" / "tiny-gpt2" / "merges.txt",
    )
    hidden_vectors = np.stack(
        [output_head.final_hidden(tokenizer.encode(prompt), state)
         for prompt in output_head.PROMPTS]
    )
    embeddings = state["transformer.wte.weight"][:VOCABULARY]
    logits = hidden_vectors @ embeddings.T
    winners = logits.argmax(axis=1).astype(int)
    floor = math.floor(float(logits.min())) - 1
    buckets = np.rint(np.clip((logits - floor) * SCORE_SCALE, 0, 65_535)).astype(int)
    bucket_winners = buckets.argmax(axis=1)
    if not np.array_equal(winners, bucket_winners):
        raise RuntimeError(
            f"quantized winners {bucket_winners.tolist()} != {winners.tolist()}"
        )
    if int(buckets.max()) >= 65_535:
        raise RuntimeError("score quantizer clipped at its upper bound")
    groups = math.ceil(len(embeddings) / GROUP_SIZE)
    (OUTPUT / "index.css").write_text(render_css(hidden_vectors, floor, groups))
    (OUTPUT / "index.html").write_text(render_html(embeddings, groups))
    reference = {
        "model": "calum/tinystories-gpt2-3M",
        "prompts": output_head.PROMPTS,
        "vocabulary": len(embeddings),
        "width": embeddings.shape[1],
        "groups": groups,
        "scoreFloor": floor,
        "scoreScale": SCORE_SCALE,
        "winners": winners.tolist(),
        "maximums": logits.max(axis=1).astype(float).tolist(),
        "winnerBuckets": buckets[np.arange(len(winners)), winners].tolist(),
        "minimumWinnerMargin": float(np.min(
            np.max(logits, axis=1) - np.partition(logits, -2, axis=1)[:, -2]
        )),
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps(reference, indent=2))


if __name__ == "__main__":
    main()
