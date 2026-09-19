#!/usr/bin/env python3
"""Offline structural lint of an F3b bundle (index.html + runtime.css).

Checks the Chromium rules the anchor->container transport depends on (F3.md §2/§3b):
  1. HTML nesting depth < 512 everywhere (parser cap re-parents deeper elements).
  2. Every anchor-size(--X) reader's anchor exists exactly once and precedes the
     reader in tree order; anchors hosted in a fixed subtree must belong to an
     out-of-flow root that is earlier than the reader's out-of-flow root.
  3. No ancestor of .f3-mlp carries a containing-block-forming property
     (position other than static, contain, transform, filter, will-change,
     perspective, content-visibility other than the gates, overflow != visible).
  4. Counts: fc anchors, proj anchors, containers, per-layer decode rules.
  5. No leftover view-timeline / timeline-scope / receipt / gate for fc and proj.
usage: lint_f3b.py <bundle-dir> [--blocks N]
"""
import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

VOID = {"i_", "br", "img", "input", "meta", "link", "set", "hr"}  # <i> is NOT void here (it has content)
FORBIDDEN = re.compile(
    r"^(position|contain|transform|filter|backdrop-filter|will-change|perspective|clip-path|mask|overflow(-x|-y)?|content-visibility)\s*:\s*(.*)$"
)


class Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack = []  # (tag, classes, id, index)
        self.elements = []  # dict per element
        self.maxdepth = 0
        self.deepest = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        el = {
            "tag": tag,
            "classes": (a.get("class") or "").split(),
            "id": a.get("id"),
            "style": a.get("style") or "",
            "index": len(self.elements),
            "parent": self.stack[-1]["index"] if self.stack else None,
            "depth": len(self.stack) + 1,
        }
        self.elements.append(el)
        self.stack.append(el)
        if el["depth"] > self.maxdepth:
            self.maxdepth, self.deepest = el["depth"], el
        if tag in ("br", "img", "input", "meta", "link", "hr"):
            self.stack.pop()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1]["tag"] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for k in range(len(self.stack) - 1, -1, -1):
            if self.stack[k]["tag"] == tag:
                del self.stack[k:]
                return


def css_rules(css):
    """Flatten (selector, declarations) including rules nested in @container blocks."""
    out = []
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        prelude = css[i:j].strip()
        if prelude.startswith("@container") or prelude.startswith("@media") or prelude.startswith("@supports"):
            i = j + 1  # descend
            continue
        k = css.find("}", j)
        if k < 0:
            break
        body = css[j + 1 : k]
        if not prelude.startswith("@"):
            out.append((prelude, body))
        i = k + 1
        while i < n and css[i] == "}":
            i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("--blocks", type=int, default=None)
    a = ap.parse_args()
    html = (a.bundle / "index.html").read_text()
    css = (a.bundle / "runtime.css").read_text()
    manifest = {}
    try:
        import json

        manifest = json.loads((a.bundle / "manifest.json").read_text())
    except Exception:
        pass
    blocks = a.blocks or manifest.get("blocks", 12)
    doc = Doc()
    doc.feed(html)
    els = doc.elements
    problems = []
    print(f"elements {len(els)}  max depth {doc.maxdepth} at {doc.deepest['tag']}#{doc.deepest['id']}.{'.'.join(doc.deepest['classes'])}")
    if doc.maxdepth >= 512:
        problems.append(f"nesting depth {doc.maxdepth} >= 512")

    # --- ancestors of .f3-mlp
    mlp = [e for e in els if "f3-mlp" in e["classes"]]
    if len(mlp) != 1:
        problems.append(f"expected one .f3-mlp, found {len(mlp)}")
    rules = css_rules(css)
    # index rules by simple class/id tokens they mention
    by_token = {}
    for sel, body in rules:
        for tok in set(re.findall(r"[.#][\w-]+", sel)):
            by_token.setdefault(tok, []).append((sel, body))
    if mlp:
        e = mlp[0]
        chain = []
        while e["parent"] is not None:
            e = els[e["parent"]]
            chain.append(e)
        print(f".f3-mlp depth {mlp[0]['depth']}, {len(chain)} ancestors")
        for anc in chain:
            toks = [f".{c}" for c in anc["classes"]] + ([f"#{anc['id']}"] if anc["id"] else [])
            decls = []
            for tok in toks:
                for sel, body in by_token.get(tok, []):
                    # only rules whose LAST compound mentions the token (rough: selector ends with it or has it before a comma)
                    if not re.search(re.escape(tok) + r"(?![\w-])(?:[^,\s>+~]*)?(?:,|$)", sel.split(">")[-1]):
                        continue
                    decls.extend((sel, d.strip()) for d in body.split(";") if d.strip())
            for sel, d in decls + [("inline", d.strip()) for d in anc["style"].split(";") if d.strip()]:
                m = FORBIDDEN.match(d)
                if not m:
                    continue
                prop, _, val = m.groups()
                val = val.strip()
                ok = (
                    (prop == "position" and val == "static")
                    or (prop.startswith("overflow") and val == "visible")
                    or (prop == "content-visibility" and val in ("visible", "hidden"))  # gates: hidden only while inactive
                    or (prop == "contain" and val == "none")
                )
                if not ok:
                    problems.append(f"ancestor {anc['tag']}.{'.'.join(anc['classes'])}#{anc['id']} has {d} (rule {sel[:60]})")

    # --- anchors and readers
    anchors = {}
    for e in els:
        for m in re.finditer(r"anchor-name:\s*(--[\w-]+)", e["style"]):
            anchors.setdefault(m[1], []).append(e)
    dup = {k: len(v) for k, v in anchors.items() if len(v) > 1}
    if dup:
        problems.append(f"duplicate anchor names: {list(dup.items())[:5]}")
    fc_anchors = sum(1 for k in anchors if k.startswith("--f3f"))
    proj_anchors = sum(1 for k in anchors if k.startswith("--f3p"))
    range_anchors = sum(1 for k in anchors if k.startswith("--f3m"))
    containers = [e for e in els if "f3-c" in e["classes"]]
    print(f"fc anchors {fc_anchors}  proj anchors {proj_anchors}  range anchors {range_anchors}  containers {len(containers)}")
    if fc_anchors != 3072 or proj_anchors != 12 * 768 or range_anchors != 12:
        problems.append("anchor counts differ from 3072 / 9216 / 12")
    by_id = {e["id"]: e for e in els if e["id"]}

    def is_oof(e):
        # our chain containers and stages; scrollers / readbacks are the other fixed things
        return ("f3-c" in e["classes"]) or ("f3-stage" in e["classes"]) or ("scroller" in e["classes"]) or ("readback" in e["classes"]) or ("position:fixed" in e["style"]) or ("position:absolute" in e["style"])

    def oof_root(e):
        root = None
        cur = e
        while cur is not None:
            if is_oof(cur):
                root = cur
            cur = els[cur["parent"]] if cur["parent"] is not None else None
        return root

    reader_rules = [(sel, body) for sel, body in rules if "anchor-size(--f3" in body]
    checked = bad_order = missing = 0
    for sel, body in reader_rules:
        m = re.fullmatch(r"#([\w-]+)", sel.strip())
        if not m or m[1] not in by_id:
            continue
        reader = by_id[m[1]]
        rroot = oof_root(reader)
        for name in set(re.findall(r"anchor-size\((--[\w]+) width", body)):
            checked += 1
            if name not in anchors:
                missing += 1
                continue
            anchor = anchors[name][0]
            aroot = oof_root(anchor)
            if anchor["index"] >= reader["index"]:
                bad_order += 1
            elif aroot is not None and rroot is not None and aroot is not rroot and aroot["index"] >= rroot["index"]:
                # anchor in a different OOF root that comes later than the reader's root
                if not (anchor["index"] < reader["index"] and is_descendant(anchor, rroot, els)):
                    bad_order += 1
    print(f"anchor-size references checked {checked}  missing {missing}  order violations {bad_order}")
    if missing or bad_order:
        problems.append(f"anchor references: missing {missing}, order violations {bad_order}")

    # --- leftovers
    for needle in ("shared-fc-receipt", "shared-proj-receipt", "shared-fc-gate", "shared-proj-gate", "--shared-fc-t0", "--shared-proj-t0"):
        if needle in html:
            problems.append(f"leftover {needle} in index.html")
    hidden_rules = len(re.findall(r"--hidden-\d{3,4}:--gelu\(calc\(\(100cq", css))
    out_rules = len(re.findall(r"--out-\d{3}:calc\(var\(--r-\d{3}\) \+ \(100cq", css))
    print(f"per-layer decode declarations: hidden {hidden_rules} (expect {3072 * blocks})  out {out_rules} (expect {768 * blocks})")
    if hidden_rules != 3072 * blocks or out_rules != 768 * blocks:
        problems.append("decode declaration counts off")
    print("PROBLEMS:" if problems else "LINT OK")
    for p in problems:
        print("  -", p)
    sys.exit(1 if problems else 0)


def is_descendant(e, root, els):
    cur = e
    while cur is not None:
        if cur is root:
            return True
        cur = els[cur["parent"]] if cur["parent"] is not None else None
    return False


if __name__ == "__main__":
    main()
