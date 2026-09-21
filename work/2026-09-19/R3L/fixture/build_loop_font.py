#!/usr/bin/env python3
"""R3L: loop-carrier fonts — a var()-free transport for the latched residual vector.

HarfBuzz rounds HVAR-varied advances to integer font units and deltas are int16, so one glyph carries <= 16 bits;
a carrier <i> therefore holds TWO glyphs whose advances add: hi_i (units = k_hi, font-size 512 px at UPM 256 -> 2 px/unit, repeated 32x) and lo_i (units = k_lo, font-size 4 px -> 1/64 px/unit). Each glyph responds to its own axis
("H%03X" / "L%03X", global value index) with delta 16384 over the normalised range, i.e. advance = 16384 + k for an
axis value k in [0, 16384] (fvar maxValue patched to 16384 so the settings list carries exact integers).
The browser path accepts <= 256 axes per font -> 128 values (256 glyphs, 256 axes) per font, 6 fonts for 768.
Glyph codepoints: hi_i = U+E000 + 2*(i % 128), lo_i = U+E001 + 2*(i % 128).
Width of a carrier = 64*k_hi + k_lo/64 + BASE_PX px with BASE_PX = 16384*64 + 16384/64 = 1048832.
usage: build_loop_font.py <out-dir>  (writes loop-carrier-{0..5}.ttf and verifies advances with uharfbuzz)
"""
import sys
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_matrix_backend_prototypes as bm  # noqa: E402

W, PER_FONT, DELTA, UPM = 768, 128, 16384, 256
BASE_UNITS = 16384
BASE_PX = BASE_UNITS * 64 + BASE_UNITS / 64  # 1048832.0


def tags(font_index):
    out = []
    for local in range(PER_FONT):
        i = font_index * PER_FONT + local
        out += [f"H{i:03X}", f"L{i:03X}"]
    return out


def build(out):
    out.mkdir(parents=True, exist_ok=True)
    bm.UNITS_PER_EM = UPM
    for f in range(W // PER_FONT):
        # 256 value glyphs (hi_i <- axis H_i, lo_i <- axis L_i, delta 16384) + 1 witness glyph (U+E100, static advance)
        weights = np.zeros((2 * PER_FONT + 1, 2 * PER_FONT), dtype=np.int16)
        for g in range(2 * PER_FONT):
            weights[g, g] = DELTA
        path = out / f"loop-carrier-{f}.ttf"
        bm.build_direct_font_backend(weights, path, base_advance=BASE_UNITS, axis_tags=tags(f))
        font = TTFont(path)
        font["head"].unitsPerEm = UPM  # advances stay in units; px = units * font-size / UPM
        for axis in font["fvar"].axes:
            axis.maxValue = 16384
        # advance-only glyphs: empty outlines (Chrome's WOFF2 decoder rejected the transformed glyf/hmtx of the
        # post-edited outlines: "Failed to convert WOFF 2.0 font to SFNT"); no WOFF2 table transforms either
        from fontTools.ttLib.tables._g_l_y_f import Glyph
        glyf = font["glyf"]
        for name in font.getGlyphOrder():
            glyf[name] = Glyph()
        font["head"].xMin = font["head"].yMin = font["head"].xMax = font["head"].yMax = 0
        for name in font.getGlyphOrder():
            font["hmtx"][name] = (font["hmtx"][name][0], 0)
        order = font.getGlyphOrder()
        for name in order[1:1 + 2 * PER_FONT]:      # value glyphs: base 0 -> advance = k units (HarfBuzz caps one advance at 32768 px)
            font["hmtx"][name] = (0, font["hmtx"][name][1])
        font.save(path)
    return [out / f"loop-carrier-{f}.ttf" for f in range(W // PER_FONT)]


def verify(paths):
    import uharfbuzz as hb
    rng = np.random.default_rng(1)
    worst = 0
    for f, path in enumerate(paths):
        blob = hb.Blob.from_file_path(str(path))
        face = hb.Face(blob)
        font = hb.Font(face)
        font.scale = (UPM, UPM)  # 1 unit = 1 hb position unit
        for trial in range(64):
            k = rng.integers(0, 16384, size=2 * PER_FONT)
            font.set_variations({t: int(v) for t, v in zip(tags(f), k)})
            for local in rng.integers(0, PER_FONT, size=8):
                for part in range(2):
                    buf = hb.Buffer()
                    buf.add_str(chr(0xE000 + 2 * local + part))
                    buf.guess_segment_properties()
                    hb.shape(font, buf)
                    adv = buf.glyph_positions[0].x_advance
                    exp = int(k[2 * local + part])
                    worst = max(worst, abs(adv - exp))
                    if adv != exp:
                        raise SystemExit(f"font {f} glyph {local}/{part}: advance {adv} != {exp}")
    print(f"uharfbuzz check: 6 fonts x 64 random axis vectors x 16 glyphs — all advances exact (worst |Δ| {worst} units)")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent / "pages" / "fonts")
    paths = build(out)
    print("built", [p.name for p in paths], "sizes", [p.stat().st_size for p in paths])
    verify(paths)
