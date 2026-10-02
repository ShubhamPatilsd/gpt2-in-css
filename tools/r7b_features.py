"""R7B (2026-10-01): three demo features on top of R6X/tools (R7P + R7S designs), each behind an env flag (default on).
Flag-off reproduces the R6X bundle byte for byte. Nothing here touches r6p_prompt.py's arming / receipt code.

  R7B_PREFILL_HEAD_SKIP  (R7P option c) skip the 50,257-row head on prefill epochs 1..N-1 (their winners are discarded
                         anyway): `.full-head` stays content-visibility:hidden on those epochs (count/epoch container rules
                         appended after the two unlock rules, same specificity -> later wins) and `#token-e-captured` gets a
                         second SMIL begin condition `r7b-prefill-ready-e.animationend` fired by a `<g>` in the core's
                         svg.loop-signals at `@container corestate style(--held:1)` (end of layer 11). `--saved-token-e`
                         latches -1 (the head never publishes epoch e), `--pf-(e+1)` ignores it (count > e), the display
                         already hides it, EOS cannot fire (winner 0 while locked). Requires R6P_TYPED_PROMPT.
  R7B_CAPACITY_36        lifts the argparse guard (capacity <= 64) and adds the prompt-count-dependent STOP RULE: with N =
                         max(prompt-count,1) prompt tokens the run stops at epoch t = N-1+total where total =
                         min(R7B_NEW_TOKENS (32), capacity-N+1) new tokens: `#token-t-ack{animation:none!important}` (no
                         epoch advance) and a SMIL relay `#r7b-stop-ready-c` -> `#r7b-complete-c.done` (inside the token-state
                         svg, i.e. inside the tkprompt container, like #eos-done) drives `.status::after` ("Complete • 32 new
                         tokens") and hides `.pg`. Progress text counts NEW tokens ("new token t of 32") and, during prefill,
                         "absorbing prompt token k of N" (per-count overrides of R6V's token counter).
  R7B_SAMPLING           (R7S) Gumbel-max sampling inside the existing head: a 7th "noise font" (64 seed columns x 50,257
                         rows, HVAR axes SEED/TEMP, one glyph per head row at U+80000+token) appended to every `.head-row`
                         and `.head-fine-row` glyph string and to both head font lists; `"SEED" var(--noise-col),"TEMP"
                         var(--temp)` appended to the latched `--head-fvs` list on `.head-input-bank`. Entropy: a `--clock`
                         0->64 / 0.97 s animation on body, running only while the controls are hovered / focused or the prompt
                         editor is focused, paused from `#run:checked` (sticky via #run-latched.done); seed = floor(clock)+1
                         unless `<select id=r7b-seed>` overrides (1..64); `<select id=r7b-temp>` greedy (T=0, default) /
                         0.7 / 1.0. Per-step column = mod(seed + epoch - N, 64) + 1 (step 1 = the first NEW token, so prefill
                         is unaffected). T=0 -> the noise glyph adds a constant 800 units (3,200 px) to every row -> argmax
                         unchanged (bit-identical to greedy). The seed/temperature reach the bank through `@container runtime
                         style(--seed:k)` relays (sticky from Run), so nothing is restyled per clock tick except body and the
                         "seed S" readout.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import r6p_prompt as r6p
import r6v_progress_ui as r6v


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


PREFILL_HEAD_SKIP = flag("R7B_PREFILL_HEAD_SKIP") and r6p.TYPED
CAPACITY_36 = flag("R7B_CAPACITY_36")
SAMPLING = flag("R7B_SAMPLING")
NEW_TOKENS = int(os.environ.get("R7B_NEW_TOKENS", "32"))
MAX_CAPACITY = 64 if CAPACITY_36 else 32
SEEDS = 64
VOCAB = 50_257
TEMPS = [("0", "greedy (T = 0)"), ("0.7", "T = 0.7"), ("1", "T = 1.0")]
ASSETS = Path(__file__).resolve().parents[1] / "assets-r7b"
NOISE_FONT = ASSETS / "gumbel-noise.ttf"
NOISE_META = ASSETS / "noise-meta.json"
HANDSHAKE = "animation:native-handshake 1ms both"
BANK_FROM_RUN = "body:has(#run:checked) .head-input-bank,body:has(#run-latched.done) .head-input-bank"


def prompt_counts():
    return list(range(0, r6p.SLOTS + 1)) if r6p.TYPED else [0]


def count_wrap(c, inner):
    """Scope `inner` to prompt count c (tkprompt = .tk-high-(SLOTS-1), an ancestor of the model)."""
    return f"@container tkprompt style(--prompt-count:{c}){{{inner}}}" if r6p.TYPED else inner


# ---------------------------------------------------------------- 1. prefill head skip (R7P option c)


def prefill_ready_ids():
    return [f"r7b-prefill-ready-{e}" for e in range(1, r6p.SLOTS)]


def insert_prefill_signals(core):
    """The `<g>` signals go into the core's svg.loop-signals (inside the corestate container, outside .loop-compute)."""
    needle = '<svg class="loop-signals"></svg>'
    if core.count(needle) != 1:
        raise ValueError(f"R7B: expected exactly one empty svg.loop-signals in the core, found {core.count(needle)}")
    return core.replace(needle, '<svg class="loop-signals">' + "".join(f'<g id="{i}"></g>' for i in prefill_ready_ids()) + "</svg>")


def add_prefill_begin(output):
    """`#token-e-captured` (e < SLOTS) also begins on r7b-prefill-ready-e.animationend."""
    for e in range(1, r6p.SLOTS):
        old = f'begin="token-{e}-ready.animationend+0.001s"'
        if output.count(old) != 1:
            raise ValueError(f"R7B: expected one {old}, found {output.count(old)}")
        output = output.replace(old, f'begin="token-{e}-ready.animationend+0.001s;r7b-prefill-ready-{e}.animationend+0.001s"')
    return output


def prefill_head_skip_css(blocks):
    css = ""
    for e in range(1, r6p.SLOTS):
        for c in range(e + 1, r6p.SLOTS + 1):
            inner = (
                ".full-head{content-visibility:hidden}"
                f"@container corestate style(--held:1){{body:has(#run:checked) #r7b-prefill-ready-{e}{{{HANDSHAKE}}}"
                + (
                    f'.pg-lay::after{{content:" · {blocks} layers done · prompt token {e} of {c} absorbed (head skipped)"}}.pg::after{{animation:none}}'
                    if r6v.ON
                    else ""
                )
                + "}"
            )
            css += count_wrap(c, f"@container runtime style(--epoch:{e}){{{inner}}}")
    return css


# ---------------------------------------------------------------- 2. capacity 36 + stop rule + new-token progress text


def totals(capacity):
    """[(prompt count c, N = max(c,1), total new tokens, stop epoch t)]."""
    out = []
    for c in prompt_counts():
        n = max(c, 1)
        total = min(NEW_TOKENS, capacity - n + 1)
        out.append((c, n, total, n - 1 + total))
    return out


def insert_stop_signals(output):
    """`#r7b-stop-ready-c` + `#r7b-complete-c` (SMIL set) next to #eos-ready in the token-state svg (under tkprompt)."""
    needle = '<g id="eos-ready"></g>'
    if output.count(needle) != 1:
        raise ValueError("R7B: expected one #eos-ready signal")
    signals = "".join(
        f'<g id="r7b-stop-ready-{c}"></g><g id="r7b-complete-{c}"><set attributeName="class" to="done" begin="r7b-stop-ready-{c}.animationend+0.001s" fill="freeze"/></g>'
        for c in prompt_counts()
    )
    return output.replace(needle, signals + needle)


def stop_css(capacity):
    css = ""
    for c, n, total, t in totals(capacity):
        inner = f"body:has(#token-{t}-captured.done) #r7b-stop-ready-{c}{{{HANDSHAKE}}}"
        if t < capacity:
            inner += f"body:has(#token-{t}-captured.done) #token-{t}-ack{{animation:none!important}}"
        css += count_wrap(c, inner)
        css += f'body:has(#r7b-complete-{c}.done) .status::after{{content:"Complete • {total} new tokens"}}'
        if r6v.ON:
            css += f"body:has(#r7b-complete-{c}.done) .pg{{display:none!important}}"  # R6V's show rule has two :has() -> (2,3,1); its own hide rules lose too (pre-existing)
    return css


def progress_text_css(capacity):
    if not r6v.ON:
        return ""
    css = ""
    for c, n, total, t in totals(capacity):
        rules = ""
        for e in range(1, capacity + 1):
            text = f"absorbing prompt token {e} of {c}" if e < c else f"new token {e - n + 1} of {total}"
            rules += f'@container runtime style(--epoch:{e}){{.pg-tok::after{{content:"{text}"}}}}'
        css += count_wrap(c, rules)
    return css


# ---------------------------------------------------------------- 3. sampling (R7S): noise font + head glyphs + seed/temperature


def noise_meta():
    if not NOISE_FONT.exists() or not NOISE_META.exists():
        raise FileNotFoundError(f"R7B: noise font missing: {NOISE_FONT} (run tools/build_noise_font_r7b.py)")
    meta = json.loads(NOISE_META.read_text())
    digest = hashlib.sha256(NOISE_FONT.read_bytes()).hexdigest()
    if digest != meta["fontSha256"]:
        raise ValueError("R7B: noise font does not match noise-meta.json")
    return meta


def check_noise_font():
    """fvar SEED [0,64] / TEMP [0,2], cmap U+80000..U+80000+50256, base advance 800, HVAR present."""
    from fontTools.ttLib import TTFont

    meta = noise_meta()
    with TTFont(NOISE_FONT, lazy=True) as font:
        axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in font["fvar"].axes}
        if axes != {"SEED": (0.0, 0.0, 64.0), "TEMP": (0.0, 0.0, 2.0)}:
            raise ValueError(f"R7B: unexpected noise font axes {axes}")
        cmap = font.getBestCmap()
        if any(0x80000 + t not in cmap for t in (0, 1, VOCAB - 1)) or 0x80000 + VOCAB in cmap:
            raise ValueError("R7B: noise font cmap does not cover exactly U+80000..U+80000+50256")
        if font["hmtx"][cmap[0x80000]][0] != meta["baseAdvance"] or "HVAR" not in font:
            raise ValueError("R7B: noise font base advance / HVAR mismatch")
        upem = font["head"].unitsPerEm
    return {"font": str(NOISE_FONT), "bytes": NOISE_FONT.stat().st_size, "fontSha256": meta["fontSha256"],
            "tableSha256": meta["tableSha256"], "tableSeed": meta["tableSeed"], "seeds": meta["S"], "upem": upem,
            "baseAdvance": meta["baseAdvance"], "sizeAdjustPercent": meta["sizeAdjustPercent"], "qPerLogit": meta["qPerLogit"]}


def size_adjust_percent():
    from build_matrix_backend_prototypes import UNITS_PER_EM
    from build_gpt2_groupwise_production_q16_sixfont import FACTOR, FONT_SIZE_PX

    value = 4 * UNITS_PER_EM / (FONT_SIZE_PX * float(FACTOR)) * 100  # one font unit of advance = 4 px of row width = 1 q
    meta = noise_meta()
    if abs(value - meta["sizeAdjustPercent"]) > 1e-9:
        raise ValueError("R7B: size-adjust disagrees with the noise font metadata")
    return value


def noise_face_css():
    return f'@font-face{{font-family:NoiseQ;src:url("{NOISE_FONT.resolve().as_uri()}") format("truetype");size-adjust:{size_adjust_percent():.9f}%}}'


_ROW = re.compile(r'<i class="head-row" data-token="(\d+)" style="([^"]*)">([^<]*)</i>')
_FINE = re.compile(
    '"([\U00020000-\U0002FFFF][\U00030000-\U0003FFFF][\U00040000-\U0004FFFF][\U00050000-\U0005FFFF][\U00060000-\U0006FFFF][\U00070000-\U0007FFFF])"'
)
_FAMILIES = "font:62.5px ProdQ16H0,ProdQ16R0,ProdQ16H1,ProdQ16R1,ProdQ16H2,ProdQ16R2"


def add_noise_glyphs(head_html, head_css):
    """7th glyph (U+80000+token) on every .head-row and every fine-row glyph string; NoiseQ joins both font lists."""

    def row(m):
        token, glyphs = int(m[1]), m[3]
        if len(glyphs) != 6 or ord(glyphs[0]) - 0x20000 != token:
            raise ValueError(f"R7B: unexpected head row {token}: {glyphs!r}")
        return f'<i class="head-row" data-token="{token}" style="{m[2]}">{glyphs}{chr(0x80000 + token)}</i>'

    head_html, rows = _ROW.subn(row, head_html)
    if rows != VOCAB:
        raise ValueError(f"R7B: expected {VOCAB} head rows, rewrote {rows}")
    head_css, strings = _FINE.subn(lambda m: f'"{m[1]}{chr(0x80000 + ord(m[1][0]) - 0x20000)}"', head_css)
    if strings != VOCAB:
        raise ValueError(f"R7B: expected {VOCAB} fine glyph strings, rewrote {strings}")
    if head_css.count(_FAMILIES) != 2:
        raise ValueError(f"R7B: expected 2 head font lists, found {head_css.count(_FAMILIES)}")
    head_css = head_css.replace(_FAMILIES, _FAMILIES + ",NoiseQ")
    return head_html, head_css


def extend_head_fvs(bank_decls):
    """Append the two noise axes to the bank's latched --head-fvs list (its last declaration)."""
    if "--head-fvs:" not in bank_decls or bank_decls.rstrip().endswith(";"):
        raise ValueError("R7B: head bank declarations do not end with the --head-fvs list")
    return bank_decls + ',"SEED" var(--noise-col),"TEMP" var(--temp)'


def sampling_regs():
    return (
        '@property --clock{syntax:"<number>";inherits:false;initial-value:0}'
        '@property --seed-live{syntax:"<integer>";inherits:false;initial-value:1}'
        '@property --seed-override{syntax:"<integer>";inherits:false;initial-value:0}'
        '@property --seed{syntax:"<integer>";inherits:false;initial-value:1}'
        '@property --temp{syntax:"<number>";inherits:false;initial-value:0}'
        '@property --r7b-n{syntax:"<integer>";inherits:false;initial-value:1}'
        '@property --noise-col{syntax:"<integer>";inherits:false;initial-value:1}'
    )


def sampling_css():
    css = sampling_regs()
    # entropy: the click time, 64 bins of 15 ms; runs only while the user is at the controls / editor; frozen from Run on
    css += "@keyframes r7b-clock{from{--clock:0}to{--clock:64}}"
    css += (
        "body{animation:r7b-clock .97s linear infinite;animation-play-state:paused;"
        "--seed-live:calc(mod(round(down,var(--clock),1),64) + 1);"
        "--seed:if(style(--seed-override:0):var(--seed-live);else:var(--seed-override))}"
        "body:has(> .controls:hover),body:has(> .controls:focus-within),body:has(> .tk-panel:focus-within){animation-play-state:running}"
        "body:has(#run:checked),body:has(#run-latched.done){animation-play-state:paused}"
    )
    for k in range(1, SEEDS + 1):
        css += f'body:has(> .controls > label > #r7b-seed > option[value="{k}"]:checked){{--seed-override:{k}}}'
    for value, _ in TEMPS[1:]:
        css += f'body:has(> .controls > label > #r7b-temp > option[value="{value}"]:checked){{--temp:{value}}}'
    # relays into the bank (sticky from Run; before Run the bank keeps its initial seed/temp so nothing downstream churns)
    for k in range(1, SEEDS + 1):
        css += f"@container runtime style(--seed:{k}){{{BANK_FROM_RUN}{{--seed:{k}}}}}"
    for value, _ in TEMPS[1:]:
        css += f"@container runtime style(--temp:{value}){{{BANK_FROM_RUN}{{--temp:{value}}}}}"
    if r6p.TYPED:
        for c in prompt_counts():
            css += count_wrap(c, f".head-input-bank{{--r7b-n:{max(c, 1)}}}")
    css += ".head-input-bank{--noise-col:calc(mod(var(--seed) + var(--epoch) - var(--r7b-n),64) + 1)}"
    # readout next to the status
    css += ".r7b-seed-out{margin-left:.5em;color:#666}"
    for k in range(1, SEEDS + 1):
        css += f'@container runtime style(--seed:{k}){{.r7b-seed-out::after{{content:"seed {k}"}}}}'
    for value, label in TEMPS:
        css += f'@container runtime style(--temp:{value}){{.r7b-seed-out::before{{content:"{label} · "}}}}'
    return css


def controls_html():
    seed_options = '<option value="0" selected>auto</option>' + "".join(f'<option value="{k}">{k}</option>' for k in range(1, SEEDS + 1))
    temp_options = "".join(f'<option value="{v}"{" selected" if v == "0" else ""}>{label}</option>' for v, label in TEMPS)
    return (
        f'<label>Seed <select id="r7b-seed">{seed_options}</select></label> '
        f'<label>Sampling <select id="r7b-temp">{temp_options}</select></label> '
    )


def insert_controls(controls):
    needle = '<small class="status"></small>'
    if controls.count(needle) != 1:
        raise ValueError("R7B: expected one .status in the controls")
    return controls.replace(needle, controls_html() + needle + '<small class="r7b-seed-out"></small>')


# ---------------------------------------------------------------- assembly


def feature_css(blocks, capacity):
    """Everything except the @font-face (which must precede the font barrier). Appended after R6V's progress rules."""
    css = ""
    if PREFILL_HEAD_SKIP:
        css += prefill_head_skip_css(blocks)
    if CAPACITY_36:
        css += stop_css(capacity) + progress_text_css(capacity)
    if SAMPLING:
        css += sampling_css()
    return css


def manifest(capacity, noise_info=None):
    return {
        "r7bPrefillHeadSkip": PREFILL_HEAD_SKIP,
        "r7bCapacity36": CAPACITY_36,
        "r7bNewTokens": NEW_TOKENS if CAPACITY_36 else None,
        "r7bStops": [{"promptCount": c, "promptTokens": n, "newTokens": total, "stopEpoch": t} for c, n, total, t in totals(capacity)] if CAPACITY_36 else None,
        "r7bSampling": SAMPLING,
        "r7bNoiseFont": noise_info,
        "r7bColumnRule": "col = mod(seed + epoch - max(promptCount,1), 64) + 1; scores = rint(raw_q + n[col]*T_realized); T_realized = round(T/2*16384)/16384*2" if SAMPLING else None,
    }
