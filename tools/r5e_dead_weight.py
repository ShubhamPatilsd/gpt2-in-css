"""R5E (2026-09-24): remove the declarations and elements that every style pass
re-applies without carrying a live value (work/2026-09-19/R5E.md).

Blink re-applies EVERY declaration of a dirtied element (audit SYNTHESIS §8.1:
4.45 us/element + 36.5 ns/byte for var() declarations, 0.72 us per short literal
declaration). The combined7 census (R5A/census.md, R5E.md §1) found four
populations that are restyled per layer pass or per token but carry no value:

  R5E_LEAN_WALLS=0       keep the two inheritance walls as emitted: `.core-reset`
                         (16,156 `--p:initial`, 309 KB, restyled every layer pass)
                         and `.head-isolation` (24,105 `--p:initial`, 463 KB, ~5
                         restyles per token). ON: each wall keeps only the
                         registered properties that some ancestor-or-self of the
                         wall element declares (CSS rule whose rightmost compound
                         can match it, inline style, or keyframes it animates);
                         every other property is provably at its initial value on
                         the wall's parent, so `initial` there is a no-op. Derived
                         mechanically from the assembled page + sheet at build
                         time (lean_walls()); identical computed values and
                         identical dirtying (the wall still pins every property
                         that can change above it).
  R5E_LP_INHERIT=0       keep R3R/F5's private `--lp-*` (proj readback numbers,
                         inherits:false) with 768 `--lp-i:inherit` forwards on
                         `.loop-input` plus R4T's 4,224 forwards on the nested
                         `.loop-reader-cK` chunks. ON: `--lp-*` stay registered
                         inherits:true (as r3r_fold_hop registers them) and the
                         forwards disappear. Same values at `.loop-input`; the
                         subtree they now inherit into is exactly the subtree the
                         decoded `--loop-in-*` (inherits:true) already dirty in the
                         same pass.
  R5E_DROP_DEAD_LISTS=0  keep `.fvs-query{--fvs-all-fields:…}` and the 8
                         `--fvs-retained-S` lists. ON (F5_BANK_LITERAL_LISTS only):
                         not emitted — the bank rules inline the literal lists and
                         nothing references these unregistered properties.
  R5E_KEEP_DIAG=1        keep the three geometry readback probe pairs
                         (`#core-probe`, `#block-11-probe`, `#reused-probe`: 15–19 KB
                         inline width calcs over 768 var() each, position:fixed,
                         plus their `*-epoch` twins) and `#core-epoch-observer`.
                         Default OFF: removed. `#reused-probe` sits in the proj
                         stage and is restyled + laid out every layer; the others
                         per token. The verifier reads computed styles of
                         `#core-result`, `.head-input-bank`, `.fvs-bank-L` and
                         `.token-slot-N`, none of which change.
"""

import os
import re
from html.parser import HTMLParser


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


LEAN_WALLS = flag("R5E_LEAN_WALLS")
LP_INHERIT = flag("R5E_LP_INHERIT")
DROP_DEAD_LISTS = flag("R5E_DROP_DEAD_LISTS")
KEEP_DIAG = flag("R5E_KEEP_DIAG", "0")

WALLS = (".core-reset", ".head-isolation")


def manifest():
    return {
        "r5eLeanWalls": LEAN_WALLS,
        "r5eLpInherit": LP_INHERIT,
        "r5eDropDeadLists": DROP_DEAD_LISTS,
        "r5eKeepDiag": KEEP_DIAG,
    }


# ---------------------------------------------------------------- DOM ancestry
_VOID = {"meta", "link", "input", "br", "img", "hr", "set", "animate"}


class _Dom(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack, self.nodes = [], []  # node = (tag, classes, id, style, parent)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        node = (tag, frozenset((a.get("class") or "").split()), a.get("id"), a.get("style") or "",
                self.stack[-1] if self.stack else -1)
        self.nodes.append(node)
        if tag not in _VOID:
            self.stack.append(len(self.nodes) - 1)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.nodes[self.stack[i]][0] == tag:
                del self.stack[i:]
                break


def _ancestors_or_self(nodes, index):
    out = []
    while index >= 0:
        out.append(nodes[index])
        index = nodes[index][4]
    return out


# ---------------------------------------------------------------- CSS scanning
def _rules(css):
    """Yield (prelude, body, parents) for every block, nested blocks included; body = the
    declarations before any nested '{'; parents = tuple of enclosing preludes (outermost first)."""
    i, n, start = 0, len(css), 0
    stack = []
    while i < n:
        c = css[i]
        if c == '"':
            j = css.find('"', i + 1)
            while j > 0 and css[j - 1] == "\\":
                j = css.find('"', j + 1)
            i = j + 1
            continue
        if c == "{":
            stack.append((css[start:i].strip(), i + 1))
            i += 1
            start = i
            continue
        if c == "}":
            pre, bstart = stack.pop()
            body = css[bstart:i]
            k = body.find("{")
            yield pre, (body if k < 0 else body[:k]), tuple(p for p, _ in stack)
            i += 1
            start = i
            continue
        if c == ";" and not stack:
            i += 1
            start = i
            continue
        i += 1


def _split_top(text, sep):
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def _rightmost_compound(selector):
    depth = 0
    for k in range(len(selector) - 1, -1, -1):
        ch = selector[k]
        if ch in ")]":
            depth += 1
        elif ch in "([":
            depth -= 1
        elif depth == 0 and ch in " >+~":
            return selector[k + 1:]
    return selector


_CLASS = re.compile(r"\.([\w-]+)")
_ID = re.compile(r"#([\w-]+)")
_TYPE = re.compile(r"^([a-zA-Z][\w-]*|\*)")


def _compound_matches(compound, node):
    """Could `compound` match `node`? Pseudo-classes are ignored (superset = safe)."""
    # strip functional pseudo-class arguments so their inner selectors do not count as constraints
    flat, depth, out = compound, 0, []
    for ch in flat:
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth -= 1
            continue
        if depth == 0:
            out.append(ch)
    flat = "".join(out)
    tag, classes, ident = node[0], node[1], node[2]
    m = _TYPE.match(flat)
    if m and m.group(1) != "*" and m.group(1).lower() != tag:
        return False
    for c in _CLASS.findall(flat):
        if c not in classes:
            return False
    for i in _ID.findall(flat):
        if i != ident:
            return False
    return True


_DECL_PROP = re.compile(r"(?:^|;)\s*(--[\w-]+)\s*:")
_ANIM_NAMES = re.compile(r"(?:^|;)\s*animation(?:-name)?\s*:([^;]*)")
_IDENT = re.compile(r"[A-Za-z_-][\w-]*")


def _declared_props(body):
    return set(_DECL_PROP.findall(body))


def _animation_names(body):
    names = set()
    for value in _ANIM_NAMES.findall(body):
        for part in value.split(","):
            for tok in _IDENT.findall(part):
                names.add(tok)
    return names


def lean_walls(css, page, walls=WALLS):
    """Shrink each wall rule to the properties that can be non-initial on the wall element.

    Returns (css, stats). A property is kept when an ancestor-or-self of the wall element
    (a) declares it in a rule whose rightmost compound can match that element,
    (b) declares it in its inline style, or
    (c) animates it (keyframes referenced by an animation on such a rule).
    """
    dom = _Dom()
    dom.feed(page)
    nodes = dom.nodes
    keyframes = {}
    matched_rules = []
    for pre, body, parents in _rules(css):
        if parents and parents[-1].startswith("@keyframes"):
            keyframes.setdefault(parents[-1].split()[1], set()).update(_declared_props(body))
            continue
        if pre.startswith("@"):
            continue
        matched_rules.append((pre, body))
    stats = {}
    for wall in walls:
        cls = wall.lstrip(".")
        targets = [i for i, n in enumerate(nodes) if cls in n[1]]
        if len(targets) != 1:
            raise ValueError(f"R5E: expected one {wall} element, found {len(targets)}")
        chain = _ancestors_or_self(nodes, targets[0])
        live, anims = set(), set()
        for node in chain:
            live |= _declared_props(node[3])
        for pre, body in matched_rules:
            if pre == wall:
                continue  # the wall rule itself
            for selector in _split_top(pre, ","):
                comp = _rightmost_compound(selector.strip())
                if any(_compound_matches(comp, node) for node in chain):
                    live |= _declared_props(body)
                    anims |= _animation_names(body)
                    break
        for name in anims:
            live |= keyframes.get(name, set())
        start = css.find(wall + "{")
        if start < 0 or css.find(wall + "{", start + 1) >= 0:
            raise ValueError(f"R5E: expected exactly one {wall} rule")
        end = css.index("}", start)
        decls = css[start + len(wall) + 1:end].split(";")
        kept, dropped = [], 0
        for d in decls:
            name = d.split(":", 1)[0].strip()
            if d.strip().endswith(":initial") and name.startswith("--") and name not in live:
                dropped += 1
                continue
            kept.append(d)
        css = css[:start] + wall + "{" + ";".join(kept) + "}" + css[end + 1:]
        stats[wall] = {"kept": len([d for d in kept if d.strip().endswith(":initial")]),
                       "dropped": dropped, "liveOnAncestors": len(live), "ancestors": len(chain) - 1}
    return css, stats
