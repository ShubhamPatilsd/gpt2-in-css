#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Fuse one real head's QK, exponential and weighted V inside a variable font.

This component deliberately starts with CSS Q/K/V numbers. The fused path must
also reduce its font advances and divide in CSS before measurement completes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
from pathlib import Path

import numpy as np
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import layer_norm
from build_matrix_backend_prototypes import build_direct_font_backend
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.varLib.builder import (
    buildDeltaSetIndexMap,
    buildVarData,
    buildVarRegionList,
    buildVarStore,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "fused-attention-font-probe"
D = 64
BASE = 16384
UNIT = 8192
TAGS = [f"{kind}{j:03d}" for kind in "QKV" for j in range(D)] + ["SCOR", "CNST"]
TOKENS = [15496, 995, 11, 428, 318, 257, 1332, 13, 0, 1, 2, 3, 4, 5, 6, 7]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def balanced(terms: list[str]) -> str:
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return f"({balanced(terms[:middle])} + {balanced(terms[middle:])})"


def real_vectors() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tensors = SafeTensors(MODEL_PATH)
    token = tensors.tensor("wte.weight")
    position = tensors.tensor("wpe.weight")
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    inputs = np.stack(
        [
            layer_norm(
                np.asarray(token[t] + position[p], dtype=np.float64), gamma, beta
            )
            for p, t in enumerate(TOKENS)
        ]
    )
    qkv = inputs @ np.asarray(
        tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64
    )
    qkv += np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    return tuple(part[:, :D] for part in np.split(qkv, 3, axis=1))


def make_font(directory: Path, config: dict) -> dict:
    path = directory / "attention.ttf"
    build_direct_font_backend(
        np.zeros((D + 1, len(TAGS)), dtype=np.int16),
        path,
        signed_axes=True,
        base_advance=BASE,
        axis_tags=TAGS,
    )
    font = TTFont(path, recalcTimestamp=False)
    positive, negative = (0, 1, 1), (-1, -1, 0)
    coefficient = config["qScale"] * config["kScale"] / (8 * config["scoreRadius"])
    avar_supports = []
    avar_deltas = []
    for j in range(D):
        for qs, ks, sign in (
            (positive, positive, 1),
            (positive, negative, -1),
            (negative, positive, -1),
            (negative, negative, 1),
        ):
            avar_supports.append({f"Q{j:03d}": qs, f"K{j:03d}": ks})
            avar_deltas.append(round(sign * coefficient * 16384))
    avar_supports.append({"CNST": positive})
    avar_deltas.append(round(-config["scoreCenter"] / config["scoreRadius"] * 16384))
    if max(abs(x) for x in avar_deltas) > 32767:
        raise ValueError("avar2 score coefficients exceed signed 16-bit range")
    avar = newTable("avar")
    avar.majorVersion, avar.minorVersion = 2, 0
    avar.segments = {tag: {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0} for tag in TAGS}
    avar.table = otTables.avar()
    avar.table.Reserved = 0
    # All original Q/K/V coordinates pass through unchanged. Only SCOR remaps.
    avar.table.VarIdxMap = buildDeltaSetIndexMap([0] * (3 * D) + [1 << 16, 0])
    avar.table.VarStore = buildVarStore(
        buildVarRegionList(avar_supports, TAGS),
        [
            buildVarData([], [[]], optimize=True),
            buildVarData(range(len(avar_supports)), [avar_deltas], optimize=True),
        ],
    )
    font["avar"] = avar

    knots = np.linspace(-1, 1, config["segments"] + 1)
    radius = config["scoreRadius"]
    zero_value = math.exp(-radius)
    pieces = []
    for i, knot in enumerate(knots):
        if knot == 0:
            continue
        support = (
            float(knots[max(0, i - 1)]),
            float(knot),
            float(knots[min(len(knots) - 1, i + 1)]),
        )
        pieces.append(
            (support, round(UNIT * (math.exp(radius * (knot - 1)) - zero_value)))
        )

    supports, data = [], [buildVarData([], [[]], optimize=True)]
    mapping = [0]
    zero_code = round(UNIT * zero_value)
    for j in range(D):
        start = len(supports)
        coefficients = []
        for sign, region in ((1, positive), (-1, negative)):
            supports.append({f"V{j:03d}": region})
            coefficients.append(sign * zero_code)
            for score_region, code in pieces:
                supports.append({"SCOR": score_region, f"V{j:03d}": region})
                coefficients.append(sign * code)
        data.append(
            buildVarData(range(start, len(supports)), [coefficients], optimize=True)
        )
        mapping.append((j + 1) << 16)
    start = len(supports)
    for score_region, _ in pieces:
        supports.append({"SCOR": score_region})
    data.append(
        buildVarData(
            range(start, len(supports)), [[code for _, code in pieces]], optimize=True
        )
    )
    mapping.append((D + 1) << 16)
    font["hmtx"].metrics[f"y{D:03d}"] = (BASE + zero_code, 0)
    font["HVAR"].table.VarStore = buildVarStore(
        buildVarRegionList(supports, TAGS), data
    )
    font["HVAR"].table.AdvWidthMap = buildDeltaSetIndexMap(mapping)
    font.save(path)
    font.flavor = "woff2"
    font.save(directory / "attention.woff2")
    return {
        "axes": len(TAGS),
        "avarRegions": len(avar_supports),
        "hvarRegions": len(supports),
        "ttfBytes": path.stat().st_size,
        "woff2Bytes": (directory / "attention.woff2").stat().st_size,
        "avarCoefficient": avar_deltas[0] / 16384,
        "avarOffset": avar_deltas[-1] / 16384,
        "zeroCode": zero_code,
        "knots": knots.tolist(),
        "knotCodes": [
            round(UNIT * (math.exp(radius * (x - 1)) - zero_value)) if x != 0 else 0
            for x in knots
        ],
    }


def reference(case: dict, config: dict, font: dict) -> dict:
    q, k, v = (np.asarray(case[name], dtype=np.float64) for name in ("q", "k", "v"))
    scores = k @ q / 8
    weights = np.exp(scores - config["scoreCenter"] - config["scoreRadius"])
    truth = weights @ v / weights.sum()
    qn = np.rint(np.clip(q / config["qScale"], -1, 1) * 16384) / 16384
    kn = np.rint(np.clip(k / config["kScale"], -1, 1) * 16384) / 16384
    vn = np.rint(np.clip(v / config["vScale"], -1, 1) * 16384) / 16384
    raw_axis = (kn @ qn) * font["avarCoefficient"] + font["avarOffset"]
    axis = np.clip(np.floor(raw_axis * 16384 + 0.5) / 16384, -1, 1)
    codes = font["zeroCode"] + np.interp(axis, font["knots"], font["knotCodes"])
    represented_denominator = float(codes.sum() / UNIT)
    represented = (codes @ vn / codes.sum()) * config["vScale"]
    return {
        "scores": scores.tolist(),
        "denominator": float(weights.sum()),
        "context": truth.tolist(),
        "representedContext": represented.tolist(),
        "representedDenominator": represented_denominator,
        "representedSums": (
            np.append(codes @ vn, codes.sum()) + len(k) * BASE
        ).tolist(),
        "scoreAxis": axis.tolist(),
        "scoreClipped": int(np.count_nonzero(abs(raw_axis) > 1)),
        "inputClipped": int(
            np.count_nonzero(abs(q) > config["qScale"])
            + np.count_nonzero(abs(k) > config["kScale"])
            + np.count_nonzero(abs(v) > config["vScale"])
        ),
        "approximationRmse": float(np.sqrt(np.mean((represented - truth) ** 2))),
        "approximationMaximum": float(np.max(abs(represented - truth))),
    }


def page(directory: Path, mode: str, cases: list[dict], config: dict) -> dict:
    count = len(cases[0]["k"])
    css = [
        "html,body{margin:0}",
        ".input{position:absolute;left:0;top:0}",
        ".answer,.den-answer{position:absolute;height:1px;left:0;top:0}",
        '@property --den{syntax:"<number>";inherits:true;initial-value:1}',
    ]
    for j in range(D):
        css.append(
            f'@property --q{j}{{syntax:"<number>";inherits:true;initial-value:0}}'
        )
    for t in range(count):
        for kind in "kv":
            for j in range(D):
                css.append(
                    f'@property --{kind}{t}-{j}{{syntax:"<number>";inherits:true;initial-value:0}}'
                )
    for index, item in enumerate(cases):
        values = [f"--q{j}:{x:.14g}" for j, x in enumerate(item["q"])]
        for kind in "kv":
            values.extend(
                f"--{kind}{t}-{j}:{x:.14g}"
                for t, row in enumerate(item[kind])
                for j, x in enumerate(row)
            )
        css.append(f'.input[data-case="{index}"]' + "{" + ";".join(values) + "}")
    if mode == "css":
        rules = []
        for t in range(count):
            css.extend(
                [
                    f'@property --s{t}{{syntax:"<number>";inherits:true;initial-value:0}}',
                    f'@property --p{t}{{syntax:"<number>";inherits:true;initial-value:0}}',
                ]
            )
            score = balanced([f"(var(--q{j}) * var(--k{t}-{j}))" for j in range(D)])
            rules.append(f"--s{t}:calc({score} / 8)")
            rules.append(
                f"--p{t}:exp(calc(var(--s{t}) - {config['scoreCenter'] + config['scoreRadius']:.14g}))"
            )
        rules.append(
            "--den:calc(" + balanced([f"var(--p{t})" for t in range(count)]) + ")"
        )
        css.append(".input{" + ";".join(rules) + "}")
        for j in range(D):
            numerator = balanced(
                [f"(var(--p{t}) * var(--v{t}-{j}))" for t in range(count)]
            )
            css.append(
                f"#answer-{j}{{width:calc(10000px + 1000px * {numerator} / var(--den))}}"
            )
        body = "".join(f'<i class="answer" id="answer-{j}"></i>' for j in range(D))
        body += '<i class="den-answer"></i>'
    else:
        css.extend(
            [
                f'@font-face{{font-family:FusedAttention;src:url("attention.{config["fontExtension"]}")}}',
                ".sumrow{position:absolute;left:0;top:0;display:flex;width:max-content;height:1px;visibility:hidden}",
                ".term{display:inline-block;flex:none;font-family:FusedAttention;font-size:1000px;line-height:1;font-kerning:none;height:1px}",
                ".den-cap,.num-cap{position:absolute;left:0;top:0;height:1px;container-type:inline-size}",
                f".den-cap{{width:anchor-size(--sum{D} width)}}",
                f".reads{{--den:calc((100cqw - {count * BASE}px) / {UNIT}px)}}",
            ]
        )
        axes = []
        for t in range(count):
            settings = [
                f'"Q{j:03d}" calc(var(--q{j}) / {config["qScale"]:.14g})'
                for j in range(D)
            ]
            for kind in "KV":
                settings.extend(
                    f'"{kind}{j:03d}" calc(var(--{kind.lower()}{t}-{j}) / {config[kind.lower() + "Scale"]:.14g})'
                    for j in range(D)
                )
            settings.extend(['"SCOR" 0', '"CNST" 1'])
            axes.append(f"--axes{t}:" + ",".join(settings))
            css.append(f".token-{t}{{font-variation-settings:var(--axes{t})}}")
        css.append(".input{" + ";".join(axes) + "}")
        sum_rows = []
        for j in range(D + 1):
            css.append(f"#sum-{j}{{anchor-name:--sum{j}}}")
            sum_rows.append(
                f'<div class="sumrow" id="sum-{j}">'
                + "".join(
                    f'<i class="term token-{t}">&#x{0xE000 + j:x};</i>'
                    for t in range(count)
                )
                + "</div>"
            )
        # Anchor sources must share the positioning scope of their readers.
        # The denominator's size container establishes a new containing block.
        body = (
            sum_rows[D]
            + '<div class="den-cap"><div class="reads"><i class="den-answer"></i>'
        )
        body += "".join(sum_rows[:D])
        for j in range(D):
            css.append(f"#cap-{j}{{width:anchor-size(--sum{j} width)}}")
            body += f'<div class="num-cap" id="cap-{j}"><i class="answer" id="answer-{j}"></i></div>'
        body += "</div></div>"
        css.append(
            f".answer{{width:calc(10000px + 1000px * {config['vScale']:.14g} * ((100cqw - {count * BASE}px) / {UNIT}px) / var(--den))}}"
        )
    css.append(".den-answer{width:calc(1000px * var(--den))}")
    html = '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
    html += (
        f"<title>Fused attention {mode}</title><style>" + "\n".join(css) + "</style>"
    )
    html += '<main class="input" data-case="0">' + body + "</main>"
    target = directory / f"{mode}.html"
    target.write_text(html)
    return {
        "file": target.name,
        "htmlBytes": target.stat().st_size,
        "sha256": digest(target),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--segments", type=int, default=64)
    parser.add_argument("--label", default="s64")
    parser.add_argument("--font-format", choices=("woff2", "ttf"), default="ttf")
    parser.add_argument("--reuse-font-from")
    args = parser.parse_args()
    if args.segments % 2 or args.segments < 4:
        raise ValueError("segments must be even and at least four")
    directory = OUT / args.label
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "builder-source.py").write_text(Path(__file__).read_text())
    q, k, v = real_vectors()
    scores = q[:8] @ k[:8].T / 8
    lower, upper = min(0, float(scores.min())), max(0, float(scores.max()))
    center = (lower + upper) / 2
    radius = max(1, (upper - lower) * 0.6)
    config = {
        "segments": args.segments,
        "fontExtension": args.font_format,
        "qScale": float(np.max(abs(q[:8]))) * 1.25,
        "kScale": float(np.max(abs(k[:8]))) * 1.25,
        "vScale": float(np.max(abs(v[:8]))) * 1.25,
        "scoreCenter": center,
        "scoreRadius": radius,
        "base": BASE,
        "unit": UNIT,
    }
    cases = []

    def add(name, query, keys, values, *, expected_failure=False):
        cases.append(
            {
                "name": name,
                "q": np.asarray(query).tolist(),
                "k": np.asarray(keys).tolist(),
                "v": np.asarray(values).tolist(),
                "expectedFailure": expected_failure,
            }
        )

    add("real-initial", q[3], k[:4], v[:4])
    add("real-query-only", q[7], k[:4], v[:4])
    add("held-out-all-inputs", q[11], k[8:12], v[8:12])
    add("zero-query-uniform", np.zeros(D), k[:4], v[:4])
    add("zero-values", q[7], k[:4], np.zeros((4, D)))
    add(
        "signed-cancellation",
        q[3],
        np.repeat(k[:1], 4, axis=0),
        np.stack([v[0], -v[0], v[0], -v[0]]),
    )
    edge_q = np.full(D, config["qScale"] * 0.5)
    edge_scores = np.array(
        [center - radius, center + radius, center, center + radius * 0.5]
    )
    edge_k = np.repeat((edge_scores * 8 / edge_q.sum())[:, None], D, axis=1)
    add("score-range-edges", edge_q, edge_k, v[:4])
    edge_scores[0] = center + radius * 1.8
    outside_k = np.repeat((edge_scores * 8 / edge_q.sum())[:, None], D, axis=1)
    add("score-outside-range", edge_q, outside_k, v[:4], expected_failure=True)
    late_path = (
        ROOT
        / "experiments/browser-gpt2-integration/dense/baseline-qkv-l0-11-r0/fixture.json"
    )
    late_fixture = json.loads(late_path.read_text())
    late_rows = [
        np.asarray(sample["expected"], dtype=np.float64)
        for sample in late_fixture["fixtureSamples"]
        if sample["layer"] == 11 and sample["kind"] == "fresh-input"
    ]
    late_qkv = [np.split(row, 3) for row in late_rows]
    add(
        "late-layer-two-state-domain-probe",
        late_qkv[1][0][:D],
        np.stack([late_qkv[i][1][:D] for i in (0, 1, 0, 1)]),
        np.stack([late_qkv[i][2][:D] for i in (0, 1, 0, 1)]),
        expected_failure=True,
    )
    if args.reuse_font_from:
        previous = OUT / args.reuse_font_from
        saved = json.loads((previous / "manifest.json").read_text())
        if saved["config"] != config:
            raise ValueError("font reuse requires an identical numeric configuration")
        font = saved["font"]
        for name in ("attention.ttf", "attention.woff2"):
            shutil.copyfile(previous / name, directory / name)
    else:
        font = make_font(directory, config)
    for case in cases:
        case["reference"] = reference(case, config, font)
    manifest = {
        "config": config,
        "font": font,
        "cases": cases,
        "pages": {
            mode: page(directory, mode, cases, config) for mode in ("css", "fused")
        },
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "source": {
            "path": str(Path(__file__).resolve()),
            "sha256": digest(Path(__file__)),
        },
        "fixture": {
            "model": str(MODEL_PATH),
            "layer": 0,
            "head": 0,
            "tokenIds": TOKENS,
            "calibrationPositions": list(range(8)),
            "heldOutPositions": list(range(8, 16)),
            "lateLayerDomainProbe": {
                "path": str(late_path),
                "sha256": digest(late_path),
                "description": "Two saved real layer-11 QKV vectors; KV pair duplicated equally to fill four slots",
            },
        },
        "scope": "CSS Q/K/V inputs through final normalized 64-vector; no dense QKV projection, cache insertion, or full model",
        "runtimeContainsJavaScript": False,
    }
    manifest["fontHashes"] = {
        name: digest(directory / name) for name in ("attention.ttf", "attention.woff2")
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "directory": str(directory),
                "config": config,
                "font": {
                    k: v for k, v in font.items() if k not in ("knots", "knotCodes")
                },
                "cases": [
                    {
                        "name": c["name"],
                        **{
                            k: c["reference"][k]
                            for k in (
                                "inputClipped",
                                "scoreClipped",
                                "approximationRmse",
                                "approximationMaximum",
                            )
                        },
                    }
                    for c in cases
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
