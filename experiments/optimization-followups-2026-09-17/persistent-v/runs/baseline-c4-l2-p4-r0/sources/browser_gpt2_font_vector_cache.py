"""Whole-head native font registers and bilinear-font attention.

Each retained K/V head is one 64-axis font-settings list plus one scale. The
font consumes the list directly: CSS never unpacks 64 separate state variables.
Private per-layer banks are nested; only the selected layer projects readable
aliases to the single attention rendering graph below them.
"""

import json
import re
from pathlib import Path

import build_hybrid_twelve_block as hybrid
import numpy as np
from build_bilinear_projected_kv_qk import CODEPOINT_BASE, build_head_font
from build_gpt2_block_css import UNITS_PER_EM
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
# Versioned assets preserve every previously measured compiled document.
FONT_DIR = ROOT / "experiments/browser-gpt2/font-vector-operators-v2"
HEADS, DIM, WIDTH = 12, 64, 768
# Chromium saturates a single shaped glyph advance near 32768 CSS pixels.
# The dot glyph can approach 60000 design units, so keep its size <=512 px.
QK_SIZE, VALUE_SIZE = 512, 1024


def fonts():
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    path = FONT_DIR / "operators.json"
    if path.exists():
        return json.loads(path.read_text())
    result = {}
    for kind, summed in (("dot", True), ("value", False)):
        scale, base, coefficients = build_head_font(
            head=0,
            query_ranges=np.ones(DIM),
            key_ranges=np.ones(DIM),
            destination=FONT_DIR / f"{kind}.ttf",
            summed_glyph=summed,
        )
        assert len(set(coefficients)) == 1
        result[kind] = {"scale": scale, "base": base, "coefficient": coefficients[0]}
        if kind == "value":
            # All 64 probability coordinates are identical in weighted V.
            # Collapse them to one shared P axis; each region still computes
            # exactly P*K_i. This changes the operator encoding, not the model.
            font = TTFont(FONT_DIR / "value.woff2", recalcTimestamp=False)
            axes = font["fvar"].axes
            probability = axes[0]
            probability.axisTag = "P000"
            font["fvar"].axes = [probability, *axes[1::2]]
            regions = font["HVAR"].table.VarStore.VarRegionList
            for region in regions.Region:
                q_axes = region.VarRegionAxis[::2]
                active = [
                    a
                    for a in q_axes
                    if (a.StartCoord, a.PeakCoord, a.EndCoord) != (0, 0, 0)
                ]
                if len(active) != 1:
                    raise ValueError("Expected exactly one Q axis per bilinear region")
                region.VarRegionAxis = [active[0], *region.VarRegionAxis[1::2]]
            regions.RegionAxisCount = DIM + 1
            buildStatTable(
                font,
                [
                    {"tag": a.axisTag, "name": a.axisNameID, "ordering": i}
                    for i, a in enumerate(font["fvar"].axes)
                ],
            )
            font.flavor = None
            font.save(FONT_DIR / "value.ttf")
            font.flavor = "woff2"
            font.save(FONT_DIR / "value.woff2")
            result[kind]["axes"] = DIM + 1
    path.write_text(json.dumps(result, indent=2))
    return result


def storage_names(capacity):
    return [
        f"--fc-{kind}-{slot}-{head}"
        for slot in range(capacity)
        for head in range(HEADS)
        for kind in ("k", "v", "ks", "vs")
    ]


def cache_slot(position, capacity, sinks=0):
    """Zero-based absolute position to native ring slot (diagnostics/compiler)."""
    return (
        position
        if position < sinks
        else sinks + (position - sinks) % (capacity - sinks)
    )


def value_axis(slot, coordinate):
    """Private four-byte tags for one fallback font's retained V axes."""
    return f"V{slot * DIM + coordinate:03X}"


def fallback_value_fonts(capacity):
    """Same bilinear operator, disjoint character coverage and V/P axis tags."""
    if not 1 <= capacity <= 64:
        raise ValueError("Fallback value packing currently supports 1–64 slots")
    paths = []
    directory = FONT_DIR / "fallback"
    directory.mkdir(parents=True, exist_ok=True)
    for slot in range(capacity):
        path = directory / f"value-{slot}.woff2"
        if not path.exists():
            font = TTFont(FONT_DIR / "value.woff2", recalcTimestamp=False)
            font["fvar"].axes[0].axisTag = f"P{slot:03X}"
            for i, axis in enumerate(font["fvar"].axes[1:]):
                axis.axisTag = value_axis(slot, i)
            for table in font["cmap"].tables:
                if table.isUnicode():
                    table.cmap = {
                        code + slot * DIM: glyph for code, glyph in table.cmap.items()
                    }
            for name_id in (1, 3, 4, 6):
                font["name"].setName(f"FvsValueSlot{slot}", name_id, 3, 1, 0x409)
            buildStatTable(
                font,
                [
                    {"tag": a.axisTag, "name": a.axisNameID, "ordering": i}
                    for i, a in enumerate(font["fvar"].axes)
                ],
            )
            font.save(path)
        paths.append(path)
    return paths


def attention(
    capacity,
    blocks,
    context_carrier,
    write_epoch="--epoch",
    kv_window=None,
    kv_sinks=0,
    value_layout="runs",
    prewarm_values=False,
):
    positions = capacity
    capacity = capacity if kv_window is None else kv_window
    if not 1 <= capacity <= positions or not 0 <= kv_sinks < capacity:
        raise ValueError("Require 1 <= KV window <= positions and 0 <= sinks < window")
    if value_layout not in ("runs", "fallback", "widths"):
        raise ValueError("Unknown value layout")
    if prewarm_values and value_layout != "widths":
        raise ValueError("Early value preparation requires fixed font widths")
    operators = fonts()
    zero = ",".join(f'"K{i:03d}" 0' for i in range(DIM))
    all_fields = storage_names(capacity)
    css = ""
    for alias, inherits in (("fc", "false"), ("fr", "true")):
        for slot in range(capacity):
            for head in range(HEADS):
                for kind in ("k", "v", "ks", "vs"):
                    vector = kind in ("k", "v")
                    css += f'@property --{alias}-{kind}-{slot}-{head}{{syntax:"{"*" if vector else "<number>"}";inherits:{inherits};initial-value:{zero if vector else "0"}}}'
    css += hybrid.regs([f"--fqs-{h}" for h in range(HEADS)] + ["--fvs-write-slot"])
    css += (
        ".fvs-query{container-name:fvscache;--fvs-write-slot:calc(min("
        f"var({write_epoch}) - 1,{kv_sinks} + mod(max(0,var({write_epoch}) - 1 - {kv_sinks}),{capacity - kv_sinks})))}}"
    )
    css += (
        ".fvs-query{--fvs-all-fields:"
        + ",".join(all_fields)
        + "}.fvs-bank{transition-property:var(--fvs-all-fields);transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
    )
    for head in range(HEADS):
        maximum = ",".join(f"abs(var(--qkv-{head * DIM + i:03d}))" for i in range(DIM))
        css += f".fvs-query{{--fqs-{head}:max(.000001,{maximum})}}"
        query = ",".join(
            f'"Q{i:03d}" calc(var(--qkv-{head * DIM + i:03d}) / var(--fqs-{head}))'
            for i in range(DIM)
        )
        css += f".fvs-query{{--fvs-query-{head}:{query}}}"
        for kind, offset in (("k", WIDTH), ("v", 2 * WIDTH)):
            scale = f"--fvs-live-{kind}s-{head}"
            maximum = ",".join(
                f"abs(var(--qkv-{offset + head * DIM + i:03d}))" for i in range(DIM)
            )

            def settings_for(slot=None, offset=offset, head=head, scale=scale):
                return ",".join(
                    f'"{value_axis(slot, i) if slot is not None else f"K{i:03d}"}" calc(var(--qkv-{offset + head * DIM + i:03d}) / var({scale}))'
                    for i in range(DIM)
                )

            if kind == "v" and value_layout == "fallback":
                settings = (
                    "if("
                    + ";".join(
                        f"style(--fvs-write-slot:{slot}):{settings_for(slot)}"
                        for slot in range(capacity)
                    )
                    + f";else:{settings_for(0)})"
                )
            else:
                settings = settings_for()
            css += hybrid.regs([scale])
            css += f".fvs-query{{{scale}:max(.000001,{maximum});--fvs-live-{kind}-{head}:{settings}}}"
    for slot in range(capacity):
        fields = {
            f"--fc-{kind}-{slot}-{head}"
            for head in range(HEADS)
            for kind in ("k", "v", "ks", "vs")
        }
        retained = ",".join(name for name in all_fields if name not in fields) or "none"
        css += f".fvs-query{{--fvs-retained-{slot}:{retained}}}"
        writes = []
        for head in range(HEADS):
            for kind in ("k", "v", "ks", "vs"):
                writes.append(
                    f"--fc-{kind}-{slot}-{head}:var(--fvs-live-{kind}-{head})"
                )
        for layer in range(blocks):
            css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{transition-property:var(--fvs-retained-{slot});{';'.join(writes)}}}}}}}"
    for layer in range(blocks):
        aliases = ";".join(
            f"{name.replace('--fc-', '--fr-')}:var({name})" for name in all_fields
        )
        css += f"@container runtime style(--layer:{layer}){{.fvs-bank-{layer}{{{aliases}}}}}"
    for kind, family in (("dot", "FvsDot"), ("value", "FvsValue")):
        css += f'@font-face{{font-family:{family};src:url("{(FONT_DIR / (kind + ".woff2")).as_uri()}")}}'
    if value_layout == "fallback":
        for slot, path in enumerate(fallback_value_fonts(capacity)):
            start = CODEPOINT_BASE + slot * DIM
            css += f'@font-face{{font-family:FvsValueSlot{slot};src:url("{path.as_uri()}");unicode-range:U+{start:X}-{start + DIM - 1:X}}}'
    dot = operators["dot"]
    unit = QK_SIZE / UNITS_PER_EM
    score_fields = [f"--fs-{h}-{s}" for h in range(HEADS) for s in range(capacity)]
    progress_fields = [f"--fsp-{h}-{s}" for h in range(HEADS) for s in range(capacity)]
    css += hybrid.regs(
        score_fields + progress_fields + ["--fss", "--fvs-score-ready"]
    ).replace("inherits:true", "inherits:false")
    metrics, timelines, animations, reads = [], [], [], []
    for head in range(HEADS):
        for slot in range(capacity):
            name, timeline = f"fvs-score-{head}-{slot}", f"--fvs-score-{head}-{slot}"
            progress = f"--fsp-{head}-{slot}"
            timelines.append(timeline)
            animations.append(name)
            css += f"@keyframes {name}{{from{{{progress}:-2}}to{{{progress}:1}}}}"
            css += (
                f".{name}{{font:{QK_SIZE}px FvsDot;line-height:1;font-kerning:none;font-variation-settings:var(--fr-k-{slot}-{head}),var(--fvs-query-{head});"
                f"width:calc-size(max-content,calc(262144px + (size - {dot['base'] * unit:.12g}px) * var(--fqs-{head}) * var(--fr-ks-{slot}-{head}) * {128 / (8 * dot['coefficient'] * unit):.12g}))}}"
            )
            metrics.append(
                f'<i class="metric {name}" style="view-timeline:{timeline} inline">&#x{CODEPOINT_BASE:X};</i>'
            )
            reads.append(
                f"--fs-{head}-{slot}:calc((1572864 / (var({progress}) + 2) - 786432) / 128)"
            )
    metrics.append(
        '<i class="metric" style="width:calc(262144px + var(--epoch)*1024px);view-timeline:--fvs-score-stamp inline"></i>'
    )
    score_source = (
        '<div class="scroller fvs-score-source"><div class="track">'
        + "".join(metrics)
        + "</div></div>"
    )
    css += ".fvs-score-source{width:524288px}.fvs-score-source>.track{width:1572864px}"
    css += (
        ".fvs-score-reader{animation-name:"
        + ",".join(animations)
        + ";animation-duration:1s;animation-fill-mode:both;animation-timing-function:linear;animation-timeline:"
        + ",".join(timelines)
        + ";"
        + ";".join(reads)
        + "}"
        "@keyframes fvs-score-stamp{from{--fss:0}to{--fss:1}}"
        ".fvs-score-receipt{container-name:fvsscore;animation:fvs-score-stamp 1s linear both;animation-timeline:--fvs-score-stamp;"
        "--fvs-score-ready:calc(1 - min(1,abs(round(nearest,(524288 / var(--fss) - 786432) / 1024,1) - var(--epoch))))}"
        ".fvs-score-gate{content-visibility:hidden;contain-intrinsic-size:0px 0px}@container fvsscore style(--fvs-score-ready:1){.fvs-score-gate{content-visibility:visible}}"
    )
    soft = []
    soft_fields = []
    for head in range(HEADS):
        maximum, denominator, bases = f"--fm-{head}", f"--fd-{head}", f"--fb-{head}"
        soft_fields += [maximum, denominator, bases]
        valid_scores = ",".join(
            f"if(style(--fv-{slot}:1):var(--fs-{head}-{slot});else:-1000000)"
            for slot in range(capacity)
        )
        soft.append(f"{maximum}:max({valid_scores})")
        for slot in range(capacity):
            exponent = f"--fe-{head}-{slot}"
            soft_fields.append(exponent)
            soft.append(
                f"{exponent}:if(style(--fv-{slot}:1):exp(calc(var(--fs-{head}-{slot}) - var({maximum})));else:0)"
            )
        soft.append(
            f"{denominator}:calc({' + '.join(f'var(--fe-{head}-{slot})' for slot in range(capacity))})"
        )
        soft.append(
            f"{bases}:max(.000001,{','.join(f'var(--fr-vs-{slot}-{head})' for slot in range(capacity))})"
        )
    css += hybrid.regs(soft_fields)
    css += hybrid.regs([f"--fv-{slot}" for slot in range(capacity)]).replace(
        "inherits:true", "inherits:false"
    )
    css += (
        ".fvs-score-reader{"
        + ";".join(
            f"--fv-{slot}:clamp(0,sign(var({write_epoch}) - {slot + 1}) + 1,1)"
            for slot in range(capacity)
        )
        + "}"
    )
    # Scores and their animated progress are local scratch. Resolve softmax
    # on the same element so these arrays need not inherit into every V glyph.
    css += ".fvs-score-reader{" + ";".join(soft) + "}"
    value = operators["value"]
    value_unit = VALUE_SIZE / UNITS_PER_EM
    for head in range(HEADS):
        combined_settings = []
        for slot in range(capacity):
            exponent = f"--fe-{head}-{slot}"
            # Keep every font at a fixed, safe pixel size. Fold each stored V
            # scale into the <=1 probability axis, then restore the common
            # maximum scale after native inline width summation. Large neural
            # activations therefore cannot saturate individual glyph advances.
            weight = (
                f"calc(var({exponent}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
            )
            settings = f'"P000" {weight}'
            if value_layout == "fallback":
                combined_settings.append(
                    f'var(--fr-v-{slot}-{head}),"P{slot:03X}" {weight}'
                )
            else:
                width_rule = ""
                if value_layout == "widths":
                    # Keep the V font location unchanged as queries change.
                    # Weight its already-shaped width, not its variation axes.
                    # The positive base keeps every flex-item width nonnegative.
                    settings = '"P000" 1'
                    base_pixels = value["base"] * value_unit
                    width_rule = f"width:calc-size(max-content,calc({base_pixels:.12g}px + (size - {base_pixels:.12g}px) * {weight}));min-width:0;"
                css += f".fvs-v-{head}-{slot}{{font-family:FvsValue;font-size:{VALUE_SIZE}px;font-variation-settings:var(--fr-v-{slot}-{head}),{settings};font-kerning:none;font-style:normal;display:block;white-space:pre;flex:none}}"
                if width_rule:
                    css += f".fvs-v-{head}-{slot}{{{width_rule}}}"
        if value_layout == "fallback":
            families = ",".join(f"FvsValueSlot{slot}" for slot in range(capacity))
            css += f".fvs-value-head-{head}{{display:contents;font:{VALUE_SIZE}px {families};font-variation-settings:{','.join(combined_settings)};font-kerning:none}}"
    pattern = r'<i class="metric" style="width:calc\(262144px \+ var\(--(?:ctx|out)-(\d+)\) \* 128px\);view-timeline:([^ ]+) inline"></i>'

    def row(match):
        coordinate, timeline = int(match[1]), match[2]
        head, local = divmod(coordinate, DIM)
        dimensions = f"calc-size(max-content,calc(262144px + (size - {capacity * value['base'] * value_unit:.12g}px) * var(--fb-{head}) / var(--fd-{head}) * {128 / (value['coefficient'] * value_unit):.12g}))"
        if value_layout == "fallback":
            runs = "".join(
                f"&#x{CODEPOINT_BASE + slot * DIM + local:X};"
                for slot in range(capacity)
            )
            prefix = f'<div class="fvs-value-head-{head}">' if local == 0 else ""
            suffix = "</div>" if local == DIM - 1 else ""
            return f'{prefix}<span class="metric fvs-value-row" style="width:{dimensions};view-timeline:{timeline} inline">{runs}</span>{suffix}'
        runs = "".join(
            f'<i class="fvs-v-{head}-{slot}">&#x{CODEPOINT_BASE + local:X};</i>'
            for slot in range(capacity)
        )
        return f'<span class="metric fvs-value-row" style="width:{dimensions};view-timeline:{timeline} inline">{runs}</span>'

    value_source, count = re.subn(pattern, row, context_carrier)
    if count != WIDTH:
        raise ValueError(f"Expected 768 native context carriers, found {count}")
    if prewarm_values:
        # Let fixed V fonts shape before attention scores are ready. Keep the
        # output generation marker blocked, so speculative geometry cannot
        # release a downstream operator before the new weights are available.
        if value_source.count("var(--epoch)") != 1:
            raise ValueError("Expected one context generation marker")
        value_source = value_source.replace(
            "var(--epoch)", "var(--fvs-value-epoch)"
        )
        css += (
            ".fvs-score-gate{content-visibility:visible;--fvs-value-epoch:0}"
            "@container fvsscore style(--fvs-score-ready:1){"
            ".fvs-score-gate{--fvs-value-epoch:var(--epoch)}}"
        )
    css += (
        ".fvs-value-row{display:block;white-space:pre;font-style:normal;line-height:1}"
        if value_layout == "fallback"
        else ".fvs-value-row{display:inline-flex;gap:0;font:0px monospace;line-height:1}"
    )
    body = (
        score_source
        + '<div class="fvs-score-reader"><div class="fvs-score-receipt"><div class="fvs-score-gate"><div class="fvs-softmax">'
        + value_source
        + "</div></div></div></div>"
    )
    for layer in reversed(range(blocks)):
        body = (
            f'<div class="fvs-bank fvs-bank-{layer}" data-layer="{layer}">'
            + body
            + "</div>"
        )
    body = '<div class="fvs-query">' + body + "</div>"
    css += "html{timeline-scope:" + ",".join(timelines + ["--fvs-score-stamp"]) + "}"
    return (
        body,
        css,
        {
            "cacheFieldsPerLayer": len(all_fields),
            "fontVectorWidth": DIM,
            "kvSlots": capacity,
            "kvSinks": kv_sinks,
            "valueLayout": value_layout,
            "prewarmValues": prewarm_values,
            "attentionMask": "full causal"
            if capacity == positions
            else "initial sinks plus rolling recent context",
            "operators": operators,
        },
    )
