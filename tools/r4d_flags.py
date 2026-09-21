"""R4D (2026-09-20): flatten the capacity-32 cost of the font-vector KV attention
without changing the model. Every change is an environment flag:

  R4D_EMPTY_UNFILLED=0  keep the full 768-axis zero list as the registered initial
                        value of the `*` KV lists (--fc-k/v-*, --fr-k/v-*);
                        ON: a one-axis `"K000" 0` / `"V000" 0` list. Unfilled slots
                        are never aliased (F5 filter), so their 768·(cap-p) V glyph
                        leaves and 12·(cap-p) score glyphs substitute 12 B instead of
                        ~7.7 KB. Exact: every fvar axis of the operator fonts defaults
                        to 0, so an omitted axis equals an explicit 0.
  R4D_LEAN_LATCH=0      keep the 26·capacity-name `transition-property` lists;
                        ON (full causal window only): at write-slot W the banks list
                        only the fields of slots 0..W (write rule: 0..W-1). Slots > W
                        were never written, have no running transition to retain, and
                        (css-transitions §3) nothing is cancelled by unlisting them.
  R4D_UNPACK_V=0        keep F4's one 768-axis V list per slot (1 latch);
                        ON: 12 per-head 64-axis V lists per slot (12 latches, 37 per
                        slot instead of 26). Each V glyph then substitutes and parses
                        its own head's 65-axis list instead of 769 axes. Same entries
                        (var(--fvn-v-H-i)), same tags, same fonts: exact.
  R4D_HIDE_UNFILLED=0   keep the 768·(cap-p) unfilled V glyph leaves laid out (advance =
                        base, weight 0); ON (full causal window only): unfilled slots' leaves
                        are display:none and the row formula subtracts (W+1)·base instead of
                        capacity·base (--fvs-nbase). Same arithmetic; the only difference is
                        that the LayoutUnit-snapped base advance of an absent glyph
                        (12320.78125 vs 12320.768 px) no longer enters `size` — a bias of
                        ≤ 31/64 px ≈ 4e-5·fb/fd ctx units that the NumPy reference never had.
  R4D_GATE_SCORES=1     (default OFF) display:none the score carriers of unfilled
                        slots (their view-timelines go inactive). Masked numerically
                        by --fv-S already; timing of timeline re-activation untested.
"""

import os


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


EMPTY_UNFILLED = flag("R4D_EMPTY_UNFILLED")
LEAN_LATCH = flag("R4D_LEAN_LATCH")
UNPACK_V = flag("R4D_UNPACK_V")
HIDE_UNFILLED = flag("R4D_HIDE_UNFILLED")
GATE_SCORES = flag("R4D_GATE_SCORES", "0")


def head_of(name):
    """--fc-v-{slot}-{head} -> head, or None for a packed per-slot list."""
    parts = name.split("-")
    return int(parts[5]) if len(parts) > 5 else None
