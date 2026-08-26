#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Reuse one small digit alphabet across all positions of a connected sum."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-reusable-digits"
WEIGHTS = (3, -2, 5, 1)


def build(width):
    weights = [WEIGHTS[i % 4] for i in range(width)]
    offset = -sum(min(w * x for x in range(-8, 8)) for w in weights)
    maximum = sum(max(w * x for x in range(-8, 8)) for w in weights)
    assert 2 * (maximum + offset) + 1 < 65536, "four-digit unsigned result overflow"
    identifier = f"reusable-w{width}"
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

    cls("D", [glyph(f"d{v}") for v in range(16)])
    cls("T", [glyph(f"t{v}") for v in range(32)])
    cls("Low", [f"t{v}" for v in range(16)])
    cls("Carry", [f"t{v}" for v in range(16, 32)])
    for label in ("acc", "operand", "consumed"):
        glyph(label)
    glyph("base", advance=64)
    for slot in range(4):
        cls(f"Out{slot}", [glyph(f"o{slot}v{v}", advance=v * 16**slot) for v in range(16)])
    for value in range(65):
        glyph(f"nonce{value}", cp=0xE800 + value)

    # Character alphabets depend on weight and seed/operand role, not input index.
    # Repeated weights reuse exactly the same characters and product glyphs.
    for alphabet in range(5):
        for value in range(16):
            glyph(f"i{alphabet}v{value}", cp=0xE000 + 16 * alphabet + value)
    input_cps = [0xE000] + [0xE010 + 16 * (i % 4) for i in range(1, width)]
    products = []
    for alphabet in range(5):
        weight = 3 if alphabet == 0 else WEIGHTS[alphabet - 1]
        minimum = min(weight * value for value in range(-8, 8))
        for encoded in range(16):
            value = weight * (encoded - 8) - minimum
            word = " ".join(f"d{value // 16**slot % 16}" for slot in range(4))
            products.append(f"sub i{alphabet}v{encoded} by {'acc' if alphabet == 0 else 'operand'} {word};")
    lookup("Products", products, "productRules", "ss01")
    for constant in range(17):
        lookup(f"Add{constant}", [f"sub d{value} by t{value + constant};" for value in range(16)], "sharedDigitAddition")
    lookup("MarkConsumed", [f"sub d{value} by consumed;" for value in range(16)], "sharedConsumedMapping")
    lookup("Normalize", [f"sub t{value} by d{value % 16};" for value in range(32)], "sharedNormalization")

    # Every pass has distinct top-level lookup IDs. Repeating a single lookup ID
    # in a feature would not guarantee repeated application by the shaper.
    for iteration in range(width - 1):
        for slot in range(4):
            rules = []
            for value in range(16):
                left = ["acc"] + ["@D"] * slot + [f"d{value}"] + ["@D"] * (3 - slot) + ["operand"]
                if slot:
                    left += ["@T"] * (slot - 1)
                    for carry in (0, 1):
                        rules.append("sub " + " ".join(left + ["@Carry" if carry else "@Low"]) + f" @D' lookup Add{value + carry};")
                else:
                    rules.append("sub " + " ".join(left) + f" @D' lookup Add{value};")
            lookup(f"Pass{iteration}Digit{slot}", rules, "digitContextWrappers", "ss02")
        lookup(f"Pass{iteration}Mark", ["sub acc @D' lookup MarkConsumed @D' lookup MarkConsumed @D' lookup MarkConsumed @D' lookup MarkConsumed operand;"], "consumedContextWrappers", "ss02")
        lookup(f"Pass{iteration}Absorb", ["sub acc consumed consumed consumed consumed operand by acc;"], "consumedLigatures", "ss02")
        lookup(f"Pass{iteration}Normalize", ["sub acc @T' lookup Normalize @T' lookup Normalize @T' lookup Normalize @T' lookup Normalize;"], "normalizationContextWrappers", "ss02")

    for carry in (0, 1):
        lookup(f"Double{carry}", [f"sub d{value} by t{2 * value + carry};" for value in range(16)], "dependentSharedMappings")
    lookup("DependentLow", ["sub acc @D' lookup Double1;"], "dependentContexts", "ss03")
    for slot in range(1, 4):
        prefix = " ".join(["acc"] + ["@T"] * (slot - 1))
        lookup(f"Dependent{slot}", [f"sub {prefix} @Low @D' lookup Double0;", f"sub {prefix} @Carry @D' lookup Double1;"], "dependentContexts", "ss03")
    for slot in range(4):
        lookup(f"Publish{slot}", [f"sub t{value} by o{slot}v{value % 16};" for value in range(32)], "publishDigitMappings")
    lookup("PublishDigits", ["sub acc @T' lookup Publish0 @T' lookup Publish1 @T' lookup Publish2 @T' lookup Publish3;"], "publishContexts", "ss04")
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
    family = f"ReusableDigits{width}"
    builder.setupNameTable({"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": family + "-v1", "fullName": family, "psName": family})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost(); builder.setupMaxp()
    addOpenTypeFeaturesFromString(builder.font, feature)
    builder.font.save(directory / "weighted.ttf")
    builder.font.flavor = "woff2"; builder.font.save(directory / "weighted.woff2")
    result = {
        "id": identifier, "width": width, "topology": "reusable-sequential", "weights": weights,
        "fontFile": f"{identifier}/weighted.woff2", "fontFamily": family,
        "inputCodepoints": input_cps, "nonceCodepoint": 0xE800, "nonces": 65,
        "features": list(calls), "dependent": {"kind": "affine", "multiplier": 2, "bias": 1},
        "output": {"offset": 64 + 2 * offset, "unitsPerEm": 1024, "fontSize": 1024},
        "disableControls": [{"feature": tag, "label": label} for tag, label in zip(calls, ("products and markers", "connected reduction", "dependent operation", "publication"))],
        "representation": {"digitGlyphs": 16, "temporaryDigitGlyphs": 32, "digitsPerNumber": 4, "radix": 16,
                           "sumOffset": offset, "signedSumMin": -offset, "signedSumMax": maximum,
                           "Pmax": maximum + offset, "Qmax": 2 * (maximum + offset) + 1,
                           "inputAlphabetCount": 5, "markerGlyphs": ["acc", "operand", "consumed"],
                           "maximumBacktrackGlyphs": 9, "maximumAbsorptionLigatureComponents": 6,
                           "invariant": "Exactly one acc marker; its four following digits hold the total. Each remaining operand marker precedes four unprocessed product digits."},
        "structure": {"fontGlyphs": len(glyphs), "fontLookups": len(builder.font["GSUB"].table.LookupList.Lookup),
                      "topLevelLookups": sum(len(v) for v in calls.values()), "ruleCounts": counts, "ruleCountTotal": sum(counts.values()),
                      "reductionPasses": width - 1, "inputTextGlyphs": width + 1,
                      "peakGlyphBuffer": 5 * width + 1, "finalGlyphs": 6,
                      "lookupCallsByFeature": calls},
        "compilerSourceAtBuildSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "files": {},
    }
    for name in ("program.fea", "weighted.ttf", "weighted.woff2"):
        payload = (directory / name).read_bytes()
        result["files"][f"{identifier}/{name}"] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    (directory / "reference.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"{identifier}: glyphs={len(glyphs)} lookups={result['structure']['fontLookups']} WOFF2={(directory / 'weighted.woff2').stat().st_size}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--widths", type=int, nargs="+", default=[4])
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    reference_file = OUT / "reference.json"
    variants = json.loads(reference_file.read_text())["variants"] if args.append and reference_file.exists() else []
    new_variants = [build(width) for width in args.widths]
    replaces = {v["id"] for v in new_variants}
    variants = [v for v in variants if v["id"] not in replaces] + new_variants
    old_root = ROOT / "experiments/gsub-weighted-sum-probe"
    old = json.loads((old_root / "reference.json").read_text())
    widths = {v["width"] for v in variants}
    for original in old["variants"]:
        if original["topology"] != "sequential" or original["width"] not in widths:
            continue
        retained = dict(original)
        retained["id"] = "retained-" + original["id"]
        retained["topology"] = "retained-sequential"
        retained["fontFile"] = "retained/" + original["fontFile"]
        target = OUT / retained["fontFile"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_root / original["fontFile"], target)
        retained["retainedOriginalFontFile"] = str((old_root / original["fontFile"]).relative_to(ROOT))
        retained["retainedFontSha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        retained["retainedOriginalBuildFiles"] = retained.pop("files")
        retained["files"] = {retained["fontFile"]: {"bytes": target.stat().st_size, "sha256": retained["retainedFontSha256"]}}
        variants = [v for v in variants if v["id"] != retained["id"]] + [retained]
    reference_file.write_text(json.dumps({"description": "Reusable digit and marker alphabet versus retained position-specific sequential sum", "variants": variants}, indent=2) + "\n")


if __name__ == "__main__":
    main()
