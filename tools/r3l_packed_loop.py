"""R3L (2026-09-20): fewer loop-bank latch transitions — 2 per bank instead of 769.

Flags:
  R3L_FONT_LOOP   (default ON)  ONE `*` font-variation-settings list per bank (+ the epoch) latched by a single
                                `transition-behavior:allow-discrete` transition (F4's `--head-fvs` idiom); the 768
                                values leave the bank as glyph advances of the loop-carrier fonts (var()-free).
  R3L_PACKED_LOOP (default OFF) 384 packed 2 x 26-bit `<number>` pairs — NUMERICALLY WRONG in Blink: `var()`
                                substitutes a registered <number> as text with 6 significant digits (R3L fixture,
                                R3L.md §2), so a 52-bit packed integer decodes to garbage. Kept for the record.

Why (work/2026-09-19/R2A.md §3, R3L.md): the loop banks hold the residual vector between layers as 769 registered
`<number>`s per bank; at every phase flip 769 delayed transitions START on the new read bank and 769 are cancelled
on the new write bank (≈218 µs style + ≈107 µs paint lifecycle per start in the demo ≈ 0.25 s/layer ≈ 3 s/token).
The fixture confirmed the cost is per started transition (385 starts: −11 ms style, −7.5 ms paint, −22 ms busy per
flip; list length is not the cost — 8 shorter lists on 8 elements were slower).

Font-axis carrier: HarfBuzz rounds HVAR-varied advances to integer font units and deltas are int16, so one glyph
carries ≤ 16 bits; each carrier <i> therefore holds two glyphs whose advances add: hi (k_hi units at font-size
512 px, UPM 256 → 2 px/unit, repeated 32× — HarfBuzz caps one advance at 32768 px) and lo (k_lo units at 4 px → 1/64 px/unit). Each glyph responds to its own axis
("H%03X"/"L%03X", global value index) with delta 16384 over the normalised range, with a ZERO base advance, i.e. advance = k units for
an integer axis value k ∈ [0, 16384] (fvar maxValue patched to 16384 so the list carries exact integers — integers
survive the 6-digit var() serialisation). ≤ 256 axes per font (the tested browser path) → 6 fonts × 128 values.
Write side (typed numbers on the bank; s = (v + 2048)·2 = today's width / 64 px):
  k_hi = clamp(0, round(down, s, 1), 16383);  k_lo = clamp(0, round(down, (s − k_hi) · 4096, 1), 4095)
Carrier width = max-content = 32·2·k_hi + k_lo/64 = 64·k_hi + k_lo/64 px = today's `262144px + v·128px`
truncated to the 1/64-px LayoutUnit grid (today: float32 then truncation — equal or ±1 LayoutUnit). Read side
(timelines, `--lp-*`, `.loop-input` decodes, R2F pass markers) unchanged.
"""

import hashlib
import os
from pathlib import Path


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


FONT_LOOP = flag("R3L_FONT_LOOP")
PACKED_LOOP = flag("R3L_PACKED_LOOP", "0")
if FONT_LOOP and PACKED_LOOP:
    raise ValueError("R3L: set at most one of R3L_FONT_LOOP / R3L_PACKED_LOOP")

WIDTH = 768
PER_FONT = 128
FONTS = WIDTH // PER_FONT
DELTA = BASE_UNITS = 16384
UPM = 256
HI_PX, LO_PX = 512, 4                        # font sizes: 2 px/unit (x32 copies -> 64 px per k_hi) and 1/64 px/unit
HI_COPIES = 32                               # HarfBuzz caps ONE glyph advance at 32768 px (16.16 positions); 32 x 32766 covers 2^20 px
ASSETS = Path(__file__).resolve().parents[1] / "loop-carrier-assets"   # not under the `assets` symlink (-> F4)

# ---- numeric packing (R3L_PACKED_LOOP; wrong in Blink, see module docstring)
M26, MAXQ, SCALE, OFFSET = 67108864, 67108863, 8192, 2048


def pairs(width):
    if width % 2:
        raise ValueError("R3L packing needs an even vector width")
    return width // 2


def quantize(src):
    return f"clamp(0,round(nearest,({src} + {OFFSET}) * {SCALE},1),{MAXQ})"


def pack(src_hi, src_lo):
    return f"calc({quantize(src_hi)} * {M26} + {quantize(src_lo)})"


def _packed_carrier_style(bank, i, width):
    if i == width:
        return f"--saved-{bank}-{width}:inherit;width:calc(262144px + var(--saved-{bank}-{width}) * 128px)"
    p = f"var(--sv-{bank}-{i // 2})"
    hi = f"round(down,{p} / {M26},1)"
    body = f"calc({hi} * 0.015625px)" if i % 2 == 0 else f"calc(({p} - {hi} * {M26}) * 0.015625px)"
    return f"--sv-{bank}-{i // 2}:inherit;width:{body}"


# ---- shared API used by probe_native_reused_loop / browser_gpt2_reused_core
def active(width):
    return (FONT_LOOP or PACKED_LOOP) and width == WIDTH


def latched_names(bank, width):
    """The bank's transition-property list."""
    if FONT_LOOP:
        return [f"--lst-{bank}", f"--saved-{bank}-{width}"]
    return [f"--sv-{bank}-{j}" for j in range(pairs(width))] + [f"--saved-{bank}-{width}"]


def private_names(width):
    """Registered helper properties that must stay non-inherited."""
    if FONT_LOOP:
        return [f"--l{h}-{b}-{i}" for b in range(2) for i in range(width) for h in "hl"] + [f"--lst-{b}" for b in range(2)]
    return []


def registrations(width):
    """@property rules for the latched values (replaces the 2 x 769 `--saved-b-i` <number> registrations)."""
    if FONT_LOOP:
        css = "".join(f'@property --saved-{b}-{width}{{syntax:"<number>";inherits:false;initial-value:0}}' for b in range(2))
        css += "".join(f'@property --lst-{b}{{syntax:"*";inherits:false;initial-value:"H000" 0}}' for b in range(2))
        css += "".join(f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}' for p in private_names(width) if p.startswith("--l") and not p.startswith("--lst"))
        return css
    return "".join(f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}' for b in range(2) for p in latched_names(b, width))


def transition_extra():
    return ";transition-behavior:allow-discrete" if FONT_LOOP else ""


def write_declarations(bank, width, epoch_source):
    """Write-bank declarations (inside `@container loopcontrol style(--loop-phase:b)`)."""
    if FONT_LOOP:
        decls = []
        for i in range(width):
            s = f"(var(--loop-out-{i}) + 2048) * 2"
            decls.append(f"--lh-{bank}-{i}:clamp(0,round(down,{s},1),16383)")
            decls.append(f"--ll-{bank}-{i}:clamp(0,round(down,({s} - round(down,{s},1)) * 4096,1),4095)")
        decls.append(f"--lst-{bank}:" + ",".join(f'"H{i:03X}" var(--lh-{bank}-{i}),"L{i:03X}" var(--ll-{bank}-{i})' for i in range(width)))
        decls.append(f"--saved-{bank}-{width}:{epoch_source}")
        return decls
    decls = [f"--sv-{bank}-{j}:{pack(f'var(--loop-out-{2 * j})', f'var(--loop-out-{2 * j + 1})')}" for j in range(pairs(width))]
    decls.append(f"--saved-{bank}-{width}:{epoch_source}")
    return decls


def carrier_markup(bank, i, width, timeline):
    """The whole carrier element (incl. the F5 explicit forward of its non-inherited latched property)."""
    if FONT_LOOP and i < width:
        local = i % PER_FONT
        return (f'<i class="loop-metric lf-{i // PER_FONT}" style="width:max-content;view-timeline:{timeline} inline">'
                f'<b class="lh">{f"&#x{0xE000 + 2 * local:X};" * HI_COPIES}</b><b class="ll">&#x{0xE001 + 2 * local:X};</b></i>')
    if FONT_LOOP:
        style = f"--saved-{bank}-{width}:inherit;width:calc(262144px + var(--saved-{bank}-{width}) * 128px)"
    else:
        style = _packed_carrier_style(bank, i, width)
    return f'<i class="loop-metric" style="{style};view-timeline:{timeline} inline"></i>'


def style_css():
    if not FONT_LOOP:
        return ""
    css = font_faces_css()
    css += "".join(f".lf-{k}{{font-family:LoopCarrier{k}}}" for k in range(FONTS))
    css += (".loop-metric{white-space:pre;line-height:1;font-kerning:none;letter-spacing:0;word-spacing:0}"
            f".lh{{font-size:{HI_PX}px}}.ll{{font-size:{LO_PX}px}}")
    css += "".join(f".loop-bank-{b}>.loop-scroll>.loop-track{{font-variation-settings:var(--lst-{b})}}" for b in range(2))
    return css


# ---- fonts
def _tags(font_index):
    out = []
    for local in range(PER_FONT):
        i = font_index * PER_FONT + local
        out += [f"H{i:03X}", f"L{i:03X}"]
    return out


def ensure_fonts():
    """Build the 6 loop-carrier woff2 files once (deterministic; fontTools HVAR via build_matrix_backend_prototypes)."""
    # TrueType, not WOFF2: Chrome's WOFF2 decoder rejects these 256-axis fonts ("Failed to convert WOFF 2.0 font to
    # SFNT", even the builder's own untouched woff2 — R3L fontprobe bisect); the TTF loads and varies correctly.
    paths = [ASSETS / f"loop-carrier-{k}.ttf" for k in range(FONTS)]
    if all(p.exists() for p in paths):
        return paths
    import numpy as np
    from fontTools.ttLib import TTFont
    import build_matrix_backend_prototypes as bm

    ASSETS.mkdir(parents=True, exist_ok=True)
    for k, path in enumerate(paths):
        # 256 value glyphs (hi_i <- H_i, lo_i <- L_i, delta 16384, ZERO base advance) + 1 static witness glyph (U+E100) for font_barrier
        weights = np.zeros((2 * PER_FONT + 1, 2 * PER_FONT), dtype=np.int16)
        for g in range(2 * PER_FONT):
            weights[g, g] = DELTA
        ttf = path.with_name(f"build-{k}.ttf")
        bm.build_direct_font_backend(weights, ttf, base_advance=BASE_UNITS, axis_tags=_tags(k))
        font = TTFont(ttf, recalcTimestamp=False)
        font["head"].unitsPerEm = UPM
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
        for name in font.getGlyphOrder()[1:1 + 2 * PER_FONT]:
            font["hmtx"][name] = (0, font["hmtx"][name][1])
        font["post"].formatType = 3.0  # no glyph names
        font.save(path)
        ttf.unlink()
        for stray in (ttf.with_suffix(".woff2"),):
            if stray.exists():
                stray.unlink()
    return paths


def font_faces_css():
    css = ""
    for k, path in enumerate(ensure_fonts()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        css += f'@font-face{{font-family:LoopCarrier{k};src:url("file://{path}?v={digest}") format("truetype")}}'
    return css
