#!/usr/bin/env python3
"""F5 latch micro-test pages (Fix 4), same manifest schema as M1's gen.py.

12 bank elements x 1,536 latched custom properties (768 `*` 64-axis lists +
768 <number>, exactly the ctx32 KV bank shape), latched as

  transition  emitter idiom: value written by `html:not([class]) .bank-L{...}`,
              base `transition-property:<1536 names>;transition-delay:86400s`;
              the harness' warm-up mutation (html.go-0) un-matches the write rule
              -> 18,432 retained transitions in their delay phase
  paused      1,536 `animation-name` entries per bank, animation-play-state:paused
  static      plain declarations (12 rules x 1,536 decls), no animation
  static-cv   static, banks wrapped in content-visibility:hidden
  none        no banks (floor)

scope=sib: traced mutation is an unrelated `#target{--in}` change (per-frame
servicing + bookkeeping); scope=inh: `--in` (inherits:true) changes on <html>
so every bank is restyled (the emitter's S2 case: qkv write above the banks).
"""

import json
import os
import random
import sys
from dataclasses import asdict, dataclass, field

BANKS, SLOTS, HEADS, DIM = 12, 32, 12, 64
N_GO = 16


@dataclass
class Page:
    id: str
    family: str
    title: str
    params: dict
    target: str
    in_range: list = field(default_factory=lambda: [0.0, 1.0])
    in_inherits: bool = True
    verify_selector: str = "#target"
    verify_property: str = "--out"
    hypothesis: str = ""
    file: str = ""
    bytes: int = 0
    seed: int = 0
    go_values: list = field(default_factory=list)
    in_initial: float = 0.0
    element_count_hint: int = 0
    notes: str = ""


def num(v, d=6):
    s = f"{v:.{d}f}".rstrip("0").rstrip(".")
    return s.replace("0.", ".").replace("-0.", "-.") or "0"


def names():
    out = []
    for slot in range(SLOTS):
        for head in range(HEADS):
            for kind in ("k", "v", "ks", "vs"):
                out.append((f"--fc-{kind}-{slot}-{head}", kind in ("k", "v")))
    return out


def build(pid, kind, scope, seed, out_dir):
    rng = random.Random(seed)
    fields = names()
    page = Page(
        id=pid,
        family="f5latch",
        title=f"F5 latch {kind} scope={scope}",
        params={"kind": kind, "scope": scope, "banks": BANKS, "fields": len(fields)},
        target="html" if scope == "inh" else "#target",
        seed=seed,
        go_values=[rng.random() for _ in range(N_GO)],
        in_initial=rng.random(),
        hypothesis={
            "transition": "18,432 in-delay transitions: expect per-frame servicing ~0.7us each + 2.6x restyle surcharge on the banks (inh)",
            "paused": "18,432 paused animations: same class of cost as transition, no capture semantics",
            "static": "plain declarations: floor for holding the same bytes without animation objects",
            "static-cv": "static under content-visibility:hidden: banks not restyled even for inh",
            "none": "no banks: harness floor",
        }[kind],
    )
    css = [
        f'@property --in{{syntax:"<number>";inherits:true;initial-value:{num(page.in_initial)}}}\n',
        f"#target{{--in:{num(page.in_initial)}}}\n" if scope == "sib" else f"html{{--in:{num(page.in_initial)}}}\n",
    ]
    for k, v in enumerate(page.go_values):
        sel = f"html.go-{k}" if scope == "inh" else f"html.go-{k} #target"
        css.append(f"{sel}{{--in:{num(v)}}}\n")
    css.append("html,body{margin:0;padding:0}\n")
    css.append("#vis{position:fixed;left:0;top:0;width:8px;height:8px;background:hsl(calc(var(--in) * 360deg) 70% 50%)}\n")
    css.append('@property --out{syntax:"<number>";inherits:false;initial-value:0}\n')
    css.append("#target{display:block;height:1px;--out:calc(var(--in) * .5 + .25)}\n")
    css.append(".bank{display:block;height:0}\n")
    zero = ",".join(f'"K{i:03d}" 0' for i in range(DIM))
    body_banks = ""
    if kind != "none":
        for name, vector in fields:
            css.append(
                f'@property {name}{{syntax:"{"*" if vector else "<number>"}";inherits:false;initial-value:{zero if vector else "0"}}}\n'
            )
        all_names = ",".join(n for n, _ in fields)

        def value(vector):
            if vector:
                return ",".join(f'"K{i:03d}" {num(rng.uniform(-1, 1))}' for i in range(DIM))
            return num(rng.uniform(0, 8))

        if kind == "transition":
            css.append(
                f".bank{{transition-property:{all_names};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}}\n"
            )
            for b in range(BANKS):
                decls = ";".join(f"{n}:{value(v)}" for n, v in fields)
                css.append(f"html:not([class]) .bank-{b}{{{decls}}}\n")
        elif kind == "paused":
            # one keyframes rule per (bank, field) so every bank holds distinct values
            for b in range(BANKS):
                anims = []
                for i, (n, v) in enumerate(fields):
                    key = f"k{b}-{i}"
                    css.append(f"@keyframes {key}{{to{{{n}:{value(v)}}}}}\n")
                    anims.append(key)
                css.append(
                    f".bank-{b}{{animation-name:{','.join(anims)};animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-play-state:paused}}\n"
                )
        else:  # static, static-cv
            for b in range(BANKS):
                decls = ";".join(f"{n}:{value(v)}" for n, v in fields)
                css.append(f".bank-{b}{{{decls}}}\n")
        banks = "".join(f'<div class="bank bank-{b}"></div>' for b in range(BANKS))
        if kind == "static-cv":
            css.append(".lock{content-visibility:hidden;contain-intrinsic-size:0px 0px}\n")
            body_banks = f'<div class="lock">{banks}</div>'
        else:
            body_banks = f"<div>{banks}</div>"
    html = (
        f"<!doctype html><html><head><meta charset=\"utf-8\"><title>{page.title} seed={seed}</title>\n<style>\n"
        + "".join(css)
        + '</style></head><body>\n<div id="vis"></div>\n<div id="target"></div>'
        + body_banks
        + "\n</body></html>\n"
    )
    page.file = f"{pid}.html"
    path = os.path.join(out_dir, page.file)
    with open(path, "w") as fh:
        fh.write(html)
    page.bytes = os.path.getsize(path)
    page.element_count_hint = 4 + (BANKS + 1 if kind != "none" else 0)
    return page


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")
    os.makedirs(out_dir, exist_ok=True)
    seed = 20260919
    pages = []
    for scope in ("sib", "inh"):
        for kind in ("none", "transition", "paused", "static", "static-cv"):
            pid = f"f5latch-{kind}-{scope}"
            pages.append(build(pid, kind, scope, seed + len(pages), out_dir))
    manifest = {"generator": "gen_latch.py", "seed": seed, "python": sys.version.split()[0], "n_go_values": N_GO, "pages": [asdict(p) for p in pages]}
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    for p in pages:
        print(f"{p.id:32} {p.bytes:>12,}")


if __name__ == "__main__":
    main()
