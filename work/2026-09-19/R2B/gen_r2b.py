#!/usr/bin/env python3
"""
R2B page generator (MB6..MB9), pure HTML+CSS, no <script>.  Reuses gen.py's Page/Builder/mutation
contract: a registered `--in` on the mutation target, 16 pre-baked random values behind
`html.go-k` classes (the harness flips the <html> class via CDP), verify property read back.

  python3 gen_r2b.py [--seed 20260919] [--only mb6,mb7,mb8,mb9] [--out pages]

Fonts: pages/fonts/r2b-{0..11}.ttf (make_fonts.py): 256 HVAR axes each, tags X{k*256+i:03X},
range +-16384, cmap U+F0000 + k*768 + i.  A list of L entries uses tags X000..X{L-1:03X} and a
font-family stack of ceil(L/256) fonts; the element's text is one glyph from every font in the stack.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen import Page, Builder, prop, num, stable_seed, N_GO_VALUES  # noqa: E402

ROUND = "round(nearest,calc(var(--{x})/266.248396912*16384),1)"  # the demo's consumer shape (F2 §1, head.css)
SCALE = 266.248396912


def tag(i: int) -> str:
    return f"X{i:03X}"


def font_faces(b: Builder, n_fonts: int) -> str:
    fams = []
    for k in range(n_fonts):
        fam = f"R2B{k}"
        fams.append(fam)
        b.head_css.append(f'@font-face{{font-family:{fam};src:url("fonts/r2b-{k}.ttf") format("truetype")}}\n')
    return ",".join(fams)


def font_text(n_fonts: int) -> str:
    return "".join(f"&#x{0xF0000 + k * 768:X};" for k in range(n_fonts))


# --------------------------------------------------------------------------- #
# MB6  inherited registration count tax
# --------------------------------------------------------------------------- #
def gen_mb6(seed: int, out: str) -> list[Page]:
    pages: list[Page] = []
    N = 5000

    def build(pid: str, K: int, inh: bool, on: str, q_inh: bool, declared: bool = True) -> Page:
        page = Page(id=pid, family="mb6", title=f"MB6 K={K} inherits={inh} on={on} q_inh={q_inh} declared={declared}",
                    params={"N": N, "K": K, "root_inherits": inh, "declared_on": on, "q_inherits": q_inh, "declared": declared},
                    target="#par", verify_selector="#d0", verify_property="--q",
                    hypothesis="per-element restyle cost and RSS independent of K unless descendants write an inherited custom property under a non-root ancestor that holds K inherited values (Blink StyleInheritedVariables root+delta layout)")
        page.seed = stable_seed(seed, pid)
        rng = random.Random(page.seed)
        b = Builder(page, rng)
        # K registrations
        for j in range(K):
            b.css.append(prop(f"--k{j}", inherits=inh, initial=num(rng.uniform(-1, 1), 4)))
        if declared:
            b.css.append(f"{on}{{" + ";".join(f"--k{j}:{num(rng.uniform(-1, 1), 4)}" for j in range(K)) + "}\n")
        b.css.append(prop("--q", inherits=q_inh, initial="0"))
        b.css.append("#par{display:block}\n.d{display:inline}\n")
        for i in range(N):
            b.css.append(f"#d{i}{{--q:calc(var(--in)*{num(rng.uniform(-1, 1), 4)})}}\n")
        b.body.append('<div id="par">' + "".join(f'<i class="d" id="d{i}"></i>' for i in range(N)) + "</div>")
        page.element_count_hint = N + 3
        return b.write(out)

    for K in (16, 1000, 15000):
        for inh in (True, False):
            for on in ("html", "body"):
                pages.append(build(f"mb6-K{K}-inh{int(inh)}-on{on}-q1", K, inh, on, True))
    for on in ("html", "body"):
        pages.append(build(f"mb6-K15000-inh1-on{on}-q0", 15000, True, on, False))
    pages.append(build("mb6-K16-inh1-onbody-q0", 16, True, "body", False))
    pages.append(build("mb6-K15000-inh1-undeclared-q1", 15000, True, "html", True, declared=False))
    return pages


# --------------------------------------------------------------------------- #
# MB7  font-variation-settings list evaluation cost (L entries, M elements, 4 spellings)
# --------------------------------------------------------------------------- #
SPELLINGS = ("lit", "var", "round", "hoist")


def fvs_entries(rng: random.Random, L: int, spelling: str) -> str:
    parts = []
    for i in range(L):
        x = "in" if i == 0 else f"x{i}"
        if spelling == "lit":
            parts.append(f'"{tag(i)}" {int(round(rng.uniform(-SCALE, SCALE) / SCALE * 16384))}')
        elif spelling == "round-lit":  # MB8 mechanism probe: round() of a literal, no var()
            parts.append(f'"{tag(i)}" round(nearest,{num(rng.uniform(-16384, 16384), 3)},1)')
        elif spelling == "calcdiv":  # the combined bundle's shared-qkv/attn/fc/proj shape: calc(var(--n) / var(--range))
            parts.append(f'"{tag(i)}" calc(var(--{x}) / var(--r))')
        elif spelling == "calc":  # MB8 mechanism probe: calc(var()) without round()
            parts.append(f'"{tag(i)}" calc(var(--{x})/266.248396912*16384)')
        elif spelling == "var":
            parts.append(f'"{tag(i)}" var(--{x})')
        elif spelling == "round":
            parts.append(f'"{tag(i)}" ' + ROUND.format(x=x))
        elif spelling == "hoist":
            parts.append(f'"{tag(i)}" var(--q{i})')
    return ",".join(parts)


def setup_parent(b: Builder, rng: random.Random, L: int, spelling: str, const_inputs: bool = False) -> None:
    """--x1..--x{L-1} registered inherited numbers with literal values on #par; --x0 = var(--in) (or a literal
    when const_inputs, MB8); for 'hoist' also --q0..--q{L-1} = round(...) on #par."""
    decls = []
    for i in range(L):
        b.css.append(prop(f"--x{i}", inherits=True, initial="0"))
        if i == 0:
            decls.append("--x0:" + (num(rng.uniform(-SCALE, SCALE), 6) if const_inputs else "var(--in)"))
        else:
            decls.append(f"--x{i}:{num(rng.uniform(-SCALE, SCALE), 6)}")
    if spelling == "hoist":
        for i in range(L):
            b.css.append(prop(f"--q{i}", inherits=True, initial="0"))
            decls.append(f"--q{i}:" + ROUND.format(x=f"x{i}"))
    elif spelling == "hoist-lit":  # MB8 var-const: literal integers on the parent
        for i in range(L):
            b.css.append(prop(f"--q{i}", inherits=True, initial="0"))
            decls.append(f"--q{i}:{int(round(rng.uniform(-SCALE, SCALE) / SCALE * 16384))}")
    if spelling == "calcdiv":
        b.css.append(prop("--r", inherits=True, initial="1"))
        decls.append(f"--r:{num(SCALE / 16384, 9)}")
    b.css.append("#par{display:block;width:800px}\n#par{" + ";".join(decls) + "}\n")


def gen_mb7(seed: int, out: str) -> list[Page]:
    pages: list[Page] = []

    def build(pid: str, L: int, M: int, spelling: str, shared: bool) -> Page:
        n_fonts = math.ceil(L / 256)
        page = Page(id=pid, family="mb7", title=f"MB7 {spelling} L={L} M={M} shared={shared}",
                    params={"L": L, "M": M, "spelling": spelling, "shared_rule": shared, "n_fonts": n_fonts},
                    target="#par", in_range=(-SCALE, SCALE),
                    verify_selector="#f0", verify_property="--in" if spelling == "lit" else "font-variation-settings",
                    hypothesis="restyle ms = M * (c_elem + L * c_entry[spelling]); c_entry(round) ~ 16x c_entry(var/hoist) (M1 MB5 law); a changed list re-instantiates the font per unique list -> Layout ms grows with L and with M unless lists are shared")
        page.seed = stable_seed(seed, pid)
        rng = random.Random(page.seed)
        b = Builder(page, rng)
        fams = font_faces(b, n_fonts)
        setup_parent(b, rng, L, spelling)
        b.css.append(f".f{{display:inline-block;white-space:pre;font:16px {fams};font-kerning:none;line-height:1}}\n")
        if shared:
            b.css.append(".f{font-variation-settings:" + fvs_entries(rng, L, spelling) + "}\n")
        else:
            for m in range(M):
                # one differing literal entry per element defeats MatchedPropertiesCache sharing (demo: per-(H,S) rules)
                b.css.append(f"#f{m}{{font-variation-settings:" + fvs_entries(rng, L, spelling) + f',"P000" {m}}}\n')
        txt = font_text(n_fonts)
        b.body.append('<div id="par">' + "".join(f'<i class="f" id="f{m}">{txt}</i>' for m in range(M)) + "</div>")
        page.element_count_hint = M + 3
        return b.write(out)

    for L in (64, 256, 768, 3072):
        for sp in SPELLINGS:
            pages.append(build(f"mb7-{sp}-L{L}-M32-uniq", L, 32, sp, False))
    for M in (1, 128):
        for sp in SPELLINGS:
            pages.append(build(f"mb7-{sp}-L768-M{M}-uniq", 768, M, sp, False))
    for sp in SPELLINGS:
        pages.append(build(f"mb7-{sp}-L768-M128-shared", 768, 128, sp, True))
    for L in (768, 3072):
        pages.append(build(f"mb7-calcdiv-L{L}-M32-uniq", L, 32, "calcdiv", False))
    pages.append(build("mb7-calcdiv-L768-M128-uniq", 768, 128, "calcdiv", False))
    return pages


# --------------------------------------------------------------------------- #
# MB8  dirtied font element whose list does NOT change
# --------------------------------------------------------------------------- #
def gen_mb8(seed: int, out: str) -> list[Page]:
    pages: list[Page] = []
    L, M = 768, 128

    def build(pid: str, kind: str) -> Page:
        n_fonts = math.ceil(L / 256)
        page = Page(id=pid, family="mb8", title=f"MB8 {kind} L={L} M={M}",
                    params={"L": L, "M": M, "kind": kind},
                    target="#par", in_range=(-SCALE, SCALE), verify_selector="#f0", verify_property="--in",
                    hypothesis="an inherited write that does not touch the list still re-applies the L-entry list (M1 MB1b: 60-70% of dependent cost) and, if the resolved list is unchanged, does NOT re-instantiate the font (Layout ~ 0)")
        page.seed = stable_seed(seed, pid)
        rng = random.Random(page.seed)
        b = Builder(page, rng)
        if kind == "plain":
            b.css.append(prop("--z", inherits=False, initial="0"))
            b.css.append("#par{display:block;width:800px}\n.f{display:inline-block;width:1px;height:1px}\n")
            for m in range(M):
                b.css.append(f"#f{m}{{--z:{m}}}\n")
            b.body.append('<div id="par">' + "".join(f'<i class="f" id="f{m}"></i>' for m in range(M)) + "</div>")
        else:
            spelling = {"lit": "lit", "nofont-lit": "lit", "var-const": "hoist", "round-const": "round",
                        "hoist-const": "hoist", "calc-const": "calc", "round-lit": "round-lit"}[kind]
            if kind == "nofont-lit":
                b.css.append("#par{display:block;width:800px}\n.f{display:inline-block;white-space:pre;font:16px monospace;line-height:1}\n")
                txt = "a"
            else:
                fams = font_faces(b, n_fonts)
                b.css.append(f".f{{display:inline-block;white-space:pre;font:16px {fams};font-kerning:none;line-height:1}}\n")
                txt = font_text(n_fonts)
            if kind == "var-const":
                setup_parent(b, rng, L, "hoist-lit", const_inputs=True)  # literal integer --qI on the parent
            elif kind in ("round-const", "calc-const"):
                setup_parent(b, rng, L, spelling, const_inputs=True)  # --x0 literal: nothing in the list depends on --in
            elif kind == "hoist-const":
                # parent computes --qI = round(calc(var(--xI)/c*c)) from constant --xI (the proposed hoist); children read var(--qI)
                setup_parent(b, rng, L, "hoist", const_inputs=True)
            else:
                b.css.append("#par{display:block;width:800px}\n")
            for m in range(M):
                b.css.append(f"#f{m}{{font-variation-settings:" + fvs_entries(rng, L, spelling) + f',"P000" {m}}}\n')
            b.body.append('<div id="par">' + "".join(f'<i class="f" id="f{m}">{txt}</i>' for m in range(M)) + "</div>")
        page.element_count_hint = M + 3
        return b.write(out)

    for kind in ("plain", "nofont-lit", "lit", "var-const", "round-const", "hoist-const", "calc-const", "round-lit"):
        pages.append(build(f"mb8-{kind}-L{L}-M{M}", kind))
    return pages


# --------------------------------------------------------------------------- #
# MB9  frame overhead knobs
# --------------------------------------------------------------------------- #
def gen_mb9(seed: int, out: str) -> list[Page]:
    pages: list[Page] = []
    NSUB = 50000
    NFC = 1926

    def build(pid: str, knob: str, mouse: bool, dirty: bool, subtree: bool = True) -> Page:
        page = Page(id=pid, family="mb9", title=f"MB9 {knob} mouse={mouse} dirty={dirty} subtree={subtree}",
                    params={"knob": knob, "mouse": mouse, "dirty": dirty, "subtree": subtree, "NSUB": NSUB if subtree else 0,
                            "NFC": NFC if knob.startswith("fixed") or knob.startswith("staticfc") else 0},
                    target="html", verify_selector="#gate", verify_property="animation-name",
                    hypothesis="(gate animates width so each frame has Layout, as the demo) per-frame PrePaint / paint-lifecycle / hit-test ms scale with the number of live layout objects; contain:paint and visibility:hidden cut paint-side walks, pointer-events:none (or no cursor) cuts hit-test, position:fixed containers add per-frame property-tree cost")
        page.seed = stable_seed(seed, pid)
        rng = random.Random(page.seed)
        b = Builder(page, rng)
        b.css.append(prop("--gv", inherits=False, initial="0"))
        b.css.append("#gate{position:fixed;left:20px;top:0;width:calc(8px + var(--gv)*8px);height:8px;background:hsl(calc(var(--gv)*360deg) 70% 50%);"
                     "animation-duration:1ms;animation-timing-function:linear;animation-fill-mode:forwards}\n")
        for k in range(N_GO_VALUES):
            b.css.append(f"@keyframes g{k}{{to{{--gv:{num(rng.uniform(0, 1), 4)}}}}}\nhtml.go-{k} #gate{{animation-name:g{k}}}\n")
        b.css.append("#sub{width:800px;font-size:0;line-height:0}\n.s{display:inline-block;width:1px;height:1px}\n")
        if knob == "containpaint":
            b.css.append("#sub{contain:paint}\n")
        elif knob == "vishidden":
            b.css.append("#sub{visibility:hidden}\n")
        elif knob == "noptr":
            b.css.append("html{pointer-events:none}\n")
        elif knob == "fixedfc":
            b.css.append(".fc{position:fixed;left:0;top:0;width:1px;height:1px;container-type:size}\n")
        elif knob == "staticfc":
            b.css.append(".fc{display:block;width:1px;height:1px;container-type:size}\n")
        body = ['<div id="gate"></div>']
        if subtree:
            if dirty:
                b.css.append(prop("--z", inherits=False, initial="0"))
                for i in range(NSUB):
                    b.css.append(f"#s{i}{{--z:calc(var(--in)*{num(rng.uniform(-1, 1), 3)})}}\n")
                body.append('<div id="sub">' + "".join(f'<i class="s" id="s{i}"></i>' for i in range(NSUB)) + "</div>")
            else:
                body.append('<div id="sub">' + '<i class="s"></i>' * NSUB + "</div>")
        if knob in ("fixedfc", "staticfc"):
            body.append('<div id="fcs">' + '<div class="fc"></div>' * NFC + "</div>")
        b.body.append("".join(body))
        page.element_count_hint = (NSUB if subtree else 0) + 4
        return b.write(out)

    pages.append(build("mb9-none-mouse", "default", True, False, subtree=False))
    pages.append(build("mb9-default-nomouse", "default", False, False))
    pages.append(build("mb9-default-mouse", "default", True, False))
    pages.append(build("mb9-containpaint-mouse", "containpaint", True, False))
    pages.append(build("mb9-vishidden-mouse", "vishidden", True, False))
    pages.append(build("mb9-noptr-mouse", "noptr", True, False))
    pages.append(build("mb9-fixedfc-mouse", "fixedfc", True, False))
    pages.append(build("mb9-staticfc-mouse", "staticfc", True, False))
    pages.append(build("mb9-default-mouse-dirty", "default", True, True))
    pages.append(build("mb9-containpaint-mouse-dirty", "containpaint", True, True))
    pages.append(build("mb9-vishidden-mouse-dirty", "vishidden", True, True))
    pages.append(build("mb9-noptr-mouse-dirty", "noptr", True, True))
    return pages


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260919)
    ap.add_argument("--only", default="mb6,mb7,mb8,mb9")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages"))
    a = ap.parse_args()
    only = set(a.only.split(","))
    os.makedirs(a.out, exist_ok=True)
    pages: list[Page] = []
    for fam, fn in (("mb6", gen_mb6), ("mb7", gen_mb7), ("mb8", gen_mb8), ("mb9", gen_mb9)):
        if fam in only:
            pages.extend(fn(a.seed, a.out))
    manifest_path = os.path.join(a.out, "manifest.json")
    if only != {"mb6", "mb7", "mb8", "mb9"} and os.path.exists(manifest_path):
        with open(manifest_path) as fh:
            old = json.load(fh)
        kept = [Page(**e) for e in old["pages"] if e["family"] not in only]
        pages = kept + pages
    with open(manifest_path, "w") as fh:
        json.dump({"generator": "gen_r2b.py", "seed": a.seed, "python": sys.version.split()[0],
                   "n_go_values": N_GO_VALUES, "pages": [asdict(p) for p in pages]}, fh, indent=1)
    total = sum(p.bytes for p in pages)
    for p in pages:
        print(f"{p.id:40} {p.bytes:>12,}")
    print(f"{'TOTAL':40} {total:>12,}  ({len(pages)} pages)")


if __name__ == "__main__":
    main()
