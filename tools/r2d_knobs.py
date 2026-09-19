"""R2D (2026-09-19, round 2): lock the output head outside its own pass, and
cheap per-frame knobs. Every change is behind an environment flag:

  R2D_HEAD_LOCK=0      keep the head unlocked forever after token 1 (the
                       `@container headinput not style(--head-input-epoch:0)`
                       unlock rule); default ON.
  R2D_OVERFLOW_CLIP=0  keep `overflow:hidden` on the 50,257 `.head-row`, the
                       256 `.head-fine-row` and the 8,551 `.metric` carriers
                       (each a scroll container = a PaintLayer +
                       PaintLayerScrollableArea walked on every frame).
  R2D_POINTER_EVENTS=0 keep the compute roots hit-testable (Blink re-hit-tests
                       the last mouse position after every layout). Default OFF
                       (A/B 06:14: no gain).
  R2D_CONTAIN_PAINT=0  no `contain:paint` on the head-row groups / loop and
                       embedding scrollers (R2B MB9: paint containment on a
                       50k-object static subtree cuts the per-frame Paint walk
                       12.6 -> 0.02 ms).

Mechanism (bench/combined.md + audit SYNTHESIS §8.2): the head's 51,247-row
style pass is exactly one per token (its own evaluation), but the head rows
stay laid out, painted, compositing-input-walked and hit-tested on every one
of the ~85 frames per token although they change only once. A
`content-visibility:hidden` lock skips the subtree in style, layout, paint,
compositing inputs and hit testing; it is opened by the existing
`@container b11-bridge style(--bridge-ready:1)` stamp (the head's own
evaluation window: end of layer 11 -> the epoch advance) and closed by the
same stamp, so no new frames or animations.
"""

import os
import re


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


HEAD_LOCK = flag("R2D_HEAD_LOCK")
OVERFLOW_CLIP = flag("R2D_OVERFLOW_CLIP")
POINTER_EVENTS = flag("R2D_POINTER_EVENTS", "0")
CONTAIN_PAINT = flag("R2D_CONTAIN_PAINT")

# Subtree roots whose geometry is never painted for the user and none of whose
# descendants is read from outside through anchor-size()/container units:
#   .head-group (197 x 256 head rows; the group itself is the anchor read by
#   .head-score-N, paint containment on the anchor does not affect that),
#   .head-fine (256 fine rows; anchor --head-local on itself), .loop-scroll
#   (1,538 loop carriers, read by view-timelines inside), .embedding-scroller
#   (769 carriers). NOT .position-embedding / .head-isolation / .full-head /
#   .head-coarse-reader: they contain .detached-head-source whose anchor is read
#   by .detached-head-reader outside, and `contain:paint` would also become the
#   containing block of every position:fixed probe/scroller inside. .scroller and
#   .readback already carry contain:strict. The roots contain no position:fixed
#   descendants; the absolutely positioned carriers keep their relative track as
#   containing block, so no geometry changes.
CONTAIN_PAINT_ROOTS = [".head-group", ".head-fine", ".loop-scroll", ".embedding-scroller"]  # A/B 06:14: hit-test 11.2 vs 10.7 ms/frame, no gain -> default OFF

# Compute subtrees no user interaction ever reaches. `.position-embedding`
# holds the core and the head; `.detached-head-reader` the token state
# (its `.token-display` is empty in the production build); the rest are
# off-screen probes.
POINTER_EVENTS_ROOTS = [
    ".position-embedding",
    ".detached-head-reader",
    ".font-status",
    ".font-witness",
    ".font-proof",
    ".feedback-scroller",
    ".native-signals",
]


def head_lock_css(blocks):
    """Replacement for the permanent head unlock: hidden unless the bridge
    stamp says the head input for the CURRENT epoch is ready."""
    return (
        ".head-input-bank{container-name:headinput}"
        ".full-head{content-visibility:hidden;contain-intrinsic-size:0px 0px}"
        f"@container b{blocks - 1}-bridge style(--bridge-ready:1){{.full-head{{content-visibility:visible}}}}"
    )


def _swap(css, old, new, expected):
    count = css.count(old)
    if count != expected:
        raise ValueError(f"R2D: expected {expected} x {old!r}, found {count}")
    return css.replace(old, new)


def overflow_clip(css):
    """`overflow:hidden` -> `overflow:clip` on the dense leaf populations.

    `clip` clips identically but does not make the box a scroll container, so
    Blink creates no PaintLayer / PaintLayerScrollableArea for it. The only
    sizing difference between the two values is the automatic minimum size of
    grid/flex items (`min-width:auto` is 0 for scroll containers, content-based
    otherwise); the head rows are grid items, so pin `min-width:0` explicitly.
    `.metric` is absolutely positioned (auto minimum already 0) but gets the
    same pin for clarity.
    """
    css = _swap(
        css,
        ".head-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:hidden;",
        ".head-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:clip;min-width:0;",
        1,
    )
    css = _swap(
        css,
        ".head-fine-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:hidden;",
        ".head-fine-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:clip;min-width:0;",
        1,
    )
    css = _swap(
        css,
        ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;height:1px;overflow:hidden;white-space:pre}",
        ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;height:1px;overflow:clip;min-width:0;white-space:pre}",
        1,
    )
    return css


def pointer_events_css():
    return ",".join(POINTER_EVENTS_ROOTS) + "{pointer-events:none}"


def contain_paint_css():
    return ",".join(CONTAIN_PAINT_ROOTS) + "{contain:paint}"


def manifest():
    return {
        "r2dHeadLock": HEAD_LOCK,
        "r2dOverflowClip": OVERFLOW_CLIP,
        "r2dPointerEvents": POINTER_EVENTS,
        "r2dContainPaint": CONTAIN_PAINT,
    }
