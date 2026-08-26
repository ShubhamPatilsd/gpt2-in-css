#!/usr/bin/env python3
"""Build real-GPT 768x768 four- versus five-font-metric scaling fixtures."""

from __future__ import annotations

import json
import multiprocessing
import os
import sys
from pathlib import Path

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from analyze_full_gpt2 import MODEL_PATH, SafeTensors  # noqa: E402
from build_hvar_five_metric_fullwidth import (  # noqa: E402
    BASE,
    DELTA_SCALE,
    FONT_SIZE,
    UNITS_PER_EM,
    axis_tag,
    build_font as build_five_font,
)
from build_pretrained_gpt2 import layer_norm  # noqa: E402


OUT = ROOT / "experiments" / "hvar-five-metric-scale"
WIDTH = 768
FIVE_CHANNELS = ("ex", "cap", "ch", "ic", "lh")
FOUR_CHANNELS = ("cap", "ch", "ic", "lh")
TOKEN_IDS = (11, 612, 373, 257, 464, 3290)
WEIGHT_QUANT_MAX = 32


def rectangle(width: int, height: int):
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((width, 0))
    pen.lineTo((width, height))
    pen.lineTo((0, height))
    pen.closePath()
    return pen.glyph()


def build_four_font(name: str, weights: np.ndarray, path: Path) -> None:
    """Build cap/ch/ic/lh outputs with 256 axes and no outline variation."""
    axis_count = weights.shape[1]
    glyphs = [".notdef", "zero", "water"]
    fb = FontBuilder(UNITS_PER_EM, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap({0x30: "zero", 0x6C34: "water"})
    fb.setupGlyf({glyph: rectangle(1, 1) for glyph in glyphs})
    fb.setupHorizontalMetrics({
        ".notdef": (500, 0), "zero": (BASE, 0), "water": (BASE, 0),
    })
    fb.setupHorizontalHeader(ascent=BASE, descent=0, lineGap=0)
    fb.setupNameTable({
        "familyName": f"CSS Four Metric {name}",
        "styleName": "Regular",
        "uniqueFontIdentifier": f"CSS-Four-Metric-{name}-Regular",
        "fullName": f"CSS Four Metric {name} Regular",
        "psName": f"CSSFourMetric{name.title()}-Regular",
    })
    fb.setupOS2(
        version=4, sTypoAscender=BASE, sTypoDescender=0, sTypoLineGap=0,
        usWinAscent=BASE, usWinDescent=0, sCapHeight=BASE, fsSelection=0xC0,
    )
    fb.setupPost()
    fb.setupMaxp()
    fb.setupHead(created=2_082_844_800, modified=2_082_844_800)
    fb.font.recalcTimestamp = False
    fb.save(path)

    font = TTFont(path, recalcTimestamp=False)
    tags = [axis_tag(index) for index in range(axis_count)]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for index, tag in enumerate(tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = 0
        axis.defaultValue = 0
        axis.maxValue = 1
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    supports = [{tag: (0, 1, 1)} for tag in tags]
    encoded = [
        [2 * DELTA_SCALE * int(value) for value in row]
        for row in weights
    ]
    regions = buildVarRegionList(supports, tags)
    hvar_rows = [[0] * axis_count for _ in glyphs]
    hvar_rows[1] = encoded[1]
    hvar_rows[2] = encoded[2]
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions, [buildVarData(range(axis_count), hvar_rows, optimize=True)])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    mvar = newTable("MVAR")
    mvar.table = otTables.MVAR()
    mvar.table.Version = 0x00010000
    mvar.table.Reserved = 0
    mvar.table.VarStore = buildVarStore(
        regions, [buildVarData(range(axis_count), [encoded[0], encoded[3]], optimize=True)])
    mvar.table.ValueRecordSize = 8
    mvar.table.ValueRecordCount = 2
    records = []
    for index, tag in enumerate(("cpht", "hasc")):
        record = otTables.MetricsValueRecord()
        record.ValueTag = tag
        record.VarIdx = index
        records.append(record)
    mvar.table.ValueRecord = sorted(records, key=lambda record: record.ValueTag)
    font["MVAR"] = mvar
    font.recalcTimestamp = False
    font.save(path)


def build_one(task: tuple[str, int, int, np.ndarray]) -> tuple[str, int, int]:
    mode, group, shard, weights = task
    stem = f"{mode}-g{group:03d}-s{shard}"
    ttf_path = OUT / f"{stem}.ttf"
    woff_path = OUT / f"{stem}.woff"
    if mode == "five":
        build_five_font(stem, weights, ttf_path)
    else:
        build_four_font(stem, weights, ttf_path)
    sfnt_bytes = ttf_path.stat().st_size
    web_font = TTFont(ttf_path, recalcTimestamp=False)
    web_font.flavor = "woff"
    web_font.save(woff_path)
    web_bytes = woff_path.stat().st_size
    ttf_path.unlink()
    return mode, sfnt_bytes, web_bytes


def real_fixture() -> dict[str, object]:
    tensors = SafeTensors(MODEL_PATH)
    matrix = np.asarray(
        tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64
    ).T
    real_vectors = []
    for token_id in TOKEN_IDS:
        state = np.asarray(
            tensors.tensor("wte.weight")[token_id] + tensors.tensor("wpe.weight")[0],
            dtype=np.float64,
        )
        normalized = layer_norm(
            state,
            tensors.tensor("h.0.ln_1.weight"),
            tensors.tensor("h.0.ln_1.bias"),
        )
        qkv = (
            normalized @ tensors.tensor("h.0.attn.c_attn.weight")
            + tensors.tensor("h.0.attn.c_attn.bias")
        )
        real_vectors.append(np.asarray(qkv[2 * WIDTH:], dtype=np.float64))
    real_vectors = np.asarray(real_vectors)
    input_scale = float(np.max(np.abs(real_vectors)) * 1.001)
    rng = np.random.default_rng(0x5245414C)
    random_normalized = rng.uniform(-0.9, 0.9, size=(4, WIDTH))
    normalized_vectors = np.vstack((real_vectors / input_scale, random_normalized))
    kinds = [f"token-{token_id}" for token_id in TOKEN_IDS] + [f"random-{i}" for i in range(4)]

    row_max = np.maximum(np.max(np.abs(matrix), axis=1), 1e-12)
    row_scales = WEIGHT_QUANT_MAX / row_max
    quantized = np.rint(matrix * row_scales[:, None]).astype(np.int16)
    output_factors = input_scale / row_scales
    true_vectors = normalized_vectors * input_scale
    expected_true = true_vectors @ matrix.T
    expected_quantized = (normalized_vectors @ quantized.T) * output_factors

    one_axis = {}
    for value in (-0.8, 0.8):
        vector = normalized_vectors[0].copy()
        vector[0] = value
        one_axis[str(value)] = {
            "true": ((vector * input_scale) @ matrix.T).tolist(),
            "quantized": ((vector @ quantized.T) * output_factors).tolist(),
        }
    return {
        "matrix": matrix,
        "quantized": quantized,
        "row_scales": row_scales,
        "output_factors": output_factors,
        "input_scale": input_scale,
        "normalized_vectors": normalized_vectors,
        "vector_kinds": kinds,
        "expected_true": expected_true,
        "expected_quantized": expected_quantized,
        "one_axis": one_axis,
    }


def build_mode(
    mode: str,
    channels: tuple[str, ...],
    shard_width: int,
    quantized: np.ndarray,
    factors: np.ndarray,
    initial: np.ndarray,
) -> tuple[list[tuple[str, int, int, np.ndarray]], dict[str, object]]:
    groups = (WIDTH + len(channels) - 1) // len(channels)
    padded = groups * len(channels)
    weights = np.zeros((padded, WIDTH), dtype=np.int16)
    weights[:WIDTH] = quantized
    padded_factors = np.ones(padded, dtype=np.float64)
    padded_factors[:WIDTH] = factors
    shards = WIDTH // shard_width
    tasks = []
    for group in range(groups):
        rows = weights[group * len(channels):(group + 1) * len(channels)]
        for shard in range(shards):
            start = shard * shard_width
            tasks.append((mode, group, shard, rows[:, start:start + shard_width]))

    faces = []
    font_rules = []
    shared_rules = []
    properties = []
    unit_by_channel = {"ex": "1ex", "cap": "1cap", "ch": "1ch", "ic": "1ic", "lh": "1lh"}
    for shard in range(shards):
        start = shard * shard_width
        settings = ",".join(
            f'"{axis_tag(local)}" calc((var(--v{start + local:03d}) + 1) / 2)'
            for local in range(shard_width)
        )
        shared_rules.append(
            f'.s{shard}{{font-size:{FONT_SIZE}px;line-height:normal;'
            f'font-variation-settings:{settings}}}')
        for channel in range(len(channels)):
            properties.append(
                f'@property --p{shard}{channel}{{syntax:"<number>";inherits:true;initial-value:-99999}}')
    for channel in range(len(channels)):
        properties.append(
            f'@property --o{channel}{{syntax:"<number>";inherits:true;initial-value:-99999}}')

    groups_html = []
    for group in range(groups):
        rows = weights[group * len(channels):(group + 1) * len(channels)]
        sums = []
        for channel in range(len(channels)):
            output = group * len(channels) + channel
            partials = " + ".join(f"var(--p{shard}{channel})" for shard in range(shards))
            sums.append(f"--o{channel}:calc(({partials}) * {padded_factors[output]:.12g})")
        child = (
            f'<output class="result r{group:03d}" data-group="{group}" '
            f'style="{";".join(sums)}">ready</output>'
        )
        for shard in reversed(range(shards)):
            start = shard * shard_width
            stop = start + shard_width
            family = f"F{mode[0]}{group:03d}_{shard}"
            faces.append(
                f'@font-face{{font-family:{family};src:url("{mode}-g{group:03d}-s{shard}.woff") format("woff")}}')
            values = ";".join(
                f'--p{shard}{channel}:calc(({unit_by_channel[channel_name]} / 1px '
                f'* {UNITS_PER_EM} / {FONT_SIZE} - {BASE}) / {DELTA_SCALE} '
                f'+ {-int(rows[channel, start:stop].sum())})'
                for channel, channel_name in enumerate(channels)
            )
            font_rules.append(f'.f{group:03d}_{shard}{{font-family:{family};{values}}}')
            child = f'<div class="s{shard} f{group:03d}_{shard}">{child}</div>'
        groups_html.append(f'<section class="group">{child}</section>')

    root_values = ";".join(
        f"--v{index:03d}:{value:.12g}" for index, value in enumerate(initial))
    html = (
        f'<!doctype html><meta charset="utf-8"><title>{mode} metric real GPT scale</title><style>'
        + "".join(faces) + "".join(properties)
        + f'.root{{{root_values}}}' + "".join(shared_rules) + "".join(font_rules)
        + '.result{font:14px monospace}.group{contain:style}'
        + '</style><main class="root">' + "".join(groups_html) + "</main>"
    )
    (OUT / f"{mode}.html").write_text(html)
    return tasks, {
        "channels": list(channels),
        "groups": groups,
        "shard_width": shard_width,
        "shards_per_group": shards,
        "font_count": len(tasks),
        "html_bytes": len(html.encode()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.woff"):
        stale.unlink()
    fixture = real_fixture()
    all_tasks = []
    modes = {}
    for mode, channels, shard_width in (
        ("five", FIVE_CHANNELS, 128),
        ("four", FOUR_CHANNELS, 256),
    ):
        tasks, metadata = build_mode(
            mode,
            channels,
            shard_width,
            fixture["quantized"],
            fixture["output_factors"],
            fixture["normalized_vectors"][0],
        )
        all_tasks.extend(tasks)
        modes[mode] = metadata

    workers = int(os.environ.get("FIVE_METRIC_BUILD_WORKERS", min(12, os.cpu_count() or 1)))
    sizes = {mode: {"sfnt_bytes": 0, "web_font_bytes": 0} for mode in modes}
    with multiprocessing.Pool(workers) as pool:
        for index, (mode, sfnt_bytes, web_bytes) in enumerate(
            pool.imap_unordered(build_one, all_tasks), 1
        ):
            sizes[mode]["sfnt_bytes"] += sfnt_bytes
            sizes[mode]["web_font_bytes"] += web_bytes
            if index % 100 == 0 or index == len(all_tasks):
                print(f"built {index}/{len(all_tasks)} fonts", flush=True)
    for mode in modes:
        modes[mode].update(sizes[mode])

    quantization_errors = fixture["expected_quantized"] - fixture["expected_true"]
    reference = {
        "matrix": "GPT-2-small h.0.attn.c_proj.weight (transposed to 768 output rows)",
        "tokens": list(TOKEN_IDS),
        "weight_quant_max": WEIGHT_QUANT_MAX,
        "input_scale": fixture["input_scale"],
        "normalized_vectors": fixture["normalized_vectors"].tolist(),
        "vector_kinds": fixture["vector_kinds"],
        "expected_true": fixture["expected_true"].tolist(),
        "expected_quantized": fixture["expected_quantized"].tolist(),
        "one_axis": fixture["one_axis"],
        "weight_quantization_rmse": float(np.sqrt(np.mean(quantization_errors ** 2))),
        "weight_quantization_max_error": float(np.max(np.abs(quantization_errors))),
        "modes": modes,
    }
    (OUT / "reference.json").write_text(json.dumps(reference) + "\n")
    print(json.dumps({
        "weight_quantization_rmse": reference["weight_quantization_rmse"],
        "weight_quantization_max_error": reference["weight_quantization_max_error"],
        "modes": modes,
    }, indent=2))


if __name__ == "__main__":
    main()
