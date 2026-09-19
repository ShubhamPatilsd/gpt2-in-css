"""F4 latch micro-test pages (same manifest schema as F5's gen_latch.py / M1 gen.py).

Real latch shapes of the capacity-8 demo at position 8, scope = sib (the traced
mutation is an unrelated `#target{--in}` change; cost = what every style pass pays):

  before   KV: 12 banks x 384 listed names, all running after warm-up
               (8 slots x 12 heads x {k 64-axis `*`, v 64-axis `*`, ks, vs});
           head: 769 numbers; loop: bank 0 769 running, bank 1 769 listed only
  after    KV: 12 banks x 208 names (8 slots x {k 768-axis `*`, v 768-axis `*`, 24 numbers});
           head: 1 x 768-entry `*` list + 1 number; loop unchanged
  before-kv / after-kv   banks only (no head, no loop)
  none     floor
"""
import json, os, random, sys
from dataclasses import asdict, dataclass, field

BANKS, SLOTS, HEADS, DIM, W = 12, 8, 12, 64, 768
N_GO = 16


@dataclass
class Page:
    id: str; family: str; title: str; params: dict; target: str
    in_range: list = field(default_factory=lambda: [0.0, 1.0]); in_inherits: bool = True
    verify_selector: str = "#target"; verify_property: str = "--out"; hypothesis: str = ""
    file: str = ""; bytes: int = 0; seed: int = 0; go_values: list = field(default_factory=list)
    in_initial: float = 0.0; element_count_hint: int = 0; notes: str = ""


def num(v, d=6):
    s = f"{v:.{d}f}".rstrip("0").rstrip(".")
    return s.replace("0.", ".").replace("-0.", "-.") or "0"


def tag(kind, head, i):
    return f"{kind.upper()}{head * DIM + i:03X}"


def kv_fields(packed):
    """[(name, kind)] kind in {'list64','list768','num'} with tags for lists."""
    out = []
    for s in range(SLOTS):
        if packed:
            out.append((f"--fc-k-{s}", "list768", [tag("k", h, i) for h in range(HEADS) for i in range(DIM)]))
            out.append((f"--fc-v-{s}", "list768", [tag("v", h, i) for h in range(HEADS) for i in range(DIM)]))
            for h in range(HEADS):
                out += [(f"--fc-ks-{s}-{h}", "num", None), (f"--fc-vs-{s}-{h}", "num", None)]
        else:
            for h in range(HEADS):
                out.append((f"--fc-k-{s}-{h}", "list64", [f"K{i:03d}" for i in range(DIM)]))
                out.append((f"--fc-v-{s}-{h}", "list64", [f"K{i:03d}" for i in range(DIM)]))
                out += [(f"--fc-ks-{s}-{h}", "num", None), (f"--fc-vs-{s}-{h}", "num", None)]
    return out


def head_fields(packed):
    if packed:
        return [("--head-fvs", "list768", [f"X{i:03d}" for i in range(W)]), ("--head-input-epoch", "num", None)]
    return [(f"--h{i}", "num", None) for i in range(W)] + [("--head-input-epoch", "num", None)]


def loop_fields(bank):
    return [(f"--saved-{bank}-{i}", "num", None) for i in range(W + 1)]


ENTRY_STYLE = "calc"


def build(pid, arm, seed, out_dir, entry_style="calc"):
    rng = random.Random(seed)
    page = Page(id=pid, family="f4latch", title=f"F4 latch {arm} scope=sib", params={"arm": arm}, target="#target", seed=seed,
                go_values=[rng.random() for _ in range(N_GO)], in_initial=rng.random(),
                hypothesis="per in-delay transition cost ~5.7us on every pass (F5 §4); packed lists cut the count 6,146 -> 3,267")
    css = [f'@property --in{{syntax:"<number>";inherits:true;initial-value:{num(page.in_initial)}}}\n', f"#target{{--in:{num(page.in_initial)}}}\n"]
    for k, v in enumerate(page.go_values):
        css.append(f"html.go-{k} #target{{--in:{num(v)}}}\n")
    css.append("html,body{margin:0;padding:0}\n#vis{position:fixed;left:0;top:0;width:8px;height:8px;background:hsl(calc(var(--in) * 360deg) 70% 50%)}\n")
    css.append('@property --out{syntax:"<number>";inherits:false;initial-value:0}\n#target{display:block;height:1px;--out:calc(var(--in) * .5 + .25)}\n.bank,.head,.loop{display:block;height:0}\n')
    groups = []  # (selector, fields, running)
    running = listed = 0
    body = ""
    if arm != "none":
        packed = arm.startswith("after")
        for b in range(BANKS):
            groups.append((f".bank-{b}", kv_fields(packed), True))
        body += "".join(f'<div class="bank bank-{b}"></div>' for b in range(BANKS))
        if not arm.endswith("-kv"):
            groups.append((".head", head_fields(packed), True))
            groups.append((".loop-0", loop_fields(0), True))
            groups.append((".loop-1", loop_fields(1), False))
            body += '<div class="head"></div><div class="loop loop-0"></div><div class="loop loop-1"></div>'
        registered = set()
        for sel, fields, is_running in groups:
            for name, kind, tags in fields:
                if name in registered: continue
                registered.add(name)
                if kind == "num":
                    css.append(f'@property {name}{{syntax:"<number>";inherits:false;initial-value:0}}\n')
                else:
                    css.append(f'@property {name}{{syntax:"*";inherits:false;initial-value:{",".join(f"{chr(34)}{t}{chr(34)} 0" for t in tags)}}}\n')
            names = ",".join(n for n, _, _ in fields)
            css.append(f"{sel}{{transition-property:{names};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}}\n")
            def value(kind, tags):
                if kind == "num": return num(rng.uniform(0, 8))
                if tags[0].startswith("X"): return ",".join(f'"{t}" {rng.randint(-16384, 16384)}' for t in tags)
                if entry_style == "num": return ",".join(f'"{t}" {num(rng.uniform(-1, 1))}' for t in tags)
                if entry_style == "tiny": return ",".join(f'"{t}" {rng.randint(1, 9)}' for t in tags)
                return ",".join(f'"{t}" calc({num(rng.uniform(-8, 8), 4)} / {num(rng.uniform(1, 9), 5)})' for t in tags)
            decls = ";".join(f"{n}:{value(k, t)}" for n, k, t in fields)
            css.append((f"html:not([class]) {sel}{{{decls}}}\n") if is_running else (f"{sel}{{{decls}}}\n"))
            listed += len(fields); running += len(fields) if is_running else 0
    page.params.update({"running": running, "listed": listed, "entry_style": entry_style})
    html = f'<!doctype html><html><head><meta charset="utf-8"><title>{page.title} seed={seed}</title>\n<style>\n' + "".join(css) + '</style></head><body>\n<div id="vis"></div>\n<div id="target"></div><div>' + body + "</div>\n</body></html>\n"
    page.file = f"{pid}.html"
    with open(os.path.join(out_dir, page.file), "w") as fh: fh.write(html)
    page.bytes = os.path.getsize(os.path.join(out_dir, page.file))
    page.element_count_hint = 5 + len(groups)
    return page


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages"); os.makedirs(out_dir, exist_ok=True)
    seed = 20260919; pages = []
    variants = [("none", "calc"), ("before", "calc"), ("after", "calc"), ("before-kv", "calc"), ("after-kv", "calc")]
    if len(sys.argv) > 1 and sys.argv[1] == "bytes":
        variants = [("none", "calc"), ("after-kv", "calc"), ("after-kv", "num"), ("after-kv", "tiny"), ("before-kv", "num")]
    for arm, style in variants:
        pages.append(build(f"f4latch-{arm}-{style}-sib" if style != "calc" else f"f4latch-{arm}-sib", arm, seed + len(pages), out_dir, style))
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        json.dump({"generator": "gen_f4_latch.py", "seed": seed, "python": sys.version.split()[0], "n_go_values": N_GO, "pages": [asdict(p) for p in pages]}, fh, indent=1)
    for p in pages: print(f"{p.id:28} {p.bytes:>12,} running={p.params['running']} listed={p.params['listed']}")


if __name__ == "__main__":
    main()
