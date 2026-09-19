#!/usr/bin/env python3
"""Ordering probe: which (reader generation, anchor generation) pairs resolve for position:fixed readers?

Two chains A and B of depth D (fixed size containers, gen k+1 holds in-flow anchor --aX_k of width 1000+k+X*100
+ 7*in). Readers (fixed, container-type:size, width:anchor-size(...)) placed at various generations read anchors
at various generations; each reader's child publishes --q<name>:calc(100cqw/1px) on a global out element via
... no: numbers cannot leave the subtree, so each reader child IS the verify node (#r<name>).
"""
import json
from pathlib import Path

D = 6
here = Path(__file__).resolve().parent
css = ["html,body{margin:0;padding:0}", '@property --in{syntax:"<number>";inherits:true;initial-value:0}',
       '@property --q{syntax:"<number>";inherits:false;initial-value:-1}',
       ".c{position:fixed;left:0;top:0;container-type:size;width:1px;height:1px}",
       ".r{display:block;height:1px;width:1px}", ".a{display:block;height:1px}",
       ".rd{position:fixed;left:0;top:0;container-type:size;height:1px}", ".v{--q:calc(100cqw / 1px)}"]
for k in range(16):
    css.append(f"html.go-{k}{{--in:{k}}}")
readers = {}  # name -> (host chain, host gen, anchor spec)


def anchor(chain, gen):
    return f"--a{chain}_{gen}"


OFF = {"A": 0, "B": 100, "C": 200}


def width(chain, gen, k):
    return 1000 + gen + OFF[chain] + 7 * k


def chain(name, extra):
    """extra: dict gen -> list of (reader name, css width expr)"""
    parts = []
    for g in range(1, D + 1):
        parts.append(f'<div class="c"><div class="r"><i class="a" style="anchor-name:{anchor(name, g)};width:calc({1000 + g + OFF[name]}px + var(--in) * 7px)"></i>')
        for rname, expr in extra.get(g, []):
            parts.append(f'<div class="rd" style="width:{expr}"><div class="v" id="r{rname}"></div></div>')
    parts.append("</div></div>" * D)
    return "".join(parts)


# readers hosted in chain A at generation g (they are OOF children of gen-g in-flow content => generation g+1)
extra_a = {
    6: [("A6_C6", f"anchor-size({anchor('C', 6)} width)"),      # deep reader, anchor in EARLIER anchored root
        ("A6_C1", f"anchor-size({anchor('C', 1)} width)"),
("A6_B6", f"anchor-size({anchor('B', 6)} width)"),      # deep reader, same-gen anchor in other chain
        ("A6_A6", f"anchor-size({anchor('A', 6)} width)"),      # deep reader, own previous sibling
        ("A6_B5", f"anchor-size({anchor('B', 5)} width)"),      # deep reader, one-shallower anchor other chain
        ("A6_B1", f"anchor-size({anchor('B', 1)} width)"),      # deep reader, shallow anchor
        ("A6_maxB", "max(" + ",".join(f"anchor-size({anchor('B', g)} width)" for g in range(1, D + 1)) + ")")],
    3: [("A3_B6", f"anchor-size({anchor('B', 6)} width)"),      # mid reader, deeper anchor other chain
        ("A3_B3", f"anchor-size({anchor('B', 3)} width)"),
        ("A3_A3", f"anchor-size({anchor('A', 3)} width)")],
    1: [("A1_B6", f"anchor-size({anchor('B', 6)} width)"),
        ("A1_B1", f"anchor-size({anchor('B', 1)} width)")],
}
top = [("T_B6", f"anchor-size({anchor('B', 6)} width)"), ("T_A1", f"anchor-size({anchor('A', 1)} width)"),
       ("T_maxB", "max(" + ",".join(f"anchor-size({anchor('B', g)} width)" for g in range(1, D + 1)) + ")")]
pre_top = [("P_B6", f"anchor-size({anchor('B', 6)} width)"), ("P_C6", f"anchor-size({anchor('C', 6)} width)")]  # top-level readers BEFORE A and B
html = "".join(f'<div class="rd" style="width:{e}"><div class="v" id="r{n}"></div></div>' for n, e in pre_top) + chain("C", {}) + chain("A", extra_a) + chain("B", {}) + "".join(f'<div class="rd" style="width:{e}"><div class="v" id="r{n}"></div></div>' for n, e in top)
# B placed AFTER A in tree order; also a chain C before A read by A? keep simple.
page = ('<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
        f"<title>order probe</title><style>{''.join(css)}</style></head><body>{html}</body></html>")
names = [n for n, _ in pre_top] + [n for g in extra_a.values() for n, _ in g] + [n for n, _ in top]


def expected(name, k):
    spec = name.split("_")[1]
    if spec.startswith("max"):
        return width("B", D, k)
    return width(spec[0], int(spec[1:]), k)


meta = {"id": "order-probe", "file": "order-probe.html", "bytes": len(page),
        "verify": [{"selector": f"#r{n}", "props": ["--q"]} for n in names],
        "expected": [[expected(n, k) for n in names] for k in range(16)], "names": names, "tolerance": 1e-9}
(here / "pages" / "order-probe.html").write_text(page)
(here / "pages" / "order-probe.json").write_text(json.dumps(meta))
print("order-probe", len(page), names)
