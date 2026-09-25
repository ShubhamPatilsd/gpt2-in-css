"""R2G (as applied by R3F): bound the traversal of every handshake `:has()` argument.

Why (R2G.md §3b/§4): Blink's `:has()` matcher walks the anchor's WHOLE subtree once per distinct argument
(the fast-reject filter cannot reject `#id.done` once any `.done` exists), in reverse DOM order. With only
child combinators in the argument Blink limits the traversal to a fixed depth
(check_pseudo_has_argument_context.cc). R2G rewrote the 272 `.core-controller:where(:has(#loop-…))` rules
(gone since R2F's lean handshake), the 7 `:where(body:has(#token-N-advanced.done)) .core-controller` rules
and the `.core-block` visibility rule. R3F generalises the rewrite to EVERY body-anchored `:has(#id…)`
argument in the sheet (token captured/advanced, run/run-latched/fonts-loaded/eos-done, N-ready/ack
subjects): each `:has(#id.done)` / `:has(#id:checked)` becomes `:has(> .a > .b > … > #id.done)` with the
exact ancestor chain read from the emitted HTML, and the chain is VERIFIED (the id's ancestor path must
start at the anchor and equal the chain), so a DOM change fails the build instead of emitting a handshake
that never fires. `:has()` takes the specificity of its most specific argument, so every chain step is
written as `> :where(.a)` (zero specificity): the rewritten rules keep exactly their original specificity and
cascade order (the token-slot / epoch / handshake rules compete with @container rules on the same properties).
Flag: R2G_SCOPED_HAS (default on).
"""
from __future__ import annotations

import html.parser
import os
import re

SCOPED_HAS = os.environ.get("R2G_SCOPED_HAS", "1") not in ("0", "false", "no", "off")

import r4t_consumer_chunk as _r4t

LOOP_CHAIN = [".core-block", ".loop-reader", *(f".{c}" for c in _r4t.loop_reader_classes(768)), ".loop-input", ".loop-signals"]


class _Paths(html.parser.HTMLParser):
    """Ancestor path (tag, classes) of every element with an id we care about."""

    def __init__(self, wanted):
        super().__init__()
        self.wanted = wanted
        self.stack = []
        self.paths = {}

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if d.get("id") in self.wanted:
            self.paths[d["id"]] = list(self.stack)
        if tag not in {"br", "meta", "link", "input", "img", "hr", "set", "option"}:
            self.stack.append((tag, d.get("class", "").split()))

    def handle_startendtag(self, tag, attrs):
        d = dict(attrs)
        if d.get("id") in self.wanted:
            self.paths[d["id"]] = list(self.stack)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()


def _step(tag, classes):
    return f".{classes[0]}" if classes else tag


def _chain_from(path, anchor_index):
    steps = [_step(t, c) for t, c in path[anchor_index + 1 :]]
    return " ".join(f"> :where({s})" for s in steps)


def scope_has_arguments(css: str, page_html: str, capacity: int) -> tuple[str, dict]:
    """Rewrite every handshake `:has()` argument to a fixed-depth child chain; verify against page_html."""
    id_args = sorted(set(re.findall(r":has\((#[\w-]+)(?:\.done|:checked)\)", css)))
    ids = set(a.lstrip("#") for a in id_args)
    parser = _Paths(ids)
    parser.feed(page_html)
    paths = parser.paths
    missing = ids - set(paths)
    if missing:
        raise ValueError(f"R2G: :has() ids not found in the page: {sorted(missing)[:8]}")

    def anchor(path, klass):
        for i, (tag, classes) in enumerate(path):
            if klass in classes or tag == klass:
                return i
        raise ValueError(f"anchor {klass} not found in path {path}")

    stats = {"rewritten": {}, "chains": {}}
    total = 0

    # 1. R2G's original loop rules (absent when R2F's lean handshake is on): anchor .core-controller.
    n_loop = 0
    if re.search(r"\.core-controller:where\(:has\(#loop-", css):
        for key in ("loop-captured-1", "loop-advanced-1"):
            p = paths[key]
            below = p[anchor(p, "core-controller") + 1 :]
            if [c[0] for t, c in below] != [s.lstrip(".") for s in LOOP_CHAIN]:
                raise ValueError(f"loop signal chain mismatch for {key}: {below}")
        loop_chain = " ".join(f"> :where({s})" for s in LOOP_CHAIN)
        css, n_loop = re.subn(
            r"\.core-controller:where\(:has\((#loop-(?:captured|advanced)-\d+\.done)\)\)",
            lambda m: f".core-controller:where(:has({loop_chain} > {m[1]}))",
            css,
        )
        stats["chains"]["loop"] = loop_chain
    stats["rewritten"]["loop"] = n_loop
    total += n_loop

    # 2. every body-anchored `:has(#id.done)` / `:has(#id:checked)`: chain = ancestors strictly below body.
    #    A compound may carry several :has() (`body:has(#run:checked):has(#token-N-captured.done)`); each
    #    occurrence is rewritten in place after verifying that, skipping earlier balanced `:has(...)` groups,
    #    the compound is anchored on `body`.
    chains = {}
    for arg in id_args:
        key = arg.lstrip("#")
        if key.startswith("loop-"):
            continue
        p = paths[key]
        chain = _chain_from(p, anchor(p, "body"))
        if not chain:
            raise ValueError(f"{key} is a direct child of body (nothing to scope)")
        chains[key] = chain
        stats["rewritten"][key] = 0
        stats["chains"][key] = chain

    def anchored_on_body(text, pos):
        """text[:pos] ends with the compound preceding `:has(`: skip balanced `:has(...)` groups, expect `body`."""
        i = pos
        while text.endswith(")", 0, i):
            depth, j = 0, i - 1
            while j >= 0:
                if text[j] == ")":
                    depth += 1
                elif text[j] == "(":
                    depth -= 1
                    if depth == 0:
                        break
                j -= 1
            if j < 4 or text[j - 4 : j + 1] != ":has(":
                return False
            i = j - 4
        return text.endswith("body", 0, i)

    def rewrite(m):
        key = m[1].lstrip("#")
        if key.startswith("loop-") or key not in chains:
            return m[0]
        if not anchored_on_body(css, m.start()):
            raise ValueError(f"R2G: :has({m[1]}) not anchored on body at {css[max(0, m.start() - 80):m.start()]!r}")
        stats["rewritten"][key] += 1
        return f":has({chains[key]} > {m[1]}{m[2]})"

    css = re.sub(r":has\((#[\w-]+)(\.done|:checked)\)", rewrite, css)
    total += sum(v for k, v in stats["rewritten"].items() if k != "loop")

    left = re.findall(r":has\(#[\w-]+(?:\.done|:checked)\)", css)
    if left:
        raise ValueError(f"R2G: unscoped :has() arguments left: {sorted(set(left))[:8]}")
    if stats["rewritten"].get("token-1-advanced", 0) != 2 or total == 0:
        raise ValueError(f"R2G: unexpected :has() rule counts {stats['rewritten']}")
    stats["total"] = total
    return css, stats
