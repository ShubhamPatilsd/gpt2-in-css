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
import f4_packing as f4
import f5_scoping as f5
import r4d_flags as r4d
import r4w_precat as r4w
import r2c_hoist as r2c
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
    if f4.PACKED_BANKS:
        # F4: one 768-axis list per vector kind (12 heads on disjoint tags) and
        # the 24 per-head scales: 26 latched fields per slot instead of 48.
        names = []
        for slot in range(capacity):
            names += [f"--fc-k-{slot}"]
            if r4d.UNPACK_V:
                # R4D: 12 per-head 64-axis V lists (each V glyph parses 65 axes
                # instead of 769); the K list stays packed (12 score glyphs/slot).
                names += [f"--fc-v-{slot}-{head}" for head in range(HEADS)]
            else:
                names += [f"--fc-v-{slot}"]
            names += [
                f"--fc-{kind}-{slot}-{head}"
                for head in range(HEADS)
                for kind in ("ks", "vs")
            ]
        return names
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
    value_weight_once=True,
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
    packed = f4.PACKED_BANKS
    if packed and value_layout not in ("runs", "widths"):
        # R4D: the widths layout (fixed V font location, weight applied to the
        # shaped width) uses the same per-slot lists and leaf structure as runs.
        raise ValueError("F4 packed banks are implemented for the runs/widths value layouts only")
    # R4W: V-leaf allocation fix (see r4w_precat.py); only defined for the widths
    # layout with F4 packed banks and R4D per-head V lists.
    precat = r4w.mode() if (value_layout == "widths" and packed and r4d.UNPACK_V) else "off"
    wrapper_v, alias_v = precat == "wrapper", precat == "alias"
    if wrapper_v and not value_weight_once:
        raise ValueError("R4W_V_PRECAT=wrapper requires the slim (weight-once) V leaves")
    zero = ",".join(f'"K{i:03d}" 0' for i in range(DIM))
    all_fields = storage_names(capacity)
    css = ""
    for alias, inherits in (("fc", "false"), ("fr", "true")):
        for name in all_fields:
            kind = f4.kind_of(name)
            vector = kind in ("k", "v")
            initial = (f4.zero_list(kind) if packed else zero) if vector else "0"
            if vector and packed and r4d.head_of(name) is not None:
                initial = ",".join(
                    f'"{f4.head_axis(kind, r4d.head_of(name), i)}" 0' for i in range(DIM)
                )
                if wrapper_v:
                    # R4W: per-slot tags (one font per slot, see r4w_precat.py).
                    initial = ",".join(f'"{value_axis(f4.slot_of(name), i)}" 0' for i in range(DIM))
            if vector and r4d.EMPTY_UNFILLED:
                # R4D: one explicit zero axis (fvar defaults are 0) instead of
                # every axis at zero: unfilled slots substitute 12 B, not ~7.7 KB.
                head = r4d.head_of(name)
                initial = f'"{f4.head_axis(kind, 0 if head is None else head, 0) if packed else "K000"}" 0'
                if wrapper_v and head is not None:
                    initial = f'"{value_axis(f4.slot_of(name), 0)}" 0'
            css += f'@property {name.replace("--fc-", f"--{alias}-")}{{syntax:"{"*" if vector else "<number>"}";inherits:{inherits};initial-value:{initial}}}'
    css += hybrid.regs([f"--fqs-{h}" for h in range(HEADS)] + ["--fvs-write-slot"])
    css += (
        ".fvs-query{container-name:fvscache;--fvs-write-slot:calc(min("
        f"var({write_epoch}) - 1,{kv_sinks} + mod(max(0,var({write_epoch}) - 1 - {kv_sinks}),{capacity - kv_sinks})))}}"
    )
    literal = f5.BANK_LITERAL_LISTS
    css += (
        ".fvs-query{--fvs-all-fields:"
        + ",".join(all_fields)
        + "}.fvs-bank{transition-property:"
        + (",".join(all_fields) if literal else "var(--fvs-all-fields)")
        + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
    )
    sequential = kv_window is None or (kv_sinks == 0 and capacity == positions)
    lean = r4d.LEAN_LATCH and sequential
    if lean:
        # R4D: with a full causal window slots fill in order; at write-slot W only
        # slots 0..W can hold a value (W in the banks of layers already written
        # this token), so only their fields need a retaining transition-property
        # entry. Slots > W have no running transition, so unlisting them cancels
        # nothing. The full-list base rule above stays for the no-match state.
        for write_slot in range(capacity):
            listed = ",".join(n for n in all_fields if f4.slot_of(n) <= write_slot)
            if not literal:
                css += f".fvs-query{{--fvs-base-{write_slot}:{listed}}}"
            css += (
                f"@container fvscache style(--fvs-write-slot:{write_slot}){{.fvs-bank{{transition-property:"
                + (listed if literal else f"var(--fvs-base-{write_slot})")
                + "}}"
            )
    for head in range(HEADS):
        maximum = ",".join(f"abs(var(--qkv-{head * DIM + i:03d}))" for i in range(DIM))
        css += f".fvs-query{{--fqs-{head}:max(.000001,{maximum})}}"
        query = ",".join(
            f'"Q{i:03d}" calc(var(--qkv-{head * DIM + i:03d}) / var(--fqs-{head}))'
            for i in range(DIM)
        )
        if r2c.HOIST_QUERY:
            # R2C: every score glyph of this head (one per slot) re-parsed these 64
            # calc()s; evaluate them once here as typed numbers (F4's --fvn pattern).
            query, pairs = r2c.hoist_settings(
                query, lambda _src, i, head=head: f"--fq-q-{head}-{i}"
            )
            css += r2c.private_regs(name for name, _ in pairs)
            css += ".fvs-query{" + r2c.declarations(pairs) + "}"
        css += f".fvs-query{{--fvs-query-{head}:{query}}}"
        for kind, offset in (("k", WIDTH), ("v", 2 * WIDTH)):
            scale = f"--fvs-live-{kind}s-{head}"
            maximum = ",".join(
                f"abs(var(--qkv-{offset + head * DIM + i:03d}))" for i in range(DIM)
            )

            def entry(i, offset=offset, head=head, scale=scale, kind=kind):
                quotient = f"calc(var(--qkv-{offset + head * DIM + i:03d}) / var({scale}))"
                if f4.NUMERIC_LISTS:
                    # F4: evaluate once as a typed number on this element; the
                    # list then latches ~15 B per axis instead of a ~45 B calc().
                    return f"var(--fvn-{kind}-{head}-{i})"
                return quotient

            if f4.NUMERIC_LISTS:
                numeric = [f"--fvn-{kind}-{head}-{i}" for i in range(DIM)]
                css += "".join(
                    f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}'
                    for p in numeric
                )
                css += ".fvs-query{" + ";".join(
                    f"{p}:calc(var(--qkv-{offset + head * DIM + i:03d}) / var({scale}))"
                    for i, p in enumerate(numeric)
                ) + "}"

            def settings_for(slot=None, offset=offset, head=head, scale=scale, kind=kind):
                def tag(i):
                    if slot is not None:
                        return value_axis(slot, i)
                    if packed:
                        return f4.head_axis(kind, head, i)
                    return f"K{i:03d}"

                return ",".join(f'"{tag(i)}" {entry(i)}' for i in range(DIM))

            if kind == "v" and wrapper_v and r4w.LIVE_V == "lists":
                # R4W fallback form: one slot-tagged live list per (head, slot);
                # the write rule for slot S references --fvs-live-v-H-S.
                css += ".fvs-query{" + ";".join(
                    f"--fvs-live-v-{head}-{slot}:{settings_for(slot)}" for slot in range(capacity)
                ) + "}"
                settings = settings_for(0)
            elif kind == "v" and (value_layout == "fallback" or wrapper_v):
                # (R4W wrapper: the latched list must carry the write slot's tags.)
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
        fields = {name for name in all_fields if f4.slot_of(name) == slot}
        retained = ",".join(
            name for name in all_fields
            if name not in fields and (not lean or f4.slot_of(name) < slot)
        ) or "none"
        css += f".fvs-query{{--fvs-retained-{slot}:{retained}}}"
        writes = []
        if packed:
            # F4: the 12 live head lists concatenate into one latched list per kind.
            for kind in ("k", "v"):
                if kind == "v" and r4d.UNPACK_V:
                    # R4W alias: latch the COMPLETE leaf value (list + P000) once.
                    suffix = ',"P000" 1' if alias_v else ""
                    live_slot = f"-{slot}" if (wrapper_v and r4w.LIVE_V == "lists") else ""
                    writes += [
                        f"--fc-v-{slot}-{head}:var(--fvs-live-v-{head}{live_slot}){suffix}"
                        for head in range(HEADS)
                    ]
                    continue
                writes.append(
                    f"--fc-{kind}-{slot}:"
                    + ",".join(f"var(--fvs-live-{kind}-{head})" for head in range(HEADS))
                )
            for head in range(HEADS):
                for kind in ("ks", "vs"):
                    writes.append(
                        f"--fc-{kind}-{slot}-{head}:var(--fvs-live-{kind}-{head})"
                    )
        else:
            for head in range(HEADS):
                for kind in ("k", "v", "ks", "vs"):
                    writes.append(
                        f"--fc-{kind}-{slot}-{head}:var(--fvs-live-{kind}-{head})"
                    )
        retained_value = retained if literal else f"var(--fvs-retained-{slot})"
        for layer in range(blocks):
            css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{transition-property:{retained_value};{';'.join(writes)}}}}}}}"
    if f5.BANK_FILLED_ALIASES and sequential:
        # F5: with a full causal window slots fill in order, so while slot S
        # is being written only slots 0..S hold values; the others equal the
        # zero initial value that --fr-* already has. Alias only those.
        for layer in range(blocks):
            for slot in range(capacity):
                # names are --fc-{kind}-{slot}-{head}
                filled = [name for name in all_fields if f4.slot_of(name) <= slot]
                aliases = ";".join(
                    f"{name.replace('--fc-', '--fr-')}:var({name})" for name in filled
                )
                css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{{aliases}}}}}}}"
    else:
        for layer in range(blocks):
            aliases = ";".join(
                f"{name.replace('--fc-', '--fr-')}:var({name})" for name in all_fields
            )
            css += f"@container runtime style(--layer:{layer}){{.fvs-bank-{layer}{{{aliases}}}}}"
    if packed:
        # F4: 12 dot + 12 value fonts, K axes retagged per head (F2's recipe).
        for head, (dot_path, value_path) in enumerate(f4.packed_operator_fonts(FONT_DIR)):
            css += f'@font-face{{font-family:FvsDot{head};src:url("{dot_path.as_uri()}")}}'
            if not wrapper_v:
                css += f'@font-face{{font-family:FvsValue{head};src:url("{value_path.as_uri()}")}}'
        if wrapper_v:
            # R4W: one value font per KV slot (retagged v2 operator, cmap shifted),
            # selected per leaf by its character through unicode-range.
            for slot, (path, start) in enumerate(r4w.slot_fonts(FONT_DIR / "value.woff2", capacity, CODEPOINT_BASE)):
                css += f'@font-face{{font-family:FvsValueSlot{slot};src:url("{path.as_uri()}");unicode-range:U+{start:X}-{start + DIM - 1:X}}}'
    else:
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
            dot_family = f"FvsDot{head}" if packed else "FvsDot"
            fr_k = f"--fr-k-{slot}" if packed else f"--fr-k-{slot}-{head}"
            css += (
                f".{name}{{font:{QK_SIZE}px {dot_family};line-height:1;font-kerning:none;font-variation-settings:var({fr_k}),var(--fvs-query-{head});"
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
    slim_glyphs = value_weight_once and value_layout in ("runs", "widths")
    hide_unfilled = r4d.HIDE_UNFILLED and sequential and value_layout in ("runs", "widths")
    if hide_unfilled:
        # R4D: unfilled slots' V glyphs have no box; the row subtracts one base
        # advance per PRESENT glyph ((W+1)·base, W = write slot = position-1)
        # instead of capacity·base, so (size - subtracted) is the same sum of
        # weighted deltas as before (minus the snapped-advance residue of absent
        # glyphs, see r4d_flags.py).
        css += '@property --fvs-nbase{syntax:"<length>";inherits:true;initial-value:0px}'
        css += f".fvs-query{{--fvs-nbase:calc((var(--fvs-write-slot) + 1) * {value['base'] * value_unit:.12g}px)}}"
    if slim_glyphs:
        # F2: each (head, slot) softmax weight is one registered number on the
        # score reader; every V glyph references it instead of re-evaluating
        # calc(var()*var()/var()). The reader sits inside the banks, so the
        # inherited --fr-vs alias is visible there. Numerically identical.
        weight_fields = [
            f"--fw-{head}-{slot}" for head in range(HEADS) for slot in range(capacity)
        ]
        css += hybrid.regs(weight_fields)
        css += ".fvs-score-reader{" + ";".join(
            f"--fw-{head}-{slot}:calc(var(--fe-{head}-{slot}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
            for head in range(HEADS)
            for slot in range(capacity)
        ) + "}"
    for head in range(HEADS):
        combined_settings = []
        for slot in range(capacity):
            exponent = f"--fe-{head}-{slot}"
            # Keep every font at a fixed, safe pixel size. Fold each stored V
            # scale into the <=1 probability axis, then restore the common
            # maximum scale after native inline width summation. Large neural
            # activations therefore cannot saturate individual glyph advances.
            weight = (
                f"var(--fw-{head}-{slot})"
                if slim_glyphs
                else f"calc(var({exponent}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
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
                fr_v = (
                    f"--fr-v-{slot}"
                    if packed and not r4d.UNPACK_V
                    else f"--fr-v-{slot}-{head}"
                )
                value_family = f"FvsValue{head}" if packed else "FvsValue"
                if wrapper_v:
                    # R4W: no font property on the leaf at all — font (family
                    # list, size, kerning) and the head's font-variation-settings
                    # are inherited by pointer from .fvs-value-head-H; the leaf's
                    # character selects the slot font via unicode-range.
                    css += f".fvs-v-{head}-{slot}{{{width_rule}flex:none}}"
                elif slim_glyphs:
                    # font-family/size/kerning/white-space inherit from the row
                    # rule below; flex items are blockified; .metric i already
                    # sets font-style. Only the per-(head, slot) list remains
                    # (+ the per-head family when the banks are packed, F4).
                    family_decl = f"font-family:{value_family};" if packed else ""
                    # R4D: the widths rule (if any) is merged into the same rule.
                    # R4W alias: the latched list already ends in "P000" 1.
                    fvs_decl = f"var({fr_v})" if alias_v else f"var({fr_v}),{settings}"
                    css += f".fvs-v-{head}-{slot}{{{family_decl}font-variation-settings:{fvs_decl};{width_rule}flex:none}}"
                else:
                    css += f".fvs-v-{head}-{slot}{{font-family:{value_family};font-size:{VALUE_SIZE}px;font-variation-settings:var({fr_v}),{settings};font-kerning:none;font-style:normal;display:block;white-space:pre;flex:none}}"
                    if width_rule:
                        css += f".fvs-v-{head}-{slot}{{{width_rule}}}"
        if value_layout == "fallback":
            families = ",".join(f"FvsValueSlot{slot}" for slot in range(capacity))
            css += f".fvs-value-head-{head}{{display:contents;font:{VALUE_SIZE}px {families};font-variation-settings:{','.join(combined_settings)};font-kerning:none}}"
        if wrapper_v:
            # R4W: the head's complete V settings, substituted + parsed once per
            # head per pass; `font` (shorthand) precedes font-variation-settings
            # because it resets it. P000 = 1: the weight stays in the leaf width.
            families = ",".join(f"FvsValueSlot{slot}" for slot in range(capacity))
            wrapper_settings = ",".join(f"var(--fr-v-{slot}-{head})" for slot in range(capacity)) + ',"P000" 1'
            css += f".fvs-value-head-{head}{{display:contents;font:{VALUE_SIZE}px {families};font-kerning:none;font-style:normal;font-variation-settings:{wrapper_settings}}}"
    pattern = r'<i class="metric" style="width:calc\(262144px \+ var\(--(?:ctx|out)-(\d+)\) \* 128px\);view-timeline:([^ ]+) inline"></i>'

    def row(match):
        coordinate, timeline = int(match[1]), match[2]
        head, local = divmod(coordinate, DIM)
        subtracted = (
            "var(--fvs-nbase)"
            if hide_unfilled
            else f"{capacity * value['base'] * value_unit:.12g}px"
        )
        dimensions = f"calc-size(max-content,calc(262144px + (size - {subtracted}) * var(--fb-{head}) / var(--fd-{head}) * {128 / (value['coefficient'] * value_unit):.12g}))"
        if value_layout == "fallback":
            runs = "".join(
                f"&#x{CODEPOINT_BASE + slot * DIM + local:X};"
                for slot in range(capacity)
            )
            prefix = f'<div class="fvs-value-head-{head}">' if local == 0 else ""
            suffix = "</div>" if local == DIM - 1 else ""
            return f'{prefix}<span class="metric fvs-value-row" style="width:{dimensions};view-timeline:{timeline} inline">{runs}</span>{suffix}'
        if wrapper_v:
            # R4W: slot S's character lives in slot font S's unicode-range.
            runs = "".join(
                f'<i class="fvs-v-{head}-{slot}">&#x{CODEPOINT_BASE + slot * DIM + local:X};</i>'
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
        # R4W: no font property on the row either (a `font:` shorthand here would
        # reset the inherited font-variation-settings and re-create a Font per row).
        else ".fvs-value-row{display:inline-flex;gap:0;line-height:1;white-space:pre}"
        if wrapper_v
        else f".fvs-value-row{{display:inline-flex;gap:0;font:{VALUE_SIZE}px {'FvsValue0' if packed else 'FvsValue'};line-height:1;font-kerning:none;white-space:pre}}"
        if slim_glyphs
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
    gate_scores = r4d.GATE_SCORES and sequential
    if hide_unfilled or gate_scores:
        # R4D: per-slot filled flag on the fvscache container (same expression
        # as --fv-S on the score reader, which is inherits:false and therefore
        # invisible to the glyph leaves).
        css += hybrid.regs([f"--fvq-{slot}" for slot in range(capacity)]).replace(
            "inherits:true", "inherits:false"
        )
        css += ".fvs-query{" + ";".join(
            f"--fvq-{slot}:clamp(0,sign(var({write_epoch}) - {slot + 1}) + 1,1)"
            for slot in range(capacity)
        ) + "}"
    if hide_unfilled:
        for slot in range(capacity):
            selectors = ",".join(f".fvs-v-{head}-{slot}" for head in range(HEADS))
            css += f"@container fvscache style(--fvq-{slot}:0){{{selectors}{{display:none}}}}"
    if gate_scores:
        # R4D (opt-in): unfilled slots' score carriers have no box, so their 12
        # view-timelines are inactive; --fs/--fe of those slots are masked by
        # --fv-S anyway (both branches give the same masked values).
        for slot in range(capacity):
            selectors = ",".join(f".fvs-score-source .fvs-score-{head}-{slot}" for head in range(HEADS))
            css += f"@container fvscache style(--fvq-{slot}:0){{{selectors}{{display:none}}}}"
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
            "valueWeightOnce": slim_glyphs,
            "f4PackedBanks": packed,
            "f4NumericLists": f4.NUMERIC_LISTS,
            "latchedFieldsPerSlot": len(all_fields) // capacity,
            "r4dEmptyUnfilled": r4d.EMPTY_UNFILLED,
            "r4dLeanLatch": lean,
            "r4dUnpackV": r4d.UNPACK_V,
            "r4dHideUnfilled": hide_unfilled,
            "r4dGateScores": r4d.GATE_SCORES and sequential,
            "r4wVPrecat": precat,
            "prewarmValues": prewarm_values,
            "attentionMask": "full causal"
            if capacity == positions
            else "initial sinks plus rolling recent context",
            "operators": operators,
        },
    )
