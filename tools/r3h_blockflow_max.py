#!/usr/bin/env python3
"""R3H option #1 (R3H.md §4 #1): block-flow group maximum for the coarse head.

Template: experiments/gpt2-mixed-hot2-blockflow-group-max-shard256 (#176,
`tools/build_mixed_hot2_blockflow_group_probe.py:30-31`), whose two override
rules turned each 256-row vocabulary group from a one-column grid with every
row in cell 1/1 into a block container of in-flow zero-height rows. A block's
max-content inline size is the maximum of its in-flow children's max-content
contributions, exactly the quantity the single `max-content` grid track was
computing, so `anchor-size(--head-group-g width)` is unchanged by
construction (#176: 30/30 exact; -13 % layout, -30 % style on the same
50,257-row topology). Only the always-on coarse groups change; `.head-fine`
stays a grid (experiments/gpt2-mixed-hot2-all-blockflow: all-block-flow
regressed the fine stage).

Flag: R3H_BLOCKFLOW_MAX (default 1; `0` reproduces the previous bundle).

What is appended to head.css (after F4's packing, before R2D's knobs):
  .head-group{display:block;grid-template-columns:none;grid-template-rows:none}
      keeps position:fixed, width:max-content and the epoch stamp
      height:calc(var(--head-input-epoch)*1px) of the base rule.
  .head-row{grid-area:auto;justify-self:auto;height:0}
      the grid placement properties become inert; height 0 as in #176 so the
      256 in-flow rows do not overflow the 1-px-per-epoch group. The base
      rule's display:block, white-space:pre, overflow:hidden (R2D: clip) and
      the two-pass `width:calc-size(max-content, …)` are untouched, so R2D's
      exact-string `overflow_clip` swap still matches once.
"""

import os


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


BLOCKFLOW_MAX = flag("R3H_BLOCKFLOW_MAX")

GROUP_RULE = (
    ".head-group{position:fixed;left:0;top:-80000px;display:grid;"
    "grid-template-columns:max-content;grid-template-rows:1px;width:max-content;"
    "height:calc(var(--head-input-epoch)*1px)}"
)
ROW_PREFIX = ".head-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:hidden;"
FINE_PREFIX = ".head-fine{position:fixed;left:0;top:-80000px;display:grid;grid-template-columns:max-content;grid-template-rows:1px;"
OVERRIDE = (
    ".head-group{display:block;grid-template-columns:none;grid-template-rows:none}"
    ".head-row{grid-area:auto;justify-self:auto;height:0}"
)


def blockflow_max(head_css):
    """Append the #176 override rules to the head stylesheet (verified shape)."""
    for name, needle in (("group", GROUP_RULE), ("row", ROW_PREFIX), ("fine", FINE_PREFIX)):
        count = head_css.count(needle)
        if count != 1:
            raise ValueError(f"R3H: expected 1 x head {name} rule, found {count}")
    if OVERRIDE in head_css:
        raise ValueError("R3H: block-flow override already present")
    return head_css + OVERRIDE
