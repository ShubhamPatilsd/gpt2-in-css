"""R6L (2026-09-30): stop the 31 s unstyled layout at page load and paint a boot message first.

R5X/run-combined8-c32/c32-p40.json: with `<link rel=stylesheet href=runtime.css>` in <head>, Chrome
parses the 7 MB body in 0.17 s, then spends ONE 30.8 s main-thread task (LayoutCount 1,
LayoutDuration 31.4 s, 169k layout objects) laying out the UA-styled model markup — 84,592 <i>
elements whose 780k text characters live in unassigned/PUA planes, so every character runs a
system font-fallback lookup — while the 50 MB stylesheet body stalls behind the blocked main
thread (responseEnd 31.8 s). CSS parse + first styled recalc + fonts + first paint then take 2.5 s.

  R6L_BODY_LINK=1  the <link> moves from <head> to the start of <body>. A parser-inserted body
                   stylesheet is parser-blocking in Chromium: nothing after it is parsed until the
                   sheet has loaded, so the model markup never exists in the UA-only state and the
                   content before the link paints immediately. Cascade order is unchanged (the link
                   still follows the inline boot <style>). Every other byte of the page is identical.
  R6L_BOOT=1       an inline <style> in <head>: `html::before` shows a one-line boot message and
                   `body{display:none}` guarantees a zero-cost layout should any Chrome version lay
                   out UA-styled content before the sheet applies. runtime.css ends with
                   `html::before{content:none}body{display:block}` (later author sheet, same
                   specificity → wins), restoring the exact pre-R6L computed values.
Both default ON. Flag-off build == bundles/combined8-c32 byte-for-byte (index.html and runtime.css).
"""

import os

BODY_LINK = os.environ.get("R6L_BODY_LINK", "1") == "1"
BOOT = os.environ.get("R6L_BOOT", "1") == "1"
BOOT_TEXT = os.environ.get(
    "R6L_BOOT_TEXT",
    "Loading the model stylesheet (50 MB)… Chrome parses it, then loads the 283 weight fonts (239 MB). "
    "Nothing else is shown until then.",
)

LINK_HTML = '<link rel="stylesheet" href="runtime.css">'


def head_style():
    """Inline shell sheet: applied before runtime.css exists; overridden by css_tail()."""
    text = BOOT_TEXT.replace("\\", "\\\\").replace('"', '\\"')
    return (
        "<style>html::before{content:\"" + text + "\";display:block;margin:24px;"
        "font:16px/1.5 system-ui;color:#222;background:#f7f5ef}body{display:none}</style>"
    )


def css_tail():
    return "html::before{content:none}body{display:block}"


def head_html():
    return (head_style() if BOOT else "") + ("" if BODY_LINK else LINK_HTML)


def body_prefix():
    return LINK_HTML if BODY_LINK else ""


def finish_css(css):
    return css + css_tail() if BOOT else css


def manifest():
    return {"r6lBodyLink": BODY_LINK, "r6lBoot": BOOT}
