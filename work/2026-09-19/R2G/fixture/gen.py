#!/usr/bin/env python3
"""R2G fixtures: why do the loop-handshake passes (357 / 485 elements) cost 3-6x the cost model?

Pages reproduce the `combined` bundle's loop-controller topology at the demo's shapes
(96 passes, 768-wide vectors, 16,311-element locked compute subtree, 51,149-element locked
head sibling, 7 token slots) and vary ONE thing at a time.  Same manifest schema as
F4/latch/gen_f4_latch.py (M1 gen.py), plus `mutations`: an explicit list of CDP attribute
writes (selector, attribute, value) consumed in order by run.mjs `--trigger attr`
(index = trial * (warmup + 1) + mutationIndex; `{v}` in a value is replaced by a seeded random).

Families
  pa-*   the pass-advance restyle (R2A population 485): `.done` class lands on #loop-advanced-k
         -> :has() -> .core-controller{--pass:k+1} -> @container loopcontrol style(--pass) fan-out
  svg-*  restyle of the svg.loop-signals subtree via an inherited var on .loop-input (R2A 357)
  rd-*   .loop-reader with 1,538 view-timeline animations fed by 2 x 769 carriers; readback pass
"""
from __future__ import annotations
import argparse, hashlib, json, os, random, re
from dataclasses import asdict, dataclass, field

W, STEPS, BLOCKS, CAPACITY = 768, 96, 12, 8
CORE_FILL, HEAD_FILL = 16311, 51149
N_GO = 16


@dataclass
class Page:
    id: str; family: str; title: str; params: dict; target: str
    in_range: list = field(default_factory=lambda: [0.0, 1.0]); in_inherits: bool = True
    verify_selector: str = "#target"; verify_property: str = "--out"; hypothesis: str = ""
    file: str = ""; bytes: int = 0; seed: int = 0; go_values: list = field(default_factory=list)
    in_initial: float = 0.0; element_count_hint: int = 0; notes: str = ""
    mutations: list = field(default_factory=list)


def stable_seed(base, pid):
    return int(hashlib.sha256(f"{base}:{pid}".encode()).hexdigest()[:12], 16)


def regs(names, inherits=False, initial="0", syntax="<number>"):
    inh = "true" if inherits else "false"
    return "".join(f'@property {n}{{syntax:"{syntax}";inherits:{inh};initial-value:{initial}}}' for n in names)


# ----------------------------------------------------------------------------- DOM pieces
def signals_svg(steps=STEPS, smil="demo"):
    """384 <g> + 192 <set>; smil='demo' keeps the demo's begin= wiring, 'inert' uses begin=indefinite
    (same elements, but the <set> never fires so the harness controls every .done)."""
    out = ['<svg class="loop-signals">']
    for s in range(1, steps + 1):
        b1 = f"loop-ready-{s}.animationend+0.001s" if smil == "demo" else "indefinite"
        b2 = f"loop-ack-{s}.animationend+0.001s" if smil == "demo" else "indefinite"
        out.append(f'<g id="loop-ready-{s}"></g><g id="loop-ack-{s}"></g>'
                   f'<g id="loop-captured-{s}"><set attributeName="class" to="done" begin="{b1}" fill="freeze"/></g>'
                   f'<g id="loop-advanced-{s}"><set attributeName="class" to="done" begin="{b2}" fill="freeze"/></g>')
    out.append("</svg>")
    return "".join(out)


def token_chain(depth_chain=True):
    """7 token slots' handshake <g>s.  demo: nested .token-slot-N chain (depth ~36); the fixed-depth
    variant puts the svg directly under body>.detached-head-reader>.detached-head-state."""
    gs = "".join(f'<g id="token-{t}-ready"></g><g id="token-{t}-ack"></g>'
                 f'<g id="token-{t}-captured"><set attributeName="class" to="done" begin="indefinite" fill="freeze"/></g>'
                 f'<g id="token-{t}-advanced"><set attributeName="class" to="done" begin="indefinite" fill="freeze"/></g>'
                 for t in range(1, CAPACITY + 1))
    svg = f'<svg class="token-signals">{gs}</svg>'
    inner = svg
    if depth_chain:
        for t in range(CAPACITY, 0, -1):
            inner = f'<div class="token-slot-{t}">{inner}</div>'
        inner = f'<div class="token-state">{inner}</div>'
    return f'<div class="detached-head-reader"><div class="detached-head-state">{inner}</div></div>'


def filler(n):
    return "<i></i>" * n


def native_signals():
    return ('<svg class="native-signals"><g id="run-start" class="done"></g><g id="run-latched" class="done"></g>'
            '<g id="fonts-detected" class="done"></g><g id="fonts-loaded" class="done"></g></svg>')


# ----------------------------------------------------------------------------- CSS pieces
BASE_CSS = (
    "html,body{margin:0}.loop-signals,.token-signals,.native-signals{position:fixed;width:1px;height:1px;top:0;left:0}"
    "@keyframes loop-pulse{from{opacity:.99}to{opacity:1}}"
    ".loop-scroll{position:fixed;top:-100000px;left:0;width:524288px;height:1px;overflow:scroll;visibility:hidden}"
    ".loop-track{width:1572864px;height:1px;position:relative}.loop-metric{position:absolute;top:0;left:0;height:1px}"
    ".loop-compute{content-visibility:hidden;contain-intrinsic-size:0px 0px}"
    "@container loopreceipt style(--loop-ready:1){.loop-compute{content-visibility:visible}}"
    ".loop-input{container-name:loopreceipt}"
    ".full-head{content-visibility:hidden;contain-intrinsic-size:0px 0px}"
)

CONTROL_REGS = regs(["--pass", "--loop-phase", "--loop-held", "--loop-captured-pass", "--native-pass",
                     "--loop-ready", "--loop-ack", "--layer", "--position", "--epoch"])


def controller_css(pass0=1):
    return (f".core-controller{{--pass:{pass0};container-name:loopcontrol;--loop-phase:mod(calc(var(--pass) - 1),2);"
            "--loop-held:calc(1 - min(1,abs(var(--pass) - var(--loop-captured-pass))))}"
            ".core-controller{--layer:mod(calc(var(--pass) - 1),12);--position:calc(round(down,calc((var(--pass) - 1) / 12),1) + 1)}"
            ".core-controller{container-name:loopcontrol corestate}")


def core_block_css(has="demo"):
    if has == "none":
        return ".core-block{content-visibility:visible}"
    if has == "fixed":
        return (".core-block{content-visibility:hidden;contain-intrinsic-size:0px 0px}"
                "body:has(> .native-signals > #fonts-loaded.done):has(> .native-signals > #run-latched.done) .core-block{content-visibility:visible}")
    return (".core-block{content-visibility:hidden;contain-intrinsic-size:0px 0px}"
            "body:has(#fonts-loaded.done):has(#run-latched.done) .core-block{content-visibility:visible}")


LOOP_CHAIN = "> .core-block > .loop-reader > .loop-input > .loop-signals > "
TOKEN_CHAIN_FIXED = "> .detached-head-reader > .detached-head-state > .token-signals > "

PASS_READERS = (".loop-input,.loop-bank-0,.loop-bank-1,.reused-input,.fvs-query,.fvs-score-reader,.pass-reader,"
                ".shared-qkv-receipt,.shared-attn-receipt,.shared-fc-receipt,.shared-proj-receipt,.cache-bridge-receipt,.fvs-score-receipt")


def handshake_css(has="demo", steps=STEPS, stamps=True):
    """The demo's per-pass rules (adapter.py): has='demo' descendant :has(); 'fixed' fixed-depth child chain;
    'none' no :has() rules at all (pass advanced by the harness via inline style)."""
    css = []
    lp = LOOP_CHAIN if has == "fixed" else ""
    tp = TOKEN_CHAIN_FIXED if has == "fixed" else ""
    for s in range(1, steps + 1):
        css.append(f"@container loopreceipt style(--loop-ack:1){{@container loopcontrol style(--pass:{s}){{#loop-ready-{s}{{animation:loop-pulse 1ms both}}}}}}")
        if has != "none":
            css.append(f".core-controller:where(:has({lp}#loop-captured-{s}.done)){{--loop-captured-pass:{s}}}")
            if s % BLOCKS:
                css.append(f".core-controller:where(:has({lp}#loop-captured-{s}.done)) #loop-ack-{s}{{animation:loop-pulse 1ms both}}")
                css.append(f".core-controller:where(:has({lp}#loop-advanced-{s}.done)){{--pass:{s + 1}}}")
            elif s // BLOCKS < CAPACITY:
                css.append(f":where(body:has({tp}#token-{s // BLOCKS}-advanced.done)) .core-controller{{--pass:{s + 1}}}")
        if stamps:
            css.append(f"@container loopcontrol style(--pass:{s}){{{PASS_READERS}{{--native-pass:{s}}}}}")
    return "".join(css)


def loop_input_css(ready="0", ack="1", phase_calcs=True):
    """.loop-input: 1,538 --lp forwards (F5), 768 --loop-in calcs per phase (60 KB x2), pass-1 rule, ready/ack."""
    lp = [f"--lp-{b}-{i}" for b in range(2) for i in range(W + 1)]
    css = [".loop-input{" + ";".join(f"{p}:inherit" for p in lp) + "}"]
    for phase in range(2):
        rb = 1 - phase
        decls = [f"--loop-in-{i}:calc((1572864 / (var(--lp-{rb}-{i}) + 2) - 524288 - 262144) / 128)" for i in range(W)] if phase_calcs else []
        decls.append(f"--loop-ready:{ready}")
        decls.append(f"--loop-ack:{ack}")
        css.append(f"@container loopcontrol style(--loop-phase:{phase}){{.loop-input{{" + ";".join(decls) + "}}")
    css.append("@container loopcontrol style(--pass:1){.loop-input{" + ";".join(f"--loop-in-{i}:var(--initial-{i},0)" for i in range(W)) + "}}")
    return "".join(css)


def loop_reader_inputs_css():
    return ".loop-reader{" + ";".join(f"--input-{i}:var(--x-{i:03d})" for i in range(W)) + "}"


def vector_regs():
    return (regs([f"--loop-in-{i}" for i in range(W)], inherits=True)
            + regs([f"--x-{i:03d}" for i in range(W)], inherits=True)
            + regs([f"--lp-{b}-{i}" for b in range(2) for i in range(W + 1)])
            + regs([f"--saved-{b}-{i}" for b in range(2) for i in range(W + 1)])
            + regs([f"--loop-out-{i}" for i in range(W)]))


def reader_anim_css(split=False):
    """1,538 view-timeline animations (+ keyframes) on .loop-reader, or 769 each on .loop-reader-0/-1."""
    css = []
    for b in range(2):
        for i in range(W + 1):
            css.append(f"@keyframes loop-k-{b}-{i}{{from{{--lp-{b}-{i}:-2}}to{{--lp-{b}-{i}:1}}}}")
    def rule(sel, banks):
        names = ",".join(f"loop-k-{b}-{i}" for b in banks for i in range(W + 1))
        tls = ",".join(f"--loop-t-{b}-{i}" for b in banks for i in range(W + 1))
        return f"{sel}{{animation-name:{names};animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:{tls};}}"
    if split:
        css.append(rule(".loop-reader-0", [0]))
        css.append(rule(".loop-reader-1", [1]))
        lp1 = [f"--lp-1-{i}" for i in range(W + 1)]
        css.append(".loop-reader-0{" + ";".join(f"{p}:inherit" for p in lp1) + "}")  # inner reader-0 forwards outer reader-1's values
    else:
        css.append(rule(".loop-reader", [0, 1]))
    return "".join(css)


def timeline_scope_css():
    names = [f"--loop-t-{b}-{i}" for b in range(2) for i in range(W + 1)]
    names += [f"--b11-bridge-t{i}" for i in range(W)] + [f"--cache-bridge-t{i}" for i in range(W)]
    names += [f"--fvs-score-{h}-{s}" for h in range(12) for s in range(8)] + [f"--feedback-t{i}" for i in range(8)]
    names += ["--b11-bridge-stamp", "--cache-bridge-stamp", "--fvs-score-stamp"]
    return "html{timeline-scope:" + ",".join(names) + "}"


def banks_html(rng, latch=False):
    """.loop-bank-1 > scroll > track > 769 carriers, then .loop-bank-0 nested inside (demo order), then #loop-result.
    Bank 0 is the written bank: --saved-0-i = calc(var(--in) + c_i) with seeded constants; bank 1 static."""
    def carriers(b):
        return "".join(f'<i class="loop-metric" style="--saved-{b}-{i}:inherit;width:calc(262144px + var(--saved-{b}-{i}) * 128px);view-timeline:--loop-t-{b}-{i} inline"></i>'
                       for i in range(W + 1))
    inner = '<i id="loop-result"></i>'
    for b in (0, 1):
        inner = f'<div class="loop-bank-{b}"><div class="loop-scroll"><div class="loop-track">{carriers(b)}</div></div>{inner}</div>'
    consts = [rng.uniform(-1.5, 1.5) for _ in range(W + 1)]
    css = (".loop-bank-0{" + ";".join(f"--saved-0-{i}:calc(var(--in) + {consts[i]:.4f})" for i in range(W + 1)) + "}"
           ".loop-bank-1{" + ";".join(f"--saved-1-{i}:{rng.uniform(-1.5, 1.5):.4f}" for i in range(W + 1)) + "}"
           ".loop-scroll,.loop-track{" + ";".join(f"--saved-{b}-{i}:inherit" for b in range(2) for i in range(W + 1)) + "}")
    if latch:
        for b in range(2):
            names = ",".join(f"--saved-{b}-{i}" for i in range(W + 1))
            css += f".loop-bank-{b}{{transition-property:{names};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}}"
        css += "@container loopcontrol style(--loop-phase:1){.loop-bank-0{transition-property:none}}"
    return inner, css


# ----------------------------------------------------------------------------- page assembly
def write_page(out, p: Page, css: str, body: str):
    p.seed = stable_seed(SEED, p.id)
    rng = random.Random(p.seed)
    p.go_values = [rng.uniform(*p.in_range) for _ in range(N_GO)]
    for m in p.mutations:
        if "{v}" in m["value"]:
            m["value"] = m["value"].replace("{v}", f"{rng.uniform(*p.in_range):.6f}")
    html = (f'<!doctype html><html><head><meta charset="utf-8"><title>{p.title} seed={p.seed}</title><style>'
            + css + "</style></head><body>" + body + "</body></html>")
    p.file = f"{p.id}.html"
    path = os.path.join(out, p.file)
    with open(path, "w") as f:
        f.write(html)
    p.bytes = os.path.getsize(path)
    p.element_count_hint = html.count("<") - html.count("</")
    return p


def core_dom(signals_html, compute_inner, core_fill, head_fill, token_depth=True, reader_extra=""):
    """body > native-signals + position-embedding > [core-controller > core-block > loop-reader > loop-input >
    (svg, loop-compute > filler + compute_inner)] + b11-bridge-c0 > full-head > head filler ; detached-head-reader chain."""
    core = (f'<div class="core-controller"><div class="core-block" id="block-0"><div class="loop-reader"{reader_extra}>'
            f'<div class="loop-input">{signals_html}<div class="loop-compute"><div class="core-reset core-valid reused-input">'
            f'{filler(core_fill)}{compute_inner}</div></div></div></div></div></div>')
    head = f'<div class="b11-bridge-c0"><div class="full-head">{filler(head_fill)}</div></div>'
    return native_signals() + f'<div class="position-embedding">{core}{head}</div>' + token_chain(token_depth)


def gen_pa(out, only):
    pages = []
    variants = {
        # id: (has, core_fill, head_fill, svg?, notes)
        "pa-demo":        ("demo",  CORE_FILL, HEAD_FILL, True,  "exact demo selectors; 272 descendant :has() on .core-controller + 7 body:has() + 2 body:has() for .core-block"),
        "pa-nofill":      ("demo",  0,         0,         True,  "same rules, no filler: traversal = signals only"),
        "pa-corefill":    ("demo",  CORE_FILL, 0,         True,  "core filler only: isolates the body:has() token/core-block rules' share"),
        "pa-fixed":       ("fixed", CORE_FILL, HEAD_FILL, True,  "proposed: :has(> .core-block > ... > #loop-x-N.done) fixed-depth + body:has(> ...) fixed-depth"),
        "pa-nohas":       ("none",  CORE_FILL, HEAD_FILL, True,  "control: no :has(); harness writes --pass inline on .core-controller"),
        "pa-nohas-nosvg": ("none",  CORE_FILL, HEAD_FILL, False, "control: no :has(), no signals svg (fan-out floor)"),
    }
    # + the same two with the demo's live reader: 1,538 view-timeline animations on .loop-reader fed by 2 x 769 carriers
    variants["pa-demo-anims"] = ("demo", CORE_FILL, HEAD_FILL, True, "pa-demo + .loop-reader 1,538 timeline anims + carriers (the 485 pass exactly)")
    variants["pa-nohas-anims"] = ("none", CORE_FILL, HEAD_FILL, True, "pa-nohas + reader anims + carriers: fan-out floor incl. 1,538 unchanged anims")
    # demo condition at pass-advance time: the carriers (timeline subjects) sit INSIDE the display-locked .loop-compute
    variants["pa-demo-anims-locked"] = ("demo", CORE_FILL, HEAD_FILL, True, "pa-demo-anims with the 1,538 carriers inside content-visibility:hidden .loop-compute (inactive timelines)")
    variants["pa-nohas-anims-locked"] = ("none", CORE_FILL, HEAD_FILL, True, "pa-nohas-anims with locked carriers")
    for pid, (has, cf, hf, svg, notes) in variants.items():
        if only and not any(pid.startswith(o) for o in only):
            continue
        anims = "-anims" in pid
        locked = pid.endswith("-locked")
        css = (CONTROL_REGS + vector_regs() + regs(["--in"], inherits=True) + BASE_CSS + controller_css(1) + core_block_css(has)
               + handshake_css(has) + loop_input_css() + loop_reader_inputs_css())
        extra = ""
        if anims:
            rng = random.Random(stable_seed(SEED, pid + ":banks"))
            banks, bank_css = banks_html(rng)
            css += reader_anim_css(False) + timeline_scope_css() + bank_css + ".reused-output{position:absolute}"
            extra = f'<div class="reused-output" id="reused-result">{banks}</div>'
        body = core_dom((signals_svg(smil="inert") if svg else "") + ("" if locked else extra), extra if locked else "", cf, hf, token_depth=(has != "fixed"))
        if anims:
            body = body.replace('<div class="loop-bank-0">', '<div class="loop-bank-0" style="--in:0">')
        muts = []
        for k in range(1, 4):  # trial k: warm-up = captured-k (demo: also starts #loop-ack-k pulse), traced = advanced-k
            if has == "none":
                muts += [{"selector": ".core-controller", "name": "style", "value": f"--pass:{k}"},
                         {"selector": ".core-controller", "name": "style", "value": f"--pass:{k + 1}"}]
            else:
                muts += [{"selector": f"#loop-captured-{k}", "name": "class", "value": "done"},
                         {"selector": f"#loop-advanced-{k}", "name": "class", "value": "done"}]
        p = Page(id=pid, family="pa", title=f"R2G {pid}", params={"has": has, "core_fill": cf, "head_fill": hf, "svg": svg, "anims": anims, "locked": locked},
                 target=".core-controller", verify_selector=".core-controller", verify_property="--pass",
                 hypothesis="H-e: :has() argument traversal over the controller subtree", notes=notes, mutations=muts)
        pages.append(write_page(out, p, css, body))
    return pages


def gen_svg(out, only):
    pages = []
    variants = {
        "svg-demo":   ("demo", True,  "inherited --in on .loop-input restyles svg subtree; #loop-ack-N rules carry ancestor :has()"),
        "svg-nohas":  ("none", True,  "same svg, no :has() rules anywhere"),
        "svg-plain":  ("none", False, "577 <i> instead of the svg (no SMIL, no ids)"),
    }
    for pid, (has, svg, notes) in variants.items():
        if only and not any(pid.startswith(o) for o in only):
            continue
        css = (CONTROL_REGS + vector_regs() + regs(["--in"], inherits=True) + BASE_CSS + controller_css(5) + core_block_css(has)
               + handshake_css(has) + loop_input_css() + loop_reader_inputs_css())
        sig = signals_svg(smil="inert") if svg else '<div class="loop-signals">' + "<i></i>" * 576 + "</div>"
        body = core_dom(sig, "", CORE_FILL, HEAD_FILL)
        # mark passes 1..4 done so `.done` exists in the subtree (fast-reject cannot reject), as in the demo mid-token
        for k in range(1, 5):
            body = body.replace(f'<g id="loop-captured-{k}">', f'<g id="loop-captured-{k}" class="done">').replace(
                f'<g id="loop-advanced-{k}">', f'<g id="loop-advanced-{k}" class="done">')
        muts = [{"selector": ".loop-input", "name": "style", "value": "--in:{v}"} for _ in range(6)]
        p = Page(id=pid, family="svg", title=f"R2G {pid}", params={"has": has, "svg": svg}, target=".loop-input",
                 verify_selector=".loop-input", verify_property="--in", hypothesis="(a) SMIL <g>/<set> per-element restyle cost; ancestor :has() per <g>",
                 notes=notes, mutations=muts)
        pages.append(write_page(out, p, css, body))
    return pages


def gen_rd(out, only):
    pages = []
    variants = {
        # id: (split, svg, latch, mutation)
        "rd-change":        (False, True,  False, "bank"),
        "rd-change-split":  (True,  True,  False, "bank"),
        "rd-change-nosvg":  (False, False, False, "bank"),
        "rd-change-latch":  (False, True,  True,  "bank"),
        "rd-unrelated":     (False, True,  False, "reader"),
        "rd-unrelated-split": (True, True, False, "reader"),
    }
    for pid, (split, svg, latch, mut) in variants.items():
        if only and not any(pid.startswith(o) for o in only):
            continue
        rng = random.Random(stable_seed(SEED, pid + ":banks"))
        banks, bank_css = banks_html(rng, latch=latch)
        css = (CONTROL_REGS + vector_regs() + regs(["--in"], inherits=True) + regs(["--unrelated"]) + BASE_CSS
               + controller_css(2) + core_block_css("none") + handshake_css("none") + loop_input_css(ready="1", ack="0")
               + loop_reader_inputs_css() + reader_anim_css(split) + timeline_scope_css() + bank_css
               + ".reused-output{position:absolute}")
        sig = signals_svg(smil="inert") if svg else ""
        # banks sit in a visible wrapper under .loop-input (demo: under the open proj gate); compute filler stays locked
        body = core_dom(sig + f'<div class="reused-output" id="reused-result">{banks}</div>', "", CORE_FILL, 0)
        if split:
            body = body.replace('<div class="loop-reader">', '<div class="loop-reader loop-reader-1"><div class="loop-reader-0">').replace(
                '<div class="loop-input">', '<div class="loop-input">', 1)
            body = body.replace('</div></div></div></div>' + '<div class="b11-bridge-c0">', '</div></div></div></div></div>' + '<div class="b11-bridge-c0">', 1)
        body = body.replace('<div class="loop-bank-0">', '<div class="loop-bank-0" style="--in:0">')
        if mut == "bank":
            muts = [{"selector": ".loop-bank-0", "name": "style", "value": "--in:{v}"} for _ in range(6)]
            target, vsel, vprop = ".loop-bank-0", ".loop-input", "--loop-in-0"
        else:
            muts = [{"selector": ".loop-reader", "name": "style", "value": "--unrelated:{v}"} for _ in range(6)]
            target, vsel, vprop = ".loop-reader", ".loop-reader", "--unrelated"
        p = Page(id=pid, family="rd", title=f"R2G {pid}", params={"split": split, "svg": svg, "latch": latch, "mutation": mut},
                 target=target, in_range=[-1.0, 1.0], verify_selector=vsel, verify_property=vprop,
                 hypothesis="(b)/(d) 1,538 timeline animations on one element; 769 changed carriers", mutations=muts)
        pages.append(write_page(out, p, css, body))
    return pages



def demo_bank_css(rng, held=True):
    """Demo loop-bank rules (probe_native_reused_loop.loop_parts + F5 forwards): base 769-name latch lists,
    phase rule (write bank tracks --loop-out live, transition-property:none), held rule (list back on)."""
    lists = {b: ",".join(f"--saved-{b}-{i}" for i in range(W + 1)) for b in range(2)}
    css = "".join(f".loop-bank-{b}{{transition-property:{lists[b]};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}}" for b in range(2))
    css += ".reused-output{" + ";".join(f"--loop-out-{i}:calc(var(--in) + {rng.uniform(-1.5, 1.5):.4f})" for i in range(W)) + "}"
    css += ".loop-bank-0,.loop-bank-1{" + ";".join(f"--loop-out-{i}:inherit" for i in range(W)) + "}"
    for b in range(2):
        css += (f"@container loopcontrol style(--loop-phase:{b}){{.loop-bank-{b}{{transition-property:none;"
                + ";".join(f"--saved-{b}-{i}:var(--loop-out-{i})" for i in range(W)) + f";--saved-{b}-{W}:var(--native-pass)}}}}")
        if held:
            css += f"@container loopcontrol style(--loop-held:1){{.loop-bank-{b}{{transition-property:{lists[b]}}}}}"
    css += ".loop-scroll,.loop-track{" + ";".join(f"--saved-{b}-{i}:inherit" for b in range(2) for i in range(W + 1)) + "}"
    return css


def carriers_html():
    def carriers(b):
        return "".join(f'<i class="loop-metric" style="--saved-{b}-{i}:inherit;width:calc(262144px + var(--saved-{b}-{i}) * 128px);view-timeline:--loop-t-{b}-{i} inline"></i>'
                       for i in range(W + 1))
    inner = '<i id="loop-result"></i>'
    for b in (0, 1):
        inner = f'<div class="loop-bank-{b}"><div class="loop-scroll"><div class="loop-track">{carriers(b)}</div></div>{inner}</div>'
    return f'<div class="reused-output" id="reused-result" style="--in:0.25">{inner}</div>'


def gen_cap(out, only):
    """The F transition (R2A population 485): #loop-captured-k.done -> --loop-captured-pass:k, --loop-held:1 -> #loop-ack-k pulse."""
    pages = []
    variants = {  # has, banks, held, anims
        "cap-demo":    ("demo", True,  True,  True,  "capture with demo bank rules (held list swap), carriers, reader anims"),
        "cap-nohas":   ("none", True,  True,  True,  "same, no :has(): harness writes --loop-captured-pass inline"),
        "cap-noheld":  ("demo", True,  False, True,  "no --loop-held rule (banks not container-dependent on held)"),
        "cap-noanims": ("demo", True,  True,  False, "banks + held, no reader animations"),
        "cap-nobanks": ("demo", False, False, False, "controller/signals only (= pa-demo traced at capture)"),
    }
    for pid, (has, banks, held, anims, notes) in variants.items():
        if only and not any(pid.startswith(o) for o in only):
            continue
        rng = random.Random(stable_seed(SEED, pid + ":banks"))
        css = (CONTROL_REGS + vector_regs() + regs(["--in"], inherits=True) + BASE_CSS + controller_css(1) + core_block_css(has)
               + handshake_css(has) + loop_input_css() + loop_reader_inputs_css() + ".reused-output{position:absolute}")
        extra = ""
        if banks:
            css += demo_bank_css(rng, held=held)
            extra = carriers_html()
        if anims:
            css += reader_anim_css(False) + timeline_scope_css()
        body = core_dom(signals_svg(smil="inert") + extra, "", CORE_FILL, HEAD_FILL)
        muts = []
        for k in range(1, 4):
            if has == "none":
                muts += [{"selector": ".core-controller", "name": "style", "value": f"--pass:{k}"},
                         {"selector": ".core-controller", "name": "style", "value": f"--pass:{k};--loop-captured-pass:{k}"}]
            else:
                muts += [({"selector": "#loop-ready-1", "name": "class", "value": "warm"} if k == 1 else
                          {"selector": f"#loop-advanced-{k - 1}", "name": "class", "value": "done"}),
                         {"selector": f"#loop-captured-{k}", "name": "class", "value": "done"}]
        p = Page(id=pid, family="cap", title=f"R2G {pid}", params={"has": has, "banks": banks, "held": held, "anims": anims},
                 target=".core-controller", verify_selector=".core-controller", verify_property="--loop-captured-pass",
                 hypothesis="F pass = capture: --loop-held flips the write bank's transition-property none -> 769 names", notes=notes, mutations=muts)
        pages.append(write_page(out, p, css, body))
    return pages

SEED = 20260919

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages"))
    ap.add_argument("--only", default="")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    SEED = a.seed
    only = [o for o in a.only.split(",") if o]
    os.makedirs(a.out, exist_ok=True)
    pages = gen_pa(a.out, only) + gen_svg(a.out, only) + gen_rd(a.out, only) + gen_cap(a.out, only)
    man = {"seed": SEED, "pages": [asdict(p) for p in pages]}
    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump(man, f, indent=1)
    for p in pages:
        print(f"{p.id:22s} {p.bytes / 1e6:6.2f} MB  elements~{p.element_count_hint:6d}  target={p.target}  muts={len(p.mutations)}")
