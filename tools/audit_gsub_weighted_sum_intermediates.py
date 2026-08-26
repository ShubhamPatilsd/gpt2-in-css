#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Inspect every fanout channel before channel-combination in the built font.

One hb-shape subprocess receives all 65,536 lines. This is an independent
HarfBuzz CLI observation, not an observation of Chromium's intermediate state.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-weighted-sum-probe"
# Deliberately independent of the compiler module and its final collapsed row.
EXPECTED_MATRIX = ((3, -2, 5, 1), (-1, 4, 2, -3), (2, 1, -2, 5), (5, -2, 1, 2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hb-shape", default="/opt/homebrew/bin/hb-shape")
    args = parser.parse_args()
    reference = json.loads((OUT / "w4-fanouttree/reference.json").read_text())
    browser_font = OUT / reference["fontFile"]
    font = browser_font.with_suffix(".ttf")
    # This hb-shape build does not accept WOFF2. Check that the original TTF
    # supplies exactly the same substitutions, input mapping and metrics.
    ttf, woff2 = TTFont(font), TTFont(browser_font)
    equivalence = {
        "GSUBTableIdentical": ttf.getTableData("GSUB") == woff2.getTableData("GSUB"),
        "glyphOrderIdentical": ttf.getGlyphOrder() == woff2.getGlyphOrder(),
        "cmapIdentical": ttf.getBestCmap() == woff2.getBestCmap(),
        "horizontalMetricsIdentical": ttf["hmtx"].metrics == woff2["hmtx"].metrics,
    }
    assert all(equivalence.values()), equivalence
    offsets = [-sum(min(w * x for x in range(-8, 8)) for w in row) for row in EXPECTED_MATRIX]
    assert reference["representation"]["channelWeightMatrix"] == [list(row) for row in EXPECTED_MATRIX]
    assert reference["representation"]["channelOffsets"] == offsets
    inputs = [tuple(((code >> (4 * i)) & 15) - 8 for i in range(4)) for code in range(65536)]
    text = "\n".join(chr(reference["nonceCodepoint"]) + "".join(chr(cp + x + 8) for cp, x in zip(reference["inputCodepoints"], values))
                     for values in inputs) + "\n"
    features = "ss01=1,ss02=1,ss03=0,ss04=0,ss05=0"
    command = [args.hb_shape, str(font), "--features=" + features, "--output-format=json",
               "--no-clusters", "--no-positions", "--no-advances"]
    started = time.monotonic()
    shaped = subprocess.run(command, input=text, text=True, capture_output=True, check=True)
    lines = shaped.stdout.splitlines()
    assert len(lines) == len(inputs), (len(lines), len(inputs))
    pattern = re.compile(r"n6d(\d+)v(\d+)")
    failures = []
    channel_checks = [0] * 4
    examples = []
    for index, (values, line) in enumerate(zip(inputs, lines)):
        glyphs = json.loads(line)
        if len(glyphs) != 17 or glyphs[0]["g"] != "nonce0":
            failures.append({"input": values, "reason": "wrong number/order of intermediate glyphs", "glyphs": glyphs})
            continue
        digits = []
        for slot, glyph in enumerate(glyphs[1:]):
            match = pattern.fullmatch(glyph["g"])
            if not match or int(match[1]) != slot or not 0 <= int(match[2]) <= 15:
                failures.append({"input": values, "reason": "unexpected intermediate glyph tag", "glyph": glyph, "slot": slot})
                break
            digits.append(int(match[2]))
        if len(digits) != 16:
            continue
        decoded = [sum(digits[channel * 4 + slot] * 16 ** slot for slot in range(4)) - offsets[channel]
                   for channel in range(4)]
        expected = [sum(w * x for w, x in zip(row, values)) for row in EXPECTED_MATRIX]
        for channel in range(4):
            channel_checks[channel] += 1
            if decoded[channel] != expected[channel]:
                failures.append({"input": values, "channel": channel, "actual": decoded[channel], "expected": expected[channel]})
        if index in (0, 1, 0x8888, 0xFFFF, 0x1234):
            examples.append({"input": values, "channelOutputs": decoded, "expected": expected,
                             "glyphs": [g["g"] for g in glyphs]})
    result = {
        "description": "Exhaustive internal four-channel check of the same fanout font before channel summation",
        "scope": "HarfBuzz CLI internal glyph observation, separate engine build from Chromium. Native Chromium final output is tested by the browser harness.",
        "harfbuzzVersion": subprocess.run([args.hb_shape, "--version"], text=True, capture_output=True, check=True).stdout.strip(),
        "fontFile": str(font.relative_to(ROOT)), "fontSha256": hashlib.sha256(font.read_bytes()).hexdigest(),
        "browserFontFile": str(browser_font.relative_to(ROOT)), "browserFontSha256": hashlib.sha256(browser_font.read_bytes()).hexdigest(),
        "ttfToBrowserWoff2Equivalence": equivalence,
        "verifierSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "features": features, "expectedGlyphSequence": "nonce0 followed by n6d0v{0..15} through n6d15v{0..15}",
        "oracleMatrix": EXPECTED_MATRIX, "channelOffsets": offsets,
        "inputCases": len(inputs), "channelChecks": channel_checks, "totalChannelChecks": sum(channel_checks),
        "failureCount": len(failures), "failures": failures[:20], "examples": examples,
        "wallSecondsIncludingShapingAndAudit": time.monotonic() - started,
        "performanceInterpretation": "This wall time includes subprocess IO and Python checking; it is not a browser performance measurement.",
        "stderr": shaped.stderr,
    }
    (OUT / "fanout-intermediate-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("inputCases", "totalChannelChecks", "failureCount", "wallSecondsIncludingShapingAndAudit")}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
