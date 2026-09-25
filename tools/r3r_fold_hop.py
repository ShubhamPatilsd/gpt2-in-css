"""R3R (2026-09-20): fold the loop-transport hop into the proj readback.

Flag (default ON): R3R_FOLD_HOP=0 restores the two loop banks (769 carriers each,
769 latch transitions per layer) and the separate loop readback pass.

Mechanism (work/2026-09-19/R3R.md §1): per layer the reused core needs seven
geometry->number hops; the seventh (proj carriers -> `--out = r + proj` on the
proj consumers) is followed by a pure *transport* hop (`--out` -> loop-bank
carriers -> `.loop-reader` -> `--x`) whose only job is to carry 768 numbers
from depth ~47 up to depth ~13 and to hold them for a layer (two-bank latch).

Here the proj carriers themselves publish the layer output at the loop bank's
encoding: carrier i gets

    width: calc-size(max-content, 262144px + --pc-i * 1px + size * --pk-i)

with per-layer constants declared on `.shared-proj` (same layer block as the
proj weights):  --pk-i = 128 * s_i * UPM/FS * range,
                --pc-i = 128 * (r_i + b_i - base_i * s_i * range),
so that width = 262144 + 128 * (r_i + ((size*UPM/FS - base_i) * s_i * range + b_i))
             = 262144 + 128 * out_i            (the loop bank's `262144px + v*128px`).

The proj timelines (+ the proj generation marker) are scoped on `html`; the
existing `.loop-reader` reads the 768 proj carriers directly (`--lp-i`, private,
F5 forward to `.loop-input`) and `.loop-input` decodes `--loop-in-i` with the
loop bank's exact centered formula. `.core-pass-reader` reads the proj marker:
`--pass = min(marker + 1, --pass-cap)`.

Why no latch is needed: the proj stage sits under the fc gate (and the attn,
cache-bridge, qkv gates above it). Within a pass P the gates close in cascade
one hop after the previous gate opens (each receipt is restyled for the first
time in P only when its parent gate opens and then closes its own gate because
its stamp still reads P-1), so the proj stage is restyled/laid out exactly once
per pass, in the fc-readback pass (C2), with the final `--r` and `--hidden`.
Its carriers hold out_P from that layout until C2 of pass P+1; the top-level
readers see the change once, in the pass after C2's layout (= the old proj
readback pass D1), which is where `--pass` advances and S1 of P+1 runs.

Token boundary: `--pass` is capped at 12k while the head runs; with a single
carrier set `--loop-in` would already show out_{12k} in that pass, so the core
is display-locked while held (`--held: marker >= cap` -> `--loop-ready: 0`) and
the layer-11 export (`.reused-final-export`, bridge carriers reading
`--loop-in-*`) moves out of the locked subtree to `.loop-input` and is shown
only while held (it used to be shown at --layer:11 under the proj gate).
"""

import os

import r4t_consumer_chunk as r4t
import r5e_dead_weight as r5e
from build_pretrained_gpt2 import css_number as num


def flag(name):
    return os.environ.get(name, "1") not in ("0", "false", "no", "off")


FOLD_HOP = flag("R3R_FOLD_HOP")

# Loop-bank encoding, reused verbatim: viewport 524288, track 1572864, carrier width
# 262144 + 128 * value, centered progress keyframes (-2 -> 1).
VIEWPORT = 524288
OFFSET = 262144
SCALE = 128
MARKER_BASE = VIEWPORT // 4  # 131072; marker width = base + pass * 1024

DECODE = "(1572864 / (var({p}) + 2) - 524288 - 262144) / 128"
MARKER_DECODE = "round(nearest,(1572864 / (var(--pr-stamp) + 2) - 524288 - 131072) / 1024,1)"
# progress of a marker laid out with pass 0: p = vp / (vp + vp/4) = 0.8 -> centered 3p - 2 = 0.4
MARKER_INITIAL = "0.4"

STAGE = "proj"
TIMELINE = "--shared-proj-t{i}"
MARKER_TIMELINE = "--shared-proj-generation"


def reader_names(width):
    return [f"--lp-{i}" for i in range(width)]


def carrier_width(i):
    """Inline width of proj carrier i (layer independent; constants come from .shared-proj)."""
    return f"width:calc-size(max-content,{OFFSET}px + var(--pc-{i:03d}) * 1px + size * var(--pk-{i:03d}))"


def stage_constants(stem, bases, scales, biases, units_per_em, font_size):
    """Per-layer declarations on the proj stage element (inside its layer block)."""
    decls = []
    for i, (base, s, bias) in enumerate(zip(bases, scales, biases)):
        decls.append(
            f"--pk-{i:03d}:calc(var(--range-{STAGE}) * {num(SCALE * float(s) * units_per_em / font_size)})"
        )
        decls.append(
            f"--pc-{i:03d}:calc((var(--r-{i:03d}) + ({num(bias)}) - {int(base)} * {num(s)} * var(--range-{STAGE})) * {SCALE})"
        )
    return f".{stem}{{{';'.join(decls)}}}"


def constant_regs(count):
    return "".join(
        f'@property --{k}-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for k in ("pk", "pc")
        for i in range(count)
    )


def loop_parts(width, blocks, capacity):
    """Replacement for probe_native_reused_loop.loop_parts(): no banks, no SMIL relay."""
    css = "".join(
        f'@property {p}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for p in ["--pass", "--loop-ready"] + [f"--loop-in-{i}" for i in range(width)] + reader_names(width)
    )
    css += (
        '@property --held{syntax:"<number>";inherits:false;initial-value:0}'
        '@property --pass-cap{syntax:"<number>";inherits:false;initial-value:0}'
        f'@property --pr-stamp{{syntax:"<number>";inherits:false;initial-value:{MARKER_INITIAL}}}'
    )
    # the controller (`body` here; the adapter renames it to .core-controller)
    css += (
        f"body{{--pass:min(calc({MARKER_DECODE} + 1),var(--pass-cap));--pass-cap:{blocks};--pr-stamp:inherit;"
        f"--held:clamp(0,calc({MARKER_DECODE} - var(--pass-cap) + 1),1);container-name:loopcontrol}}"
    )
    css += (
        ".core-pass-reader{animation-name:prstamp;animation-duration:1s;animation-timing-function:linear;"
        f"animation-fill-mode:both;animation-timeline:{MARKER_TIMELINE};animation-range:cover}}"
        "@keyframes prstamp{from{--pr-stamp:-2}to{--pr-stamp:1}}"
    )
    css += "".join(f"@keyframes lpk{i}{{from{{--lp-{i}:-2}}to{{--lp-{i}:1}}}}" for i in range(width))
    chunk_classes = r4t.loop_reader_classes(width)
    if chunk_classes:
        # R4T: the 768 reader animations spread over nested .loop-reader-cK elements (≤ R4T_CONSUMER_CHUNK each);
        # --lp-* are inherited registered numbers, so .loop-input reads them unchanged.
        for k, cls in enumerate(chunk_classes):
            ids = range(k * r4t.CHUNK, min(width, (k + 1) * r4t.CHUNK))
            # --lp-* are registered inherits:false by the core's scoped_state and forwarded with `inherit` at .loop-input
            # (one level): every chunk element must forward the earlier chunks' values so the innermost one holds all of them.
            forward = "" if r5e.LP_INHERIT else "".join(f";--lp-{i}:inherit" for i in range(0, k * r4t.CHUNK))  # R5E
            css += (
                f".{cls}{{animation-name:"
                + ",".join(f"lpk{i}" for i in ids)
                + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
                + ",".join(TIMELINE.format(i=i) for i in ids)
                + ";animation-range:cover" + forward + "}"
            )
    else:
        css += (
            ".loop-reader{animation-name:"
            + ",".join(f"lpk{i}" for i in range(width))
            + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
            + ",".join(TIMELINE.format(i=i) for i in range(width))
            + ";animation-range:cover}"
        )
    css += (
        ".loop-input{"
        + ";".join(f"--loop-in-{i}:calc({DECODE.format(p=f'--lp-{i}')})" for i in range(width))
        + ";--loop-ready:1}"
        "@container loopcontrol style(--held:1){.loop-input{--loop-ready:0}}"
    )
    css += ".loop-signals{position:fixed;width:1px;height:1px;top:0;left:0}"
    css += (
        ".loop-input{container-name:loopreceipt}.loop-compute{content-visibility:hidden;contain-intrinsic-size:0px 0px}"
        "@container loopreceipt style(--loop-ready:1){.loop-compute{content-visibility:visible}}"
    )
    for token in range(1, capacity):
        css += f"body:has(#token-{token}-advanced.done){{--pass-cap:{(token + 1) * blocks}}}"
    source = (
        '<div class="loop-reader">'
        + "".join(f'<div class="{cls}">' for cls in chunk_classes)
        + '<div class="loop-input"><svg class="loop-signals"></svg>'
        '<div class="loop-compute">{child}</div></div>'
        + "</div>" * len(chunk_classes)
        + "</div>"
    )
    return source, "{child}", css


def move_export(body, css, export, last):
    """Put the layer-11 export beside .loop-compute, reading --loop-in-*, shown only while held."""
    import re

    export = re.sub(r"--out-(\d{3})", lambda m: f"--loop-in-{int(m[1])}", export)
    needle = '<svg class="loop-signals"></svg>'
    if body.count(needle) != 1:
        raise ValueError("R3R: expected one svg.loop-signals")
    body = body.replace(needle, needle + export)
    css += ".reused-final-export{display:none}@container loopcontrol style(--held:1){.reused-final-export{display:block}}"
    return body, css
