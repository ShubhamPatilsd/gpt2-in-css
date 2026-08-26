#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Compile connected signed weighted sums from local, four-bit GSUB pieces.

The page supplies only signed input values. Product lookup, routing, carry,
reduction and a dependent 2*S+1 calculation all happen during font shaping.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "experiments/gsub-weighted-sum-probe"
DIGITS = 4
RADIX = 16
BASE = 64
WEIGHTS = (3, -2, 5, 1)
FANOUT_MATRIX = ((3, -2, 5, 1), (-1, 4, 2, -3), (2, 1, -2, 5), (5, -2, 1, 2))


def digit(node, slot, value):
    return f"{node}d{slot}v{value}"


def reduction(width, topology):
    levels = []
    next_node = width
    if topology == "sequential":
        accumulator = 0
        for right in range(1, width):
            levels.append([(accumulator, right, next_node)])
            accumulator = next_node
            next_node += 1
    else:
        current = list(range(width))
        while len(current) > 1:
            following, pairs = [], []
            for index in range(0, len(current), 2):
                if index + 1 == len(current):
                    following.append(current[index])
                    continue
                pairs.append((current[index], current[index + 1], next_node))
                following.append(next_node)
                next_node += 1
            levels.append(pairs)
            current = following
    return levels, next_node - 1


def build(width, topology, out, fanout=False):
    identifier = "w4-fanouttree" if fanout else f"w{width}-{topology}"
    directory = out / identifier
    directory.mkdir(parents=True, exist_ok=True)
    matrix = [list(row) for row in FANOUT_MATRIX] if fanout else [[WEIGHTS[index % len(WEIGHTS)] for index in range(width)]]
    channels = len(matrix)
    weights = [sum(row[index] for row in matrix) for index in range(width)]
    minima = [[min(weight * value for value in range(-8, 8)) for weight in row] for row in matrix]
    input_offset = -sum(sum(row) for row in minima)
    signed_min = sum(min(weight * value for value in range(-8, 8)) for weight in weights)
    signed_max = sum(max(weight * value for value in range(-8, 8)) for weight in weights)
    max_positive = signed_max + input_offset
    assert 2 * max_positive + 1 < RADIX ** DIGITS
    primary_levels, primary_final = reduction(width, topology)
    levels = list(primary_levels)
    node_slots = {node: DIGITS * channels for node in range(primary_final + 1)}
    cross_leaves = []
    final_node = primary_final
    if fanout:
        cross_levels, cross_final = reduction(channels, "tree")
        cross_start = primary_final + 1
        cross_leaves = list(range(cross_start, cross_start + channels))
        levels += [[tuple(node + cross_start for node in pair) for pair in level] for level in cross_levels]
        final_node = cross_start + cross_final
        node_slots.update({node: DIGITS for node in range(cross_start, final_node + 1)})
    pairs = [pair for level in levels for pair in level]
    glyphs = [".notdef"]
    advances = {".notdef": 1}
    cmap = {}
    definitions, classes = [], []
    feature_calls = {tag: [] for tag in (("ss01", "ss02", "ss03", "ss04", "ss05") if fanout else ("ss01", "ss02", "ss03", "ss04"))}
    dependent_feature = "ss04" if fanout else "ss03"
    publish_feature = "ss05" if fanout else "ss04"
    counts = {}
    top_level_lookups = []

    def glyph(label, advance=0, cp=None):
        if label in advances:
            raise ValueError(f"duplicate glyph {label}")
        glyphs.append(label)
        advances[label] = advance
        if cp is not None:
            if cp in cmap:
                raise ValueError(f"input codepoint U+{cp:04X} overlaps {cmap[cp]}; assign a larger/disjoint input alphabet before increasing width")
            cmap[cp] = label
        return label

    def cls(label, members):
        classes.append(f"@{label} = [" + " ".join(members) + "];")
        return "@" + label

    def lookup(label, rules, phase, feature=None, extension=False):
        counts[phase] = counts.get(phase, 0) + len(rules)
        qualifier = " useExtension" if extension else ""
        definitions.append(f"lookup {label}{qualifier} {{\n" + "\n".join(rules) + f"\n}} {label};")
        if feature:
            feature_calls[feature].append(label)
            top_level_lookups.append(label)

    nonce_cp = 0xE800
    for value in range(65):
        glyph(f"nonce{value}", cp=nonce_cp + value)
        glyph(f"base{value}", advance=BASE)
    input_cps = []
    glyph("consumed")
    for index in range(width):
        input_cps.append(0xE000 + index * 16)
        for value in range(16):
            glyph(f"input{index}v{value}", cp=input_cps[-1] + value)
    node_classes = {}
    for node in range(final_node + 1):
        for slot in range(node_slots[node]):
            members = [glyph(digit(f"n{node}", slot, value)) for value in range(RADIX)]
            node_classes[node, slot] = cls(f"N{node}D{slot}", members)
    temporary_classes, carry_classes, no_carry_classes = {}, {}, {}
    for _, _, parent in pairs:
        for slot in range(node_slots[parent]):
            members = [glyph(digit(f"t{parent}", slot, value)) for value in range(32)]
            temporary_classes[parent, slot] = cls(f"T{parent}D{slot}", members)
            no_carry_classes[parent, slot] = cls(f"T{parent}D{slot}Low", members[:16])
            carry_classes[parent, slot] = cls(f"T{parent}D{slot}Carry", members[16:])
    for slot in range(DIGITS):
        members = [glyph(digit("dep", slot, value)) for value in range(32)]
        cls(f"Dep{slot}Low", members[:16])
        cls(f"Dep{slot}Carry", members[16:])
        for value in range(16):
            glyph(digit("final", slot, value))
            glyph(digit("out", slot, value), advance=value * RADIX ** slot)

    product_rules = []
    for index in range(width):
        for encoded in range(16):
            targets = []
            for channel in range(channels):
                product = matrix[channel][index] * (encoded - 8) - minima[channel][index]
                targets += [digit(f"n{index}", channel * DIGITS + slot, product // RADIX ** slot % RADIX)
                            for slot in range(DIGITS)]
            target = " ".join(targets)
            product_rules.append(f"sub input{index}v{encoded} by {target};")
    lookup("Products", product_rules, "products", "ss01", extension=True)

    # A contextual lookup selects a constant from one left digit and its carry.
    # Nested constant-addition tables act only on the corresponding right digit.
    # All nodes share these seventeen lookup definitions; their operands retain
    # position tags, and their table entries enumerate individual digits only.
    for constant in range(17):
        rules = []
        for _, right, parent in pairs:
            for slot in range(node_slots[parent]):
                for value in range(16):
                    rules.append(f"sub {digit(f'n{right}', slot, value)} by {digit(f't{parent}', slot, value + constant)};")
        lookup(f"Add{constant}", rules, "digitAddMappings", extension=True)

    for level_index, level in enumerate(levels):
        stage_feature = "ss02" if level_index < len(primary_levels) else "ss03"
        if fanout and level_index == len(primary_levels):
            lookup("ExposeChannels", [f"sub {digit(f'n{primary_final}', channel * DIGITS + slot, value)} by {digit(f'n{cross_leaves[channel]}', slot, value)};"
                                      for channel in range(channels) for slot in range(DIGITS) for value in range(16)],
                   "channelRouting", stage_feature)
        slots = node_slots[level[0][2]]
        for slot in range(slots):
            rules = []
            for left, right, parent in level:
                for value in range(16):
                    context = [digit(f"n{left}", slot, value)]
                    context += [node_classes[left, higher] for higher in range(slot + 1, slots)]
                    has_carry = slot % DIGITS != 0
                    context += [temporary_classes[parent, lower] for lower in range(slot - 1 if has_carry else slot)]
                    if has_carry:
                        for carry in (0, 1):
                            previous = (carry_classes if carry else no_carry_classes)[parent, slot - 1]
                            rules.append("sub " + " ".join(context + [previous]) +
                                         f" {node_classes[right, slot]}' lookup Add{value + carry};")
                    else:
                        rules.append("sub " + " ".join(context) +
                                     f" {node_classes[right, slot]}' lookup Add{value};")
            lookup(f"Level{level_index}Digit{slot}", rules, "routingContexts", stage_feature, extension=True)
        absorption, normalization = [], []
        for left, _, parent in level:
            for slot in range(slots):
                normalization += [f"sub {digit(f'n{left}', slot, value)} by consumed;" for value in range(16)]
                normalization += [f"sub {digit(f't{parent}', slot, value)} by {digit(f'n{parent}', slot, value % RADIX)};"
                                  for value in range(32)]
            absorption += [f"sub {' '.join(['consumed'] * slots)} {digit(f'n{parent}', 0, value)} by {digit(f'n{parent}', 0, value)};"
                           for value in range(16)]
        lookup(f"Level{level_index}Normalize", normalization, "digitNormalization", stage_feature, extension=True)
        lookup(f"Level{level_index}ConsumeLeft", absorption, "consumedDigitAbsorption", stage_feature, extension=True)

    # Keep the second calculation inside the shaped glyph string. Each digit
    # doubles; the low digit receives the +1 and carries flow to higher digits.
    for carry in (0, 1):
        rules = [f"sub {digit(f'n{final_node}', slot, value)} by {digit('dep', slot, 2 * value + carry)};"
                 for slot in range(DIGITS) for value in range(16)]
        lookup(f"DoublePlus{carry}", rules, "dependentDigitMappings")
    lookup("DependentLow", [f"sub {digit(f'n{final_node}', 0, value)} by {digit('dep', 0, 2 * value + 1)};"
                            for value in range(16)], "dependentContexts", dependent_feature)
    for slot in range(1, DIGITS):
        lookup(f"DependentDigit{slot}",
               [f"sub @Dep{slot - 1}Low {node_classes[final_node, slot]}' lookup DoublePlus0;",
                f"sub @Dep{slot - 1}Carry {node_classes[final_node, slot]}' lookup DoublePlus1;"],
               "dependentContexts", dependent_feature)
    lookup("DependentNormalize", [f"sub {digit('dep', slot, value)} by {digit('final', slot, value % 16)};"
                                  for slot in range(DIGITS) for value in range(32)],
           "dependentNormalization", dependent_feature)
    lookup("Publish", [f"sub nonce{value} by base{value};" for value in range(65)] +
           [f"sub {digit('final', slot, value)} by {digit('out', slot, value)};"
            for slot in range(DIGITS) for value in range(16)], "publish", publish_feature)
    feature = "languagesystem DFLT dflt;\n" + "\n".join(classes + definitions)
    for tag, calls in feature_calls.items():
        feature += f"\nfeature {tag} {{ " + " ".join(f"lookup {label};" for label in calls) + f" }} {tag};\n"
    (directory / "program.fea").write_text(feature)
    builder = FontBuilder(1024, isTTF=True)
    builder.setupGlyphOrder(glyphs)
    builder.setupCharacterMap(cmap)
    empty = TTGlyphPen(None).glyph()
    outlines = {name: empty for name in glyphs}
    notdef = TTGlyphPen(None)
    notdef.moveTo((0, 0))
    notdef.lineTo((1, 0))
    notdef.lineTo((0, 1))
    notdef.closePath()
    outlines[".notdef"] = notdef.glyph()
    builder.setupGlyf(outlines)
    builder.setupHorizontalMetrics({name: (advance, 0) for name, advance in advances.items()})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    family = "GSUBWeighted" + identifier.replace("-", "")
    builder.setupNameTable({"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": family + "-v1",
                           "fullName": family, "psName": family})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    addOpenTypeFeaturesFromString(builder.font, feature)
    builder.font.save(directory / "weighted.ttf")
    builder.font.flavor = "woff2"
    builder.font.save(directory / "weighted.woff2")
    record = {
        "id": identifier, "width": width, "topology": topology, "weights": weights,
        "compilerSourceAtBuildSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fontFile": f"{identifier}/weighted.woff2", "fontFamily": family,
        "inputCodepoints": input_cps, "nonceCodepoint": nonce_cp, "nonces": 65,
        "features": list(feature_calls),
        "disableControls": [{"label": label, "feature": tag} for tag, label in
                            ([("ss01", "fixed-weight products and input fanout"), ("ss02", "per-channel connected reduction"),
                              ("ss03", "cross-channel connected reduction"), (dependent_feature, "dependent double-plus-one"), (publish_feature, "numeric publication")]
                             if fanout else [("ss01", "fixed-weight products"), ("ss02", "connected reduction"),
                                             (dependent_feature, "dependent double-plus-one"), (publish_feature, "numeric publication")])],
        "output": {"offset": BASE + 2 * input_offset, "unitsPerEm": 1024, "fontSize": 1024,
                   "advanceBase": BASE, "advanceFormula": "64 + 2*P + 1", "decodedFormula": "2*S + 1"},
        "dependent": {"kind": "affine", "multiplier": 2, "bias": 1},
        "representation": {"signedInputMin": -8, "signedInputMax": 7, "inputCounterBias": 8,
                           "digits": DIGITS, "radix": RADIX, "digitOrder": "little endian",
                           "productOffsets": [[-value for value in row] for row in minima] if fanout else [-value for value in minima[0]], "sumOffset": input_offset,
                           "Pmax": max_positive, "Qmax": 2 * max_positive + 1,
                           "signedSumMin": signed_min, "signedSumMax": signed_max,
                           "intermediateAdvances": 0,
                           "routing": "position-tagged contextual lookups across adjacent four-digit words",
                           "consumption": "left digits map to zero-width consumed glyphs, then the consumed word block and the first result digit form one ligature",
                           "channels": channels,
                           "channelWeightMatrix": matrix if fanout else None,
                           "channelOffsets": [-sum(row) for row in minima],
                           "fanoutGlyphsPerInput": DIGITS * channels,
                           "maximumBacktrackGlyphs": DIGITS * channels,
                           "maximumAbsorptionLigatureComponents": DIGITS * channels + 1},
        "structure": {"mergeNodes": len(pairs), "reductionLevels": len(levels),
                      "fontGlyphs": len(glyphs), "fontLookups": len(builder.font["GSUB"].table.LookupList.Lookup),
                      "topLevelLookups": len(top_level_lookups), "lookupCallsByFeature": feature_calls,
                      "ruleCounts": counts, "ruleCountTotal": sum(counts.values()),
                      "inputTextGlyphs": width + 1, "afterProductGlyphs": DIGITS * channels * width + 1,
                      "finalGlyphs": 5, "maxEnumeratedLocalDigitPairStates": 256},
        "files": {},
    }
    for path in (directory / "weighted.ttf", directory / "weighted.woff2", directory / "program.fea"):
        payload = path.read_bytes()
        record["files"][str(path.relative_to(out))] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    (directory / "reference.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{identifier}: {len(glyphs)} glyphs, {record['structure']['fontLookups']} lookups, "
          f"{(directory / 'weighted.woff2').stat().st_size} WOFF2 bytes", flush=True)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--widths", nargs="+", type=int, default=[4, 8, 16, 64])
    parser.add_argument("--topologies", nargs="+", choices=["sequential", "tree"], default=["sequential", "tree"])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fanout-only", action="store_true", help="Append the four-input/four-channel connected fixture without rebuilding standard variants")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.fanout_only:
        prior = json.loads((args.out / "reference.json").read_text()) if (args.out / "reference.json").exists() else {"variants": []}
        variants = [variant for variant in prior["variants"] if variant["id"] != "w4-fanouttree"]
        variants.append(build(4, "tree", args.out, fanout=True))
    else:
        variants = [build(width, topology, args.out) for width in args.widths for topology in args.topologies]
    manifest = {"description": "Signed fixed weighted sums followed by a dependent 2*S+1 operation inside GSUB",
                "runtimeScripts": 0, "variants": variants,
                "compilerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.out / "reference.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
