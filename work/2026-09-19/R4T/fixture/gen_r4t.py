"""R4T fixture pages: does per-frame view-timeline servicing scale with DOM depth / scroller structure?
Shapes mirror combined4: .scroller{position:fixed;top:-60000px;overflow-x:scroll;contain:strict;visibility:hidden} > .track{position:relative}
> subjects (.metric{position:absolute;left:0;top:0;height:1px} with inline `width:calc(262144px + (i + var(--in)) * 128px); view-timeline:--t{i} inline`),
consumers hold the view-timeline animations (animation-range:cover, fill both) publishing registered numbers --o-i = (524288/p - 524288 - 262144)/128 = i + in.
A .tick element runs a 1 s infinite custom-property animation so the page produces one main-thread frame per vsync.
Knobs (one page per variant; variants listed in VARIANTS): n, above (wrapper divs between .stage and the scroller group), below (wrappers between scroller
and track), scrollers (subjects split round-robin), subject abs|iblock|inline, contain none|layout|cv (on every wrapper), scope near (on the group) | root (html),
consumers (elements sharing the animations), change (fraction of carriers whose width follows a 20 s --drive animation on their track => layout + snapshot change +
consumer restyle every frame = the demo's two-passes-per-frame hop shape), bigdom (inert elements elsewhere), heavy (each wrapper declares 200 inherited registered numbers).
usage: python3 gen_r4t.py [variant ...]   (default: all)"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V, B, S = 524288, 262144, 128
BASE = dict(n=2000, above=2, below=0, scrollers=1, subject="abs", contain="none", scope="near", consumers=1, change=0.0, bigdom=0, heavy=0, nested=0)
VARIANTS = {
    "ctrl-n0": dict(n=0),
    "base": {},
    "n1000": dict(n=1000),
    "above20": dict(above=20), "above40": dict(above=40), "above60": dict(above=60),
    "below5": dict(below=5), "below20": dict(below=20), "below40": dict(below=40), "below60": dict(below=60),
    "scr12": dict(scrollers=12), "scr96": dict(scrollers=96),
    "iblock": dict(subject="iblock"), "inline": dict(subject="inline"),
    "scope-root": dict(scope="root"),
    "cons16": dict(consumers=16),
    "change50": dict(change=0.5),
    "bigdom100k": dict(bigdom=100000),
    "heavy-a40": dict(above=40, heavy=200),
    "demo": dict(above=40, scrollers=12, scope="root", consumers=12),
    "demo-contain": dict(above=40, scrollers=12, scope="root", consumers=12, contain="layout"),
    "demo-cv": dict(above=40, scrollers=12, scope="root", consumers=12, contain="cv"),
    "demo-change50": dict(above=40, scrollers=12, scope="root", consumers=12, change=0.5),
    "demo-below20": dict(above=40, below=20, scrollers=12, scope="root", consumers=12),
    # sweep2: cost per changing carrier vs animations per consumer element (1 scroller; chg = even carriers => every consumer gets half changing)
    "c50-cons4": dict(change=0.5, consumers=4), "c50-cons16": dict(change=0.5, consumers=16), "c50-cons64": dict(change=0.5, consumers=64),
    "c100-cons1": dict(change=1.0), "c100-cons16": dict(change=1.0, consumers=16), "c100-cons64": dict(change=1.0, consumers=64),
    "n1000-c100-cons1": dict(n=1000, change=1.0), "n500-c100-cons1": dict(n=500, change=1.0),
    "c100-cons4-nested": dict(change=1.0, consumers=4, nested=1), "c100-cons16-nested": dict(change=1.0, consumers=16, nested=1),
    # sweep3: knee search (animations per element = 2000/consumers): 250, 62, 31, 15 nested as the demo chain
    "c100-cons8-nested": dict(change=1.0, consumers=8, nested=1), "c100-cons32-nested": dict(change=1.0, consumers=32, nested=1),
    "c100-cons64-nested": dict(change=1.0, consumers=64, nested=1), "c100-cons128-nested": dict(change=1.0, consumers=128, nested=1),
}


def page(name, **kw):
    p = dict(BASE); p.update(kw)
    n, above, below, scr, subj, contain, scope, cons, change, bigdom, heavy = (p[k] for k in ("n", "above", "below", "scrollers", "subject", "contain", "scope", "consumers", "change", "bigdom", "heavy"))
    scr = max(1, scr)
    chg = [False] * n
    if change > 0:
        if change >= 1: chg = [True] * n
        elif scr == 1: chg = [(i % 2 == 0) for i in range(n)]
        else: chg = [((i % scr) < scr * change) for i in range(n)]
    regs = "".join(f'@property --p-{i}{{syntax:"<number>";inherits:false;initial-value:0}}@property --o-{i}{{syntax:"<number>";inherits:false;initial-value:-1}}@keyframes k{i}{{from{{--p-{i}:0}}to{{--p-{i}:1}}}}' for i in range(n))
    regs += '@property --in{syntax:"<number>";inherits:true;initial-value:0}@property --drive{syntax:"<number>";inherits:true;initial-value:0}@property --tk{syntax:"<number>";inherits:false;initial-value:0}'
    if heavy: regs += "".join(f'@property --h{j}{{syntax:"<number>";inherits:true;initial-value:0}}' for j in range(heavy))
    css = regs + "html,body{margin:0}.tick{position:fixed;left:0;top:0;width:1px;height:1px;animation:tick 1s linear infinite}@keyframes tick{from{--tk:0}to{--tk:1}}"
    css += ".scroller{position:fixed;left:0;top:-60000px;width:%dpx;height:1px;overflow-x:scroll;overflow-y:hidden;contain:strict;visibility:hidden}" % V
    if subj == "abs":
        css += ".track{position:relative;width:%dpx;height:1px}.metric{position:absolute;left:0;top:0;display:inline-flex;height:1px;overflow:clip;min-width:0;white-space:pre}" % (3 * V)
    elif subj == "iblock":  # in-flow inline-blocks, each wider than the 1px track => one per line, all start at x=0
        css += ".track{position:relative;width:1px;height:%dpx;white-space:normal;line-height:1px;font-size:1px}.metric{display:inline-block;height:1px;vertical-align:top}" % (max(1, n // scr) + 1)
    else:  # true inline spans; width via padding-left (horizontal padding applies to inlines), one per line
        css += ".track{position:relative;width:1px;height:%dpx;white-space:normal;line-height:1px;font-size:1px}.metric{display:inline;padding-left:var(--w)}" % (max(1, n // scr) + 1)
    wrap = ""
    if contain == "layout": wrap = "contain:layout;"
    elif contain == "cv": wrap = "content-visibility:auto;"
    css += ".w{%s}" % wrap
    if heavy: css += ".w{" + ";".join(f"--h{j}:{j}" for j in range(heavy)) + "}"
    css += ".consumer{position:fixed;left:0;top:10px;width:1px;height:1px}"
    scope_sel = "html" if scope == "root" else ".group"
    if n: css += scope_sel + "{timeline-scope:" + ",".join(f"--t{i}" for i in range(n)) + "}"
    if change > 0: css += "@keyframes drive{from{--drive:0}to{--drive:1000}}.track.chg{animation:drive 20s linear infinite}"
    for c in range(cons):
        ids = [i for i in range(n) if i % cons == c]
        if not ids: continue
        css += (f".c{c}{{animation-name:" + ",".join(f"k{i}" for i in ids) + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
                + ",".join(f"--t{i}" for i in ids) + ";animation-range:cover;" + ";".join(f"--o-{i}:calc(({V} / var(--p-{i}) - {V} - {B}) / {S})" for i in ids) + "}")
    css += ".big{position:fixed;left:0;top:-70000px;width:1px;height:1px;visibility:hidden}.big i{display:block;width:1px;height:1px}"
    # subjects
    tracks = [[] for _ in range(scr)]
    for i in range(n):
        wexpr = f"calc({B}px + ({i} + var(--in)" + (" + var(--drive)" if chg[i] else "") + f") * {S}px)"
        style = (f"--w:{wexpr};" if subj == "inline" else f"width:{wexpr};") + f"view-timeline:--t{i} inline"
        tag = "span" if subj != "abs" else "i"
        tracks[i % scr].append(f'<{tag} class="metric" style="{style}"></{tag}>')
    body = '<div class="tick"></div><div class="stage" id="stage" style="--in:0">'
    body += '<div class="w">' * above
    body += '<div class="group" id="group">'
    for s in range(scr):
        chg_track = change > 0 and ((scr == 1) or (s < scr * change))
        body += '<div class="scroller">' + '<div class="w">' * below + f'<div class="track{" chg" if chg_track else ""}" id="track{s}">' + "".join(tracks[s]) + "</div>" + "</div>" * below + "</div>"
    if p["nested"]:  # demo shape: consumer chain c0 > c1 > ... (each inherits the others' outputs)
        body += "".join(f'<div class="consumer c{c}" id="c{c}">' for c in range(cons)) + "</div>" * cons
    else:
        for c in range(cons): body += f'<div class="consumer c{c}" id="c{c}"></div>'
    body += "</div>" + "</div>" * above + "</div>"
    if bigdom: body += '<div class="big">' + "<i></i>" * bigdom + "</div>"
    meta = dict(p); meta["name"] = name
    return "<!doctype html><html><head><meta charset=utf-8><title>r4t " + name + "</title><style>" + css + "</style></head><body>" + body + "</body></html>", meta


if __name__ == "__main__":
    import json
    names = sys.argv[1:] or list(VARIANTS)
    (HERE / "pages").mkdir(exist_ok=True)
    metas = {}
    for name in names:
        html, meta = page(name, **VARIANTS[name])
        out = HERE / "pages" / f"{name}.html"; out.write_text(html); metas[name] = meta
        print(name, out.stat().st_size, "B", meta)
    (HERE / "pages" / "variants.json").write_text(json.dumps(metas, indent=1))
