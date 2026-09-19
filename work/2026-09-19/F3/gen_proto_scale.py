#!/usr/bin/env python3
"""Scale probe: G sibling groups ("layers") x C sibling chains x D containers, all position:fixed.

Group g's anchors are in-flow blocks whose width depends on --in (so one root mutation dirties all
values); every chain is independent (no cross-group dependency) so this measures the pure per-level
cost of G*C*D interleaved container levels inside ONE lifecycle, at token scale.
Verify: the first and last chain bottoms (2*D values each).
"""
import argparse
import json
import random
from pathlib import Path


def build(groups: int, chains: int, depth: int, seed: int, out: Path) -> dict:
    rng = random.Random(seed)
    css = ["html,body{margin:0;padding:0}",
           '@property --in{syntax:"<number>";inherits:true;initial-value:0}',
           ".g{display:block;height:1px;width:calc((var(--w) + var(--in) * 7) * 1px)}",
           ".c{position:fixed;left:0;top:0;container-type:size}",
           ".r{display:block;height:1px;width:1px}",
           ".o{display:block;height:1px;width:1px}"]
    for k in range(16):
        css.append(f"html.go-{k}{{--in:{k}}}")
    n = 2 * depth
    for i in range(n):
        css.append(f'@property --v{i}{{syntax:"<number>";inherits:true;initial-value:-1}}')
    for k in range(depth):
        css.append(f".r{k}{{--v{2 * k}:calc(100cqw / 1px);--v{2 * k + 1}:calc(100cqh / 1px)}}")
    html = []
    widths_first = widths_last = None
    total_chains = groups * chains
    for g in range(groups):
        for c in range(chains):
            idx = g * chains + c
            widths = [100 + rng.randrange(0, 4000) for _ in range(n)]
            if idx == 0:
                widths_first = widths
            if idx == total_chains - 1:
                widths_last = widths
            html.append('<div class="src">' + "".join(
                f'<i class="g" style="--w:{w};anchor-name:--a{idx}_{i}"></i>' for i, w in enumerate(widths)) + "</div>")
            parts = []
            for k in range(depth):
                parts.append(f'<div class="c" style="width:anchor-size(--a{idx}_{2 * k} width);height:anchor-size(--a{idx}_{2 * k + 1} width)"><div class="r r{k}">')
            parts.append(f'<div class="o" id="out{idx}"></div>')
            parts.append("</div></div>" * depth)
            html.append("".join(parts))
    page = ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
            f"<title>scale G{groups} C{chains} D{depth}</title><style>{''.join(css)}</style></head><body>{''.join(html)}</body></html>")
    pid = f"s-G{groups}-C{chains}-D{depth}"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{pid}.html").write_text(page)
    props = [f"--v{i}" for i in range(n)]
    meta = {"id": pid, "file": f"{pid}.html", "bytes": len(page), "groups": groups, "chains": chains, "depth": depth,
            "containers": groups * chains * depth,
            "verify": [{"selector": "#out0", "props": props}, {"selector": f"#out{total_chains - 1}", "props": props}],
            "expected": [[w + 7 * k for w in widths_first] + [w + 7 * k for w in widths_last] for k in range(16)],
            "tolerance": 1e-9}
    (out / f"{pid}.json").write_text(json.dumps(meta))
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", type=int, default=1)
    ap.add_argument("--chains", type=int, default=33)
    ap.add_argument("--depth", type=int, default=128)
    ap.add_argument("--seed", type=int, default=20260919)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "pages"))
    a = ap.parse_args()
    m = build(a.groups, a.chains, a.depth, a.seed, Path(a.out))
    print(m["id"], m["bytes"], "bytes", m["containers"], "containers")


if __name__ == "__main__":
    main()
