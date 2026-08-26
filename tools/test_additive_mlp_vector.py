#!/usr/bin/env python3
"""Verify the packed fallback-run GPT-2 MLP projection artifacts."""

from __future__ import annotations

import json
import re

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer

from build_additive_mlp_vector import (
    FIXED_FC_TRANSPORT_PATH,
    FONT_SIZE,
    MLP_WIDTH,
    OUT,
    PACKED_CSS_PATH,
    PACKED_HTML_PATH,
    PACKED_REFERENCE_PATH,
    PAIRED_FC_CSS_PATH,
    PAIRED_FC_TRANSPORT_PATH,
    PAIRED_HTML_PATH,
    SCALING_REFERENCE_PATH,
    SHARD,
    UNITS_PER_EM,
    WIDTH,
)
from build_gpt2_block_css import global_axis_tag


def main() -> None:
    page = PACKED_HTML_PATH.read_text()
    css = PACKED_CSS_PATH.read_text()
    reference = json.loads(PACKED_REFERENCE_PATH.read_text())

    assert "<script" not in page.lower()
    assert page.count('class="combined"') == WIDTH
    runs = re.findall(r'<i class="combined"[^>]*>(.*?)</i>', page)
    assert len(runs) == WIDTH
    assert all(run.count("&#x") == MLP_WIDTH // SHARD for run in runs)
    assert "anchor-size(" not in css
    assert reference["projection_elements"] == WIDTH
    assert reference["projection_glyphs"] == WIDTH * (MLP_WIDTH // SHARD)

    tags = [global_axis_tag(index) for index in range(MLP_WIDTH)]
    assert len(tags) == len(set(tags)) == MLP_WIDTH
    assert all(len(tag) == 4 for tag in tags)
    assert all(f'"{tag}" var(--h{index})' in css for index, tag in enumerate(tags))

    normalized_hidden = (
        np.asarray(reference["hidden"], dtype=np.float64)
        / float(reference["hidden_range"])
    )
    actual_units = np.zeros(WIDTH, dtype=np.float64)
    for shard, start in enumerate(range(0, MLP_WIDTH, SHARD)):
        font = TTFont(OUT / f"mlp-proj-run-s{shard}.woff2")
        axes = font["fvar"].axes
        assert axes[0].axisTag == global_axis_tag(start)
        assert axes[-1].axisTag == global_axis_tag(start + SHARD - 1)
        location = {
            global_axis_tag(index): float(normalized_hidden[index])
            for index in range(start, start + SHARD)
        }
        instancer = VarStoreInstancer(font["HVAR"].table.VarStore, axes, location)
        cmap = font.getBestCmap()
        codepoint_start = 0xF0000 + shard * WIDTH
        for output in range(WIDTH):
            glyph = cmap[codepoint_start + output]
            glyph_id = font.getGlyphID(glyph)
            base = font["hmtx"].metrics[glyph][0]
            actual_units[output] += base + instancer[glyph_id]

    expected_units = (
        np.asarray(reference["expected_widths"], dtype=np.float64)
        * UNITS_PER_EM
        / FONT_SIZE
    )
    maximum_unit_error = float(np.max(np.abs(actual_units - expected_units)))
    assert maximum_unit_error < 0.01

    scaling = json.loads(SCALING_REFERENCE_PATH.read_text())
    by_name = {case["name"]: case for case in scaling["cases"]}
    assert set(by_name) == {
        "fixed-fc-transport",
        "paired-fc-transport",
        "paired-live-12",
        "transport-only",
        "fixed-12",
        "live-1",
        "live-2",
        "live-4",
        "live-8",
        "live-12",
    }
    for name, case in by_name.items():
        variant = (OUT / case["path"]).read_text()
        assert "<script" not in variant.lower()
        transport_cases = {"transport-only", "fixed-fc-transport", "paired-fc-transport"}
        assert variant.count('class="combined"') == (0 if name in transport_cases else WIDTH)
        if name.startswith("live-"):
            shard_count = int(name.removeprefix("live-"))
            assert variant.count("&#x") == MLP_WIDTH * 3 + WIDTH * shard_count
    assert "font-variation-settings:normal" in (
        OUT / by_name["fixed-12"]["path"]
    ).read_text()
    fixed_fc_page = FIXED_FC_TRANSPORT_PATH.read_text()
    assert "<script" not in fixed_fc_page.lower()
    assert fixed_fc_page.count('class="fc-metric"') == MLP_WIDTH
    assert fixed_fc_page.count("view-timeline:") == MLP_WIDTH
    paired_page = PAIRED_FC_TRANSPORT_PATH.read_text()
    paired_css = PAIRED_FC_CSS_PATH.read_text()
    assert "<script" not in paired_page.lower()
    assert paired_page.count('class="pair"') == MLP_WIDTH // 2
    assert paired_page.count('class="subject"') == MLP_WIDTH // 2
    assert paired_css.count("@keyframes ") == MLP_WIDTH // 2
    assert paired_css.count("entry 100%") == MLP_WIDTH // 2
    paired_full_page = PAIRED_HTML_PATH.read_text()
    assert "<script" not in paired_full_page.lower()
    assert paired_full_page.count('class="combined"') == WIDTH
    print(
        {
            "projection_elements": WIDTH,
            "projection_glyphs": WIDTH * (MLP_WIDTH // SHARD),
            "unique_axis_values": MLP_WIDTH,
            "maximum_font_unit_error": maximum_unit_error,
            "no_javascript": True,
        }
    )


if __name__ == "__main__":
    main()
