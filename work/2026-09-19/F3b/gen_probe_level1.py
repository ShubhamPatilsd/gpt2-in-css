#!/usr/bin/env python3
"""Probe: one element per chain level (container k+1 publishes container k's cq values).

Prototype A used container + plain child per level (2 elements). The emitter's out chain
needs 768 values = 390 levels, which only fits the 512 parser cap with ONE element per level:
  #c{k}{position:fixed;container-type:size;width:anchor-size(--g{2k});height:anchor-size(--g{2k+1});
        --v{2k-2}:calc(100cqw/1px);--v{2k-1}:calc(100cqh/1px)}   (cq units resolve against the PARENT container)
Pages (no JS): N=2D in-flow anchors, D containers, #out at the bottom; mutation html.class=go-k adds 7k px.
  l1-D384   the out-chain shape (768 values), anchors in-flow
  l1-D384-fixedsrc   anchors inside a fixed .stage (as the emitter's glyph rows), placed before the chain
  l1-D128   the fc-chain shape
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(depth, fixed_src, seed=20260919, base=100, spread=4000):
    rng = random.Random(seed)
    n = 2 * depth
    widths = [base + rng.randrange(0, spread) for _ in range(n)]
    css = ["html,body{margin:0;padding:0}", '@property --in{syntax:"<number>";inherits:true;initial-value:0}']
    css += [f'@property --v{i}{{syntax:"<number>";inherits:true;initial-value:-1}}' for i in range(n)]
    css += [f"html.go-{k}{{--in:{k}}}" for k in range(16)]
    css.append(".g{display:block;height:1px;width:calc((var(--w) + var(--in) * 7) * 1px)}")
    css.append("#src{position:fixed;left:0;top:-60000px;visibility:hidden}" if fixed_src else "#src{display:block}")
    css.append(".c{position:fixed;left:0;top:0;container-type:size}")
    css.append("#out{display:block;height:1px;width:1px}")
    for k in range(depth):
        css.append(f"#c{k}{{width:anchor-size(--g{2 * k} width);height:anchor-size(--g{2 * k + 1} width)}}")
        if k >= 1:
            css.append(f"#c{k}{{--v{2 * k - 2}:calc(100cqw / 1px);--v{2 * k - 1}:calc(100cqh / 1px)}}")
    css.append(f"#out{{--v{n - 2}:calc(100cqw / 1px);--v{n - 1}:calc(100cqh / 1px)}}")
    src = '<div id="src">' + "".join(f'<i class="g" style="--w:{w};anchor-name:--g{i}"></i>' for i, w in enumerate(widths)) + "</div>"
    chain = "".join(f'<div class="c" id="c{k}">' for k in range(depth)) + '<div id="out"></div>' + "</div>" * depth
    page = (
        '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
        f"<title>level1 D={depth}</title><style>{''.join(css)}</style></head><body>{src}<div id=\"chain\">{chain}</div></body></html>"
    )
    pid = f"l1-D{depth}" + ("-fixedsrc" if fixed_src else "")
    out = HERE / "pages"
    out.mkdir(exist_ok=True)
    (out / f"{pid}.html").write_text(page)
    meta = {"id": pid, "file": f"{pid}.html", "depth": depth, "count": n, "widths": widths, "step": 7,
            "verify_selector": "#out", "verify_props": [f"--v{i}" for i in range(n)], "bytes": len(page)}
    (out / f"{pid}.json").write_text(json.dumps(meta))
    print(pid, len(page), "bytes")


if __name__ == "__main__":
    build(384, False)
    build(384, True)
    build(128, False)
