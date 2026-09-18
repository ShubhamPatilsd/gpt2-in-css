#!/usr/bin/env python3
"""Full-vocabulary q16 head with bounded native geometry reductions.

Reuses the existing six analytic-LayerNorm-bounded HVAR fonts. Every token is
scored. A build-time, input-independent LayerNorm bound supplies the positive
score offset; no oracle-selected candidates or per-input floors are emitted.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import numpy as np
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_groupwise_production_q16_sixfont import (
    AXIS_STEPS,
    BANK,
    FACTOR,
    FONT_SIZE_PX,
    SCORE_GAIN,
    WEIGHT_SCALE,
    R,
    font_settings,
    parse_bank_rows,
    six_font_faces,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2/head"
GROUPS = 197


def bound_score_floor():
    tensors = SafeTensors(MODEL_PATH)
    gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    maximum = 0.0
    for start in range(0, 50257, 1024):
        w = np.asarray(
            tensors.tensor("wte.weight")[start : start + 1024], dtype=np.float64
        )
        w = np.rint(w / WEIGHT_SCALE) * WEIGHT_SCALE
        a = w * gamma
        radius = np.sqrt(768 * np.maximum(0, (a * a).sum(1) - a.sum(1) ** 2 / 768))
        center = np.abs(w @ beta)
        axis_rounding = np.abs(w).sum(1) * R / (2 * AXIS_STEPS)
        maximum = max(maximum, float(np.max(radius + center + axis_rounding)))
    # Two represented logit units also cover the measured transport buckets.
    return -math.ceil(maximum * SCORE_GAIN + 2)


def reduce_geometry(anchors, prefix, operation="max", fan_in=16):
    html, css, level = [], [], 0
    current = list(anchors)
    while len(current) > 1:
        following = []
        for start in range(0, len(current), fan_in):
            group = current[start : start + fan_in]
            name = f"--{prefix}-{level}-{start // fan_in}"
            cls = name[2:]
            widths = ",".join(f"anchor-size({a} width,0px)" for a in group)
            heights = ",".join(f"anchor-size({a} height,0px)" for a in group)
            html.append(f'<i class="head-reduction {cls}"></i>')
            css.append(
                f".{cls}{{anchor-name:{name};width:{operation}({widths});height:min({heights})}}"
            )
            following.append(name)
        current = following
        level += 1
    return "".join(html), "".join(css), current[0]


def compile_head(decoder="two-pass"):
    rows = parse_bank_rows()
    floor = bound_score_floor()
    faces, families = six_font_faces()
    faces = re.sub(
        r'url\("([^\"]+)"\)',
        lambda m: (
            f'url("{(BANK.parent / "gpt2-groupwise-cauchy-blockflow-production-range-q16-sixfont" / m[1]).resolve().as_uri()}")'
        ),
        faces,
    )
    css = faces + "".join(
        f'@property --h{i}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for i in range(768)
    )
    css += (
        '@property --winner{syntax:"<number>";inherits:true;initial-value:-1}'
        '@property --head-bucket{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --head-input-epoch{syntax:"<number>";inherits:true;initial-value:1}'
        ".full-head{anchor-scope:all;position:relative;width:1px;height:1px;"
        f"font:{FONT_SIZE_PX}px {families};font-variation-settings:{font_settings()};"
        "font-kerning:none;font-synthesis:none;line-height:1}"
        ".head-group{position:fixed;left:0;top:-80000px;display:grid;"
        "grid-template-columns:max-content;grid-template-rows:1px;width:max-content;height:calc(var(--head-input-epoch)*1px)}"
        ".head-row{grid-area:1/1;display:block;justify-self:start;height:1px;"
        "white-space:pre;overflow:hidden;font-style:normal;"
        f"width:calc-size(max-content,calc(round(nearest,(size - var(--base)*1px)*{FACTOR} "
        f"+ {-floor * 1024}px,4px) + var(--tie)/64*1px))}}"
        ".head-reduction,.head-score,.head-match{position:fixed;left:0;top:-70000px;"
        "height:1px;display:block;font:12px monospace}"
    )
    groups, score_boxes, matches = [], [], []
    for group in range(GROUPS):
        group_rows = rows[group * 256 : min((group + 1) * 256, len(rows))]
        markup = "".join(
            f'<i class="head-row" data-token="{row["token"]}" '
            f'style="--base:{row["base"]};--tie:{row["tie"]}">{row["glyphs"]}</i>'
            for row in group_rows
        )
        groups.append(
            f'<section class="head-group" style="anchor-name:--head-group-{group}">{markup}</section>'
        )
        score_boxes.append(f'<i class="head-score head-score-{group}"></i>')
        css += f".head-score-{group}{{anchor-name:--head-score-{group};width:round(down,anchor-size(--head-group-{group} width,0px),4px);height:anchor-size(--head-group-{group} height,0px)}}"
    score_html, score_css, score_anchor = reduce_geometry(
        [f"--head-score-{i}" for i in range(GROUPS)], "head-max"
    )
    css += score_css
    for group in range(GROUPS):
        matches.append(f'<i class="head-match head-match-{group}"></i>')
        css += (
            f".head-match-{group}{{anchor-name:--head-match-{group};width:calc("
            f"clamp(0px,anchor-size(--head-score-{group} width,0px) - anchor-size({score_anchor} width,0px) + 1px,1px)"
            f" * {(GROUPS - group) * 4} + mod(anchor-size(--head-group-{group} width,0px),4px))}}"
        )
        css += f".head-match-{group}{{height:min(anchor-size(--head-score-{group} height,0px),anchor-size({score_anchor} height,0px))}}"
    choice_html, choice_css, choice_anchor = reduce_geometry(
        [f"--head-match-{i}" for i in range(GROUPS)], "head-choice"
    )
    css += choice_css
    css += (
        f".head-reader{{position:fixed;left:0;top:0;width:anchor-size({choice_anchor} width,0px);"
        "height:1px;container:head-result/inline-size;font:12px monospace}"
        ".head-result{display:block;width:calc(var(--winner)*1px);height:1px;"
        "--winner:calc((197 - round(down,100cqi/4px,1))*256 + 255 - round(nearest,mod(100cqi,4px)/1px*64,1))}"
    )
    html = (
        '<div class="full-head" id="full-head">'
        + "".join(groups)
        + "".join(score_boxes)
        + score_html
        + "".join(matches)
        + choice_html
        + '<div class="head-reader"><output class="head-result" id="head-result">{child}</output></div></div>'
    )
    if decoder == "two-pass":
        # Keep large score widths integral. Local identity is selected in a
        # second 256-row pass with widths at most 256 px, avoiding loss of the
        # old 1/64-pixel tie digits when large scores cross float precision bins.
        css += (
            '@property --head-group-index{syntax:"<number>";inherits:true;initial-value:0}'
            '@property --head-max-score{syntax:"<number>";inherits:true;initial-value:0}'
            '@property --head-pipeline-epoch{syntax:"<number>";inherits:true;initial-value:0}'
            '@property --head-output-epoch{syntax:"<number>";inherits:true;initial-value:0}'
            f".head-row{{width:calc-size(max-content,round(nearest,(size - var(--base)*1px)*{FACTOR} + {-floor * 1024}px,4px))}}"
            f".head-coarse-reader{{position:fixed;left:0;top:-900000px;container-type:size;"
            f"width:anchor-size({choice_anchor} width,0px);height:calc(anchor-size({score_anchor} width,0px)*16 + anchor-size({choice_anchor} height,0px))}}"
            ".head-group-state{--head-group-index:calc(197 - round(nearest,100cqi/4px,1));"
            "--head-max-score:round(down,100cqb/16px,1);--head-pipeline-epoch:mod(round(nearest,100cqb/1px,1),16)}"
            ".head-fine{position:fixed;left:0;top:-80000px;display:grid;grid-template-columns:max-content;grid-template-rows:1px;"
            f"width:max-content;height:calc(var(--head-pipeline-epoch)*1px);anchor-name:--head-local;font:{FONT_SIZE_PX}px {families};"
            f"font-variation-settings:{font_settings()};font-kerning:none;font-synthesis:none}}"
            ".head-fine-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:hidden;font-style:normal;"
            f"width:calc-size(max-content,calc(clamp(0px,round(nearest,(size - var(--fine-base)*1px)*{FACTOR} + {-floor * 1024}px,4px) - var(--head-max-score)*1px + 1px,1px)*var(--rank)))}}"
            ".head-fine-row::before{content:var(--fine-glyphs)}"
            ".head-final-reader{position:fixed;left:0;top:0;width:anchor-size(--head-local width,0px);height:anchor-size(--head-local height,0px);container-type:size}"
            ".head-result{--winner:calc(var(--head-group-index)*256 + 256 - round(nearest,100cqi/1px,1));"
            "--head-output-epoch:round(nearest,100cqb/1px,1)}"
        )
        fine = []
        for local in range(256):
            selected = [rows[token] for token in range(local, 50257, 256)]
            bases = ";".join(
                f"style(--head-group-index:{g}):{row['base']}"
                for g, row in enumerate(selected)
            )
            glyphs = ";".join(
                f'style(--head-group-index:{g}):"{row["glyphs"]}"'
                for g, row in enumerate(selected)
            )
            css += f'.head-fine-row:nth-child({local + 1}){{--rank:{256 - local};--fine-base:if({bases};else:0);--fine-glyphs:if({glyphs};else:"");'
            if local >= 81:
                css += "display:if(style(--head-group-index:196):none;else:block);"
            css += "}"
            fine.append('<i class="head-fine-row"></i>')
        old = '<div class="head-reader"><output class="head-result" id="head-result">{child}</output></div>'
        replacement = (
            '<div class="head-coarse-reader"><div class="head-group-state"><div class="head-fine">'
            + "".join(fine)
            + '</div><div class="head-final-reader"><output class="head-result" id="head-result">{child}</output></div></div></div>'
        )
        html = html.replace(old, replacement)
    return (
        html,
        css,
        {
            "vocabulary": len(rows),
            "scoreFloor": floor,
            "inputRange": R,
            "reductionFanIn": 16,
            "scoreGain": SCORE_GAIN,
            "decoder": decoder,
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--decoder", choices=("direct", "two-pass"), default="two-pass")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    html, css, metadata = compile_head(args.decoder)
    reference = json.loads((BANK / "reference.json").read_text())
    metadata["fixtures"] = reference["fixtures"]
    metadata["runtimeJavaScript"] = False
    (args.output / "head.css").write_text(css)
    (args.output / "head-body.html").write_text(html)
    states = np.load(ROOT / "experiments/gpt2-supervised-group-router/states.npz")[
        "hidden"
    ]
    state_ids = reference["fixtureSelection"]["states"]
    metadata["sourceStates"] = state_ids
    metadata["hidden"] = np.asarray(states[state_ids], dtype=np.float64).tolist()
    initial = ";".join(f"--h{i}:{v:.12g}" for i, v in enumerate(metadata["hidden"][0]))
    page = (
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><link rel="stylesheet" href="head.css"><style>body{'
        + initial
        + "}</style><body>"
        + html.replace("{child}", "")
        + "</body>"
    )
    (args.output / "index.html").write_text(page)
    (args.output / "reference.json").write_text(json.dumps(metadata))
    print(
        {k: v for k, v in metadata.items() if k not in ("hidden", "fixtures")},
        flush=True,
    )


if __name__ == "__main__":
    main()
