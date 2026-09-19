#!/usr/bin/env python3
"""Prototype A pages: N anchors -> D-deep chain of size containers -> one element with 2D numbers.

Each page is no-JS.  The mutation is `html.class = go-k` which adds 7*k px to every anchor
width; the harness reads --v0..--v{2D-1} on #out before/after and checks exact round trip.

Variants (--variant):
  fixed    chain containers are position:fixed (containing block = viewport)        [expected to work]
  abs      chain containers are position:absolute nested (CB = previous container)  [expected fallback]
  static   chain containers are in-flow blocks with width: anchor-size()             [probe: allowed?]
  late     as fixed, but the anchors come AFTER the chain in tree order              [expected fallback]
  inside   as fixed, but the anchors sit inside a fixed size container               [E5 #301 trap]
  shadow   as fixed, chain split into declarative-shadow-root segments of 100 levels [depth probe]
"""
import argparse
import json
import random
from pathlib import Path


def build(variant: str, depth: int, base: int, spread: int, seed: int, out: Path, segment: int = 100) -> dict:
    rng = random.Random(seed)
    n = 2 * depth
    widths = [base + rng.randrange(0, spread) for _ in range(n)]
    css = []
    css.append("html,body{margin:0;padding:0}")
    for i in range(n):
        css.append(f'@property --v{i}{{syntax:"<number>";inherits:true;initial-value:-1}}')
    css.append('@property --in{syntax:"<number>";inherits:true;initial-value:0}')
    for k in range(16):
        css.append(f"html.go-{k}{{--in:{k}}}")
    # anchors: in-flow blocks, width = (w + 7*in) px
    css.append(".g{display:block;height:1px;width:calc((var(--w) + var(--in) * 7) * 1px)}")
    css.append("#src{position:relative}")
    if variant == "inside":
        css.append("#src{position:fixed;left:0;top:0;container-type:size;width:10px;height:10px}")
    # chain
    if variant == "abs":
        css.append(".c{position:absolute;left:0;top:0;container-type:size}")
    elif variant == "static":
        css.append(".c{display:block;container-type:size}")
    else:
        css.append(".c{position:fixed;left:0;top:0;container-type:size}")
    css.append(".r{display:block;height:1px;width:1px}")
    css.append("#out{display:block;height:1px;width:1px}")
    for k in range(depth):
        css.append(f"#c{k}{{width:anchor-size(--g{2 * k} width);height:anchor-size(--g{2 * k + 1} width)}}")
        css.append(f"#r{k}{{--v{2 * k}:calc(100cqw / 1px);--v{2 * k + 1}:calc(100cqh / 1px)}}")
    src = '<div id="src">' + "".join(
        f'<i class="g" id="g{i}" style="--w:{w};anchor-name:--g{i}"></i>' for i, w in enumerate(widths)
    ) + "</div>"
    parts = []
    for k in range(depth):
        if variant == "shadow" and k > 0 and k % segment == 0:
            parts.append('<template shadowrootmode="open"><style>' + "".join(css) + "</style>")
        parts.append(f'<div class="c" id="c{k}"><div class="r" id="r{k}">')
    parts.append('<div id="out"></div>')
    closes = []
    for k in reversed(range(depth)):
        closes.append("</div></div>")
        if variant == "shadow" and k > 0 and k % segment == 0:
            closes.append("</template>")
    chain = '<div id="chain">' + "".join(parts) + "".join(closes) + "</div>"
    body = chain + src if variant == "late" else src + chain
    html = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
        f"<title>proto A {variant} D={depth}</title><style>{''.join(css)}</style></head><body>{body}</body></html>"
    )
    pid = f"a-{variant}-D{depth}-B{base}"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{pid}.html").write_text(html)
    meta = {
        "id": pid,
        "file": f"{pid}.html",
        "variant": variant,
        "depth": depth,
        "count": n,
        "widths": widths,
        "step": 7,
        "verify_selector": "#out",
        "verify_props": [f"--v{i}" for i in range(n)],
        "bytes": len(html),
        "shadow": variant == "shadow",
    }
    (out / f"{pid}.json").write_text(json.dumps(meta))
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="fixed")
    ap.add_argument("--depth", type=int, default=128)
    ap.add_argument("--base", type=int, default=100)
    ap.add_argument("--spread", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20260919)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "pages"))
    a = ap.parse_args()
    m = build(a.variant, a.depth, a.base, a.spread, a.seed, Path(a.out))
    print(m["id"], m["bytes"], "bytes")


if __name__ == "__main__":
    main()
