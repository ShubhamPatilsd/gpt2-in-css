"""R4T mechanism fixture: what does a 12-layer build pay per extra publishing consumer element?
Publishers = M elements each declaring 64 inherited registered numbers from an input (`--o-m-i: calc(var(--in) + m*64 + i)`), restyled when
`--in` on .stage changes (html.go-k rules). Knobs: nest (publishers nested chain vs siblings), layers (the publisher rule is wrapped in
`@container corestate style(--layer:L)` for L in 0..layers-1, only L=3 matches -> per-layer rule variants as in the demo), big (D inherited registered
numbers declared on an ancestor, inflating the inherited-variables map), anim (each publisher additionally carries 64 view-timeline animations on
private progress numbers, decoded into the published numbers — the real consumer shape; carriers in one scroller; the mutation then also changes the
carriers' widths). usage: python3 gen_mech.py -> pages/mech-*.html + pages/mech-variants.json"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
V, B, S = 524288, 262144, 128
BASE = dict(M=160, nest=1, layers=1, big=0, anim=0)
VARIANTS = {
    "m160-sib": dict(nest=0), "m160-nest": {}, "m160-nest-l12": dict(layers=12), "m160-nest-big": dict(big=30000), "m160-nest-l12-big": dict(layers=12, big=30000),
    "m160-sib-l12-big": dict(nest=0, layers=12, big=30000),
    "m1200-nest": dict(M=1200), "m1200-nest-l12": dict(M=1200, layers=12), "m1200-nest-big": dict(M=1200, big=30000), "m1200-nest-l12-big": dict(M=1200, layers=12, big=30000),
    "m1200-sib-l12-big": dict(M=1200, nest=0, layers=12, big=30000),
    "m20-sib-l12-big": dict(M=20, nest=0, layers=12, big=30000), "m20-nest-l12-big": dict(M=20, layers=12, big=30000),
    # animated shape: 48 publishers x 64 anims (= fc split 64) vs 6 x 512 (= combined4), nested, 12 layer rules, big map
    "a48x64-nest-l12-big": dict(M=48, anim=64, layers=12, big=30000), "a6x512-nest-l12-big": dict(M=6, anim=512, layers=12, big=30000),
    "a48x64-nest": dict(M=48, anim=64), "a6x512-nest": dict(M=6, anim=512),
}
def page(name, **kw):
    p = dict(BASE); p.update(kw); M, nest, layers, big, anim = p["M"], p["nest"], p["layers"], p["big"], p["anim"]
    K = anim or 64  # numbers per publisher
    css = '@property --in{syntax:"<number>";inherits:true;initial-value:0}@property --layer{syntax:"<number>";inherits:false;initial-value:3}'
    css += "".join(f'@property --o-{m}-{i}{{syntax:"<number>";inherits:true;initial-value:0}}' for m in range(M) for i in range(K))
    if big: css += "".join(f'@property --big-{j}{{syntax:"<number>";inherits:true;initial-value:0}}' for j in range(big)) + ".bigdecl{" + ";".join(f"--big-{j}:{j}" for j in range(big)) + "}"
    css += "html,body{margin:0}.ctl{container-name:corestate;container-type:normal;--layer:3}" + "".join(f"html.go-{k} .stage{{--in:{k * 7}}}" for k in range(1, 8))
    body_pubs = []
    if anim:
        css += "".join(f'@property --p-{m}-{i}{{syntax:"<number>";inherits:false;initial-value:0}}@keyframes k{m}-{i}{{from{{--p-{m}-{i}:0}}to{{--p-{m}-{i}:1}}}}' for m in range(M) for i in range(K))
        css += ".scroller{position:fixed;left:0;top:-60000px;width:%dpx;height:1px;overflow-x:scroll;overflow-y:hidden;contain:strict;visibility:hidden}.track{position:relative;width:%dpx;height:1px}.metric{position:absolute;left:0;top:0;display:inline-flex;height:1px}" % (V, 3 * V)
        css += ".stage{timeline-scope:" + ",".join(f"--t{m}-{i}" for m in range(M) for i in range(K)) + "}"
        metrics = "".join(f'<i class="metric" style="width:calc({B}px + ({m * K + i} + var(--in)) * {S}px);view-timeline:--t{m}-{i} inline"></i>' for m in range(M) for i in range(K))
        scroller = f'<div class="scroller"><div class="track">{metrics}</div></div>'
    else: scroller = ""
    for m in range(M):
        if anim:
            decl = (f"animation-name:{','.join(f'k{m}-{i}' for i in range(K))};animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:{','.join(f'--t{m}-{i}' for i in range(K))};animation-range:cover;"
                    + ";".join(f"--o-{m}-{i}:calc(({V} / var(--p-{m}-{i}) - {V} - {B}) / {S} * 1.0001 + 0.5)" for i in range(K)))
        else:
            decl = ";".join(f"--o-{m}-{i}:calc(var(--in) * 1.0001 + {m * K + i})" for i in range(K))
        if layers > 1:
            for L in range(layers): css += f"@container corestate style(--layer:{L}){{.pub-{m}{{{decl if L == 3 else decl.replace('1.0001', f'1.000{L}')}}}}}"
        else: css += f".pub-{m}{{{decl}}}"
    if nest: pubs = "".join(f'<div class="pub pub-{m}">' for m in range(M)) + '<div class="reader" id="reader"></div>' + "</div>" * M
    else: pubs = "".join(f'<div class="pub pub-{m}"></div>' for m in range(M)) + '<div class="reader" id="reader"></div>'
    html = ("<!doctype html><html><head><meta charset=utf-8><style>" + css + "</style></head><body>"
            + f'<div class="stage{" bigdecl" if big else ""}" id="stage">' + '<div class="ctl">' + scroller + '<div class="core">' + pubs + "</div></div></div></body></html>")
    meta = dict(p); meta["name"] = name; return html, meta
if __name__ == "__main__":
    metas = {}
    for name in (sys.argv[1:] or list(VARIANTS)):
        html, meta = page(name, **VARIANTS[name]); out = HERE / "pages" / f"mech-{name}.html"; out.write_text(html); metas[name] = meta; print(name, out.stat().st_size)
    (HERE / "pages" / "mech-variants.json").write_text(json.dumps(metas, indent=1))
