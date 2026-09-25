"""R4T: cap the number of view-timeline animations per consumer element.

Why (R4T.md §Results): in Blink the per-frame cost of a carrier whose width changed is not fixed —
it grows with the number of animations that share the consumer element: measured (2,000 changing
carriers, nested consumer chain) 110 µs at 2,000 animations/element, 61 at 1,000, 42 at 500, 29 at
250, 23 at 125, 19.7 at 62, 19.0 at 31, 19.8 at 15 => ≈18.5 µs + 0.046 µs x animations-per-element,
almost all of it in RunPaintLifecyclePhase self (PendingAnimations::Update) — the style pass itself is
≈10 µs per changed carrier regardless. combined4 puts 512 animations on every matvec/bridge consumer
(`.shared-qkv-cN`, `.shared-attn-cN`, `.shared-fc-cN`, `.cache-bridge-cN`, `.bN-bridge-cN`), 768 on
`.loop-reader` (R3R) and 256 on `.embedding-consumer-N`: ≈40 µs per changed carrier = R3A's measured
constant. Splitting the same animations over more nested consumer elements (each still an ancestor of
the readers, all registered numbers inherit) keeps every pass/frame identical and drops the constant to
≈20 µs. Knee = 64 animations per element (no further gain at 31 or 15).

Flag: R4T_CONSUMER_CHUNK = animations per consumer element (default 64; 0 = off, i.e. the old 512/768/256).
Sites: browser_gpt2_reused_core.py (h.matvec chunk, h.bridge chunk), r3r_fold_hop.py (.loop-reader ->
.loop-reader > .loop-reader-cK chain), browser_gpt2_embedding.py (.embedding-consumer-N step),
r2g_has_scope.py (LOOP_CHAIN gains the .loop-reader-cK steps). `.fvs-score-reader` (96 animations) is left
as is (predicted 21 vs 20 µs).
"""
import os

_raw = os.environ.get("R4T_CONSUMER_CHUNK", "64").strip().lower()
CHUNK = 0 if _raw in ("", "0", "false", "no", "off") else int(_raw)
ENABLED = CHUNK > 0


def chunk(default):
    """Animations per consumer element for a site whose historical chunk is `default`."""
    return min(CHUNK, default) if ENABLED else default


def loop_reader_classes(width):
    """Classes of the nested chunk elements between .loop-reader and .loop-input (outermost first)."""
    if not ENABLED:
        return []
    return [f"loop-reader-c{k}" for k in range(0, (width + CHUNK - 1) // CHUNK)]
