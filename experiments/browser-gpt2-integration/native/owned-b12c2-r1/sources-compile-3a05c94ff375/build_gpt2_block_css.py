#!/usr/bin/env python3
"""Build one faithful, one-token GPT-2-small block in HTML/CSS only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

try:
    import brotli
except ModuleNotFoundError:
    brotli = None
import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_matrix_backend_prototypes import (
    ROOT,
    UNITS_PER_EM,
    build_direct_font_backend,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import QuantizedRows, quantize_float_rows, safe_base_advance


OUT = Path(
    os.environ.get(
        "GPT2_BLOCK_CSS_OUT",
        ROOT / "experiments" / "gpt2-block-css",
    )
)
WIDTH = 768
MLP_WIDTH = 3072
SHARD = 256
PACK_SHARDS = 3
PACKED_CODEPOINT_BASE = 0xF0000
FC_STAGE_OUTPUTS = 768
FC_STAGES = MLP_WIDTH // FC_STAGE_OUTPUTS
QUANT_BITS = 9
FONT_SIZE = 512
TOKEN_ID = 15496  # GPT-2 token "Hello"
EPSILON = 1e-5
PACKED_READBACK_BASE = 4097
PACKED_READBACK_OFFSET = 2048


@dataclass(frozen=True)
class FontGroup:
    names: tuple[str, ...]
    tags: tuple[str, ...]
    bases: tuple[int, ...]
    codepoint_starts: tuple[int, ...]
    output_count: int
    row_bases: tuple[np.ndarray, ...] | None = None


def layer_norm(
    vector: np.ndarray, gamma: np.ndarray, beta: np.ndarray
) -> np.ndarray:
    mean = np.mean(vector)
    variance = np.mean((vector - mean) ** 2)
    return (vector - mean) / np.sqrt(variance + EPSILON) * gamma + beta


def gelu_new(vector: np.ndarray) -> np.ndarray:
    inner = math.sqrt(2 / math.pi) * (vector + 0.044715 * vector**3)
    return 0.5 * vector * (1 + np.tanh(inner))


def model_data(
    block_index: int = 0,
    input_vector: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    tensors = SafeTensors(MODEL_PATH)
    prefix = f"h.{block_index}"
    x = (
        np.asarray(input_vector, dtype=np.float64)
        if input_vector is not None
        else np.asarray(
            tensors.tensor("wte.weight")[TOKEN_ID]
            + tensors.tensor("wpe.weight")[0],
            dtype=np.float64,
        )
    )
    c_attn_weight = np.asarray(
        tensors.tensor(f"{prefix}.attn.c_attn.weight"), dtype=np.float64
    )
    c_attn_bias = np.asarray(
        tensors.tensor(f"{prefix}.attn.c_attn.bias"), dtype=np.float64
    )
    return {
        "x": x,
        "ln1_gamma": np.asarray(tensors.tensor(f"{prefix}.ln_1.weight"), dtype=np.float64),
        "ln1_beta": np.asarray(tensors.tensor(f"{prefix}.ln_1.bias"), dtype=np.float64),
        # With one token, causal softmax has one entry and attention returns V exactly.
        "v_weight": c_attn_weight[:, 2 * WIDTH :].T,
        "v_bias": c_attn_bias[2 * WIDTH :],
        "attn_proj_weight": np.asarray(
            tensors.tensor(f"{prefix}.attn.c_proj.weight"), dtype=np.float64
        ).T,
        "attn_proj_bias": np.asarray(
            tensors.tensor(f"{prefix}.attn.c_proj.bias"), dtype=np.float64
        ),
        "ln2_gamma": np.asarray(tensors.tensor(f"{prefix}.ln_2.weight"), dtype=np.float64),
        "ln2_beta": np.asarray(tensors.tensor(f"{prefix}.ln_2.bias"), dtype=np.float64),
        "fc_weight": np.asarray(
            tensors.tensor(f"{prefix}.mlp.c_fc.weight"), dtype=np.float64
        ).T,
        "fc_bias": np.asarray(tensors.tensor(f"{prefix}.mlp.c_fc.bias"), dtype=np.float64),
        "mlp_proj_weight": np.asarray(
            tensors.tensor(f"{prefix}.mlp.c_proj.weight"), dtype=np.float64
        ).T,
        "mlp_proj_bias": np.asarray(
            tensors.tensor(f"{prefix}.mlp.c_proj.bias"), dtype=np.float64
        ),
    }


def final_layer_norm_data() -> tuple[np.ndarray, np.ndarray]:
    tensors = SafeTensors(MODEL_PATH)
    return (
        np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64),
        np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64),
    )


def build_font_group(
    name: str,
    codes: np.ndarray,
    shard_size: int = SHARD,
    *,
    rebuild: bool = True,
    row_specific_bases: bool = False,
    global_axis_offset: int | None = None,
) -> FontGroup:
    names: list[str] = []
    tags: list[str] = []
    bases: list[int] = []
    codepoint_starts: list[int] = []
    row_bases: list[np.ndarray] = []
    for shard_index, start in enumerate(range(0, codes.shape[1], shard_size)):
        stop = min(start + shard_size, codes.shape[1])
        shard_codes = codes[:, start:stop]
        base = safe_base_advance(shard_codes)
        bases_for_rows = (
            np.sum(np.abs(shard_codes.astype(np.int64)), axis=1).astype(np.int32)
            + 32
        )
        stem = f"{name}-s{shard_index}"
        path = OUT / f"{stem}.ttf"
        codepoint_start = PACKED_CODEPOINT_BASE + shard_index * codes.shape[0]
        if rebuild:
            build_direct_font_backend(
                shard_codes,
                path,
                signed_axes=True,
                base_advance=bases_for_rows if row_specific_bases else base,
                codepoint_start=codepoint_start,
                axis_tags=[
                    global_axis_tag(global_axis_offset + start + local)
                    if global_axis_offset is not None
                    else packed_axis_tag(shard_index % PACK_SHARDS, local)
                    for local in range(stop - start)
                ],
            )
        woff2 = path.with_suffix(".woff2")
        if not woff2.exists():
            raise FileNotFoundError(f"missing generated font: {woff2}")
        names.append(stem)
        tags.append(hashlib.sha256(woff2.read_bytes()).hexdigest()[:12])
        bases.append(base)
        row_bases.append(bases_for_rows)
        codepoint_starts.append(codepoint_start)
    return FontGroup(
        tuple(names),
        tuple(tags),
        tuple(bases),
        tuple(codepoint_starts),
        codes.shape[0],
        tuple(row_bases) if row_specific_bases else None,
    )


def packed_axis_tag(shard_in_pack: int, local: int) -> str:
    return f"{chr(ord('A') + shard_in_pack)}{local:03d}"


def global_axis_tag(index: int) -> str:
    """Return a unique four-byte private axis tag for a large fallback run."""
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if not 0 <= index < len(alphabet) ** 3:
        raise ValueError("global font-axis index must fit in three base-36 digits")
    digits = []
    for _ in range(3):
        index, remainder = divmod(index, len(alphabet))
        digits.append(alphabet[remainder])
    return "X" + "".join(reversed(digits))


def css_sum(values: list[str]) -> str:
    return " + ".join(values)


def registrations(raw_count: int = WIDTH) -> str:
    names = ["--mean1", "--var1", "--mean2", "--var2"]
    for prefix, count in (
        ("raw", raw_count),
        ("x", WIDTH),
        ("n1", WIDTH),
        ("v", WIDTH),
        ("r1", WIDTH),
        ("n2", WIDTH),
        ("pre", MLP_WIDTH),
        ("hidden", MLP_WIDTH),
        ("out", WIDTH),
    ):
        names.extend(f"--{prefix}-{index:03d}" for index in range(count))
    return "".join(
        f'@property {name}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for name in names
    )


def norm_declarations(
    source: str,
    target: str,
    gamma: np.ndarray,
    beta: np.ndarray,
    mean_name: str,
    variance_name: str,
) -> list[str]:
    source_values = [f"var(--{source}-{index:03d})" for index in range(WIDTH)]
    declarations = [
        f"--{mean_name}:calc(({css_sum(source_values)}) / {WIDTH})",
        f"--{variance_name}:calc(("
        + css_sum(
            [
                f"(var(--{source}-{index:03d}) - var(--{mean_name})) * "
                f"(var(--{source}-{index:03d}) - var(--{mean_name}))"
                for index in range(WIDTH)
            ]
        )
        + f") / {WIDTH})",
    ]
    for index in range(WIDTH):
        declarations.append(
            f"--{target}-{index:03d}:calc("
            f"(var(--{source}-{index:03d}) - var(--{mean_name})) / "
            f"sqrt(var(--{variance_name}) + {EPSILON}) * {css_number(gamma[index])} "
            f"+ ({css_number(beta[index])}))"
        )
    return declarations


def global_css(
    data: dict[str, np.ndarray],
    refs: dict[str, object],
    *,
    composed_attention: bool = False,
    collapsed_fc: bool = False,
    fc_stage_outputs_override: int | None = None,
) -> str:
    fc_outputs_per_stage = (
        MLP_WIDTH
        if collapsed_fc
        else (fc_stage_outputs_override or FC_STAGE_OUTPUTS)
    )
    rules: list[str] = [registrations(fc_outputs_per_stage)]
    input_declarations = [
        f"--x-{index:03d}:{css_number(value)}"
        for index, value in enumerate(data["x"])
    ]
    input_declarations += norm_declarations(
        "x", "n1", data["ln1_gamma"], data["ln1_beta"], "mean1", "var1"
    )
    rules.append(f'.norm1{{{";".join(input_declarations)}}}')

    after_attn = []
    if composed_attention:
        q_composed: QuantizedRows = refs["q_composed"]  # type: ignore[assignment]
        composed_bias: np.ndarray = refs["composed_bias"]  # type: ignore[assignment]
        composed_range = float(refs["n1_range"])
        for index in range(WIDTH):
            factor = composed_range * q_composed.scales[index]
            after_attn.append(
                f"--r1-{index:03d}:calc(var(--x-{index:03d}) + var(--raw-{index:03d}) / "
                f"{css_number(1 / factor)} + ({css_number(composed_bias[index])}))"
            )
    else:
        q_v: QuantizedRows = refs["q_v"]  # type: ignore[assignment]
        v_range = float(refs["n1_range"])
        v_declarations = []
        for index in range(WIDTH):
            factor = v_range * q_v.scales[index]
            v_declarations.append(
                f"--v-{index:03d}:calc(var(--raw-{index:03d}) / "
                f"{css_number(1 / factor)} + ({css_number(data['v_bias'][index])}))"
            )
        rules.append(f'.after-v{{{";".join(v_declarations)}}}')

        q_attn: QuantizedRows = refs["q_attn"]  # type: ignore[assignment]
        attn_range = float(refs["v_range"])
        for index in range(WIDTH):
            factor = attn_range * q_attn.scales[index]
            after_attn.append(
                f"--r1-{index:03d}:calc(var(--x-{index:03d}) + var(--raw-{index:03d}) / "
                f"{css_number(1 / factor)} + ({css_number(data['attn_proj_bias'][index])}))"
            )
    after_attn += norm_declarations(
        "r1", "n2", data["ln2_gamma"], data["ln2_beta"], "mean2", "var2"
    )
    rules.append(f'.after-attn{{{";".join(after_attn)}}}')

    q_fc: QuantizedRows = refs["q_fc"]  # type: ignore[assignment]
    fc_range = float(refs["n2_range"])
    fc_stage_count = MLP_WIDTH // fc_outputs_per_stage
    for fc_stage in range(fc_stage_count):
        declarations = []
        start = fc_stage * fc_outputs_per_stage
        output_count = fc_outputs_per_stage
        for local in range(output_count):
            output = start + local
            factor = fc_range * q_fc.scales[output]
            declarations.append(
                f"--pre-{output:03d}:calc(var(--raw-{local:03d}) / "
                f"{css_number(1 / factor)} + ({css_number(data['fc_bias'][output])}))"
            )
            z = f"var(--pre-{output:03d})"
            t = (
                f"({css_number(math.sqrt(2 / math.pi))} * "
                f"({z} + 0.044715 * {z} * {z} * {z}))"
            )
            declarations.append(
                f"--hidden-{output:03d}:calc(0.5 * {z} * "
                f"(1 + (exp(2 * {t}) - 1) / (exp(2 * {t}) + 1)))"
            )
        selector = ".hidden-all" if collapsed_fc else f".hidden-stage-{fc_stage:02d}"
        rules.append(f'{selector}{{{";".join(declarations)}}}')

    q_mlp: QuantizedRows = refs["q_mlp"]  # type: ignore[assignment]
    hidden_range = float(refs["hidden_range"])
    final_declarations = []
    for output in range(WIDTH):
        factor = hidden_range * q_mlp.scales[output]
        final_declarations.append(
            f"--out-{output:03d}:calc(var(--r1-{output:03d}) + "
            f"var(--raw-{output:03d}) / {css_number(1 / factor)} + "
            f"({css_number(data['mlp_proj_bias'][output])}))"
        )
    rules.append(f'.final{{{";".join(final_declarations)}}}')
    rules.append(
        "html{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}"
        "body{margin:2rem}css-stage{display:block;position:relative}"
        "h1{font:600 1.25rem system-ui,sans-serif}.status{max-width:52rem}"
    )
    return "".join(rules)


def pack_font_settings(
    input_names: list[str], activation_range: float, first_shard: int
) -> str:
    settings = []
    for shard in range(first_shard, min(first_shard + PACK_SHARDS, math.ceil(len(input_names) / SHARD))):
        start = shard * SHARD
        stop = min(start + SHARD, len(input_names))
        settings.extend(
            f'"{packed_axis_tag(shard % PACK_SHARDS, local)}" '
            f'calc(var({input_names[start + local]}) / {css_number(activation_range)})'
            for local in range(stop - start)
        )
    return ",".join(settings)


def pair_chain(output_indices: list[int], child: str, font_group: FontGroup) -> str:
    if len(output_indices) % 2:
        raise ValueError("paired chain needs an even output count")
    for local in reversed(range(0, len(output_indices), 2)):
        metrics = []
        for offset in (0, 1):
            index = local + offset
            glyph_index = output_indices[index]
            packs = []
            for pack, first_shard in enumerate(
                range(0, len(font_group.names), PACK_SHARDS)
            ):
                characters = "".join(
                    f'&#x{font_group.codepoint_starts[shard] + glyph_index:X};'
                    for shard in range(
                        first_shard,
                        min(first_shard + PACK_SHARDS, len(font_group.names)),
                    )
                )
                packs.append((pack, characters))
            if len(packs) == 1:
                contents = packs[0][1]
                pack_class = ""
            else:
                contents = "".join(
                    f'<i class="pack pack-{pack}">{characters}</i>'
                    for pack, characters in packs
                )
                pack_class = ""
            metrics.append(
                f'<span class="metric metric-{index:03d}{pack_class}">{contents}</span>'
            )
        child = (
            "".join(metrics)
            + f'<div class="probe probe-{local // 2:03d}">{child}</div>'
        )
    return child


def packed_quad_chain(
    output_indices: list[int], child: str, font_group: FontGroup
) -> str:
    if len(output_indices) % 4:
        raise ValueError("packed chain needs an output count divisible by four")
    for local in reversed(range(0, len(output_indices), 4)):
        metrics = []
        for offset in range(4):
            index = local + offset
            glyph_index = output_indices[index]
            packs = []
            for pack, first_shard in enumerate(
                range(0, len(font_group.names), PACK_SHARDS)
            ):
                characters = "".join(
                    f'&#x{font_group.codepoint_starts[shard] + glyph_index:X};'
                    for shard in range(
                        first_shard,
                        min(first_shard + PACK_SHARDS, len(font_group.names)),
                    )
                )
                packs.append((pack, characters))
            if len(packs) == 1:
                contents = packs[0][1]
            else:
                contents = "".join(
                    f'<i class="pack pack-{pack}">{characters}</i>'
                    for pack, characters in packs
                )
            metrics.append(
                f'<span class="metric metric-{index:03d}">{contents}</span>'
            )
        child = (
            "".join(metrics)
            + f'<div class="probe probe-{local // 4:03d}">{child}</div>'
        )
    return child


def font_faces(stage_name: str, font_group: FontGroup) -> str:
    faces = []
    for shard, (name, tag, codepoint_start) in enumerate(
        zip(font_group.names, font_group.tags, font_group.codepoint_starts)
    ):
        family = f"{stage_name.replace('-', '')}S{shard}"
        faces.append(
            f'@font-face{{font-family:{family};src:url("{name}.woff2?v={tag}") '
            f'format("woff2");unicode-range:U+{codepoint_start:X}-'
            f'{codepoint_start + font_group.output_count - 1:X}}}'
        )
    return "".join(faces)


def matrix_shadow(
    stage_name: str,
    font_group: FontGroup,
    input_properties: list[str],
    activation_range: float,
    output_indices: list[int],
    *,
    family_prefix: str | None = None,
    packed_readback: bool = False,
    direct_readback: bool = False,
) -> str:
    if packed_readback and direct_readback:
        raise ValueError("packed and direct readback are separate transports")
    families = []
    family_stem = (family_prefix or stage_name).replace("-", "")
    for shard, (name, tag, codepoint_start) in enumerate(
        zip(font_group.names, font_group.tags, font_group.codepoint_starts)
    ):
        family = f"{family_stem}S{shard}"
        families.append(family)
    pack_rules = []
    pack_count = math.ceil(len(families) / PACK_SHARDS)
    for pack, first_shard in enumerate(range(0, len(families), PACK_SHARDS)):
        selector = ":host" if pack_count == 1 else f".pack-{pack}"
        pack_rules.append(
            f'{selector}{{font-family:{",".join(families[first_shard:first_shard + PACK_SHARDS])};'
            f'font-variation-settings:{pack_font_settings(input_properties, activation_range, first_shard)}}}'
        )

    output_count = len(output_indices)
    probe_rules = []
    query_rules = []
    base_total = sum(font_group.bases)
    if packed_readback:
        for local in range(0, output_count, 4):
            group = local // 4
            anchors = []
            for offset in range(4):
                index = local + offset
                probe_rules.append(
                    f'.metric-{index:03d}{{anchor-name:--m{index:03d}}}'
                )
                anchors.append(
                    f"round(nearest, anchor-size(--m{index:03d} width) / 1px * "
                    f"{UNITS_PER_EM} / {FONT_SIZE} - {base_total}, 1)"
                )
            x = (
                f"(({anchors[0]} + {PACKED_READBACK_OFFSET}) + "
                f"({anchors[1]} + {PACKED_READBACK_OFFSET}) * {PACKED_READBACK_BASE}) * 1px"
            )
            y = (
                f"(({anchors[2]} + {PACKED_READBACK_OFFSET}) + "
                f"({anchors[3]} + {PACKED_READBACK_OFFSET}) * {PACKED_READBACK_BASE}) * 1px"
            )
            probe_rules.append(
                f'.probe-{group:03d}{{width:calc({x});height:calc({y});'
                f'container:p{group:03d}/size}}'
            )
            target = (
                f'.probe-{group + 1:03d}'
                if local + 4 < output_count
                else "slot"
            )
            for axis, first in (("i", local), ("b", local + 2)):
                unit = "100cqi" if axis == "i" else "100cqb"
                packed = f"round(nearest, {unit} / 1px, 1)"
                query_rules.append(
                    f'@container p{group:03d} ({"width" if axis == "i" else "height"} > 0px)'
                    f'{{{target}{{--raw-{first:03d}:calc(mod({packed}, {PACKED_READBACK_BASE}) '
                    f'- {PACKED_READBACK_OFFSET});--raw-{first + 1:03d}:calc('
                    f'round(down, {packed} / {PACKED_READBACK_BASE}, 1) '
                    f'- {PACKED_READBACK_OFFSET})}}}}'
                )
        chain = packed_quad_chain(
            output_indices, '<slot name="next"></slot>', font_group
        )
    else:
        for local in range(0, output_count, 2):
            pair = local // 2
            probe_rules.append(
                f'.metric-{local:03d}{{anchor-name:--m{local:03d}}}'
                f'.metric-{local + 1:03d}{{anchor-name:--m{local + 1:03d}}}'
                f'.probe-{pair:03d}{{width:anchor-size(--m{local:03d} width);'
                f'height:anchor-size(--m{local + 1:03d} width);container:p{pair:03d}/size}}'
            )
            target = f'.probe-{pair + 1:03d}' if local + 2 < output_count else "slot"
            width_value = (
                f'calc(100cqi / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {base_total})'
            )
            height_value = (
                f'calc(100cqb / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {base_total})'
            )
            if direct_readback:
                query_rules.append(
                    f'{target}{{--raw-{local:03d}:{width_value};'
                    f'--raw-{local + 1:03d}:{height_value}}}'
                )
            else:
                query_rules.append(
                    f'@container p{pair:03d} (width > 0px){{{target}'
                    f'{{--raw-{local:03d}:{width_value}}}}}'
                )
                query_rules.append(
                    f'@container p{pair:03d} (height > 0px){{{target}'
                    f'{{--raw-{local + 1:03d}:{height_value}}}}}'
                )
        chain = pair_chain(output_indices, '<slot name="next"></slot>', font_group)
    stage_css = (
        '/* faces *//* base */:host{display:block;position:relative}.metric{position:fixed;'
        'inset:0 auto auto 0;display:inline-flex;'
        f'width:max-content;height:1px;overflow:hidden;white-space:pre;font-size:{FONT_SIZE}px;'
        'font-kerning:none}.pack{display:inline-block;width:max-content;height:1px;'
        'overflow:hidden;white-space:pre}'
        '.probe{position:fixed;inset:0 auto auto 0;overflow:visible}'
        + "/* fonts */"
        + "".join(pack_rules)
        + "/* probes */"
        + "".join(probe_rules)
        + "/* queries */"
        + "".join(query_rules)
    )
    css_path = OUT / f"stage-{stage_name}.css"
    css_path.write_text(stage_css)
    css_tag = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
    return (
        '<template shadowrootmode="open">'
        f'<link rel="stylesheet" href="stage-{stage_name}.css?v={css_tag}">'
        + chain
        + "</template>"
    )


def partial_mlp_metrics(font_group: FontGroup) -> list[str]:
    branches = []
    for branch, first_shard in enumerate(range(0, len(font_group.names), PACK_SHARDS)):
        metrics = []
        for output in range(WIDTH):
            characters = "".join(
                f'&#x{font_group.codepoint_starts[shard] + output:X};'
                for shard in range(first_shard, first_shard + PACK_SHARDS)
            )
            metrics.append(
                f'<span class="partial-metric partial-b{branch}-{output:03d}">'
                f"{characters}</span>"
            )
        branches.append("".join(metrics))
    return branches


def partial_mlp_css(font_group: FontGroup, activation_range: float) -> str:
    rules = [
        ".parallel-mlp{display:block}",
        ".partial-result{display:block}",
        ".partial-metric{position:fixed;inset:0 auto auto 0;display:inline-flex;"
        f"width:max-content;height:1px;overflow:hidden;white-space:pre;font-size:{FONT_SIZE}px;"
        "font-kerning:none}",
    ]
    hidden_inputs = [f"--hidden-{index:03d}" for index in range(MLP_WIDTH)]
    for branch, first_shard in enumerate(range(0, len(font_group.names), PACK_SHARDS)):
        families = ",".join(
            f"mlpS{shard}"
            for shard in range(first_shard, first_shard + PACK_SHARDS)
        )
        settings = pack_font_settings(hidden_inputs, activation_range, first_shard)
        rules.append(
            f'.partial-result-{branch}{{font-family:{families};'
            f"font-variation-settings:{settings}}}"
        )
        rules.extend(
            f".partial-b{branch}-{output:03d}"
            f"{{anchor-name:--partial-b{branch}-{output:03d}}}"
            for output in range(WIDTH)
        )
    return "".join(rules)


def merged_mlp_light_dom(font_group: FontGroup) -> tuple[str, str]:
    branch_count = math.ceil(len(font_group.names) / PACK_SHARDS)
    probe_rules = []
    outer_anchor_rules = []
    query_rules = []
    child = '<output id="final" class="final"></output>'
    base_total = sum(font_group.bases)
    for local in reversed(range(0, WIDTH, 2)):
        pair = local // 2
        child = (
            f'<div class="merge-probe merge-probe-{pair:03d}">{child}</div>'
        )
    for local in range(0, WIDTH, 2):
        pair = local // 2
        width = "+".join(
            f"anchor-size(--partial-b{branch}-{local:03d} width)"
            for branch in range(branch_count)
        )
        height = "+".join(
            f"anchor-size(--partial-b{branch}-{local + 1:03d} width)"
            for branch in range(branch_count)
        )
        probe_rules.append(
            f".merge-probe-{pair:03d}{{container:merged{pair:03d}/size}}"
        )
        outer_anchor_rules.append(
            f".merge-probe-{pair:03d}"
            f"{{width:calc({width});height:calc({height})}}"
        )
        target = (
            f".merge-probe-{pair + 1:03d}"
            if local + 2 < WIDTH
            else "#final"
        )
        query_rules.append(
            f"@container merged{pair:03d} (width > 0px){{{target}"
            f"{{--raw-{local:03d}:calc(100cqi / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {base_total})}}}}"
        )
        query_rules.append(
            f"@container merged{pair:03d} (height > 0px){{{target}"
            f"{{--raw-{local + 1:03d}:calc(100cqb / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {base_total})}}}}"
        )
    css = (
        ".merge-probe{position:fixed;"
        "inset:0 auto auto 0;overflow:visible}"
        + "".join(probe_rules)
        + "".join(outer_anchor_rules)
        + "".join(query_rules)
    )
    return child, css


def parallel_pipeline_html(
    v_shadow: str,
    attn_shadow: str,
    fc_shadows: dict[int, str],
    merge_html: str,
    partial_branches: list[str],
) -> str:
    branches = []
    for branch in range(FC_STAGES):
        result = (
            f'<div class="hidden-stage-{branch:02d} partial-result '
            f'partial-result-{branch}" slot="next">'
            f"{partial_branches[branch]}</div>"
        )
        branches.append(
            f'<css-stage class="fc-branch fc-branch-{branch}">'
            f"{fc_shadows[branch]}{result}</css-stage>"
        )
    merge = f'<div class="merge-stage">{merge_html}</div>'
    parallel = f'<div class="parallel-mlp">{"".join(branches)}{merge}</div>'
    after_attn = f'<div class="after-attn" slot="next">{parallel}</div>'
    after_v = host("after-v", attn_shadow, after_attn)
    return host("norm1", v_shadow, after_v, outer=True)


def host(css_class: str, shadow: str, child: str, *, outer: bool = False) -> str:
    slot = "" if outer else ' slot="next"'
    return f'<css-stage class="{css_class}"{slot}>{shadow}{child}</css-stage>'


def pipeline_html(stages: list[tuple[str, str]]) -> str:
    all_classes = [
        "norm1",
        "after-v",
        "after-attn",
        "hidden-stage-00",
        "hidden-stage-01",
        "hidden-stage-02",
        "hidden-stage-03",
    ]
    next_class = all_classes[len(stages)] if len(stages) < len(all_classes) else "final"
    child = f'<output id="final" class="{next_class}" slot="next"></output>'
    for index in reversed(range(len(stages))):
        css_class, shadow = stages[index]
        child = host(css_class, shadow, child, outer=index == 0)
    return child


def compressed_size(path: Path) -> int:
    if brotli is not None:
        return len(brotli.compress(path.read_bytes(), quality=11))
    result = subprocess.run(
        ["/opt/homebrew/bin/brotli", "-q", "11", "-c", str(path)],
        check=True,
        capture_output=True,
    )
    return len(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reuse-fonts",
        action="store_true",
        help="regenerate HTML/CSS from the existing content-addressed font files",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    data = model_data()

    q_v = quantize_float_rows(data["v_weight"], bits=QUANT_BITS)
    q_attn = quantize_float_rows(data["attn_proj_weight"], bits=QUANT_BITS)
    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    q_mlp = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    q_composed = quantize_float_rows(composed_weight, bits=QUANT_BITS)

    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    v = q_v.reconstructed @ n1 + data["v_bias"]
    attn = q_attn.reconstructed @ v + data["attn_proj_bias"]
    r1 = data["x"] + attn
    n2 = layer_norm(r1, data["ln2_gamma"], data["ln2_beta"])
    pre = q_fc.reconstructed @ n2 + data["fc_bias"]
    hidden = gelu_new(pre)
    mlp = q_mlp.reconstructed @ hidden + data["mlp_proj_bias"]
    expected = r1 + mlp

    composed_attn = q_composed.reconstructed @ n1 + composed_bias
    composed_r1 = data["x"] + composed_attn
    composed_n2 = layer_norm(
        composed_r1, data["ln2_gamma"], data["ln2_beta"]
    )
    composed_pre = q_fc.reconstructed @ composed_n2 + data["fc_bias"]
    composed_hidden = gelu_new(composed_pre)
    composed_mlp = q_mlp.reconstructed @ composed_hidden + data["mlp_proj_bias"]
    composed_expected = composed_r1 + composed_mlp

    original_n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    original_v = data["v_weight"] @ original_n1 + data["v_bias"]
    original_attn = data["attn_proj_weight"] @ original_v + data["attn_proj_bias"]
    original_r1 = data["x"] + original_attn
    original_n2 = layer_norm(original_r1, data["ln2_gamma"], data["ln2_beta"])
    original_hidden = gelu_new(data["fc_weight"] @ original_n2 + data["fc_bias"])
    original = original_r1 + data["mlp_proj_weight"] @ original_hidden + data["mlp_proj_bias"]

    ranges = {
        "n1_range": float(np.max(np.abs(n1)) * 1.01),
        "v_range": float(np.max(np.abs(v)) * 1.01),
        "n2_range": float(np.max(np.abs(n2)) * 1.01),
        "hidden_range": float(np.max(np.abs(hidden)) * 1.01),
    }
    refs: dict[str, object] = {
        "q_v": q_v,
        "q_attn": q_attn,
        "q_fc": q_fc,
        "q_mlp": q_mlp,
        **ranges,
    }
    composed_ranges = {
        "n1_range": ranges["n1_range"],
        "n2_range": float(np.max(np.abs(composed_n2)) * 1.01),
        "hidden_range": float(np.max(np.abs(composed_hidden)) * 1.01),
    }
    composed_refs: dict[str, object] = {
        "q_composed": q_composed,
        "composed_bias": composed_bias,
        "q_fc": q_fc,
        "q_mlp": q_mlp,
        **composed_ranges,
    }

    started = time.perf_counter()
    rebuild_fonts = not args.reuse_fonts
    v_fonts = build_font_group("v", q_v.codes, rebuild=rebuild_fonts)
    attn_fonts = build_font_group("attn-proj", q_attn.codes, rebuild=rebuild_fonts)
    fc_fonts = build_font_group("fc", q_fc.codes, rebuild=rebuild_fonts)
    mlp_fonts = build_font_group("mlp-proj", q_mlp.codes, rebuild=rebuild_fonts)
    composed_fonts_exist = all(
        (OUT / f"attn-composed-s{shard}.woff2").exists()
        for shard in range(math.ceil(WIDTH / SHARD))
    )
    composed_fonts = build_font_group(
        "attn-composed",
        q_composed.codes,
        rebuild=rebuild_fonts or not composed_fonts_exist,
    )
    build_seconds = time.perf_counter() - started

    n2_inputs = [f"--n2-{index:03d}" for index in range(WIDTH)]
    hidden_inputs = [f"--hidden-{index:03d}" for index in range(MLP_WIDTH)]
    mlp_shadow = matrix_shadow(
        "mlp",
        mlp_fonts,
        hidden_inputs,
        ranges["hidden_range"],
        list(range(WIDTH)),
    )
    fc_shadows: dict[int, str] = {}
    for fc_stage in reversed(range(1, FC_STAGES)):
        fc_start = fc_stage * FC_STAGE_OUTPUTS
        fc_shadow = matrix_shadow(
            f"fc{fc_stage:02d}",
            fc_fonts,
            n2_inputs,
            ranges["n2_range"],
            list(range(fc_start, fc_start + FC_STAGE_OUTPUTS)),
            family_prefix="fc",
        )
        fc_shadows[fc_stage] = fc_shadow

    fc0_shadow = matrix_shadow(
        "fc00",
        fc_fonts,
        n2_inputs,
        ranges["n2_range"],
        list(range(FC_STAGE_OUTPUTS)),
        family_prefix="fc",
    )
    fc_shadows[0] = fc0_shadow
    attn_shadow = matrix_shadow(
        "attn",
        attn_fonts,
        [f"--v-{index:03d}" for index in range(WIDTH)],
        ranges["v_range"],
        list(range(WIDTH)),
    )
    v_shadow = matrix_shadow(
        "value",
        v_fonts,
        [f"--n1-{index:03d}" for index in range(WIDTH)],
        ranges["n1_range"],
        list(range(WIDTH)),
    )
    composed_attention_shadow = matrix_shadow(
        "composed-attn",
        composed_fonts,
        [f"--n1-{index:03d}" for index in range(WIDTH)],
        composed_ranges["n1_range"],
        list(range(WIDTH)),
    )
    composed_mlp_shadow = matrix_shadow(
        "composed-mlp",
        mlp_fonts,
        hidden_inputs,
        composed_ranges["hidden_range"],
        list(range(WIDTH)),
        family_prefix="mlp",
    )
    composed_fc_shadows: dict[int, str] = {}
    for fc_stage in range(FC_STAGES):
        fc_start = fc_stage * FC_STAGE_OUTPUTS
        composed_fc_shadows[fc_stage] = matrix_shadow(
            f"composed-fc{fc_stage:02d}",
            fc_fonts,
            n2_inputs,
            composed_ranges["n2_range"],
            list(range(fc_start, fc_start + FC_STAGE_OUTPUTS)),
            family_prefix="fc",
        )
    direct_composed_attention_shadow = matrix_shadow(
        "direct-composed-attn",
        composed_fonts,
        [f"--n1-{index:03d}" for index in range(WIDTH)],
        composed_ranges["n1_range"],
        list(range(WIDTH)),
        family_prefix="composed-attn",
        direct_readback=True,
    )
    direct_composed_mlp_shadow = matrix_shadow(
        "direct-composed-mlp",
        mlp_fonts,
        hidden_inputs,
        composed_ranges["hidden_range"],
        list(range(WIDTH)),
        family_prefix="mlp",
        direct_readback=True,
    )
    direct_composed_fc_shadows: dict[int, str] = {}
    for fc_stage in range(FC_STAGES):
        fc_start = fc_stage * FC_STAGE_OUTPUTS
        direct_composed_fc_shadows[fc_stage] = matrix_shadow(
            f"direct-composed-fc{fc_stage:02d}",
            fc_fonts,
            n2_inputs,
            composed_ranges["n2_range"],
            list(range(fc_start, fc_start + FC_STAGE_OUTPUTS)),
            family_prefix="fc",
            direct_readback=True,
        )
    packed_composed_attention_shadow = matrix_shadow(
        "packed-composed-attn",
        composed_fonts,
        [f"--n1-{index:03d}" for index in range(WIDTH)],
        composed_ranges["n1_range"],
        list(range(WIDTH)),
        family_prefix="composed-attn",
        packed_readback=True,
    )
    packed_composed_mlp_shadow = matrix_shadow(
        "packed-composed-mlp",
        mlp_fonts,
        hidden_inputs,
        composed_ranges["hidden_range"],
        list(range(WIDTH)),
        family_prefix="mlp",
        packed_readback=True,
    )
    packed_composed_fc_shadows: dict[int, str] = {}
    for fc_stage in range(FC_STAGES):
        fc_start = fc_stage * FC_STAGE_OUTPUTS
        packed_composed_fc_shadows[fc_stage] = matrix_shadow(
            f"packed-composed-fc{fc_stage:02d}",
            fc_fonts,
            n2_inputs,
            composed_ranges["n2_range"],
            list(range(fc_start, fc_start + FC_STAGE_OUTPUTS)),
            family_prefix="fc",
            packed_readback=True,
        )
    packed_collapsed_fc_shadow = matrix_shadow(
        "packed-collapsed-fc",
        fc_fonts,
        n2_inputs,
        composed_ranges["n2_range"],
        list(range(MLP_WIDTH)),
        family_prefix="fc",
        packed_readback=True,
    )
    packed_two_fc_shadows = [
        matrix_shadow(
            f"packed-two-fc{stage:02d}",
            fc_fonts,
            n2_inputs,
            composed_ranges["n2_range"],
            list(range(stage * 1536, (stage + 1) * 1536)),
            family_prefix="fc",
            packed_readback=True,
        )
        for stage in range(2)
    ]
    stages = [
        ("norm1", v_shadow),
        ("after-v", attn_shadow),
        ("after-attn", fc0_shadow),
        *(
            (f"hidden-stage-{stage - 1:02d}", fc_shadows[stage])
            for stage in range(1, FC_STAGES)
        ),
        ("hidden-stage-03", mlp_shadow),
    ]
    root_stage = pipeline_html(stages)
    composed_stages = [
        ("norm1", composed_attention_shadow),
        ("after-attn", composed_fc_shadows[0]),
        *(
            (f"hidden-stage-{stage - 1:02d}", composed_fc_shadows[stage])
            for stage in range(1, FC_STAGES)
        ),
        ("hidden-stage-03", composed_mlp_shadow),
    ]
    composed_child = '<output id="final" class="final" slot="next"></output>'
    for index in reversed(range(len(composed_stages))):
        css_class, shadow = composed_stages[index]
        composed_child = host(
            css_class,
            shadow,
            composed_child,
            outer=index == 0,
        )
    composed_root = composed_child
    direct_composed_stages = [
        ("norm1", direct_composed_attention_shadow),
        ("after-attn", direct_composed_fc_shadows[0]),
        *(
            (f"hidden-stage-{stage - 1:02d}", direct_composed_fc_shadows[stage])
            for stage in range(1, FC_STAGES)
        ),
        ("hidden-stage-03", direct_composed_mlp_shadow),
    ]
    direct_composed_child = '<output id="final" class="final" slot="next"></output>'
    for index in reversed(range(len(direct_composed_stages))):
        css_class, shadow = direct_composed_stages[index]
        direct_composed_child = host(
            css_class,
            shadow,
            direct_composed_child,
            outer=index == 0,
        )
    packed_composed_stages = [
        ("norm1", packed_composed_attention_shadow),
        ("after-attn", packed_composed_fc_shadows[0]),
        *(
            (f"hidden-stage-{stage - 1:02d}", packed_composed_fc_shadows[stage])
            for stage in range(1, FC_STAGES)
        ),
        ("hidden-stage-03", packed_composed_mlp_shadow),
    ]
    packed_composed_child = '<output id="final" class="final" slot="next"></output>'
    for index in reversed(range(len(packed_composed_stages))):
        css_class, shadow = packed_composed_stages[index]
        packed_composed_child = host(
            css_class,
            shadow,
            packed_composed_child,
            outer=index == 0,
        )
    packed_collapsed_stages = [
        ("norm1", packed_composed_attention_shadow),
        ("after-attn", packed_collapsed_fc_shadow),
        ("hidden-all", packed_composed_mlp_shadow),
    ]
    packed_collapsed_child = '<output id="final" class="final" slot="next"></output>'
    for index in reversed(range(len(packed_collapsed_stages))):
        css_class, shadow = packed_collapsed_stages[index]
        packed_collapsed_child = host(
            css_class,
            shadow,
            packed_collapsed_child,
            outer=index == 0,
        )
    packed_two_fc_stages = [
        ("norm1", packed_composed_attention_shadow),
        ("after-attn", packed_two_fc_shadows[0]),
        ("hidden-stage-00", packed_two_fc_shadows[1]),
        ("hidden-stage-01", packed_composed_mlp_shadow),
    ]
    packed_two_fc_child = '<output id="final" class="final" slot="next"></output>'
    for index in reversed(range(len(packed_two_fc_stages))):
        css_class, shadow = packed_two_fc_stages[index]
        packed_two_fc_child = host(
            css_class,
            shadow,
            packed_two_fc_child,
            outer=index == 0,
        )
    merge_html, merge_css = merged_mlp_light_dom(mlp_fonts)
    partial_branches = partial_mlp_metrics(mlp_fonts)
    parallel_root = parallel_pipeline_html(
        v_shadow,
        attn_shadow,
        fc_shadows,
        merge_html,
        partial_branches,
    )

    model_css_path = OUT / "model.css"
    global_face_css = "".join(
        [
            font_faces("value", v_fonts),
            font_faces("attn", attn_fonts),
            font_faces("fc", fc_fonts),
            font_faces("mlp", mlp_fonts),
        ]
    )
    model_css_path.write_text(global_face_css + global_css(data, refs))
    model_css_tag = hashlib.sha256(model_css_path.read_bytes()).hexdigest()[:12]
    parallel_css_path = OUT / "model-parallel.css"
    parallel_css_path.write_text(
        global_face_css
        + global_css(data, refs)
        + partial_mlp_css(mlp_fonts, ranges["hidden_range"])
        + merge_css
    )
    parallel_css_tag = hashlib.sha256(parallel_css_path.read_bytes()).hexdigest()[:12]
    composed_css_path = OUT / "model-composed.css"
    composed_face_css = "".join(
        [
            font_faces("composedattn", composed_fonts),
            font_faces("fc", fc_fonts),
            font_faces("mlp", mlp_fonts),
        ]
    )
    composed_css_path.write_text(
        composed_face_css
        + global_css(data, composed_refs, composed_attention=True)
    )
    composed_css_tag = hashlib.sha256(composed_css_path.read_bytes()).hexdigest()[:12]
    collapsed_css_path = OUT / "model-composed-collapsed.css"
    collapsed_css_path.write_text(
        composed_face_css
        + global_css(
            data,
            composed_refs,
            composed_attention=True,
            collapsed_fc=True,
        )
    )
    collapsed_css_tag = hashlib.sha256(collapsed_css_path.read_bytes()).hexdigest()[:12]
    two_fc_css_path = OUT / "model-composed-two-fc.css"
    two_fc_css_path.write_text(
        composed_face_css
        + global_css(
            data,
            composed_refs,
            composed_attention=True,
            fc_stage_outputs_override=1536,
        )
    )
    two_fc_css_tag = hashlib.sha256(two_fc_css_path.read_bytes()).hexdigest()[:12]
    html_path = OUT / "index.html"
    html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>GPT-2 block in CSS</title>'
        f'<link rel="stylesheet" href="model.css?v={model_css_tag}">'
        '<h1>One GPT-2-small transformer block in HTML/CSS</h1>'
        '<p class="status">One-token causal context. No JavaScript.</p>'
        + root_stage
    )
    parallel_html_path = OUT / "parallel.html"
    parallel_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>Negative parallel GPT-2 experiment</title>'
        f'<link rel="stylesheet" href="model-parallel.css?v={parallel_css_tag}">'
        '<h1>Negative experiment: contained anchors cannot merge</h1>'
        '<p class="status">The four branches render, but their final anchors are '
        'not visible outside the size-containment chains. This page is not a correct block.</p>'
        + parallel_root
    )
    composed_html_path = OUT / "composed.html"
    composed_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>Composed GPT-2 block in CSS</title>'
        f'<link rel="stylesheet" href="model-composed.css?v={composed_css_tag}">'
        '<h1>Six-stage one-token GPT-2-small block in HTML/CSS</h1>'
        '<p class="status">The one-token V and attention-output affine maps are composed. '
        'No JavaScript.</p>'
        + composed_root
    )
    direct_composed_html_path = OUT / "composed-direct-cqi.html"
    direct_composed_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Direct-readback GPT-2 block in CSS</title>'
        f'<link rel="stylesheet" href="model-composed.css?v={composed_css_tag}">'
        '<h1>Direct-readback one-token GPT-2-small block in HTML/CSS</h1>'
        '<p class="status">Container units feed registered CSS numbers directly. '
        'No JavaScript.</p>'
        + direct_composed_child
    )
    packed_composed_html_path = OUT / "composed-packed.html"
    packed_composed_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>Packed GPT-2 block in CSS</title>'
        f'<link rel="stylesheet" href="model-composed.css?v={composed_css_tag}">'
        '<h1>Packed-readback one-token GPT-2-small block in HTML/CSS</h1>'
        '<p class="status">Four matrix outputs share each size container. No JavaScript.</p>'
        + packed_composed_child
    )
    packed_collapsed_html_path = OUT / "composed-packed-collapsed-fc.html"
    packed_collapsed_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Collapsed-FC packed GPT-2 block in CSS</title>'
        f'<link rel="stylesheet" href="model-composed-collapsed.css?v={collapsed_css_tag}">'
        '<h1>Negative limit probe: one collapsed FC stage</h1>'
        '<p class="status">The browser stops the nested chain after FC output 2,023; '
        'later outputs are zero, so this page is intentionally not a correct block. No JavaScript.</p>'
        + packed_collapsed_child
    )
    packed_two_fc_html_path = OUT / "composed-packed-two-fc.html"
    packed_two_fc_html_path.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Two-FC-stage packed GPT-2 block in CSS</title>'
        f'<link rel="stylesheet" href="model-composed-two-fc.css?v={two_fc_css_tag}">'
        '<h1>Four-stage packed-readback GPT-2-small block</h1>'
        '<p class="status">The 3,072 FC outputs use two 1,536-output stages. No JavaScript.</p>'
        + packed_two_fc_child
    )
    for stage_count in range(1, len(packed_collapsed_stages) + 1):
        child = '<output id="final" class="final" slot="next"></output>'
        for index in reversed(range(stage_count)):
            css_class, shadow = packed_collapsed_stages[index]
            child = host(css_class, shadow, child, outer=index == 0)
        (OUT / f"composed-packed-collapsed-prefix-{stage_count}.html").write_text(
            '<!doctype html><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f'<title>Collapsed packed GPT-2 prefix {stage_count}</title>'
            f'<link rel="stylesheet" href="model-composed-collapsed.css?v={collapsed_css_tag}">'
            + child
        )
    for stage_count in range(1, len(packed_composed_stages) + 1):
        child = '<output id="final" class="final" slot="next"></output>'
        for index in reversed(range(stage_count)):
            css_class, shadow = packed_composed_stages[index]
            child = host(css_class, shadow, child, outer=index == 0)
        (OUT / f"composed-packed-prefix-{stage_count}.html").write_text(
            '<!doctype html><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f'<title>Packed GPT-2 prefix {stage_count}</title>'
            f'<link rel="stylesheet" href="model-composed.css?v={composed_css_tag}">'
            + child
        )
    for stage_count in range(1, len(stages) + 1):
        (OUT / f"prefix-{stage_count}.html").write_text(
            '<!doctype html><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f'<title>GPT-2 CSS stage prefix {stage_count}</title>'
            f'<link rel="stylesheet" href="model.css?v={model_css_tag}">'
            f'<h1>GPT-2 CSS stage prefix {stage_count}/{len(stages)}</h1>'
            + pipeline_html(stages[:stage_count])
        )

    font_groups = (v_fonts, attn_fonts, fc_fonts, mlp_fonts)
    font_paths = [
        OUT / f"{name}.woff2"
        for group in font_groups
        for name in group.names
    ]
    stage_names = [
        "value",
        "attn",
        *(f"fc{stage:02d}" for stage in range(FC_STAGES)),
        "mlp",
    ]
    css_paths = [model_css_path, *(OUT / f"stage-{name}.css" for name in stage_names)]
    runtime_paths = [html_path, *css_paths, *font_paths]
    metadata = {
        "token_id": TOKEN_ID,
        "width": WIDTH,
        "mlp_width": MLP_WIDTH,
        "quant_bits": QUANT_BITS,
        "font_size": FONT_SIZE,
        "layout_strategy": "fixed-to-viewport",
        "font_face_scope": "document",
        "font_count": len(font_paths),
        "slotted_stages": len(stage_names),
        "packed_term_elements": html_path.read_text().count('<i class="pack '),
        "build_seconds": build_seconds,
        "ranges": ranges,
        "composed_ranges": composed_ranges,
        "quantized_output": expected.tolist(),
        "original_output": original.tolist(),
        "quantization_max_error": float(np.max(np.abs(expected - original))),
        "composed_quantized_output": composed_expected.tolist(),
        "composed_quantization_max_error": float(
            np.max(np.abs(composed_expected - original))
        ),
        "font_bytes": sum(path.stat().st_size for path in font_paths),
        "css_bytes": sum(path.stat().st_size for path in css_paths),
        "html_bytes": html_path.stat().st_size,
        "runtime_raw_bytes": sum(path.stat().st_size for path in runtime_paths),
        "runtime_brotli_bytes": sum(compressed_size(path) for path in runtime_paths),
        "parallel_html_bytes": parallel_html_path.stat().st_size,
        "parallel_css_bytes": parallel_css_path.stat().st_size,
        "composed_html_bytes": composed_html_path.stat().st_size,
        "composed_css_bytes": composed_css_path.stat().st_size
        + sum(
            (OUT / f"stage-{name}.css").stat().st_size
            for name in (
                "composed-attn",
                *(f"composed-fc{stage:02d}" for stage in range(FC_STAGES)),
                "composed-mlp",
            )
        ),
        "composed_font_count": len(composed_fonts.names)
        + len(fc_fonts.names)
        + len(mlp_fonts.names),
        "packed_readback_outputs_per_container": 4,
        "packed_readback_base": PACKED_READBACK_BASE,
        "packed_readback_offset": PACKED_READBACK_OFFSET,
        "packed_composed_html_bytes": packed_composed_html_path.stat().st_size,
        "packed_composed_css_bytes": composed_css_path.stat().st_size
        + sum(
            (OUT / f"stage-{name}.css").stat().st_size
            for name in (
                "packed-composed-attn",
                *(f"packed-composed-fc{stage:02d}" for stage in range(FC_STAGES)),
                "packed-composed-mlp",
            )
        ),
        "packed_collapsed_stage_count": len(packed_collapsed_stages),
        "packed_collapsed_readback_containers": WIDTH // 4
        + MLP_WIDTH // 4
        + WIDTH // 4,
        "packed_collapsed_html_bytes": packed_collapsed_html_path.stat().st_size,
        "packed_collapsed_css_bytes": collapsed_css_path.stat().st_size
        + sum(
            (OUT / f"stage-{name}.css").stat().st_size
            for name in (
                "packed-composed-attn",
                "packed-collapsed-fc",
                "packed-composed-mlp",
            )
        ),
        "packed_two_fc_stage_count": len(packed_two_fc_stages),
        "packed_two_fc_max_container_depth": 1536 // 4,
        "packed_two_fc_html_bytes": packed_two_fc_html_path.stat().st_size,
        "packed_two_fc_css_bytes": two_fc_css_path.stat().st_size
        + sum(
            (OUT / f"stage-{name}.css").stat().st_size
            for name in (
                "packed-composed-attn",
                "packed-two-fc00",
                "packed-two-fc01",
                "packed-composed-mlp",
            )
        ),
    }
    (OUT / "reference.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(
        {
            key: metadata[key]
            for key in (
                "font_count",
                "build_seconds",
                "quantization_max_error",
                "html_bytes",
                "runtime_raw_bytes",
                "runtime_brotli_bytes",
            )
        }
    )


if __name__ == "__main__":
    main()
