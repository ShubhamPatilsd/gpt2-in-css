"""R2F (2026-09-19): lean layer handshake — no pulse-end / pass-advance frames.

Flag (default ON): R2F_LEAN_HANDSHAKE=0 restores the SMIL relay
(ready pulse -> captured -> ack pulse -> advanced -> --pass).

Mechanism (work/2026-09-19/R2A.md §5, §8): per layer the loop needed three
protocol frames after the data frames A-D: E (ready pulse ends), F (`:has()`
captured -> --loop-held, ack pulse starts), G (ack pulse ends) before the
`:has()` advanced -> --pass+1 restyle in the next A. The relay exists only
because the "write bank has the current pass" fact (`--loop-ack`) lives on a
descendant of the pass controller and could reach it only through SMIL-driven
DOM state.

Here the controller reads the two bank pass markers directly: a wrapper above
`.core-controller` carries two view-timeline animations on the existing
`--loop-t-{0,1}-768` timelines (scoped on html), the controller inherits the
two progress values explicitly (private properties, F5 pattern) and computes

    --pass: min(calc(max(marker0, marker1) + 1), var(--pass-cap))

The write bank's marker becomes P in the very style pass / layout that carries
P's output (both are `--saved-b-*` declarations of the same bank, latched by
the same 86400 s transition list when the bank turns into the read bank), so
`--pass` advances in the same snapshot re-run pass that used to set
`--loop-ack:1` (frame D, pass 2) and S1 of the next layer runs in that pass.
Token boundaries hold `--pass` at k*blocks through `--pass-cap`, which the
head's `#token-k-advanced.done` raises (same `:has()` rule as before, different
declaration). The `--loop-held` arming step is not needed: transitions start
from the after-change `transition-property`, and the base bank rule already
lists every `--saved-*` name (the trace shows the 769 latch transitions start
in frame D, when the proj gate opens, not at the pass advance).
"""

import os
import re


def flag(name):
    return os.environ.get(name, "1") not in ("0", "false", "no", "off")


LEAN_HANDSHAKE = flag("R2F_LEAN_HANDSHAKE")

# centered carrier decode of loop_parts(..., centered=True): value = (1572864 / (p + 2) - 786432) / 128
_DECODE = "round(nearest,(1572864 / (var({lp}) + 2) - 524288 - 262144) / 128,1)"


def _remove_all(css, pattern, expected=None, what=""):
    css, count = re.subn(pattern, "", css)
    if expected is not None and count != expected:
        raise ValueError(f"R2F: expected {expected} {what}, removed {count}")
    return css


def apply_css(css, blocks, capacity, width=768):
    """Rewrite the loop_parts() control CSS (still in `body{}` / `var(--pass)` form)."""
    steps = blocks * capacity
    # 1. the SMIL relay: ready pulse, captured -> ack pulse, advanced -> pass
    css = _remove_all(
        css,
        r"@container loopreceipt style\(--loop-ack:1\)\{@container loopcontrol style\(--pass:\d+\)\{#loop-ready-\d+\{animation:loop-pulse 1ms both\}\}\}",
        steps,
        "ready-pulse rules",
    )
    css = _remove_all(
        css,
        r"body:has\(#loop-captured-\d+\.done\)\{--loop-captured-pass:\d+\}",
        steps,
        "captured rules",
    )
    css = _remove_all(
        css,
        r"body:has\(#loop-captured-\d+\.done\) #loop-ack-\d+\{animation:loop-pulse 1ms both\}",
        steps - 1,
        "ack-pulse rules",
    )
    css = _remove_all(
        css,
        r"body:has\(#loop-advanced-\d+\.done\)\{--pass:\d+\}",
        steps - 1,
        "advance rules",
    )
    # 2. the redundant `--loop-held` arming of the write bank
    css = _remove_all(
        css,
        r"@container loopcontrol style\(--loop-held:1\)\{\.loop-bank-[01]\{transition-property:[^{}]*\}\}",
        2,
        "held rules",
    )
    # 3. `--loop-ack` is no longer read by anything
    css, count = re.subn(
        r";--loop-ack:calc\(1 - min\(1,abs\(round\(nearest,\(1572864 / \(var\(--lp-[01]-\d+\) \+ 2\) - 524288 - 262144\) / 128,1\) - var\(--pass\)\)\)\)",
        "",
        css,
    )
    if count != 2:
        raise ValueError(f"R2F: expected 2 --loop-ack declarations, removed {count}")
    # 4. the controller: pass = min(max(markers) + 1, cap)
    old = "body{--pass:1;container-name:loopcontrol;--loop-phase:mod(calc(var(--pass) - 1),2);--loop-held:calc(1 - min(1,abs(var(--pass) - var(--loop-captured-pass))))}"
    if css.count(old) != 1:
        raise ValueError("R2F: missing unique loop controller rule")
    markers = ",".join(_DECODE.format(lp=f"--lp-{bank}-{width}") for bank in range(2))
    new = (
        f"body{{--pass:min(calc(max({markers}) + 1),var(--pass-cap));--pass-cap:{blocks};"
        f"--lp-0-{width}:inherit;--lp-1-{width}:inherit;"
        "container-name:loopcontrol;--loop-phase:mod(calc(var(--pass) - 1),2)}"
        # the marker readers live on the wrapper, above the controller
        f".core-pass-reader{{animation-name:loop-k-0-{width},loop-k-1-{width};"
        "animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;"
        f"animation-timeline:--loop-t-0-{width},--loop-t-1-{width}}}"
        '@property --pass-cap{syntax:"<number>";inherits:false;initial-value:0}'
    )
    css = css.replace(old, new)
    # 5. token boundaries raise the cap instead of writing the pass
    for token in range(1, capacity):
        css += f"body:has(#token-{token}-advanced.done){{--pass-cap:{(token + 1) * blocks}}}"
    return css


def apply_body(body):
    """Drop the 4 <g> + 2 <set> SMIL signal elements per step."""
    body, count = re.subn(
        r'<svg class="loop-signals">.*?</svg>', '<svg class="loop-signals"></svg>', body
    )
    if count != 1:
        raise ValueError("R2F: expected one svg.loop-signals")
    return body


def wrap_controller(body):
    return '<div class="core-pass-reader">' + body + "</div>"
