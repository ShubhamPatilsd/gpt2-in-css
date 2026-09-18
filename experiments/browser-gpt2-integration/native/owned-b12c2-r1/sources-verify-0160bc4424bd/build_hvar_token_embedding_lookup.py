#!/usr/bin/env python3
"""Build a two-axis HVAR lookup for all TinyStories token embeddings."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

import build_output_head_benchmark as output_head
from build_matrix_backend_prototypes import build_master


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "hvar-token-embedding-lookup"
FONT_PATH = OUTPUT / "embedding-lookup.ttf"
GROUP_SIZE = 256
BASE_ADVANCE = 20_000
EMBEDDING_SCALE = 4_096
FONT_SIZE = 1_000
CODEPOINT_START = 0xE000
AXES = (("GRUP", "Token group"), ("LOCL", "Local token"))


def add_axis(font: TTFont, tag: str, name: str, maximum: int) -> Axis:
    axis = Axis()
    axis.axisTag = tag
    # Keep every real lookup coordinate away from normalized zero. In an
    # OpenType variation region, a peak of zero means the axis does not
    # participate, which would make all group-0 or local-0 rows overlap.
    axis.minValue = -1
    axis.defaultValue = -1
    axis.maxValue = maximum
    axis.flags = 0
    axis.axisNameID = font["name"].addName(name)
    return axis


def support(position: int, maximum: int) -> tuple[float, float, float]:
    if maximum == 0:
        return (0, 0, 0)
    center = (position + 1) / (maximum + 1)
    half_step = 0.45 / (maximum + 1)
    return (max(0, center - half_step), center, min(1, center + half_step))


def build_font(embeddings: np.ndarray) -> None:
    vocabulary, width = embeddings.shape
    groups = math.ceil(vocabulary / GROUP_SIZE)
    build_master(
        FONT_PATH,
        np.full(width, BASE_ADVANCE, dtype=np.int32),
        "EmbeddingLookup",
        codepoint_start=CODEPOINT_START,
    )
    font = TTFont(FONT_PATH, recalcTimestamp=False)
    fvar = newTable("fvar")
    fvar.axes = [
        add_axis(font, "GRUP", "Token group", groups - 1),
        add_axis(font, "LOCL", "Local token", GROUP_SIZE - 1),
    ]
    fvar.instances = []
    font["fvar"] = fvar
    buildStatTable(
        font,
        [
            {"tag": tag, "name": axis.axisNameID, "ordering": index}
            for index, (tag, _name) in enumerate(AXES)
            for axis in [fvar.axes[index]]
        ],
    )

    supports = [
        {
            "GRUP": support(token // GROUP_SIZE, groups - 1),
            "LOCL": support(token % GROUP_SIZE, GROUP_SIZE - 1),
        }
        for token in range(vocabulary)
    ]
    region_list = buildVarRegionList(supports, ["GRUP", "LOCL"])
    deltas = np.rint(embeddings.T * EMBEDDING_SCALE).astype(np.int16)
    items = [[0] * vocabulary, *deltas.astype(int).tolist()]
    var_data = buildVarData(range(vocabulary), items, optimize=True)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(region_list, [var_data])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {glyph: [] for glyph in font.getGlyphOrder()}
    font["gvar"] = gvar
    font.recalcTimestamp = False
    font.save(FONT_PATH)
    compressed = TTFont(FONT_PATH, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(FONT_PATH.with_suffix(".woff2"))


def render_html(tokens: list[int], expected: np.ndarray) -> str:
    controls = "".join(
        f'<input type="radio" name="token" id="t{index}"{(" checked" if index == 0 else "")}>'
        for index in range(len(tokens))
    )
    selectors = "".join(
        f"body:has(#t{index}:checked) .bank{{--group:{token // GROUP_SIZE};"
        f"--local:{token % GROUP_SIZE}}}"
        for index, token in enumerate(tokens)
    )
    metrics = "".join(
        f'<i class="metric" style="grid-column:{dimension + 1}">'
        f'&#x{CODEPOINT_START + dimension:X};</i>'
        for dimension in range(expected.shape[1])
    )
    cells = "".join(
        f'<i class="cell" data-dimension="{dimension}" style="grid-column:{dimension + 1}">'
        '<b class="consumer"></b></i>'
        for dimension in range(expected.shape[1])
    )
    return f"""<!doctype html><meta charset="utf-8">
<title>HVAR token embedding lookup</title>
<style>
@font-face{{font-family:EmbeddingLookup;src:url("embedding-lookup.woff2") format("woff2")}}
@property --value{{syntax:"<number>";inherits:true;initial-value:-999}}
{selectors}
html,body{{margin:0;overflow:clip}}
.bank{{--group:0;--local:0;position:fixed;inset:0 auto auto 0;display:grid;
grid-template-columns:repeat({expected.shape[1]},max-content);grid-template-rows:1px 1px;
width:max-content;height:2px;font-family:EmbeddingLookup;font-size:{FONT_SIZE}px;
font-variation-settings:"GRUP" var(--group),"LOCL" var(--local);
font-kerning:none;line-height:1}}
.metric{{grid-row:1;display:block;height:1px;overflow:hidden;white-space:pre;font-style:normal}}
.transport{{display:grid;grid-template-columns:subgrid;grid-column:1/-1;grid-row:2}}
.cell{{container-type:inline-size;position:relative;height:1px;min-width:0;font-style:normal}}
.consumer{{--value:calc((100cqi / 1px - {BASE_ADVANCE}) / {EMBEDDING_SCALE});
position:absolute;width:calc((var(--value) + 2) * 100px);height:1px}}
</style>
{controls}<main id="bank" class="bank">{metrics}<div class="transport">{cells}</div></main>
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    state = output_head.load_torch_zip(output_head.download_checkpoint())
    embeddings = state["transformer.wte.weight"].astype(np.float64)
    build_font(embeddings)
    tokens = [11, 373, 0, 1, 255, 256, 50256, 612, 257, 15899, 42, 4096, 9999, 20000, 30000, 40000]
    expected = embeddings[tokens]
    (OUTPUT / "index.html").write_text(render_html(tokens, expected))
    quantized = np.rint(expected * EMBEDDING_SCALE) / EMBEDDING_SCALE
    reference = {
        "model": "calum/tinystories-gpt2-3M",
        "vocabulary": len(embeddings),
        "width": embeddings.shape[1],
        "groupSize": GROUP_SIZE,
        "tokens": tokens,
        "expected": expected.tolist(),
        "quantized": quantized.tolist(),
        "embeddingScale": EMBEDDING_SCALE,
        "quantizationRmse": float(np.sqrt(np.mean((quantized - expected) ** 2))),
        "fontBytes": FONT_PATH.with_suffix(".woff2").stat().st_size,
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference) + "\n")
    print({key: reference[key] for key in (
        "vocabulary", "width", "quantizationRmse", "fontBytes", "htmlBytes"
    )})


if __name__ == "__main__":
    main()
