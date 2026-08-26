#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Causal slot-alphabet and context-packing variants of the reusable sum.

The two layouts share exactly the same arithmetic FEA source. Packing changes
only ChainContextSubst format 3 rule storage into format 2 class rules. It never
prunes rules, alters lookup order, or merges the ordered reduction passes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import time

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.otlLib.builder import ChainContextSubstBuilder
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-partitioned-digits"
WEIGHTS = (3, -2, 5, 1)


def pack_contexts(font):
    """Pack only provably disjoint-or-identical coverage classes, without expansion."""
    packed = 0
    original_rules = 0
    for lookup in font["GSUB"].table.LookupList.Lookup:
        extension = lookup.LookupType == 7
        tables = [s.ExtSubTable if extension else s for s in lookup.SubTable]
        types = [s.ExtensionLookupType if extension else lookup.LookupType for s in lookup.SubTable]
        if set(types) != {6}:
            continue
        assert all(table.Format == 3 for table in tables)
        definitions, mappings = {}, {}
        for side in ("Backtrack", "Input", "LookAhead"):
            sets = []
            for table in tables:
                for coverage in getattr(table, side + "Coverage"):
                    item = frozenset(coverage.glyphs)
                    if item in sets:
                        continue
                    assert all(not item.intersection(previous) for previous in sets), (side, item)
                    sets.append(item)
            definitions[side] = otTables.ClassDef()
            definitions[side].classDefs = {g: i + 1 for i, group in enumerate(sets) for g in group}
            mappings[side] = {group: i + 1 for i, group in enumerate(sets)}
        result = otTables.ChainContextSubst()
        result.Format = 2
        result.Coverage = otTables.Coverage()
        covered = set().union(*(set(table.InputCoverage[0].glyphs) for table in tables))
        result.Coverage.glyphs = sorted(covered, key=font.getGlyphID)
        result.BacktrackClassDef = definitions["Backtrack"]
        result.InputClassDef = definitions["Input"]
        result.LookAheadClassDef = definitions["LookAhead"]
        result.ChainSubClassSetCount = len(mappings["Input"]) + 1
        result.ChainSubClassSet = [None] * result.ChainSubClassSetCount
        for table in tables:
            sequences = {side: [mappings[side][frozenset(c.glyphs)] for c in getattr(table, side + "Coverage")]
                         for side in ("Backtrack", "Input", "LookAhead")}
            rule = otTables.ChainSubClassRule()
            rule.Backtrack = sequences["Backtrack"]
            rule.BacktrackGlyphCount = len(rule.Backtrack)
            rule.Input = sequences["Input"][1:]
            rule.InputGlyphCount = len(rule.Input) + 1
            rule.LookAhead = sequences["LookAhead"]
            rule.LookAheadGlyphCount = len(rule.LookAhead)
            rule.SubstLookupRecord = copy.deepcopy(table.SubstLookupRecord)
            rule.SubstCount = len(rule.SubstLookupRecord)
            first_class = sequences["Input"][0]
            if result.ChainSubClassSet[first_class] is None:
                group = otTables.ChainSubClassSet()
                group.ChainSubClassRule = []
                result.ChainSubClassSet[first_class] = group
            result.ChainSubClassSet[first_class].ChainSubClassRule.append(rule)
        for group in result.ChainSubClassSet:
            if group is not None:
                group.ChainSubClassRuleCount = len(group.ChainSubClassRule)
        if extension:
            wrapper = otTables.ExtensionSubst()
            wrapper.Format = 1
            wrapper.ExtensionLookupType = 6
            wrapper.ExtSubTable = result
            lookup.SubTable = [wrapper]
        else:
            lookup.SubTable = [result]
        lookup.SubTableCount = 1
        packed += 1
        original_rules += len(tables)
    return {"packedLookups": packed, "originalContextFormat3Subtables": original_rules,
            "rulesDropped": 0, "classCoverageInvariant": "All distinct coverage sets on each side are disjoint; no rule expansion"}


def build(width, layout):
    assert width >= 4 and width % 4 == 0
    weights = [WEIGHTS[i % 4] for i in range(width)]
    offset = -sum(min(-8*w, 7*w) for w in weights)
    maximum = sum(max(-8*w, 7*w) for w in weights)
    assert 2 * (maximum + offset) + 1 < 65536
    identifier = f"slot-{layout}-w{width}"
    directory = OUT / identifier
    directory.mkdir(parents=True, exist_ok=True)
    glyphs, metrics, cmap = [".notdef"], {".notdef": 1}, {}
    classes, definitions, counts = [], [], {}
    calls = {tag: [] for tag in ("ss01", "ss02", "ss03", "ss04")}

    def glyph(label, advance=0, cp=None):
        assert label not in metrics
        glyphs.append(label); metrics[label] = advance
        if cp is not None:
            assert cp not in cmap
            cmap[cp] = label
        return label

    def cls(label, members):
        classes.append(f"@{label} = [" + " ".join(members) + "];")

    def lookup(label, rules, kind, phase=None):
        counts[kind] = counts.get(kind, 0) + len(rules)
        definitions.append(f"lookup {label} useExtension {{\n" + "\n".join(rules) + f"\n}} {label};")
        if phase:
            calls[phase].append(label)

    for slot in range(4):
        cls(f"D{slot}", [glyph(f"d{slot}v{v}") for v in range(16)])
        cls(f"T{slot}", [glyph(f"t{slot}v{v}") for v in range(32)])
        cls(f"Low{slot}", [f"t{slot}v{v}" for v in range(16)])
        cls(f"Carry{slot}", [f"t{slot}v{v}" for v in range(16, 32)])
        cls(f"Out{slot}", [glyph(f"o{slot}v{v}", advance=v * 16**slot) for v in range(16)])
    for label in ("acc", "operand", "consumed"):
        glyph(label)
    glyph("base", advance=64)
    for value in range(65):
        glyph(f"nonce{value}", cp=0xE800 + value)
    for alphabet in range(5):
        for value in range(16):
            glyph(f"i{alphabet}v{value}", cp=0xE000 + 16 * alphabet + value)
    input_cps = [0xE000] + [0xE010 + 16 * (i % 4) for i in range(1, width)]
    products = []
    for alphabet in range(5):
        weight = 3 if alphabet == 0 else WEIGHTS[alphabet - 1]
        minimum = min(-8*weight, 7*weight)
        for encoded in range(16):
            value = weight * (encoded - 8) - minimum
            word = " ".join(f"d{slot}v{value // 16**slot % 16}" for slot in range(4))
            products.append(f"sub i{alphabet}v{encoded} by {'acc' if alphabet == 0 else 'operand'} {word};")
    lookup("Products", products, "productRules", "ss01")
    for slot in range(4):
        for constant in range(17):
            lookup(f"Add{slot}c{constant}", [f"sub d{slot}v{v} by t{slot}v{v + constant};" for v in range(16)], "sharedDigitAddition")
    lookup("MarkConsumed", [f"sub d{s}v{v} by consumed;" for s in range(4) for v in range(16)], "sharedConsumedMapping")
    lookup("Normalize", [f"sub t{s}v{v} by d{s}v{v % 16};" for s in range(4) for v in range(32)], "sharedNormalization")
    for iteration in range(width - 1):
        for slot in range(4):
            rules = []
            for value in range(16):
                left = ["acc"] + [f"d{s}v{value}" if s == slot else f"@D{s}" for s in range(4)] + ["operand"]
                if slot:
                    left += [f"@T{s}" for s in range(slot - 1)]
                    for carry in (0, 1):
                        rules.append("sub " + " ".join(left + [f"@{'Carry' if carry else 'Low'}{slot-1}"]) + f" @D{slot}' lookup Add{slot}c{value + carry};")
                else:
                    rules.append("sub " + " ".join(left) + f" @D{slot}' lookup Add{slot}c{value};")
            lookup(f"Pass{iteration}Digit{slot}", rules, "digitContextWrappers", "ss02")
        marked = " ".join(f"@D{s}' lookup MarkConsumed" for s in range(4))
        normalized = " ".join(f"@T{s}' lookup Normalize" for s in range(4))
        lookup(f"Pass{iteration}Mark", [f"sub acc {marked} operand;"], "consumedContextWrappers", "ss02")
        lookup(f"Pass{iteration}Absorb", ["sub acc consumed consumed consumed consumed operand by acc;"], "consumedLigatures", "ss02")
        lookup(f"Pass{iteration}Normalize", [f"sub acc {normalized};"], "normalizationContextWrappers", "ss02")
    for slot in range(4):
        for carry in (0, 1):
            lookup(f"Double{slot}c{carry}", [f"sub d{slot}v{v} by t{slot}v{2*v + carry};" for v in range(16)], "dependentSharedMappings")
    lookup("DependentLow", ["sub acc @D0' lookup Double0c1;"], "dependentContexts", "ss03")
    for slot in range(1, 4):
        prefix = " ".join(["acc"] + [f"@T{s}" for s in range(slot - 1)])
        lookup(f"Dependent{slot}", [f"sub {prefix} @Low{slot-1} @D{slot}' lookup Double{slot}c0;", f"sub {prefix} @Carry{slot-1} @D{slot}' lookup Double{slot}c1;"], "dependentContexts", "ss03")
    for slot in range(4):
        lookup(f"Publish{slot}", [f"sub t{slot}v{v} by o{slot}v{v % 16};" for v in range(32)], "publishDigitMappings")
    published = " ".join(f"@T{s}' lookup Publish{s}" for s in range(4))
    lookup("PublishDigits", [f"sub acc {published};"], "publishContexts", "ss04")
    lookup("PublishBase", ["sub acc by base;"], "publishBase", "ss04")
    feature = "languagesystem DFLT dflt;\n" + "\n".join(classes + definitions)
    for tag, labels in calls.items():
        feature += f"\nfeature {tag} {{ " + " ".join(f"lookup {label};" for label in labels) + f" }} {tag};\n"
    (directory / "program.fea").write_text(feature)
    builder = FontBuilder(1024, isTTF=True)
    builder.setupGlyphOrder(glyphs); builder.setupCharacterMap(cmap)
    empty = TTGlyphPen(None).glyph()
    outlines = {g: empty for g in glyphs}
    pen = TTGlyphPen(None); pen.moveTo((0, 0)); pen.lineTo((1, 0)); pen.lineTo((0, 1)); pen.closePath()
    outlines[".notdef"] = pen.glyph()
    builder.setupGlyf(outlines)
    builder.setupHorizontalMetrics({g: (metrics[g], 0) for g in glyphs})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    family = f"Partitioned{layout.title()}{width}"
    builder.setupNameTable({"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": family + "-v1", "fullName": family, "psName": family})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost(); builder.setupMaxp()
    # With disjoint slot alphabets FontTools can already choose format 2. Force
    # the format-3 baseline first so the layout comparison changes storage only.
    # Restrict this temporary override to substitution contexts in this build.
    original_build = ChainContextSubstBuilder.build
    def build_coverage_context(context):
        return context.buildLookup_([context.buildFormat3Subtable(rule, True)
                                     for ruleset in context.rulesets() for rule in ruleset.rules])
    ChainContextSubstBuilder.build = build_coverage_context
    try:
        addOpenTypeFeaturesFromString(builder.font, feature)
    finally:
        ChainContextSubstBuilder.build = original_build
    before = sum(s.SubTableCount for s in builder.font["GSUB"].table.LookupList.Lookup)
    packing = pack_contexts(builder.font) if layout == "packed" else None
    builder.font.save(directory / "weighted.ttf")
    builder.font.flavor = "woff2"; builder.font.save(directory / "weighted.woff2")
    lookups = builder.font["GSUB"].table.LookupList.Lookup
    result = {
        "id": identifier, "width": width, "topology": "slot-sequential-" + layout, "weights": weights,
        "fontFile": f"{identifier}/weighted.woff2", "fontFamily": family,
        "inputCodepoints": input_cps, "nonceCodepoint": 0xE800, "nonces": 65,
        "features": list(calls), "dependent": {"kind": "affine", "multiplier": 2, "bias": 1},
        "output": {"offset": 64 + 2*offset, "unitsPerEm": 1024, "fontSize": 1024},
        "disableControls": [{"feature": tag, "label": label} for tag, label in zip(calls, ("products and markers", "connected reduction", "dependent operation", "publication"))],
        "representation": {"digitGlyphs": 64, "temporaryDigitGlyphs": 128, "digitsPerNumber": 4, "radix": 16,
                           "alphabetScope": "digit slot shared across all operands and stages", "sumOffset": offset,
                           "signedSumMin": -offset, "signedSumMax": maximum, "Pmax": maximum+offset, "Qmax": 2*(maximum+offset)+1,
                           "inputAlphabetCount": 5, "markerGlyphs": ["acc", "operand", "consumed"], "maximumBacktrackGlyphs": 9,
                           "maximumAbsorptionLigatureComponents": 6, "invariant": "Exactly one accumulator marker followed by four slot-tagged digits; each remaining operand has four slot-tagged digits"},
        "structure": {"fontGlyphs": len(glyphs), "fontLookups": len(lookups), "topLevelLookups": sum(map(len, calls.values())),
                      "ruleCounts": counts, "ruleCountTotal": sum(counts.values()), "referencedSubtablesBeforePacking": before,
                      "referencedSubtables": sum(s.SubTableCount for s in lookups), "rawGsubBytes": len(builder.font.getTableData("GSUB")),
                      "reductionPasses": width-1, "inputTextGlyphs": width+1, "peakGlyphBuffer": 5*width+1,
                      "finalGlyphs": 6, "lookupCallsByFeature": calls, "packing": packing},
        "compilerSourceAtBuildSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "files": {},
    }
    for name in ("program.fea", "weighted.ttf", "weighted.woff2"):
        payload = (directory / name).read_bytes()
        result["files"][f"{identifier}/{name}"] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    (directory / "reference.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"{identifier}: glyphs={len(glyphs)} lookups={len(lookups)} subtables={result['structure']['referencedSubtables']} WOFF2={(directory/'weighted.woff2').stat().st_size}", flush=True)
    return result


def offline_check(variant, exhaustive=False):
    width = variant["width"]
    weights = variant["weights"]
    if exhaustive and width == 4:
        inputs = [[((n >> (4*i)) & 15)-8 for i in range(4)] for n in range(65536)]
    else:
        inputs = [[0]*width, [7]*width, [-8]*width,
                  [-8 if w > 0 else 7 for w in weights], [7 if w > 0 else -8 for w in weights]]
        for coordinate in (0, width//2, width-1):
            for value in (-8, 7):
                row = [0]*width; row[coordinate] = value; inputs.append(row)
        rng = random.Random(931867 + width)
        inputs.extend([[rng.randrange(-8, 8) for _ in range(width)] for _ in range(5)])
    ttf = OUT / variant["fontFile"].replace(".woff2", ".ttf")
    font, browser_font = TTFont(ttf), TTFont(OUT / variant["fontFile"])
    equivalent = {"GSUB": font.getTableData("GSUB") == browser_font.getTableData("GSUB"),
                  "cmap": font.getBestCmap() == browser_font.getBestCmap(), "glyphOrder": font.getGlyphOrder() == browser_font.getGlyphOrder(),
                  "metrics": font["hmtx"].metrics == browser_font["hmtx"].metrics}
    assert all(equivalent.values())
    text = "\n".join(chr(variant["nonceCodepoint"]) + "".join(chr(cp+x+8) for cp,x in zip(variant["inputCodepoints"], row)) for row in inputs) + "\n"
    command = ["/opt/homebrew/bin/hb-shape", str(ttf), "--features=ss01=1,ss02=1,ss03=1,ss04=1", "--output-format=json", "--no-clusters"]
    started = time.monotonic()
    shaped = subprocess.run(command, input=text, text=True, capture_output=True, check=True, timeout=180)
    lines = shaped.stdout.splitlines()
    assert len(lines) == len(inputs)
    failures = []
    for row, line in zip(inputs, lines):
        glyphs = json.loads(line)
        expected = 2*sum(w*x for w,x in zip(weights,row))+1+variant["output"]["offset"]
        actual = sum(g["ax"] for g in glyphs)
        sequence_ok = len(glyphs) == 6 and glyphs[0]["g"] == "nonce0" and glyphs[1]["g"] == "base" and all(glyphs[s+2]["g"].startswith(f"o{s}v") for s in range(4))
        if actual != expected or not sequence_ok:
            failures.append({"input": row, "expectedWidth": expected, "actualWidth": actual, "glyphs": glyphs})
    report = {"variant": variant["id"], "scope": "Installed HarfBuzz CLI sanity check, not native browser correctness or browser timing",
              "harfbuzzVersion": subprocess.run([command[0], "--version"], capture_output=True, text=True, check=True).stdout.strip(),
              "fontSha256": hashlib.sha256(ttf.read_bytes()).hexdigest(), "browserFontSha256": hashlib.sha256((OUT/variant["fontFile"]).read_bytes()).hexdigest(),
              "ttfWoff2Equivalence": equivalent, "cases": len(inputs), "exhaustive": exhaustive and width == 4,
              "failureCount": len(failures), "failures": failures[:8], "passed": not failures,
              "wallSecondsIncludingIOAndOracle": time.monotonic()-started, "stderr": shaped.stderr}
    (OUT / variant["id"] / "offline-check.json").write_text(json.dumps(report, indent=2)+"\n")
    print(f"offline {variant['id']}: {len(inputs)} cases, {len(failures)} failures", flush=True)
    assert not failures, variant["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--widths", nargs="+", type=int, default=[4])
    parser.add_argument("--layouts", nargs="+", choices=("coverage", "packed"), default=["coverage", "packed"])
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--offline-check", action="store_true")
    parser.add_argument("--exhaustive-four", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    reference_file = OUT / "reference.json"
    variants = json.loads(reference_file.read_text())["variants"] if args.append and reference_file.exists() else []
    for width in args.widths:
        for layout in args.layouts:
            variant = build(width, layout)
            variants = [v for v in variants if v["id"] != variant["id"]] + [variant]
            reference_file.write_text(json.dumps({"description": "Slot-scoped digit alphabets; unchanged arithmetic in coverage versus packed class-rule layouts", "variants": variants}, indent=2)+"\n")
            if args.offline_check:
                offline_check(variant, args.exhaustive_four)


if __name__ == "__main__":
    main()
