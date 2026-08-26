#!/usr/bin/env python3
"""Pack multiple real GPT-2 FC rows into one HVAR advance.

This is a deliberately decisive probe. HVAR computes one continuous linear
sum for a packed row; CSS then attempts to recover radix lanes with round/mod.
The pages contain no JavaScript. An external harness supplies class changes,
forces layout, and reads the CSS-decoded values.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_avar2_hvar_real_gpt2_tile import block_zero_mlp_input
from build_gpt2_block_css import (
    FONT_SIZE,
    MLP_WIDTH,
    PACKED_CODEPOINT_BASE,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    FontGroup,
    global_axis_tag,
    model_data,
)
from build_matrix_backend_prototypes import build_direct_font_backend
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows, safe_base_advance


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "hvar-packed-output-rows"
TOKEN_IDS = (
    11, 612, 373, 257, 15496, 7454, 464, 1212,
    13, 15899, 42, 100, 1000, 5000, 10000, 20000,
)
SHARD = 256


@dataclass(frozen=True)
class Encoding:
    lanes: int
    radix: int
    bound: float
    scale: float
    intercept: float


def build_group(
    name: str,
    codes: np.ndarray,
    *,
    row_specific: bool,
) -> FontGroup:
    names: list[str] = []
    hashes: list[str] = []
    bases: list[int] = []
    starts: list[int] = []
    row_bases: list[np.ndarray] = []
    for shard, start in enumerate(range(0, codes.shape[1], SHARD)):
        stop = min(start + SHARD, codes.shape[1])
        shard_codes = codes[:, start:stop]
        base = safe_base_advance(shard_codes)
        per_row = (
            np.sum(np.abs(shard_codes.astype(np.int64)), axis=1).astype(np.int32)
            + 32
        )
        if np.any(per_row + np.sum(np.abs(shard_codes), axis=1) > 65535):
            raise ValueError(f"{name} shard {shard} exceeds uint16 advance range")
        stem = f"{name}-s{shard}"
        ttf = OUT / f"{stem}.ttf"
        start_codepoint = PACKED_CODEPOINT_BASE + shard * codes.shape[0]
        if not ttf.with_suffix(".woff2").exists():
            build_direct_font_backend(
                shard_codes,
                ttf,
                signed_axes=True,
                base_advance=per_row if row_specific else base,
                codepoint_start=start_codepoint,
                axis_tags=[global_axis_tag(index) for index in range(start, stop)],
            )
        woff2 = ttf.with_suffix(".woff2")
        names.append(stem)
        hashes.append(hashlib.sha256(woff2.read_bytes()).hexdigest()[:12])
        bases.append(base)
        starts.append(start_codepoint)
        row_bases.append(per_row)
    return FontGroup(
        tuple(names), tuple(hashes), tuple(bases), tuple(starts),
        codes.shape[0], tuple(row_bases) if row_specific else None,
    )


def font_faces(family: str, group: FontGroup) -> str:
    rules = []
    for shard, (name, fingerprint, start) in enumerate(
        zip(group.names, group.tags, group.codepoint_starts)
    ):
        rules.append(
            f'@font-face{{font-family:{family}S{shard};'
            f'src:url("{name}.woff2?v={fingerprint}") format("woff2");'
            f'unicode-range:U+{start:X}-{start + group.output_count - 1:X}}}'
        )
    return "".join(rules)


def registrations() -> str:
    names = [*(f"--i-{i:03d}" for i in range(WIDTH)), "--p", "--o0", "--o1", "--o2", "--o3"]
    return "".join(
        f'@property {name}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for name in names
    )


def input_rules(normalized: np.ndarray) -> str:
    rules = []
    for case, vector in enumerate(normalized):
        selector = "#bank" if case == 0 else f"body.case{case} #bank"
        declarations = "".join(
            f"--i-{index:03d}:{css_number(value)};"
            for index, value in enumerate(vector)
        )
        rules.append(f"{selector}{{{declarations}}}")
    return "".join(rules)


def axis_settings() -> str:
    return ",".join(
        f'"{global_axis_tag(index)}" var(--i-{index:03d})'
        for index in range(WIDTH)
    )


def characters(group: FontGroup, output: int) -> str:
    return "".join(
        f"&#x{start + output:X};" for start in group.codepoint_starts
    )


def page_shell(title: str, css: str, packets: list[str]) -> str:
    return f"""<!doctype html>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
<body><main id="bank">{''.join(packets)}</main></body>
"""


def common_css(faces: str, family: str, columns: int) -> str:
    return (
        faces
        + registrations()
        + "html,body{margin:0;padding:0}"
        + f"#bank{{position:fixed;left:-200000px;top:0;display:grid;"
        + f"grid-template-columns:repeat({columns},max-content);font:normal {FONT_SIZE}px "
        + f"{','.join(f'{family}S{i}' for i in range(3))};font-kerning:none;"
        + f"font-variation-settings:{axis_settings()}}}"
        + ".packet{position:relative;display:inline-block;width:max-content;"
        + "height:1px;overflow:visible;white-space:pre;font:inherit}"
        + ".carrier{position:absolute;inset:0;display:block;container-type:inline-size}"
        + ".decoded{position:absolute;left:0;top:0;display:block;"
        + "width:calc((var(--o0) + 256)*1px);"
        + "height:calc((var(--o1) + 256)*1px);"
        + "translate:calc((var(--o2) + 256)*1px) calc((var(--o3) + 256)*1px)}"
    )


def control_page(
    group: FontGroup,
    normalized: np.ndarray,
    factors: np.ndarray,
    bias: np.ndarray,
) -> str:
    base = sum(group.bases)
    rules = []
    packets = []
    for output in range(MLP_WIDTH):
        rules.append(
            f".g{output:04d} .decoded{{--o0:calc((100cqi/1px*{UNITS_PER_EM}/{FONT_SIZE}"
            f" - {base})*{css_number(factors[output])} + "
            f"({css_number(bias[output])}))}}"
        )
        packets.append(
            f'<span class="packet g{output:04d}" data-first="{output}">'
            f'{characters(group, output)}<i class="carrier"><b class="decoded"></b></i></span>'
        )
    return page_shell(
        "One HVAR output per advance",
        common_css(font_faces("Control", group), "Control", 64)
        + input_rules(normalized)
        + "".join(rules),
        packets,
    )


def packed_page(
    encoding: Encoding,
    group: FontGroup,
    normalized: np.ndarray,
    combined_intercepts: np.ndarray,
    output_scales: np.ndarray,
) -> str:
    if group.row_bases is None:
        raise ValueError("packed fonts require row-specific bases")
    base_totals = np.sum(np.stack(group.row_bases), axis=0)
    rules = []
    packets = []
    for packet, first in enumerate(range(0, MLP_WIDTH, encoding.lanes)):
        declarations = [
            f"--p:round(nearest,calc(100cqi/1px*{UNITS_PER_EM}/{FONT_SIZE}"
            f" - {int(base_totals[packet])} + "
            f"{css_number(combined_intercepts[packet])}),1)"
        ]
        for lane in range(encoding.lanes):
            if lane == 0:
                digit = f"mod(var(--p),{encoding.radix})"
            else:
                quotient = f"round(down,var(--p)/{encoding.radix ** lane},1)"
                digit = (
                    quotient if lane == encoding.lanes - 1
                    else f"mod({quotient},{encoding.radix})"
                )
            output = first + lane
            declarations.append(
                f"--o{lane}:calc(({digit} - {css_number(encoding.intercept)})"
                f"/{css_number(output_scales[output])})"
            )
        rules.append(
            f".g{packet:04d} .decoded{{{';'.join(declarations)}}}"
        )
        packets.append(
            f'<span class="packet g{packet:04d}" data-first="{first}">'
            f'{characters(group, packet)}<i class="carrier"><b class="decoded"></b></i></span>'
        )
    return page_shell(
        f"{encoding.lanes} FC outputs packed per HVAR advance",
        common_css(
            font_faces(f"Packed{encoding.lanes}", group),
            f"Packed{encoding.lanes}",
            64,
        )
        + input_rules(normalized)
        + "".join(rules),
        packets,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    inputs = np.stack(
        [block_zero_mlp_input(token_id, tensors) for token_id in TOKEN_IDS]
    )
    data = model_data()
    quantized = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    activation_range = float(np.max(np.abs(inputs)) * 1.01)
    normalized = inputs / activation_range
    factors = activation_range * quantized.scales
    reference = (
        normalized @ quantized.codes.astype(np.float64).T
    ) * factors[None, :] + data["fc_bias"][None, :]

    control = build_group("control", quantized.codes, row_specific=False)
    (OUT / "control.html").write_text(
        control_page(control, normalized, factors, data["fc_bias"])
    )

    encodings = (
        Encoding(lanes=2, radix=256, bound=128.0, scale=223 / 256, intercept=127.5),
        Encoding(lanes=4, radix=16, bound=32.0, scale=13 / 64, intercept=7.5),
    )
    encoding_reports = []
    for encoding in encodings:
        output_scales = np.full(MLP_WIDTH, encoding.scale, dtype=np.float64)
        bias_intercepts = (
            encoding.intercept + data["fc_bias"] * output_scales
        )
        packed_rows = []
        combined_intercepts = []
        for first in range(0, MLP_WIDTH, encoding.lanes):
            rows = range(first, first + encoding.lanes)
            combined = sum(
                encoding.radix**lane
                * quantized.codes[output]
                * (factors[output] * output_scales[output])
                for lane, output in enumerate(rows)
            )
            packed_rows.append(np.rint(combined).astype(np.int16))
            combined_intercepts.append(
                sum(
                    encoding.radix**lane * bias_intercepts[output]
                    for lane, output in enumerate(rows)
                )
            )
        packed_codes = np.stack(packed_rows)
        packed_integer = np.rint(
            normalized @ packed_codes.astype(np.float64).T
            + np.asarray(combined_intercepts)[None, :]
        ).astype(np.int64)
        offline_decoded = np.empty_like(reference)
        for lane in range(encoding.lanes):
            digits = (
                packed_integer // (encoding.radix**lane)
            ) % encoding.radix
            offline_decoded[:, lane::encoding.lanes] = (
                digits - encoding.intercept
            ) / encoding.scale
        group = build_group(
            f"packed{encoding.lanes}", packed_codes, row_specific=True
        )
        (OUT / f"packed{encoding.lanes}.html").write_text(
            packed_page(
                encoding,
                group,
                normalized,
                np.asarray(combined_intercepts),
                output_scales,
            )
        )
        max_sum_abs = int(
            max(
                np.max(np.sum(np.abs(packed_codes[:, start:start + SHARD]), axis=1))
                for start in range(0, WIDTH, SHARD)
            )
        )
        encoding_reports.append(
            {
                "lanes": encoding.lanes,
                "radix": encoding.radix,
                "bound": encoding.bound,
                "scale": encoding.scale,
                "groups": MLP_WIDTH // encoding.lanes,
                "glyphs": (MLP_WIDTH // encoding.lanes) * 3,
                "elements": (MLP_WIDTH // encoding.lanes) * 3,
                "maxShardSumAbs": max_sum_abs,
                "offlineDecoded": offline_decoded.tolist(),
            }
        )

    report = {
        "tokenIds": list(TOKEN_IDS),
        "activationRange": activation_range,
        "reference": reference.tolist(),
        "control": {"groups": MLP_WIDTH, "glyphs": MLP_WIDTH * 3, "elements": MLP_WIDTH * 3},
        "encodings": encoding_reports,
        "fontLimits": {
            "advance": "uint16 0..65535 per glyph",
            "delta": "signed int16 per HVAR region",
            "axesPerFontInBackend": 256,
        },
    }
    (OUT / "reference.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "control": report["control"],
                "encodings": [
                    {key: value for key, value in encoding.items() if key != "offlineDecoded"}
                    for encoding in encoding_reports
                ],
                "fontLimits": report["fontLimits"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
