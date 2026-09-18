#!/usr/bin/env python3
"""
M1 micro-benchmark page generator (pure HTML+CSS, no <script>).

Generates the MB1..MB5 pages under ./pages/ plus pages/manifest.json, which
run.mjs consumes.  Every page has the same mutation contract:

  * a registered custom property `--in` is declared on the *mutation target*
    (selector recorded in the manifest, usually `html`, sometimes `#target`);
  * 16 pre-baked random values are exposed as `html.go-0 .. html.go-15` rules
    (class trigger: the harness sets the <html> class attribute via
    CDP DOM.setAttributeValue -- no JS in the page);
  * the harness may instead set `style="--in:<fresh random>"` on the target
    (inline trigger) for fully-random-per-trial inputs.

Weights and constants are random (seeded; the seed is written into the
manifest and into the page <title>).  Size guard: every page must be < 30 MB;
the total budget is capped because the host has ~6 GiB free.

Usage:  python3 gen.py [--seed 20260918] [--only mb1,mb3] [--out pages]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Callable

MAX_PAGE_BYTES = 30 * 1024 * 1024
N_GO_VALUES = 16


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def num(x: float, digits: int = 4) -> str:
    """Compact CSS number: 0.1234 -> .1234, -0.5 -> -.5."""
    s = f"{x:.{digits}f}"
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    if s in ("", "-", ".", "-."):
        s = "0"
    return s


def prop(name: str, inherits: bool = True, initial: str = "0", syntax: str = "<number>") -> str:
    return f'@property {name}{{syntax:"{syntax}";inherits:{"true" if inherits else "false"};initial-value:{initial}}}\n'


def stable_seed(base: int, page_id: str) -> int:
    h = hashlib.sha256(f"{base}:{page_id}".encode()).hexdigest()
    return int(h[:12], 16)


@dataclass
class Page:
    id: str
    family: str
    title: str
    params: dict
    # mutation contract
    target: str = "html"                  # selector of the element that carries --in
    in_range: tuple = (0.0, 1.0)          # range for random --in values
    in_inherits: bool = True
    # what to verify changed (CSS.getComputedStyleForNode after the run)
    verify_selector: str | None = None
    verify_property: str | None = None
    hypothesis: str = ""
    # filled at write time
    file: str = ""
    bytes: int = 0
    seed: int = 0
    go_values: list = field(default_factory=list)
    in_initial: float = 0.0
    element_count_hint: int = 0
    notes: str = ""


class Builder:
    """Accumulates <style> text and <body> text, then writes the page."""

    def __init__(self, page: Page, rng: random.Random):
        self.page = page
        self.rng = rng
        self.head_css: list[str] = []
        self.css: list[str] = []
        self.body: list[str] = []
        lo, hi = page.in_range
        page.in_initial = rng.uniform(lo, hi)
        page.go_values = [rng.uniform(lo, hi) for _ in range(N_GO_VALUES)]
        # mutation contract
        self.head_css.append(prop("--in", inherits=page.in_inherits, initial=num(page.in_initial, 6)))
        self.head_css.append(f"{page.target}{{--in:{num(page.in_initial, 6)}}}\n")
        for k, v in enumerate(page.go_values):
            sel = f"html.go-{k}" if page.target == "html" else f"html.go-{k} {page.target}"
            self.head_css.append(f"{sel}{{--in:{num(v, 6)}}}\n")
        self.head_css.append("html,body{margin:0;padding:0}\n")
        # one paint-only visible probe so the page is not "empty" and a human can see the change
        self.head_css.append("#vis{position:fixed;left:0;top:0;width:8px;height:8px;background:hsl(calc(var(--in) * 360deg) 70% 50%)}\n")

    def write(self, out_dir: str) -> Page:
        p = self.page
        p.file = f"{p.id}.html"
        if p.verify_selector is None:
            p.verify_selector, p.verify_property = p.target, "--in"
        html = [
            f'<!doctype html><html><head><meta charset="utf-8"><title>{p.title} seed={p.seed}</title>\n<style>\n',
            *self.head_css,
            *self.css,
            "</style></head><body>\n<div id=\"vis\"></div>\n",
            *self.body,
            "\n</body></html>\n",
        ]
        data = "".join(html).encode("utf-8")
        p.bytes = len(data)
        if p.bytes >= MAX_PAGE_BYTES:
            raise SystemExit(f"{p.id}: {p.bytes} bytes exceeds 30 MB guard")
        with open(os.path.join(out_dir, p.file), "wb") as fh:
            fh.write(data)
        return p


# --------------------------------------------------------------------------- #
# shared constant inputs: --c2 .. --cM registered, inherited, declared on html
# --------------------------------------------------------------------------- #
def add_constants(b: Builder, count: int, on: str = "html") -> list[str]:
    names = [f"--c{j}" for j in range(2, count + 1)]
    for n in names:
        b.css.append(prop(n, inherits=True, initial="0"))
    decl = ";".join(f"{n}:{num(b.rng.uniform(0.05, 0.95))}" for n in names)
    if names:
        b.css.append(f"{on}{{{decl}}}\n")
    return names


def calc_terms(rng: random.Random, inputs: list[str], weight_digits: int = 4, var_weights: list[str] | None = None,
               literal_inputs: bool = False) -> str:
    """Return the inside of calc(): sum_j input_j * w_j (joined with ' + ')."""
    terms = []
    for j, inp in enumerate(inputs):
        w = rng.uniform(-1, 1)
        wtxt = f"var({var_weights[j]})" if var_weights else num(w, weight_digits)
        itxt = num(rng.uniform(0.05, 0.95), weight_digits) if literal_inputs else f"var({inp})"
        terms.append(f"{itxt}*{wtxt}")
    return " + ".join(terms)


NUM_RE = re.compile(r"-?\d*\.\d+")


def pad_decl(decl: str, target_len: int) -> str:
    """Lengthen numeric literals (round-robin, a few digits each) so the declaration has
    target_len bytes with the SAME token count.  Declarations already >= target_len are
    returned unchanged (their real length is recorded in the manifest)."""
    extra = target_len - len(decl)
    if extra <= 0:
        return decl
    spans = [m.span() for m in NUM_RE.finditer(decl)]
    if not spans:
        return decl + " " * extra
    per = [extra // len(spans)] * len(spans)
    for k in range(extra - sum(per)):
        per[k] += 1
    out, last = [], 0
    for (a, b), n in zip(spans, per):
        out.append(decl[last:b])
        out.append("7" * n)
        last = b
    out.append(decl[last:])
    return "".join(out)


# --------------------------------------------------------------------------- #
# MB1  per-element re-evaluation is O(declared bytes)?
# --------------------------------------------------------------------------- #
def gen_mb1(seed: int, out: str, only: set[str]) -> list[Page]:
    pages: list[Page] = []
    sweep_a = [(1000, 1), (1000, 16), (1000, 64), (10000, 1), (10000, 16), (10000, 64),
               (40000, 1), (40000, 16), (20000, 64)]  # (40000,64) would be ~46 MB: replaced by (20000,64)
    sweep_b = [(1000, 16), (10000, 16), (10000, 64), (40000, 16), (20000, 64)]
    sweep_c = [(10000, 16), (40000, 16)]

    def one_element(pid: str, K: int, M: int, variant: str) -> Page:
        page = Page(id=pid, family="mb1", title=f"MB1 {variant} K={K} M={M}",
                    params={"K": K, "M": M, "variant": variant},
                    target="html", verify_selector="#e", verify_property="--p0",
                    hypothesis="time per mutation ~ total declared bytes on E at ~43 MB/s regardless of how many declarations reference --in"
                    if variant == "b" else "time per mutation linear in K*M bytes at ~43 MB/s")
        page.seed = stable_seed(seed, pid)
        rng = random.Random(page.seed)
        b = Builder(page, rng)
        consts = add_constants(b, M)
        inputs = ["--in"] + consts  # M inputs total
        b.css.append("#e{display:block;width:1px;height:1px}\n")
        b.css.append("#p0{position:fixed;left:10px;top:0;width:8px;height:8px;background:hsl(calc(var(--p0) * 360deg) 70% 50%)}\n")
        regs, decls = [], []
        for i in range(K):
            regs.append(prop(f"--p{i}", inherits=False, initial="0"))
            if variant == "a" or i == 0:
                decls.append(f"--p{i}:calc({calc_terms(rng, inputs)})")
            else:  # MB1b: same bytes, literal*literal products, no var()
                decls.append(f"--p{i}:calc({calc_terms(rng, inputs, literal_inputs=True)})")
        b.css.extend(regs)
        b.css.append("#e{" + ";".join(decls) + "}\n")
        b.body.append('<div id="e"><div id="p0"></div></div>')
        page.element_count_hint = 3
        return b.write(out)

    def siblings(pid: str, K: int, M: int, target: str) -> Page:
        per = 200
        n_sib = K // per
        page = Page(id=pid, family="mb1", title=f"MB1c target={target} K={K} M={M} siblings={n_sib}",
                    params={"K": K, "M": M, "variant": "c", "siblings": n_sib, "per_sibling": per,
                            "mutate": "parent" if target == "html" else "one-sibling"},
                    target=target, verify_selector="#s0", verify_property="--p0",
                    hypothesis="parent mutation costs sum over all siblings (all inherit --in); one-sibling mutation costs 1/n of that")
        page.seed = stable_seed(seed, pid)
        rng = random.Random(page.seed)
        b = Builder(page, rng)
        consts = add_constants(b, M)
        inputs = ["--in"] + consts
        b.css.append("#par{display:block}\n.s{display:inline}\n")
        for j in range(per):
            b.css.append(prop(f"--p{j}", inherits=False, initial="0"))
        body = ['<div id="par">']
        for s in range(n_sib):
            sid = "target" if (target == "#target" and s == 0) else f"s{s}"
            decls = [f"--p{j}:calc({calc_terms(rng, inputs)})" for j in range(per)]
            b.css.append(f"#{sid}{{" + ";".join(decls) + "}\n")
            body.append(f'<i class="s" id="{sid}"></i>')
        body.append("</div>")
        if target == "#target":
            page.verify_selector = "#target"
        b.body.append("".join(body))
        page.element_count_hint = n_sib + 2
        return b.write(out)

    if "mb1" in only:
        for K, M in sweep_a:
            pages.append(one_element(f"mb1a-K{K}-M{M}", K, M, "a"))
        for K, M in sweep_b:
            pages.append(one_element(f"mb1b-K{K}-M{M}", K, M, "b"))
        for K, M in sweep_c:
            pages.append(siblings(f"mb1c-parent-K{K}-M{M}", K, M, "html"))
            pages.append(siblings(f"mb1c-sibling-K{K}-M{M}", K, M, "#target"))
    return pages


# --------------------------------------------------------------------------- #
# MB2  inheritance dirtying of unrelated descendants
# --------------------------------------------------------------------------- #
def gen_mb2(seed: int, out: str, only: set[str]) -> list[Page]:
    pages: list[Page] = []
    if "mb2" not in only:
        return pages
    sizes_a = [(1000, 200), (1000, 2000), (10000, 200), (10000, 2000), (40000, 200)]
    sizes_lit = [(1000, 2000), (10000, 2000), (40000, 200)]
    sizes_iso = [(1000, 2000), (10000, 2000), (40000, 200)]
    DECL_BYTES = 24  # approx bytes per `--qJ:calc(var(--cX)*.1234)` declaration

    def build(pid: str, N: int, bytes_per: int, variant: str, flavor: str) -> Page:
        D = max(1, bytes_per // DECL_BYTES)
        hyp = {
            "a": "restyle of N descendants scales with N*b (declared bytes) even though none reference --in; 'lit' flavour may hit Blink's independent-inherit fast path and cost ~0",
            "b": "with --in registered inherits:false no descendant is dirtied: cost ~= N=0 baseline",
            "c": "content-visibility:hidden wrapper: descendants are display-locked, style recalc skipped: cost ~= baseline",
            "d": "contain:style does not stop inheritance: cost ~= (a)",
            "e": "declarative shadow root does not stop inheritance: cost ~= (a)",
            "f": "depth-100 chains: same N*b bytes but inherited-variable-map copy per level; cost >= (a)",
        }[variant]
        page = Page(id=pid, family="mb2", title=f"MB2 {variant}/{flavor} N={N} b={bytes_per}",
                    params={"N": N, "bytes_per_element": bytes_per, "decls_per_element": D,
                            "variant": variant, "flavor": flavor},
                    target="html", in_inherits=(variant != "b"), hypothesis=hyp)
        page.seed = stable_seed(seed, pid)
        rng = random.Random(page.seed)
        b = Builder(page, rng)
        consts = add_constants(b, 9)  # --c2..--c9 constants on html
        for j in range(D):
            b.css.append(prop(f"--q{j}", inherits=False, initial="0"))
        b.css.append(".d{display:inline}\n")
        if variant == "c":
            b.css.append("#wrap{content-visibility:hidden;contain-intrinsic-size:1px 1px}\n")
        if variant == "d":
            b.css.append(".d{contain:style}\n")
        rules, elems = [], []
        for i in range(N):
            if flavor == "lit":
                decls = ";".join(f"--q{j}:{num(rng.uniform(-1, 1), 6)}" for j in range(D))
            else:  # var: reference a constant root property (not --in)
                decls = ";".join(f"--q{j}:calc(var({rng.choice(consts)})*{num(rng.uniform(-1, 1))})" for j in range(D))
            rules.append(f"#d{i}{{{decls}}}\n")
            elems.append(f'<i class="d" id="d{i}"></i>')
        if variant == "e":
            # rules must live inside the shadow tree to match shadow elements
            b.body.append('<div id="host"><template shadowrootmode="open"><style>\n')
            b.body.append(".d{display:inline}\n")
            for j in range(D):
                pass  # @property is document-global; already registered in the head
            b.body.extend(rules)
            b.body.append("</style>")
            b.body.extend(elems)
            b.body.append("</template></div>")
        elif variant == "f":
            b.css.extend(rules)
            # N/100 chains of depth 100; each element carries its own #dI rule
            depth = 100
            chains = max(1, N // depth)
            out_parts = ['<div id="wrap">']
            idx = 0
            for _ in range(chains):
                opened = 0
                for _ in range(depth):
                    if idx >= N:
                        break
                    out_parts.append(f'<i class="d" id="d{idx}">')
                    idx += 1
                    opened += 1
                out_parts.append("</i>" * opened)
            out_parts.append("</div>")
            b.body.append("".join(out_parts))
        else:
            b.css.extend(rules)
            b.body.append('<div id="wrap">' + "".join(elems) + "</div>")
        page.element_count_hint = N + 3
        return b.write(out)

    # baseline: nothing but the mutation
    pages.append(build("mb2-a-var-N0-b0", 0, 0, "a", "var"))
    for N, bp in sizes_a:
        pages.append(build(f"mb2-a-var-N{N}-b{bp}", N, bp, "a", "var"))
    for N, bp in sizes_lit:
        pages.append(build(f"mb2-a-lit-N{N}-b{bp}", N, bp, "a", "lit"))
    for variant in "bcdef":
        for N, bp in sizes_iso:
            pages.append(build(f"mb2-{variant}-var-N{N}-b{bp}", N, bp, variant, "var"))
    return pages


# --------------------------------------------------------------------------- #
# MB3  passes per boundary mechanism
# --------------------------------------------------------------------------- #
def gen_mb3(seed: int, out: str, only: set[str]) -> list[Page]:
    pages: list[Page] = []
    if "mb3" not in only:
        return pages
    TERMS = 64

    def stage_calc(rng: random.Random, xname: str, consts: list[str]) -> str:
        # contractive: y = 100 + .5*x + sum_j c_j*w_j (|w_j|<.01) keeps y in [150, 650] for x in [100,1000)
        terms = [f"var({xname})*.5"]
        for c in consts[: TERMS - 1]:
            terms.append(f"var({c})*{num(rng.uniform(-0.01, 0.01), 5)}")
        return "calc(100 + " + " + ".join(terms) + ")"

    def build(pid: str, mech: str, S: int) -> Page:
        hyp = {
            "container": "each boundary costs >=1 extra UpdateLayoutTree + 1 Layout (interleaved container-query style/layout); per-boundary wall time is the atom of the 119 recalcs/71 layouts per token",
            "anchor": "anchor-size -> size container -> cqi: two geometry hops per boundary; expect >= container cost, possibly 2x Layout",
            "viewtimeline": "scroll-driven animation readback: boundary needs a frame (animation update) per stage: expect S extra frames (~16.7 ms each in headless?)",
            "style": "control: pure var() chain resolves in ONE UpdateLayoutTree and 0 Layout regardless of S",
        }[mech]
        page = Page(id=pid, family="mb3", title=f"MB3 {mech} S={S}",
                    params={"mechanism": mech, "S": S, "terms": TERMS},
                    target="html", in_range=(100.0, 1000.0),
                    verify_selector=f"#r{S - 1}", verify_property=f"--x{S}", hypothesis=hyp)
        page.seed = stable_seed(seed, pid)
        rng = random.Random(page.seed)
        b = Builder(page, rng)
        consts = add_constants(b, TERMS)
        for s in range(S):
            b.css.append(prop(f"--x{s}", inherits=True, initial="0"))
            b.css.append(prop(f"--y{s}", inherits=True, initial="0"))
        b.css.append(prop(f"--x{S}", inherits=True, initial="0"))
        b.css.append(prop("--p", inherits=False, initial=".5"))
        b.css.append("#root{position:relative;height:0}\n")

        if mech == "style":
            # nested: stage s element sets --y{s}; child stage reads --x{s+1}: var(--y{s})
            for s in range(S):
                xin = "--in" if s == 0 else f"--x{s}"
                b.css.append(f"#s{s}{{--y{s}:{stage_calc(rng, xin, consts)}}}\n")
                b.css.append(f"#r{s}{{--x{s + 1}:var(--y{s})}}\n")
            html = ""
            for s in range(S):
                html += f'<i id="s{s}"><i id="r{s}">'
            html += "</i></i>" * S
            b.body.append(f'<div id="root">{html}</div>')

        elif mech == "container":
            # nested size containers: stage s width = y{s}px; reader inside it reads 100cqi
            for s in range(S):
                xin = "--in" if s == 0 else f"--x{s}"
                b.css.append(f"#s{s}{{display:block;container-type:inline-size;height:1px;--y{s}:{stage_calc(rng, xin, consts)};width:calc(var(--y{s}) * 1px)}}\n")
                b.css.append(f"#r{s}{{display:block;height:1px;--x{s + 1}:calc(100cqi / 1px)}}\n")
            html = ""
            for s in range(S):
                html += f'<div id="s{s}"><div id="r{s}">'
            html += "</div></div>" * S
            b.body.append(f'<div id="root">{html}</div>')

        elif mech == "anchor":
            # stage s element is an anchor (--a{s}); the next consumer is an abspos sibling
            # sized by anchor-size(--a{s} width) acting as a size container; its child reads 100cqi
            b.css.append(".anc{position:absolute;left:0;height:1px;container-type:inline-size}\n")
            for s in range(S):
                xin = "--in" if s == 0 else f"--x{s}"
                b.css.append(f"#s{s}{{display:block;height:1px;anchor-name:--a{s};--y{s}:{stage_calc(rng, xin, consts)};width:calc(var(--y{s}) * 1px)}}\n")
                b.css.append(f"#c{s}{{top:{2 * s + 2}px;position-anchor:--a{s};width:anchor-size(--a{s} width)}}\n")
                b.css.append(f"#r{s}{{display:block;height:1px;--x{s + 1}:calc(100cqi / 1px)}}\n")
            parts = []
            for s in range(S):
                # stage s lives inside consumer c{s-1}'s reader for s>0 so it inherits --x{s}
                if s == 0:
                    parts.append('<div id="s0" class="st"></div>')
                parts.append(f'<div id="c{s}" class="anc"><div id="r{s}">')
                if s + 1 < S:
                    parts.append(f'<div id="s{s + 1}" class="st"></div>')
                parts.append("</div></div>")
            b.body.append(f'<div id="root">{"".join(parts)}</div>')

        elif mech == "viewtimeline":
            # stage s: metric width = y{s}px inside an offscreen 100px scroller with a 4000px track;
            # reader r{s} animates --p over view-timeline --t{s} (cover): p = 100/(100+m) => m = 100/p - 100
            b.css.append("#root{timeline-scope:" + ",".join(f"--t{s}" for s in range(S)) + "}\n")
            b.css.append(".scroller{position:fixed;left:-20000px;top:0;width:100px;height:1px;overflow-x:scroll;overflow-y:hidden}\n")
            b.css.append(".track{position:relative;width:4000px;height:1px}\n")
            b.css.append(".metric{position:absolute;left:0;top:0;height:1px}\n")
            b.css.append("@keyframes kp{from{--p:0}to{--p:1}}\n")
            for s in range(S):
                xin = "--in" if s == 0 else f"--x{s}"
                b.css.append(f"#s{s}{{display:block;--y{s}:{stage_calc(rng, xin, consts)}}}\n")
                b.css.append(f"#m{s}{{width:calc(var(--y{s}) * 1px);view-timeline:--t{s} inline}}\n")
                b.css.append(f"#r{s}{{display:block;height:1px;animation-name:kp;animation-duration:1s;animation-timing-function:linear;"
                             f"animation-fill-mode:both;animation-timeline:--t{s};animation-range:cover;--x{s + 1}:calc(100 / var(--p) - 100)}}\n")
            parts = []
            for s in range(S):
                parts.append(f'<div id="s{s}"><div class="scroller"><div class="track"><div class="metric" id="m{s}"></div></div></div></div>')
                parts.append(f'<div id="r{s}">')
            parts.append("</div>" * S)
            b.body.append(f'<div id="root">{"".join(parts)}</div>')
        page.notes = "recovered value has ~1e-4 relative error (float progress); timing only" if mech == "viewtimeline" else ""
        page.element_count_hint = 3 * S + 3
        return b.write(out)

    for mech in ("style", "container", "anchor", "viewtimeline"):
        for S in (1, 4, 12):
            pages.append(build(f"mb3-{mech}-S{S}", mech, S))
    return pages


# --------------------------------------------------------------------------- #
# MB4  retained animation servicing
# --------------------------------------------------------------------------- #
def gen_mb4(seed: int, out: str, only: set[str]) -> list[Page]:
    pages: list[Page] = []
    if "mb4" not in only:
        return pages

    def build(pid: str, A: int, kind: str, scope: str) -> Page:
        hyp = {
            "fwd": "A finished fill-forwards animations: per-mutation extra cost from animation bookkeeping (effect stack apply on restyle when scope=inh; timeline/document-animations servicing when scope=sib)",
            "paused": "A paused animations remain active: expect per-frame servicing cost even for an unrelated (sib) mutation",
            "static": "same values as plain declarations: control, expect ~MB2 lit cost",
        }[kind]
        page = Page(id=pid, family="mb4", title=f"MB4 {kind} A={A} scope={scope}",
                    params={"A": A, "kind": kind, "scope": scope},
                    target="html" if scope == "inh" else "#target",
                    verify_selector="#target", verify_property="--out", hypothesis=hyp)
        page.seed = stable_seed(seed, pid)
        rng = random.Random(page.seed)
        b = Builder(page, rng)
        b.css.append(prop("--a", inherits=False, initial="0"))
        b.css.append(prop("--out", inherits=False, initial="0"))
        # the unrelated small mutation consumer (a sibling of the animated block)
        b.css.append("#target{display:block;height:1px;--out:calc(var(--in) * .5 + .25)}\n")
        b.css.append(".a{display:inline}\n")
        if kind == "fwd":
            b.css.append(".a{animation-duration:1ms;animation-timing-function:linear;animation-fill-mode:forwards}\n")
        elif kind == "paused":
            b.css.append(".a{animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-play-state:paused}\n")
        elems = []
        for i in range(A):
            v = num(rng.uniform(-1, 1), 6)
            if kind == "static":
                b.css.append(f"#a{i}{{--a:{v}}}\n")
            else:
                b.css.append(f"@keyframes k{i}{{to{{--a:{v}}}}}\n#a{i}{{animation-name:k{i}}}\n")
            elems.append(f'<i class="a" id="a{i}"></i>')
        b.body.append('<div id="target"></div><div id="anim">' + "".join(elems) + "</div>")
        page.element_count_hint = A + 4
        return b.write(out)

    for scope in ("sib", "inh"):
        pages.append(build(f"mb4-none-A0-{scope}", 0, "static", scope))
        for A in (1000, 10000, 100000):
            for kind in ("fwd", "paused", "static"):
                pages.append(build(f"mb4-{kind}-A{A}-{scope}", A, kind, scope))
    return pages


# --------------------------------------------------------------------------- #
# MB5  what the 43 MB/s is: same bytes, different spellings
# --------------------------------------------------------------------------- #
def gen_mb5(seed: int, out: str, only: set[str]) -> list[Page]:
    pages: list[Page] = []
    if "mb5" not in only:
        return pages
    K = 10000
    M = 16
    DECL_LEN = 320  # declarations (except lit-short) are padded up to this many bytes; calc-varw is naturally longer (~430 B) and is left as-is

    def build(pid: str, spelling: str) -> Page:
        hyp = {
            "lit-short": "lower bound: K registered literals, ~0.1 MB; cost = cascade apply only",
            "lit-calc": "same bytes as calc-var16 but no var(): parsed once at sheet load; if cheap, the 43 MB/s is var() substitution/re-parse not cascade",
            "calc-var16": "reference point: 16 var() + 16 multiplies per declaration",
            "calc-var1": "1 var() + 15 literal products: if ~= lit-calc, cost tracks var() count not term count",
            "calc-varw": "32 var() per declaration (weights via var(--w)): if ~2x calc-var16, cost ~ var() count",
            "func16": "one @function with 16 args invoked K times: measures per-invocation overhead vs inline calc",
            "unreg-var16": "unregistered --p: substitution happens but no typed parse/eval: isolates calc evaluation",
        }[spelling]
        page = Page(id=pid, family="mb5", title=f"MB5 {spelling} K={K}",
                    params={"K": K, "M": M, "spelling": spelling, "decl_len": DECL_LEN},
                    target="#target", verify_selector="#target", verify_property="--p0", hypothesis=hyp)
        page.seed = stable_seed(seed, pid)
        rng = random.Random(page.seed)
        b = Builder(page, rng)
        consts = add_constants(b, M, on="body")  # constants on body: NOT restyled when #target mutates
        inputs = ["--in"] + consts
        b.css.append("#target{display:block;width:1px;height:1px}\n")
        b.css.append("#p0{position:fixed;left:10px;top:0;width:8px;height:8px;background:hsl(calc(var(--p0) * 360deg) 70% 50%)}\n")
        if spelling == "func16":
            args = ",".join(f"--w{j}" for j in range(M))
            body = " + ".join(f"var({inp})*var(--w{j})" for j, inp in enumerate(inputs))
            b.css.append(f"@function --dot16({args}) returns <number> {{result:calc({body})}}\n")
        if spelling == "calc-varw":
            # weights as registered properties on body (ancestor, not restyled by the #target mutation)
            wregs, wdecls = [], []
            for i in range(K):
                for j in range(M):
                    wregs.append(prop(f"--w{i}_{j}", inherits=True, initial="0"))
                    wdecls.append(f"--w{i}_{j}:{num(rng.uniform(-1, 1))}")
            b.css.extend(wregs)
            b.css.append("body{" + ";".join(wdecls) + "}\n")
        decls = []
        for i in range(K):
            if spelling != "unreg-var16":
                b.css.append(prop(f"--p{i}", inherits=False, initial="0"))
            if spelling == "lit-short":
                d = f"--p{i}:{num(rng.uniform(-1, 1))}"
            elif spelling == "lit-calc":
                d = pad_decl(f"--p{i}:calc({calc_terms(rng, inputs, literal_inputs=True)})", DECL_LEN)
            elif spelling in ("calc-var16", "unreg-var16"):
                d = pad_decl(f"--p{i}:calc({calc_terms(rng, inputs)})", DECL_LEN)
            elif spelling == "calc-var1":
                first = f"var(--in)*{num(rng.uniform(-1, 1))}"
                rest = calc_terms(rng, inputs[1:], literal_inputs=True)
                d = pad_decl(f"--p{i}:calc({first} + {rest})", DECL_LEN)
            elif spelling == "calc-varw":
                d = pad_decl(f"--p{i}:calc({calc_terms(rng, inputs, var_weights=[f'--w{i}_{j}' for j in range(M)])})", DECL_LEN)
            elif spelling == "func16":
                d = pad_decl(f"--p{i}:--dot16({','.join(num(rng.uniform(-1, 1)) for _ in range(M))})", DECL_LEN)
            decls.append(d)
        b.css.append("#target{" + ";".join(decls) + "}\n")
        b.body.append('<div id="target"><div id="p0"></div></div>')
        page.params["decl_bytes_total"] = sum(len(d) for d in decls)
        page.element_count_hint = 3
        return b.write(out)

    for sp in ("lit-short", "lit-calc", "calc-var16", "calc-var1", "calc-varw", "func16", "unreg-var16"):
        pages.append(build(f"mb5-{sp}-K{K}", sp))
    return pages


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260918)
    ap.add_argument("--only", default="mb1,mb2,mb3,mb4,mb5")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages"))
    a = ap.parse_args()
    only = set(a.only.split(","))
    os.makedirs(a.out, exist_ok=True)

    pages: list[Page] = []
    for fn in (gen_mb1, gen_mb2, gen_mb3, gen_mb4, gen_mb5):
        pages.extend(fn(a.seed, a.out, only))

    manifest_path = os.path.join(a.out, "manifest.json")
    if only != {"mb1", "mb2", "mb3", "mb4", "mb5"} and os.path.exists(manifest_path):
        with open(manifest_path) as fh:
            old = json.load(fh)
        regenerated = {p.id for p in pages}
        kept = [Page(**entry) for entry in old["pages"] if entry["id"] not in regenerated and entry["family"] not in only]
        pages = sorted(kept + pages, key=lambda p: ["mb1", "mb2", "mb3", "mb4", "mb5"].index(p.family))
    manifest = {
        "generator": "gen.py",
        "seed": a.seed,
        "python": sys.version.split()[0],
        "n_go_values": N_GO_VALUES,
        "pages": [asdict(p) for p in pages],
    }
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    total = sum(p.bytes for p in pages)
    print(f"{'page':44} {'bytes':>12}")
    for p in pages:
        print(f"{p.id:44} {p.bytes:>12,}")
    print(f"{'TOTAL':44} {total:>12,}  ({len(pages)} pages)")


if __name__ == "__main__":
    main()
