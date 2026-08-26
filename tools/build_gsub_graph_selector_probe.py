#!/usr/bin/env python3
"""Build the strict 50,257-node GSUB graph-selector runtime probe."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gsub-graph-selector-probe"
VOCABULARY = 50_257
SLOTS = 16
UNITS_PER_EM = 1_000
FONT_SIZE_PX = UNITS_PER_EM // 2
CODEPOINT_START = 0xE000
DIRECT_FEATURE_TAG = "cv00"
LOW_FEATURE_TAG = "cv01"
HIGH_FEATURE_TAG = "cv02"
FONT_BASENAME = "graph-selector-50257"
REQUIRED_INDICES = (0, 1, 32_767, 50_256)
LOW_RADIX = 255
HIGH_RADIX = 198
HIGH_SUBTABLE_SOURCES = 128


def slot_glyph(slot: int) -> str:
    return f"slot{slot:02d}"


def identity_glyph(token_id: int) -> str:
    return f"n{token_id:05d}"


def intermediate_glyph(slot: int, low: int) -> str:
    return f"m{slot:02d}_{low:03d}"


def neighbor(node: int, slot: int) -> int:
    """A fixed synthetic graph edge; no GPT-2 weights or code are changed."""
    return (node * 7_919 + slot * 10_729 + slot * slot * 17 + 1) % VOCABULARY


def u16(*values: int) -> bytes:
    return struct.pack(f">{len(values)}H", *values)


def alternate_subst(sources_and_alternates: list[tuple[int, list[int]]]) -> bytes:
    count = len(sources_and_alternates)
    header_size = 6 + 2 * count
    coverage = u16(1, count, *(source for source, _ in sources_and_alternates))
    next_offset = header_size + len(coverage)
    offsets: list[int] = []
    sets = bytearray()
    for _, alternates in sources_and_alternates:
        offsets.append(next_offset + len(sets))
        sets.extend(u16(len(alternates), *alternates))
    if max(offsets, default=0) > 65_535:
        raise RuntimeError(f"AlternateSet offset exceeds uint16: {max(offsets)}")
    return u16(1, header_size, count, *offsets) + coverage + sets


def build_gsub_binary() -> bytes:
    """Build ordered cv00 direct, cv01 low, and cv02 high GSUB features."""
    script_list = (
        u16(1)
        + b"DFLT"
        + u16(8)
        + u16(4, 0)
        + u16(0, 0xFFFF, 3, 0, 1, 2)
    )
    direct_lookups = list(range(SLOTS))
    low_lookup = SLOTS
    high_lookup_count = (
        SLOTS * LOW_RADIX + HIGH_SUBTABLE_SOURCES - 1
    ) // HIGH_SUBTABLE_SOURCES
    high_lookups = list(range(SLOTS + 1, SLOTS + 1 + high_lookup_count))
    features = [
        (DIRECT_FEATURE_TAG, u16(0, len(direct_lookups), *direct_lookups)),
        (LOW_FEATURE_TAG, u16(0, 1, low_lookup)),
        (HIGH_FEATURE_TAG, u16(0, len(high_lookups), *high_lookups)),
    ]
    feature_record_size = 2 + 6 * len(features)
    feature_records = bytearray()
    feature_bodies = bytearray()
    for tag, body in features:
        feature_records.extend(tag.encode("ascii") + u16(feature_record_size + len(feature_bodies)))
        feature_bodies.extend(body)
    feature_list = u16(len(features)) + feature_records + feature_bodies

    intermediate_start = 1 + SLOTS
    identity_glyph_start = intermediate_start + SLOTS * LOW_RADIX
    real_subtables: list[bytes] = []
    for slot in range(SLOTS):
        real_subtables.append(
            alternate_subst(
                [(
                    1 + slot,
                    [identity_glyph_start + neighbor(node, slot) for node in range(VOCABULARY)],
                )]
            )
        )
    real_subtables.append(
        alternate_subst(
            [
                (
                    1 + slot,
                    [intermediate_start + slot * LOW_RADIX + low for low in range(LOW_RADIX)],
                )
                for slot in range(SLOTS)
            ]
        )
    )
    all_intermediates = SLOTS * LOW_RADIX
    for chunk_start in range(0, all_intermediates, HIGH_SUBTABLE_SOURCES):
        entries: list[tuple[int, list[int]]] = []
        chunk_end = min(chunk_start + HIGH_SUBTABLE_SOURCES, all_intermediates)
        for linear in range(chunk_start, chunk_end):
            slot, low = divmod(linear, LOW_RADIX)
            alternates = []
            for high in range(HIGH_RADIX):
                node = high * LOW_RADIX + low
                token = neighbor(node, slot) if node < VOCABULARY else 0
                alternates.append(identity_glyph_start + token)
            entries.append((intermediate_start + linear, alternates))
        real_subtables.append(alternate_subst(entries))

    lookup_count = len(real_subtables)
    lookup_list_header_size = 2 + 2 * lookup_count
    lookup_offsets = [lookup_list_header_size + lookup * 16 for lookup in range(lookup_count)]
    lookup_list_prefix = u16(lookup_count, *lookup_offsets)
    lookup_list_file_offset = 10 + len(script_list) + len(feature_list)
    large_tables_file_offset = (
        lookup_list_file_offset + len(lookup_list_prefix) + 16 * lookup_count
    )

    lookup_records = bytearray()
    alternate_subtables = bytearray()
    for lookup_offset, real_subtable in zip(lookup_offsets, real_subtables, strict=True):
        extension_file_offset = lookup_list_file_offset + lookup_offset + 8
        alternate_file_offset = large_tables_file_offset + len(alternate_subtables)
        extension_offset = alternate_file_offset - extension_file_offset
        lookup_records.extend(u16(7, 0, 1, 8))
        lookup_records.extend(u16(1, 3) + struct.pack(">I", extension_offset))
        alternate_subtables.extend(real_subtable)

    lookup_list = lookup_list_prefix + lookup_records + alternate_subtables
    script_offset = 10
    feature_offset = script_offset + len(script_list)
    lookup_offset = feature_offset + len(feature_list)
    return (
        u16(1, 0, script_offset, feature_offset, lookup_offset)
        + script_list
        + feature_list
        + lookup_list
    )


def build_font(ttf_path: Path) -> dict[str, object]:
    glyph_order = (
        [".notdef"]
        + [slot_glyph(slot) for slot in range(SLOTS)]
        + [
            intermediate_glyph(slot, low)
            for slot in range(SLOTS)
            for low in range(LOW_RADIX)
        ]
        + [identity_glyph(token_id) for token_id in range(VOCABULARY)]
    )
    empty_glyph = TTGlyphPen(None).glyph()
    glyphs = {name: empty_glyph for name in glyph_order}
    notdef_pen = TTGlyphPen(None)
    notdef_pen.moveTo((0, 0))
    notdef_pen.lineTo((1, 0))
    notdef_pen.lineTo((0, 1))
    notdef_pen.closePath()
    glyphs[".notdef"] = notdef_pen.glyph()
    metrics = {".notdef": (0, 0)}
    metrics.update({slot_glyph(slot): (0, 0) for slot in range(SLOTS)})
    metrics.update(
        {
            intermediate_glyph(slot, low): (0, 0)
            for slot in range(SLOTS)
            for low in range(LOW_RADIX)
        }
    )
    metrics.update(
        {
            identity_glyph(token_id): (token_id + 1, 0)
            for token_id in range(VOCABULARY)
        }
    )

    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(
        {CODEPOINT_START + slot: slot_glyph(slot) for slot in range(SLOTS)}
    )
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable(
        {
            "familyName": "Graph Selector Probe 50257",
            "styleName": "Regular",
            "uniqueFontIdentifier": "GraphSelectorProbe50257-Regular-v1",
            "fullName": "Graph Selector Probe 50257 Regular",
            "psName": "GraphSelectorProbe50257-Regular",
            "version": "Version 1.000",
            "description": "Strict 50257-node numbered GSUB alternate selector probe",
        }
    )
    builder.setupOS2(
        sTypoAscender=800,
        sTypoDescender=-200,
        usWinAscent=800,
        usWinDescent=200,
    )
    builder.setupPost()
    builder.setupMaxp()
    font = builder.font

    # One extension lookup per slot is intentional.  Each AlternateSet is
    # 100,516 bytes, so ordinary 16-bit Lookup/SubTable offsets cannot address
    # sixteen of them.  ExtensionSubst gives each real type-3 subtable a
    # 32-bit offset while preserving one genuine 50,257-entry AlternateSet.
    gsub = DefaultTable("GSUB")
    gsub.data = build_gsub_binary()
    font["GSUB"] = gsub
    font.recalcTimestamp = False
    font.save(ttf_path)

    compiled = TTFont(ttf_path, recalcTimestamp=False)
    lookup_list = compiled["GSUB"].table.LookupList.Lookup
    lookup_types: list[int] = []
    lookup_mappings: list[dict[str, list[str]]] = []
    for lookup in lookup_list:
        lookup_types.append(lookup.LookupType)
        mapping: dict[str, list[str]] = {}
        for extension in lookup.SubTable:
            subtable = (
                extension.ExtSubTable if hasattr(extension, "ExtSubTable") else extension
            )
            if hasattr(subtable, "alternates"):
                for source, values in subtable.alternates.items():
                    mapping[source] = list(values)
        lookup_mappings.append(mapping)

    feature_records = compiled["GSUB"].table.FeatureList.FeatureRecord
    feature_order = [record.FeatureTag for record in feature_records]
    feature_lookups = {
        record.FeatureTag: list(record.Feature.LookupListIndex)
        for record in feature_records
    }
    expected_feature_lookups = {
        DIRECT_FEATURE_TAG: list(range(SLOTS)),
        LOW_FEATURE_TAG: [SLOTS],
        HIGH_FEATURE_TAG: list(range(SLOTS + 1, len(lookup_list))),
    }
    if feature_order != [DIRECT_FEATURE_TAG, LOW_FEATURE_TAG, HIGH_FEATURE_TAG]:
        raise RuntimeError(f"compiled feature order is {feature_order!r}")
    if feature_lookups != expected_feature_lookups:
        raise RuntimeError(f"compiled feature lookups are {feature_lookups!r}")

    direct_sets = [lookup_mappings[slot][slot_glyph(slot)] for slot in range(SLOTS)]
    low_mapping = lookup_mappings[SLOTS]
    high_mapping: dict[str, list[str]] = {}
    for mapping in lookup_mappings[SLOTS + 1 :]:
        high_mapping.update(mapping)
    direct_counts = [len(values) for values in direct_sets]
    low_counts = [len(low_mapping[slot_glyph(slot)]) for slot in range(SLOTS)]
    high_counts = [
        len(high_mapping[intermediate_glyph(slot, low)])
        for slot in range(SLOTS)
        for low in range(LOW_RADIX)
    ]
    if direct_counts != [VOCABULARY] * SLOTS:
        raise RuntimeError(f"compiled direct AlternateSet counts {direct_counts!r}")
    if low_counts != [LOW_RADIX] * SLOTS:
        raise RuntimeError(f"compiled low AlternateSet counts {low_counts!r}")
    if high_counts != [HIGH_RADIX] * (SLOTS * LOW_RADIX):
        raise RuntimeError(f"compiled high AlternateSet counts are not all {HIGH_RADIX}")

    for slot, values in enumerate(direct_sets):
        for node in REQUIRED_INDICES:
            expected = identity_glyph(neighbor(node, slot))
            if values[node] != expected:
                raise RuntimeError(
                    f"slot {slot} node {node}: {values[node]!r}, expected {expected!r}"
                )
            high, low = divmod(node, LOW_RADIX)
            intermediate = low_mapping[slot_glyph(slot)][low]
            expected_intermediate = intermediate_glyph(slot, low)
            if intermediate != expected_intermediate:
                raise RuntimeError(
                    f"slot {slot} low {low}: {intermediate!r}, expected {expected_intermediate!r}"
                )
            radix_result = high_mapping[intermediate][high]
            if radix_result != expected:
                raise RuntimeError(
                    f"slot {slot} node {node} radix: {radix_result!r}, expected {expected!r}"
                )

    return {
        "glyphCount": len(compiled.getGlyphOrder()),
        "lookupCount": len(lookup_list),
        "lookupTypes": lookup_types,
        "featureOrder": feature_order,
        "featureLookupIndices": feature_lookups,
        "alternateSetCounts": direct_counts,
        "directAlternateSetCounts": direct_counts,
        "lowAlternateSetCounts": low_counts,
        "highAlternateSetCount": len(high_counts),
        "highAlternateSetEntries": HIGH_RADIX,
        "alternateSetCountFieldMaximum": 65_535,
        "maximumGlyphId": len(compiled.getGlyphOrder()) - 1,
        "verifiedAlternateIndices": list(REQUIRED_INDICES),
    }


def build_html() -> str:
    def slots(hop: int) -> str:
        return "\n".join(
            f'<i class="identity hop{hop}-slot" id="hop{hop}-slot-{slot:02d}" '
            f'data-slot="{slot}">&#x{CODEPOINT_START + slot:X};</i>'
            for slot in range(SLOTS)
        )

    direct_slots = "\n".join(
        f'<i class="identity direct-slot" id="direct-slot-{slot:02d}" '
        f'data-slot="{slot}">&#x{CODEPOINT_START + slot:X};</i>'
        for slot in range(SLOTS)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Strict 50,257-node GSUB graph selector probe</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="index.css">
</head>
<body>
  <main id="probe" aria-label="declarative graph selector probe">
    <section id="direct-baseline" class="hop direct" aria-label="direct selector baseline">
{direct_slots}
    </section>
    <section id="hop1" class="hop hop1" aria-label="first hop">
{slots(1)}
    </section>
    <section id="selected-slot-reader">
      <div id="chain">
        <section id="hop2" class="hop hop2" aria-label="second hop">
{slots(2)}
        </section>
      </div>
    </section>
    <output id="runtime-contract">CSS and OpenType only; the external harness reads geometry.</output>
  </main>
</body>
</html>
"""


def build_css() -> str:
    if_branches = ";".join(
        f"style(--edge-slot:{slot}):anchor-size(--hop1-s{slot:02d} width)"
        for slot in range(SLOTS)
    )
    anchor_rules = "\n".join(
        f"#hop1-slot-{slot:02d}{{anchor-name:--hop1-s{slot:02d}}}"
        for slot in range(SLOTS)
    )
    second_anchor_rules = "\n".join(
        f"#hop2-slot-{slot:02d}{{anchor-name:--hop2-s{slot:02d}}}"
        for slot in range(SLOTS)
    )
    return f"""@font-face{{
  font-family:GraphSelectorProbe;
  src:url("{FONT_BASENAME}.woff2") format("woff2"),url("{FONT_BASENAME}.ttf") format("truetype");
  font-display:block;
}}
@property --input-node{{syntax:"<number>";inherits:true;initial-value:0}}
@property --input-slot{{syntax:"<number>";inherits:true;initial-value:0}}
@property --current-node{{syntax:"<integer>";inherits:true;initial-value:0}}
@property --edge-slot{{syntax:"<integer>";inherits:true;initial-value:0}}
@property --low{{syntax:"<integer>";inherits:true;initial-value:0}}
@property --high{{syntax:"<integer>";inherits:true;initial-value:0}}
@property --next-node{{syntax:"<integer>";inherits:true;initial-value:0}}
@property --next-low{{syntax:"<integer>";inherits:true;initial-value:0}}
@property --next-high{{syntax:"<integer>";inherits:true;initial-value:0}}
*{{box-sizing:border-box}}
html,body{{margin:0;min-height:100%;font-family:system-ui,sans-serif}}
#probe{{
  --input-node:0;
  --input-slot:0;
  --current-node:round(nearest,var(--input-node),1);
  --edge-slot:round(nearest,var(--input-slot),1);
  --low:mod(var(--current-node),{LOW_RADIX});
  --high:round(down,var(--current-node) / {LOW_RADIX},1);
  position:relative;
}}
.hop{{position:fixed;left:0;top:-2000px;width:1px;height:1px}}
.identity{{
  position:absolute;
  display:block;
  width:max-content;
  height:1px;
  overflow:visible;
  font-family:GraphSelectorProbe;
  font-size:{FONT_SIZE_PX}px;
  font-style:normal;
  font-weight:400;
  line-height:1;
  font-kerning:none;
  font-feature-settings:normal;
}}
.direct-slot{{font-feature-settings:"{DIRECT_FEATURE_TAG}" calc(var(--current-node) + 1)}}
.hop1-slot{{font-feature-settings:"{LOW_FEATURE_TAG}" calc(var(--low) + 1),"{HIGH_FEATURE_TAG}" calc(var(--high) + 1)}}
.hop2-slot{{font-feature-settings:"{LOW_FEATURE_TAG}" calc(var(--next-low) + 1),"{HIGH_FEATURE_TAG}" calc(var(--next-high) + 1)}}
{anchor_rules}
{second_anchor_rules}
#selected-slot-reader{{
  position:fixed;
  left:0;
  top:-1000px;
  height:1px;
  width:if({if_branches};else:0px);
  container:selected-slot/inline-size;
}}
#chain{{--next-node:0;--next-low:mod(var(--next-node),{LOW_RADIX});--next-high:round(down,var(--next-node) / {LOW_RADIX},1);position:fixed;left:0;top:0;width:1px;height:1px}}
@container selected-slot (width >= 0px){{
  #chain{{--next-node:calc(round(nearest,100cqi * 2 / 1px,1) - 1)}}
}}
#runtime-contract{{display:block;margin:1rem;font:14px/1.4 system-ui,sans-serif}}
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ttf_path = OUTPUT / f"{FONT_BASENAME}.ttf"
    metadata = build_font(ttf_path)
    font = TTFont(ttf_path, recalcTimestamp=False)
    font.flavor = "woff2"
    woff2_path = OUTPUT / f"{FONT_BASENAME}.woff2"
    font.save(woff2_path)

    html_path = OUTPUT / "index.html"
    css_path = OUTPUT / "index.css"
    html_path.write_text(build_html())
    css_path.write_text(build_css())
    reference = {
        "concept": "fixed-GPT-2 graph-output selector; synthetic graph only",
        "vocabulary": VOCABULARY,
        "slots": SLOTS,
        "features": {
            "directBaseline": {"tag": DIRECT_FEATURE_TAG, "value": "node + 1"},
            "radixLow": {"tag": LOW_FEATURE_TAG, "value": "mod(node, 255) + 1"},
            "radixHigh": {"tag": HIGH_FEATURE_TAG, "value": "floor(node / 255) + 1"},
        },
        "unitsPerEm": UNITS_PER_EM,
        "fontSizePx": FONT_SIZE_PX,
        "identityAdvanceForToken": "tokenId + 1 font units; (tokenId + 1) / 2 CSS px",
        "neighborFormula": "(node * 7919 + slot * 10729 + slot * slot * 17 + 1) % 50257",
        "requiredIndices": list(REQUIRED_INDICES),
        "font": metadata,
        "files": {
            "ttfBytes": ttf_path.stat().st_size,
            "woff2Bytes": woff2_path.stat().st_size,
            "htmlBytes": html_path.stat().st_size,
            "cssBytes": css_path.stat().st_size,
        },
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({"output": str(OUTPUT), **reference}, indent=2))


if __name__ == "__main__":
    main()
