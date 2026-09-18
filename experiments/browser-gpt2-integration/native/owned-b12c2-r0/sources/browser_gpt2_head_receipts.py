"""Separate the head's score and epoch transports for longer native runs.

The original two-pass scorer packs an epoch into four low bits of a score
height. That is safe only below epoch 16. A second size container carries the
epoch independently; neither a modulo counter nor inferred completion is used.
"""

import re


def split_head_receipt(html, css):
    packed = re.search(
        r"height:calc\(anchor-size\((--head-[\w-]+) width,0px\)\*16 \+ "
        r"anchor-size\((--head-[\w-]+) height,0px\)\)",
        css,
    )
    if packed is None:
        raise ValueError("Expected the unmodified packed two-pass head receipt")
    score_anchor, choice_anchor = packed.groups()
    css = css.replace(packed[0], f"height:anchor-size({score_anchor} width,0px)", 1)
    original = (
        ".head-group-state{--head-group-index:calc(197 - round(nearest,100cqi/4px,1));"
        "--head-max-score:round(down,100cqb/16px,1);"
        "--head-pipeline-epoch:mod(round(nearest,100cqb/1px,1),16)}"
    )
    replacement = (
        ".head-score-state{--head-group-index:calc(197 - round(nearest,100cqi/4px,1));"
        "--head-max-score:round(nearest,100cqb/1px,1)}"
        ".head-epoch-reader{position:fixed;left:0;top:-900000px;container-type:inline-size;"
        f"width:anchor-size({choice_anchor} height,0px);height:1px}}"
        ".head-group-state{--head-pipeline-epoch:round(nearest,100cqi/1px,1)}"
    )
    if css.count(original) != 1:
        raise ValueError("Missing unique score/epoch decoder")
    css = css.replace(original, replacement)
    opening = '<div class="head-coarse-reader"><div class="head-group-state">'
    closing = "</output></div></div></div></div>"
    if html.count(opening) != 1 or not html.endswith(closing):
        raise ValueError("Unexpected two-pass head nesting")
    html = html.replace(
        opening,
        '<div class="head-coarse-reader"><div class="head-score-state">'
        '<div class="head-epoch-reader"><div class="head-group-state">',
    )
    html += "</div></div>"
    return html, css
