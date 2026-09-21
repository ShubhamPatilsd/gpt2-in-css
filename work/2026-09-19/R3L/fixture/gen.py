#!/usr/bin/env python3
"""R3L fixtures: is the loop-bank latch cost per STARTED transition (-> pack values) or per listed name?

Pages reproduce the demo's latch region exactly (probe_native_reused_loop.loop_parts + F5 forwards +
R2F's `--native-pass` epoch): `.core-controller` (container `loopcontrol`, `--pass` inline) > .core-block >
.loop-reader (1,538 view-timeline animations) > .loop-input (768 decodes) > .loop-compute > #reused-result
(.reused-output: 768 `--loop-out-i`) > .loop-bank-1 > [scroll > track > 769 carriers] > .loop-bank-0 > [...].
A mutation writes `--pass:k;--in:v` on the controller: the phase flips, the old write bank's write rule
drops (its latch transitions START), the new write bank's rule appears (its transitions are CANCELLED,
values change -> 769 carrier widths -> snapshot re-run -> reader restyle), exactly the demo's D' pass.

Variants (one thing at a time; the carrier/timeline/reader population is identical everywhere):
  lat-769        today: 769 separate <number> latches per bank
  lat-385-p2     384 packed pairs (2 x 26 bit, step 1/8192 over [-2048, 6144)) + the epoch latch
  lat-257-p3     256 packed triples (3 x 17 bit, step 1/16) + epoch   [cost model only; too coarse for the demo]
  lat-769-split8 769 latches split over 8 sibling sub-banks (~97 names each): per-list-length behaviour
  lat-none       no transitions at all (values revert on the flip): floor of the restyle itself
Manifest schema = R2G/fixture/gen.py (M1) + `verify_all` (selector/property read for ALL matches after the
traced mutation; compared offline by check.py against the Python model of the same expressions).
"""
from __future__ import annotations
import argparse, hashlib, json, os, random
from dataclasses import asdict, dataclass, field

W = 768
STEPS = 8
SEED = 20260920
M26, MAXQ26, S26, OFF = 67108864, 67108863, 8192, 2048          # 2 x 26 bit
M17, MAXQ17, S17 = 131072, 131071, 16                             # 3 x 17 bit
M34 = M17 * M17


@dataclass
class Page:
    id: str; family: str; title: str; params: dict; target: str
    in_range: list = field(default_factory=lambda: [0.0, 1.0]); in_inherits: bool = True
    verify_selector: str = ".loop-bank-1>.loop-scroll>.loop-track>.loop-metric:nth-child(3)"; verify_property: str = "width"
    hypothesis: str = ""; file: str = ""; bytes: int = 0; seed: int = 0; go_values: list = field(default_factory=list)
    in_initial: float = 0.0; element_count_hint: int = 0; notes: str = ""
    mutations: list = field(default_factory=list)
    verify_all: dict = field(default_factory=dict)
    consts: list = field(default_factory=list)


def stable_seed(base, pid):
    return int(hashlib.sha256(f"{base}:{pid}".encode()).hexdigest()[:12], 16)


def regs(names, inherits=False, initial="0"):
    inh = "true" if inherits else "false"
    return "".join(f'@property {n}{{syntax:"<number>";inherits:{inh};initial-value:{initial}}}' for n in names)


# ------------------------------------------------------------------ packing expressions (shared with the emitter)
def q26(src):
    return f"clamp(0,round(nearest,({src} + {OFF}) * {S26},1),{MAXQ26})"


def pack2(src0, src1):
    return f"calc({q26(src0)} * {M26} + {q26(src1)})"


def unpack2_width(p, part):
    hi = f"round(down,{p} / {M26},1)"
    if part == 0:
        return f"calc({hi} * 0.015625px)"
    return f"calc(({p} - {hi} * {M26}) * 0.015625px)"


def q17(src):
    return f"clamp(0,round(nearest,({src} + {OFF}) * {S17},1),{MAXQ17})"


def pack3(s0, s1, s2):
    return f"calc({q17(s0)} * {M34} + {q17(s1)} * {M17} + {q17(s2)})"


def unpack3_width(p, part):
    hi = f"round(down,{p} / {M34},1)"
    mid = f"round(down,({p} - {hi} * {M34}) / {M17},1)"
    if part == 0:
        return f"calc({hi} * 8px)"
    if part == 1:
        return f"calc({mid} * 8px)"
    return f"calc(({p} - {hi} * {M34} - {mid} * {M17}) * 8px)"


# ------------------------------------------------------------------ latch layouts
def latch_layout(kind):
    """Return (latched names per bank fn, write-declarations fn, carrier-style fn) for a bank b."""
    if kind in ("769", "none", "split8"):
        names = lambda b: [f"--saved-{b}-{i}" for i in range(W + 1)]
        writes = lambda b: [f"--saved-{b}-{i}:var(--loop-out-{i})" for i in range(W)] + [f"--saved-{b}-{W}:var(--native-pass)"]
        carrier = lambda b, i: f"--saved-{b}-{i}:inherit;width:calc(262144px + var(--saved-{b}-{i}) * 128px)"
        return names, writes, carrier
    if kind == "p2":
        names = lambda b: [f"--sv-{b}-{j}" for j in range(W // 2)] + [f"--saved-{b}-{W}"]
        writes = lambda b: [f"--sv-{b}-{j}:{pack2(f'var(--loop-out-{2 * j})', f'var(--loop-out-{2 * j + 1})')}" for j in range(W // 2)] + [f"--saved-{b}-{W}:var(--native-pass)"]

        def carrier(b, i):
            if i == W:
                return f"--saved-{b}-{W}:inherit;width:calc(262144px + var(--saved-{b}-{W}) * 128px)"
            p = f"--sv-{b}-{i // 2}"
            return f"{p}:inherit;width:{unpack2_width(f'var({p})', i % 2)}"
        return names, writes, carrier
    if kind == "p3":
        names = lambda b: [f"--sv-{b}-{j}" for j in range(W // 3)] + [f"--saved-{b}-{W}"]
        writes = lambda b: [f"--sv-{b}-{j}:{pack3(*(f'var(--loop-out-{3 * j + k})' for k in range(3)))}" for j in range(W // 3)] + [f"--saved-{b}-{W}:var(--native-pass)"]

        def carrier(b, i):
            if i == W:
                return f"--saved-{b}-{W}:inherit;width:calc(262144px + var(--saved-{b}-{W}) * 128px)"
            p = f"--sv-{b}-{i // 3}"
            return f"{p}:inherit;width:{unpack3_width(f'var({p})', i % 3)}"
        return names, writes, carrier
    if kind == "font":
        names = lambda b: [f"--lst-{b}", f"--saved-{b}-{W}"]

        def writes(b):
            d = []
            for i in range(W):
                s = f"(var(--loop-out-{i}) + {OFF}) * 2"                       # s/64 for s = 262144 + 128 v
                d.append(f"--lh-{b}-{i}:clamp(0,round(down,{s},1),16383)")
                d.append(f"--ll-{b}-{i}:clamp(0,round(down,({s} - round(down,{s},1)) * 4096,1),4095)")
            d.append(f"--lst-{b}:" + ",".join(f'"H{i:03X}" var(--lh-{b}-{i}),"L{i:03X}" var(--ll-{b}-{i})' for i in range(W)))
            d.append(f"--saved-{b}-{W}:var(--native-pass)")
            return d

        def carrier(b, i):
            if i == W:
                return f"--saved-{b}-{W}:inherit;width:calc(262144px + var(--saved-{b}-{W}) * 128px)"
            return "width:max-content"
        return names, writes, carrier
    raise ValueError(kind)


BASE_PX = 1048832  # 16384 units * 64 px/unit (hi glyph) + 16384 units / 64 px/unit (lo glyph)


def split_groups(kind):
    """Carrier index groups per sub-bank (split8) or one group (everything else)."""
    if kind == "split8":
        per = -(-(W + 1) // 8)
        return [list(range(k * per, min(W + 1, (k + 1) * per))) for k in range(8)]
    return [list(range(W + 1))]


def build(kind, rng):
    names_fn, writes_fn, carrier_fn = latch_layout(kind)
    groups = split_groups(kind)
    latch = kind != "none"
    consts = [rng.uniform(-30, 30) for _ in range(W)]
    for i in rng.sample(range(W), 8):
        consts[i] = rng.uniform(-2000, 5000)
    css = regs(["--pass", "--loop-phase", "--native-pass"]) + regs(["--in"], inherits=True)
    css += regs([f"--loop-out-{i}" for i in range(W)] + [f"--loop-in-{i}" for i in range(W)])
    css += regs([f"--lp-{b}-{i}" for b in range(2) for i in range(W + 1)])
    all_latched = [n for b in range(2) for n in names_fn(b)]
    if kind == "font":
        css += regs([f"--saved-{b}-{W}" for b in range(2)])
        css += "".join(f'@property --lst-{b}{{syntax:"*";inherits:false;initial-value:"H000" 0}}' for b in range(2))
        css += regs([f"--l{h}-{b}-{i}" for b in range(2) for i in range(W) for h in "hl"])
        css += "".join(f'@font-face{{font-family:LoopCarrier{k};src:url("fonts/loop-carrier-{k}.ttf") format("truetype")}}' for k in range(6))
        css += "".join(f".lf-{k}{{font-family:LoopCarrier{k}}}" for k in range(6))
        css += ".loop-metric{white-space:pre;line-height:1;font-kerning:none;letter-spacing:0;word-spacing:0}.lh{font-size:512px}.ll{font-size:4px}"
        css += "".join(f".loop-bank-{b}>.loop-scroll>.loop-track{{font-variation-settings:var(--lst-{b})}}" for b in range(2))
    else:
        css += regs(all_latched)
    css += (".core-controller{container-name:loopcontrol;--loop-phase:mod(calc(var(--pass) - 1),2)}"
            ".loop-scroll{position:fixed;top:-100000px;left:0;width:524288px;height:1px;overflow:scroll;visibility:hidden;contain:paint}"
            ".loop-track{width:1572864px;height:1px;position:relative}.loop-metric{position:absolute;top:0;left:0;height:1px}"
            ".loop-compute{contain-intrinsic-size:0px 0px}")
    for k in range(1, STEPS + 1):
        css += f"@container loopcontrol style(--pass:{k}){{.loop-bank-0,.loop-bank-1,.loop-sub{{--native-pass:{k}}}}}"
    css += ".reused-output{" + ";".join(f"--loop-out-{i}:calc(var(--in) + {consts[i]:.6f})" for i in range(W)) + "}"
    css += ".loop-bank-0,.loop-bank-1,.loop-sub{" + ";".join(f"--loop-out-{i}:inherit" for i in range(W)) + "}"
    # write / latch rules
    timelines, anims = [], []
    for b in range(2):
        names, writes = names_fn(b), writes_fn(b)
        if kind == "split8":
            for k, grp in enumerate(groups):
                sel = f".loop-sub-{b}-{k}"
                sub_names = [f"--saved-{b}-{i}" for i in grp]
                sub_writes = [writes[i] for i in grp]
                if latch:
                    css += f"{sel}{{transition-property:{','.join(sub_names)};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}}"
                css += f"@container loopcontrol style(--loop-phase:{b}){{{sel}{{transition-property:none;{';'.join(sub_writes)}}}}}"
        else:
            sel = f".loop-bank-{b}"
            if latch:
                css += f"{sel}{{transition-property:{','.join(names)};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end){';transition-behavior:allow-discrete' if kind == 'font' else ''}}}"
            css += f"@container loopcontrol style(--loop-phase:{b}){{{sel}{{transition-property:none;{';'.join(writes)}}}}}"
        for i in range(W + 1):
            timelines.append(f"--loop-t-{b}-{i}")
            anims.append(f"loop-k-{b}-{i}")
            css += f"@keyframes loop-k-{b}-{i}{{from{{--lp-{b}-{i}:-2}}to{{--lp-{b}-{i}:1}}}}"
    css += ".loop-scroll,.loop-track{" + ";".join(f"{n}:inherit" for n in all_latched) + "}"
    css += "html{timeline-scope:" + ",".join(timelines) + "}"
    css += (".loop-reader{animation-name:" + ",".join(anims) + ";animation-duration:1s;animation-timing-function:linear;"
            "animation-fill-mode:both;animation-timeline:" + ",".join(timelines) + "}")
    css += ".loop-input{" + ";".join(f"--lp-{b}-{i}:inherit" for b in range(2) for i in range(W + 1)) + "}"
    for b in range(2):
        rb = 1 - b
        css += (f"@container loopcontrol style(--loop-phase:{b}){{.loop-input{{"
                + ";".join(f"--loop-in-{i}:calc((1572864 / (var(--lp-{rb}-{i}) + 2) - 524288 - 262144) / 128)" for i in range(W)) + "}}")
    # DOM
    def carriers(b, grp):
        def one(i):
            if kind == "font" and i < W:
                local = i % 128
                return (f'<i class="loop-metric lf-{i // 128}" style="{carrier_fn(b, i)};view-timeline:--loop-t-{b}-{i} inline">'
                        f'<b class="lh">{f"&#x{0xE000 + 2 * local:X};" * 32}</b><b class="ll">&#x{0xE001 + 2 * local:X};</b></i>')
            return f'<i class="loop-metric" style="{carrier_fn(b, i)};view-timeline:--loop-t-{b}-{i} inline"></i>'
        return "".join(one(i) for i in grp)
    inner = '<i id="loop-result"></i>'
    for b in (0, 1):
        if kind == "split8":
            subs = "".join(f'<div class="loop-sub loop-sub-{b}-{k}"><div class="loop-scroll"><div class="loop-track">{carriers(b, grp)}</div></div></div>' for k, grp in enumerate(groups))
            inner = f'<div class="loop-bank-{b}">{subs}{inner}</div>'
        else:
            inner = f'<div class="loop-bank-{b}"><div class="loop-scroll"><div class="loop-track">{carriers(b, groups[0])}</div></div>{inner}</div>'
    probes = ""
    if kind == "font":
        # R3L diagnostics (read via verify_all after the carriers): P0 hi glyph, default axes -> 1048576 px if the font loaded;
        # P1 inline "H000" 1000 -> 1112576 px if variations apply; P2 lo glyph "L000" 4095 -> 319.98 px; P3 inside bank-0's track
        # (inherits font-variation-settings:var(--lst-0)) hi glyph of value 0 -> 1048576 + 64*k_hi(0) px.
        probes = ('<i class="r3l-probe lf-0 lh" style="position:fixed;top:-9000px;left:0;width:max-content;height:1px">&#xE000;</i>'
                  '<i class="r3l-probe lf-0 lh" style="position:fixed;top:-9000px;left:0;width:max-content;height:1px;font-variation-settings:\'H000\' 1000">&#xE000;&#xE000;</i>'
                  '<i class="r3l-probe lf-0 ll" style="position:fixed;top:-9000px;left:0;width:max-content;height:1px;font-variation-settings:\'L000\' 4095">&#xE001;</i>')
        inner = inner.replace('<div class="loop-bank-0"><div class="loop-scroll"><div class="loop-track">',
                              '<div class="loop-bank-0"><div class="loop-scroll"><div class="loop-track"><i class="r3l-probe lf-0 lh" style="position:absolute;top:0;left:0;width:max-content;height:1px">&#xE000;</i>', 1)
    body = (probes + '<div class="core-controller" style="--pass:1;--in:0.5"><div class="core-block"><div class="loop-reader"><div class="loop-input">'
            f'<div class="loop-compute"><div class="reused-output" id="reused-result">{inner}</div></div></div></div></div></div>')
    return css, body, consts


def write_page(out, p: Page, css, body):
    html = (f'<!doctype html><html><head><meta charset="utf-8"><title>{p.title}</title><style>' + css
            + "</style></head><body>" + body + "</body></html>")
    p.file = f"{p.id}.html"
    path = os.path.join(out, p.file)
    with open(path, "w") as f:
        f.write(html)
    p.bytes = os.path.getsize(path)
    p.element_count_hint = html.count("<") - html.count("</")
    return p


VARIANTS = {
    "lat-769": ("769", "today: 769 separate <number> latches per bank"),
    "lat-385-p2": ("p2", "384 packed pairs (2 x 26 bit, 1/8192) + epoch = 385 latches"),
    "lat-257-p3": ("p3", "256 packed triples (3 x 17 bit, 1/16) + epoch = 257 latches; cost model only"),
    "lat-769-split8": ("split8", "769 latches over 8 sibling sub-banks (~97-name lists)"),
    "lat-none": ("none", "no transition-property at all (floor: values revert on the flip)"),
    "lat-font": ("font", "ONE `*` settings list per bank (2 glyph axes per value, allow-discrete) + epoch = 2 latches; two-glyph carriers"),
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages"))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = [o for o in a.only.split(",") if o]
    os.makedirs(a.out, exist_ok=True)
    pages = []
    for pid, (kind, notes) in VARIANTS.items():
        if only and pid not in only:
            continue
        rng = random.Random(stable_seed(SEED, "consts"))       # identical constants in every variant
        css, body, consts = build(kind, rng)
        mrng = random.Random(stable_seed(SEED, "mutations"))
        muts = [{"selector": ".core-controller", "name": "style", "value": f"--pass:{k};--in:{mrng.uniform(0, 1):.6f}"} for k in range(2, STEPS)]
        p = Page(id=pid, family="lat", title=f"R3L {pid}", params={"kind": kind}, target=".core-controller", notes=notes,
                 hypothesis="latch cost is per STARTED transition, not per listed name", mutations=muts,
                 verify_all={"selector": ".loop-metric,.r3l-probe" if kind == "font" else ".loop-metric", "property": "width"}, consts=consts)
        pages.append(write_page(a.out, p, css, body))
    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump({"seed": SEED, "pages": [asdict(p) for p in pages]}, f, indent=1)
    for p in pages:
        print(f"{p.id:16s} {p.bytes / 1e6:6.2f} MB  elements~{p.element_count_hint:5d}  muts={len(p.mutations)}")
