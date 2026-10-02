"""R7H (2026-10-01): self-checking winner -> token-id hop.  Flag R7H_ID_GUARD (default on).

The head's winner reaches the model's next input through ONE geometry->number hop that no receipt
covers: `.feedback-metric-e{width:65536px+(saved+1)*8px}` inside `.feedback-scroller{width:524288px}`
is read back by a view-timeline animation and decoded with the scrollport width HARDCODED
(`524288/p - 524288 - 65536`).  A classic (non-overlay) vertical scrollbar shrinks the scrollport by
15 px and biases every readback by +W*15/524273 px, i.e. +1 id for every id >= 9283 (R6X.md s10.M:
"Shubham was" position 14, 17132 -> 17133 in headed Chrome with macOS "Show scroll bars: Always").
v6 removes the scrollbar (`scrollbar-width:none`); this module makes the hop self-checking so that
ANY perturbation of the decode (scrollbars, zoom quirks, a stale or early timeline sample) holds the
run instead of delivering a wrong id:

  G2  calibration metric: one extra metric of constant width (id 50256, the largest, i.e. the most
      bias-sensitive) decoded on `.token-state` (the `headstate` style container) and on
      `.feedback-reader`; `--fb-ok` = 1 only if it decodes to exactly 50256.  `#token-e-ready` is
      blocked (`animation:none!important`) while `--fb-ok` != 1, and a visible panel explains why.
  G3  per-slot agreement: `.token-state` reads every slot's id back through its own animation on the
      same view-timeline (`--fb-echo-p-e`) and compares the decoded id with the inherited, latched
      `--saved-token-e` (the exact cq/anchor value); `#token-e-ack` (the epoch advance = the moment
      the model consumes `--feedback-e`) is blocked while they disagree.  The echo lands one frame
      after the head frame, the ack needs the captured frame (>= 2 frames later): zero new frames.

Cost: 2 elements, 1 timeline, 34 scroll-driven animations (33 on .token-state, 1 on .feedback-reader),
35 non-inherited registered numbers, ~70 rules; no inherited property, no model rule touched.
"""

import os
import re

ON = os.environ.get("R7H_ID_GUARD", "1") not in ("0", "false", "no", "off")
CAL = 50256  # constant id of the calibration metric (bias at a 15 px scrollbar: +1.67 ids -> fails)


def decode(p):
    return f"round(nearest,(524288 / var({p}) - 524288 - 65536) / 8 - 1,1)"


_READER = re.compile(
    r"\.feedback-reader\{animation-name:(feedback1(?:,feedback\d+)*);animation-duration:1s;"
    r"animation-timing-function:linear;animation-fill-mode:both;animation-timeline:(--feedback-t1(?:,--feedback-t\d+)*)\}"
)


def apply(front, output, css, timelines, capacity):
    """front/output/css/timelines as returned by browser_gpt2_runtime.feedback(); returns the same tuple."""
    if not ON:
        return front, output, css, timelines
    last = f'<i class="feedback-metric feedback-metric-{capacity}"></i>'
    if output.count(last) != 1:
        raise ValueError("R7H: expected exactly one last feedback metric")
    output = output.replace(last, last + '<i class="feedback-metric feedback-metric-cal"></i>', 1)
    sel = '<div class="feedback-select">'
    if front.count(sel) != 1:
        raise ValueError("R7H: expected exactly one .feedback-select")
    front = front.replace(sel, '<small class="fb-warn"></small>' + sel, 1)
    m = _READER.search(css)
    if m is None:
        raise ValueError("R7H: .feedback-reader animation list not found")
    css = css.replace(
        m[0],
        f".feedback-reader{{animation-name:{m[1]},fbcal;animation-duration:1s;animation-timing-function:linear;"
        f"animation-fill-mode:both;animation-timeline:{m[2]},--feedback-tcal}}",
        1,
    )
    timelines.append("--feedback-tcal")
    slots = range(1, capacity + 1)
    reg = lambda p: f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}'
    ok = f"calc(1 - min(1,abs({decode('--fb-cal-p')} - {CAL})))"
    css += reg("--fb-cal-p") + reg("--fb-ok") + "".join(reg(f"--fb-echo-p-{e}") for e in slots)
    css += "".join(reg(f"--fb-agree-{e}") for e in slots)
    css += "@keyframes fbcal{from{--fb-cal-p:0}to{--fb-cal-p:1}}"
    css += "".join(f"@keyframes fbecho{e}{{from{{--fb-echo-p-{e}:0}}to{{--fb-echo-p-{e}:1}}}}" for e in slots)
    css += f".feedback-metric-cal{{width:calc(65536px + {CAL + 1}*8px);view-timeline:--feedback-tcal inline}}"
    css += f".feedback-reader{{--fb-ok:{ok}}}"
    css += (
        ".token-state{animation-name:fbcal," + ",".join(f"fbecho{e}" for e in slots)
        + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:--feedback-tcal,"
        + ",".join(f"--feedback-t{e}" for e in slots) + f";--fb-ok:{ok};"
        + ";".join(f"--fb-agree-{e}:calc(1 - min(1,abs({decode(f'--fb-echo-p-{e}')} - var(--saved-token-{e}))))" for e in slots)
        + "}"
    )
    # gates: the capture waits for the calibration, the advance (model consumption) for the agreement
    css += "@container headstate not style(--fb-ok:1){" + ",".join(f"#token-{e}-ready" for e in slots) + "{animation:none!important}}"
    css += "".join(f"@container headstate not style(--fb-agree-{e}:1){{#token-{e}-ack{{animation:none!important}}}}" for e in slots)
    # visible explanation (only after the fonts are in, so the pre-load frames do not flash it)
    css += (
        ".fb-warn{display:none;position:fixed;left:24px;right:24px;top:184px;z-index:120;font:14px/1.45 system-ui;color:#7a1d10;"
        "background:#fbe9e5;border:1px solid #e3b0a6;border-radius:6px;padding:8px 12px}"
        '.fb-warn::after{content:"Geometry self-check failed: a token-id readback decoded a known constant wrongly (the usual cause is a '
        'classic, space-taking scrollbar on a hidden measuring element, or an unusual zoom), so the run is held rather than show wrong '
        'words. See README \\201cscrollbars\\201d: use Chrome 121 or newer, or switch the OS/browser to overlay scrollbars, then Reset."}'
        "body:has(#fonts-loaded.done) .feedback-reader>.fb-warn{display:none}"
        "@container style(--fb-ok:0){body:has(#fonts-loaded.done) .feedback-reader>.fb-warn{display:block}}"
    )
    return front, output, css, timelines
