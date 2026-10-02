"""R6P (2026-09-30): (A) pre-Run prompt echo fix and (B) typed free-text prompt for the GPT-2 runtime.

(A) `R6P_ECHO_FIX` (default 1). `.visible-output::before` renders `counter(prompt, gpt2-vocabulary)` from
    `counter-reset: prompt var(--frozen-prompt)`. Since F5 `--frozen-prompt` is registered `inherits:false`; a
    pseudo-element only inherits *inherited* properties from its originating element, so inside `::before`
    `--frozen-prompt` is the registration's initial value 0 -> token 0 = "!" for every prompt, before and after
    Run. Fix: copy the value into an UNREGISTERED property on `.visible-output` itself (`--display-prompt`),
    which the pseudo-element does inherit. `.visible-output` is a leaf that is already restyled once per token
    (it forwards the 32 `--feedback-i` by explicit `inherit`); one more var() on it is not measurable.

(B) `R6P_TYPED_PROMPT` (default 1), `R6P_PROMPT_SLOTS` (default 4 = the positions built into the tokenizer
    fonts). The TinyStories mechanism (tools/build_tinystories_dynamic.py, tools/build_metric_tokenizer_font.py)
    ported to this runtime:
      * an editable `<style contenteditable>` holds `.tk-root{--draft-prompt:"..."}` (registered <string>,
        inherits:false -> typing restyles only the elements that hop it with `inherit`);
      * per prompt slot k two hidden 1px metric elements render the whole draft text with the two OpenType
        BPE tokenizer fonts (rlig = GPT-2's ranked merges; feature p00k keeps only token k, every other glyph
        becomes the zero-advance `zero` glyph; glyph advance = digit+1 of the token id in base 32767, part 0 =
        low digit, part 1 = high digit; upem 64 at font-size 1px -> the advance is an exact LayoutUnit);
      * `anchor-size()` copies each metric's width onto an absolutely positioned inline-size query container
        whose child reads `round(100cqi/1px*64 - 1)` = the digit (registered <integer>, inherits:false);
      * the slot element combines low + 32767*high into `--pt-id-k` (private); the values that the MODEL
        inherits (`--prompt-token-id-k`, `--prompt-has-k`, `--prompt-count`, inherits:true) are gated by
        `--prompt-armed` (private, hopped from body, 1 once #run is checked) so typing never restyles the
        model's 86k descendants, and are frozen by the runtime's 86400 s transition latch once fonts-loaded
        and run-latched are both done (same latch as `--frozen-prompt`);
      * `.feedback-select{--token}` becomes the prefill chain: epoch e <= N reads `--prompt-token-id-(e-1)`
        when the prompt has >= e tokens, else the fed-back `--feedback-(e-1)`; epoch 1 falls back to the
        dropdown's `--frozen-prompt` when nothing is typed. The embedding lookup is the SAME full-vocabulary
        HVAR font lookup (`--token` -> GRUP/LOCL axes) for prefilled and fed-back ids -> exact-class numerics
        identical to generation (the TinyStories approximation came from its 8-bit feedback table, which this
        runtime does not have);
      * the winners of epochs 1..N-1 (predictions made while prefilling) are captured like any winner but
        hidden from the display and never fed back; an EOS winner at a prefill epoch neither stops the run
        nor fires #eos-ready.
"""

from __future__ import annotations

import html as html_lib
import os
from pathlib import Path

from fontTools.ttLib import TTFont


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


ECHO_FIX = flag("R6P_ECHO_FIX")
TYPED = flag("R6P_TYPED_PROMPT")
SLOTS = int(os.environ.get("R6P_PROMPT_SLOTS", "4"))
DEFAULT_TEXT = os.environ.get("R6P_DEFAULT_PROMPT", "")
BASE = 32_767  # tools/build_metric_tokenizer_font.py TOKEN_ID_BASE (HarfBuzz exposes advances > 32767 as signed)
UPEM = 64
EOS = 50_256
ASSETS = Path(__file__).resolve().parents[1] / "assets-r6p"
FONTS = [ASSETS / f"gpt2-token-id-{part}-full.ttf" for part in range(2)]
FAMILIES = ["GPT2TokenId0", "GPT2TokenId1"]
LATCH = "transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)"


def check_fonts():
    """The fonts must carry position features p000..p(SLOTS-1), upem 64, and the +1 digit encoding."""
    info = {}
    for part, path in enumerate(FONTS):
        if not path.exists():
            raise FileNotFoundError(f"R6P: tokenizer font missing: {path}")
        with TTFont(path, lazy=True) as font:
            tags = {fr.FeatureTag for fr in font["GSUB"].table.FeatureList.FeatureRecord}
            missing = [f"p{k:03d}" for k in range(SLOTS) if f"p{k:03d}" not in tags]
            if missing:
                raise ValueError(f"R6P: {path.name} lacks position features {missing}; rebuild with --positions {SLOTS}")
            if font["head"].unitsPerEm != UPEM:
                raise ValueError(f"R6P: {path.name} unitsPerEm {font['head'].unitsPerEm} != {UPEM}")
            cmap = font.getBestCmap()
            # 'I' (U+0049) is token 40: part 0 advance 41, part 1 advance 1
            adv = font["hmtx"][cmap[0x49]][0]
            expected = (40 // BASE**part) % BASE + 1
            if adv != expected:
                raise ValueError(f"R6P: {path.name}: advance of 'I' is {adv}, expected {expected}")
            positions = sorted(int(t[1:]) for t in tags if t.startswith("p") and t[1:].isdigit())
            info[path.name] = {"positions": len(positions), "glyphs": len(font.getGlyphOrder()), "bytes": path.stat().st_size}
    return info


def font_faces_css():
    return "".join(
        f'@font-face{{font-family:{family};src:url("{path.resolve().as_uri()}") format("truetype")}}'
        for family, path in zip(FAMILIES, FONTS)
    )


def is_tokenizer_font(path):
    return Path(path).resolve().parent == ASSETS.resolve()


def barrier_codepoint(font, cmap):
    """font_barrier() picks the first cmap codepoint whose advance > 1. For the tokenizer fonts that is U+0009
    (TAB, byte token 197, advance 198 in the low-digit font): a tab in `white-space:pre` is laid out at tab stops,
    not at its glyph advance, so the witness would never match and fonts-loaded would never fire. The high-digit
    font has no advance > 1 at all (every ASCII byte token is < 32767 -> digit 0 -> advance 1). Choose the
    PRINTABLE ASCII codepoint with the largest non-zero advance instead ('~' = token 93 -> 94 units in the low font;
    '!' = token 0 -> 1 unit in the high font); a fallback-font glyph at 4px is ~1-2.5px, never within 0.125px."""
    best = max((c for c in sorted(cmap) if 32 < c < 127 and font["hmtx"][cmap[c]][0] > 0),
               key=lambda c: (font["hmtx"][cmap[c]][0], -c))
    return best


# ---------------------------------------------------------------- registrations (emitted inside feedback())


def regs(capacity):
    """@property registrations. Emitted with the feedback CSS so the head-isolation wall sees them."""
    if SLOTS < 1 or SLOTS >= capacity:
        raise ValueError(f"R6P: prompt slots {SLOTS} must be in 1..capacity-1 ({capacity - 1})")
    css = '@property --draft-prompt{syntax:"<string>";inherits:false;initial-value:""}'
    css += '@property --prompt-armed{syntax:"<integer>";inherits:false;initial-value:0}'
    css += '@property --tk-count{syntax:"<integer>";inherits:false;initial-value:0}'
    css += '@property --prompt-count{syntax:"<integer>";inherits:true;initial-value:0}'
    css += '@property --prompt-live{syntax:"<integer>";inherits:true;initial-value:0}'  # R6X v5: 1 from arming on (token-fresh embedding receipt)
    for k in range(SLOTS):
        css += f'@property --pt-low-{k}{{syntax:"<integer>";inherits:false;initial-value:0}}'
        css += f'@property --pt-high-{k}{{syntax:"<integer>";inherits:false;initial-value:0}}'
        css += f'@property --pt-present-{k}{{syntax:"<integer>";inherits:false;initial-value:0}}'
        css += f'@property --pt-id-{k}{{syntax:"<integer>";inherits:false;initial-value:-1}}'
        css += f'@property --prompt-token-id-{k}{{syntax:"<integer>";inherits:true;initial-value:-1}}'
        css += f'@property --prompt-has-{k}{{syntax:"<integer>";inherits:true;initial-value:0}}'
    for e in range(1, SLOTS + 1):
        css += f'@property --pf-{e}{{syntax:"<number>";inherits:false;initial-value:0}}'
    return css


# ---------------------------------------------------------------- the model input (replaces .feedback-select{--token})


def token_select_css(capacity):
    """Prefill chain on .feedback-select (F5: --token / --feedback-* / --frozen-prompt are private and forwarded
    there by `inherit`; --prompt-token-id-* / --prompt-count are inherited from the tokenizer chain above)."""
    pf = ".feedback-select{--pf-1:if(style(--prompt-count:0):var(--frozen-prompt);else:var(--prompt-token-id-0))"
    for e in range(2, SLOTS + 1):
        fed = f"var(--feedback-{e - 1})"
        cases = ";".join(f"style(--prompt-count:{c}):{fed}" for c in range(0, e))
        pf += f";--pf-{e}:if({cases};else:var(--prompt-token-id-{e - 1}))"
    pf += "}"
    token = ".feedback-select{--token:if(" + ";".join(
        [f"style(--epoch:{e}):var(--pf-{e})" for e in range(1, SLOTS + 1)]
        + [f"style(--epoch:{e}):var(--feedback-{e - 1})" for e in range(SLOTS + 1, capacity + 1)]
    ) + ";else:var(--frozen-prompt))}"
    return pf + token


# ---------------------------------------------------------------- tokenizer chain (HTML + CSS)


def wrap_model(model_html):
    """Nest the model (and the live token readout) under SLOTS tokenizer stages, TinyStories' structure:
    metric_k0, probe_k0 > lowbridge_k > [metric_k1, probe_k1 > highbridge_k > child]. Each probe is an
    absolutely positioned inline-size container whose width is anchor-size() of the preceding metric, so the
    anchor is always a descendant of the positioned element's containing block (acceptable anchor element)."""
    child = '<i class="tk-tokens"></i>' + model_html
    for k in reversed(range(SLOTS)):
        child = (
            f'<i class="tk-metric tk-pos-{k} tk-part-0 tk tk-{k}" aria-hidden="true"></i>'
            f'<div class="tk-probe-{k}-0 tk-probe tk tk-{k}"><div class="tk-low-{k} tk-bridge tk tk-{k}">'
            f'<i class="tk-metric tk-pos-{k} tk-part-1 tk tk-{k}" aria-hidden="true"></i>'
            f'<div class="tk-probe-{k}-1 tk-probe tk tk-{k}"><div class="tk-high-{k} tk-bridge tk tk-{k}">'
            + child
            + "</div></div></div></div>"
        )
    return '<div class="tk-root">' + child + "</div>"


def chain_css():
    last = SLOTS - 1
    digit = f"round(nearest,calc(100cqi/1px*{UPEM} - 1),1)"
    css = (
        ".tk-root{display:contents;--prompt-armed:inherit;--prompt-live:if(style(--prompt-armed:1):1;else:0)}"  # body sets --prompt-armed; .tk-root sets --draft-prompt itself; R6X v5: --prompt-live inherited by the model
        # every chain element hops the two private inputs (typing / arming restyle only these elements)
        ".tk{--draft-prompt:inherit;--prompt-armed:inherit}"
        "body:has(#run:checked),body:has(#run-latched.done){--prompt-armed:1}"  # R6X v5: sticky (survives unchecking Run / continue)
        ".tk-metric{position:absolute;left:0;top:0;opacity:0;display:inline-block;width:max-content;height:1px;"
        "overflow:hidden;font-size:1px;line-height:1;white-space:pre;pointer-events:none;font-kerning:none;"
        "font-variation-settings:normal;--tk-text:var(--draft-prompt)}"
        ".tk-metric::before{content:var(--tk-text)}"
        f".tk-part-0{{font-family:{FAMILIES[0]}}}.tk-part-1{{font-family:{FAMILIES[1]}}}"
        ".tk-probe{position:absolute;inset:0 auto auto 0;height:1px}"
        # the model's in-flow containing block keeps body's content width (viewport - 2*24px margin)
        ".tk-bridge{width:calc(100vw - 48px)}"
    )
    for k in range(SLOTS):
        css += (
            f'.tk-pos-{k}{{font-feature-settings:"p{k:03d}" 1}}'
            f".tk-pos-{k}.tk-part-0{{anchor-name:--tk-a-{k}-0}}.tk-pos-{k}.tk-part-1{{anchor-name:--tk-a-{k}-1}}"
            f".tk-probe-{k}-0{{container:tk-{k}-0/inline-size;width:anchor-size(--tk-a-{k}-0 width,0px)}}"
            f".tk-probe-{k}-1{{container:tk-{k}-1/inline-size;width:anchor-size(--tk-a-{k}-1 width,0px)}}"
            f"@container tk-{k}-0 (width > 0px){{.tk-low-{k}{{--pt-low-{k}:{digit}}}}}"
            f"@container tk-{k}-1 (width > 0px){{.tk-high-{k}{{--pt-high-{k}:{digit};--pt-present-{k}:1}}}}"
            f".tk-probe-{k}-1,.tk-high-{k}{{--pt-low-{k}:inherit}}"
            f".tk-high-{k}{{--pt-id-{k}:if(style(--pt-present-{k}:1):calc(var(--pt-low-{k}) + {BASE}*var(--pt-high-{k}));else:-1);"
            f"--prompt-token-id-{k}:if(style(--prompt-armed:1):var(--pt-id-{k});else:-1);"
            f"--prompt-has-{k}:if(style(--prompt-armed:1):var(--pt-present-{k});else:0)}}"
        )
        if k:
            hops = ";".join(f"--pt-id-{j}:inherit;--pt-present-{j}:inherit" for j in range(k))
            css += f".tk-{k}{{{hops}}}"
        # R6X v5: no transition latch — a same-pass arm+latch would freeze the pre-armed values (-1 / 0); instead nothing can change
        # after Run: arming is sticky, the editor is read-only from #run:checked and Run is enabled only after fonts-loaded
    count = " + ".join(f"var(--prompt-has-{j})" for j in range(SLOTS))
    css += f".tk-high-{last}{{container-name:tkprompt;--prompt-count:calc({count})}}"
    # live readout of the tokenizer (leaf sibling of the model root; private hops, never restyled per token)
    hops = ";".join(f"--pt-id-{j}:inherit;--pt-present-{j}:inherit" for j in range(SLOTS))
    tk_count = " + ".join(f"var(--pt-present-{j})" for j in range(SLOTS))
    parts = ";".join(
        f'--tkd-{j}:var(--pt-id-{j});--tko-{j}:if(style(--pt-present-{j}:1):"[";else:"");--tkc-{j}:if(style(--pt-present-{j}:1):"]";else:"")'
        for j in range(SLOTS)
    )
    css += (
        f".tk-tokens{{position:fixed;left:24px;right:24px;top:{TOKENS_TOP}px;font:13px/1.4 system-ui;color:#666;white-space:pre-wrap;"
        f"{hops};--tk-count:calc({tk_count});{parts};"
        f'--tk-label:if(style(--tk-count:0):"Typed prompt: none — the dropdown prompt is used. ";else:"Typed prompt → GPT-2 tokens (first {SLOTS} used, each costs one full step): ")}}'
        ".tk-tokens::after{counter-reset:"
        + " ".join(f"tkt{j} var(--tkd-{j})" for j in range(SLOTS))
        + ";content:var(--tk-label) "
        + " ".join(f"var(--tko-{j}) counter(tkt{j},gpt2-vocabulary) var(--tkc-{j})" for j in range(SLOTS))
        + "}"
    )
    return css


# ---------------------------------------------------------------- display (.visible-output) and prefill handshakes


def echo_fix_css():
    return (
        ".visible-output{--display-prompt:var(--frozen-prompt)}"
        ".visible-output::before{counter-reset:prompt var(--display-prompt);content:counter(prompt,gpt2-vocabulary)}"
    )


def display_css():
    """Pre-Run: the typed text (or the dropdown token when nothing is typed). From Run: the N decoded prompt
    tokens (what the model actually consumed) followed by the generated tokens; winners 1..N-1 are hidden."""
    css = (
        ".feedback-reader,.visible-output{--draft-prompt:inherit;--pt-present-0:inherit;--prompt-armed:inherit}"
        # R6X v5: before Run a live preview (typed text hides the dropdown symbol); from Run on ONLY the model-facing values
        # (--prompt-has-0 / --prompt-token-id-k / --prompt-count) so the output can never show a prompt the model did not use
        ".visible-output{--dp-live:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));"
        "--dp-armed:if(style(--prompt-has-0:1):-1;else:var(--frozen-prompt));"
        "--display-prompt:if(style(--prompt-armed:1):var(--dp-armed);else:var(--dp-live));"
        '--draft-echo:if(style(--prompt-armed:1):"";else:var(--draft-prompt))}'
        ".visible-output::before{counter-reset:prompt var(--display-prompt) "
        + " ".join(f"tkp{k} var(--prompt-token-id-{k})" for k in range(SLOTS))
        + ";content:counter(prompt,gpt2-vocabulary) var(--draft-echo) "
        + " ".join(f"counter(tkp{k},gpt2-vocabulary)" for k in range(SLOTS))
        + "}"
    )
    return css


def display_token_rule(i):
    """`body:has(#token-i-captured.done) .visible-output{--display-token-i:...}` for i < SLOTS: hidden when the
    prompt has more than i tokens (the winner at epoch i was a prefill prediction, not a generated token)."""
    if i >= SLOTS:
        return f"body:has(#token-{i}-captured.done) .visible-output{{--display-token-{i}:var(--feedback-{i})}}"
    cases = ";".join(f"style(--prompt-count:{c}):-1" for c in range(i + 1, SLOTS + 1))
    return f"body:has(#token-{i}-captured.done) .visible-output{{--display-token-{i}:if({cases};else:var(--feedback-{i}))}}"


def prefill_handshake_css():
    """While epoch e is a prefill position (prompt has > e tokens) an EOS winner must neither stop the run
    (ack it like any other winner) nor fire #eos-ready."""
    css = ""
    for e in range(1, SLOTS):
        for c in range(e + 1, SLOTS + 1):
            css += (
                f"@container tkprompt style(--prompt-count:{c}){{"
                f"@container headstate style(--winner:{EOS}){{body:has(#run:checked):has(#token-{e}-captured.done) #token-{e}-ack{{animation:native-handshake 1ms both}}}}"
                f"@container runtime style(--epoch:{e}){{body:has(#run:checked) #eos-ready{{animation:none!important}}}}"
                "}"
            )
    return css


# ---------------------------------------------------------------- controls


def panel_html():
    text = html_lib.escape(DEFAULT_TEXT.replace("\\", "\\\\").replace('"', '\\"'))
    return (
        '<div class="tk-panel"><label for="tk-editor">Or type a prompt between the quotes (ASCII, single spaces; the first '
        f"{SLOTS} GPT-2 tokens are used):</label>"
        f'<style id="tk-editor" class="tk-editor" contenteditable="plaintext-only" spellcheck="false" role="textbox" aria-label="Editable prompt">.tk-root {{ --draft-prompt: "{text}"; }}</style></div>'
    )


PANEL_TOP = 52  # R8U: .tk-panel top (R8U_LAYOUT moves it)
TOKENS_TOP = 118  # R8U: .tk-tokens readout top
OUTPUT_TOP = 146  # R6X: .visible-output top in px (the merge with R6V moves it below the progress row)


def panel_inline_css():
    """R6X: the panel's visual rules; also emitted in R6V's early-paint inline <style> so the editor is visible before the sheet."""
    return (
        f".tk-panel{{position:fixed;left:24px;right:24px;top:{PANEL_TOP}px;z-index:100;font:13px/1.4 system-ui;color:#444}}"
        ".tk-panel label{display:block;margin-bottom:2px}"
        ".tk-editor{display:block;box-sizing:border-box;width:100%;max-width:800px;padding:4px 8px;border:1px solid #aaa;border-radius:4px;"
        "background:#fff;color:#111;font:13px/1.4 ui-monospace,Menlo,monospace;white-space:pre;overflow:hidden;caret-color:#111}"
        ".tk-editor:focus{outline:2px solid Highlight}"
    )


def panel_css(capacity):
    return (
        panel_inline_css()
        + "body:has(#run:checked) .tk-editor,body:has(#run-latched.done) .tk-editor{-webkit-user-modify:read-only;pointer-events:none;opacity:.6}"  # R6X v5: locked from the click itself
        + ".controls>label:nth-of-type(2){pointer-events:none;opacity:.6}body:has(#fonts-loaded.done) .controls>label:nth-of-type(2){pointer-events:auto;opacity:1}"  # R6X v5: Run only after Ready (the tokenizer fonts must be in before the ids are armed)
        f".visible-output{{top:{OUTPUT_TOP}px}}"
        ".tk-aside{top:auto!important;bottom:16px}"
    )


def manifest(font_info):
    return dict(
        r6pEchoFix=ECHO_FIX,
        r6pTypedPrompt=dict(
            enabled=TYPED,
            slots=SLOTS if TYPED else 0,
            fonts=[str(p) for p in FONTS] if TYPED else [],
            fontInfo=font_info,
            defaultText=DEFAULT_TEXT if TYPED else None,
            base=BASE,
            prefill="epochs 1..N read --prompt-token-id-(e-1) through the same --token embedding lookup as fed-back ids; winners 1..N-1 hidden and never fed back",
        ),
    )
