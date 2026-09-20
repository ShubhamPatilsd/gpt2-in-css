"""R2G: bound the traversal of the loop-handshake `:has()` arguments.

Why: `.core-controller` carries 272 rules of the form `.core-controller:where(:has(#loop-captured-N.done))`
(+ 88 with a `#loop-ack-N` subject) and 7 `:where(body:has(#token-N-advanced.done)) .core-controller`
rules; `.core-block` has `body:has(#fonts-loaded.done):has(#run-latched.done)`.  Blink's `:has()` matcher
walks the anchor's WHOLE subtree once per distinct argument (the fast-reject bloom filter cannot reject
`#id.done` once any `.done` exists), in reverse DOM order, so every restyle of `.core-controller`
(pass advance, R2A population 485) visits ~184 x 16.9k + 7 x 69.5k ~ 3.6 M elements and every restyle
of the 88 `#loop-ack-N` <g>s another 88 x 16.9k.  With only child combinators in the argument Blink
limits the traversal to a fixed depth (check_pseudo_has_argument_context.cc), i.e. to the ~600-element
signal svg.

This module rewrites the arguments to exact direct-child chains and VERIFIES each chain against the
emitted HTML (the id's ancestor path must equal the chain), so a DOM change makes the build fail
instead of emitting a handshake that never fires.  Flag: R2G_SCOPED_HAS (default on).
"""
from __future__ import annotations

import html.parser
import os
import re

SCOPED_HAS = os.environ.get("R2G_SCOPED_HAS", "1") not in ("0", "false", "no", "off")

LOOP_CHAIN = [".core-block", ".loop-reader", ".loop-input", ".loop-signals"]
VOID = {"br", "meta", "link", "input", "img", "hr", "set", "option"}


class _Paths(html.parser.HTMLParser):
    """Ancestor path (as class selectors / tag) of every element with an id we care about."""

    def __init__(self, wanted):
        super().__init__()
        self.wanted = wanted
        self.stack = []
        self.paths = {}

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if d.get("id") in self.wanted:
            self.paths[d["id"]] = list(self.stack)
        if tag not in VOID:
            classes = d.get("class", "").split()
            self.stack.append((tag, classes))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()


def _chain_matches(path, anchor_index, chain):
    """path[anchor_index] is the anchor; the elements strictly below it must carry chain[i] classes in order."""
    below = path[anchor_index + 1 :]
    if len(below) != len(chain):
        return False
    return all(sel.lstrip(".") in classes for sel, (tag, classes) in zip(chain, below))


def scope_has_arguments(css: str, page_html: str, capacity: int) -> tuple[str, dict]:
    """Rewrite the handshake `:has()` arguments to fixed-depth child chains; verify against page_html."""
    ids = {f"loop-captured-1", f"loop-advanced-1", "fonts-loaded", "run-latched"} | {
        f"token-{t}-advanced" for t in range(1, capacity)
    }
    parser = _Paths(ids)
    parser.feed(page_html)
    paths = parser.paths

    def anchor(path, klass):
        for i, (tag, classes) in enumerate(path):
            if klass in classes or tag == klass:
                return i
        raise ValueError(f"anchor {klass} not found in path {path}")

    # 1. loop rules: .core-controller:where(:has(#loop-x-N.done)) [ #loop-ack-N]
    for key in ("loop-captured-1", "loop-advanced-1"):
        p = paths[key]
        if not _chain_matches(p, anchor(p, "core-controller"), LOOP_CHAIN):
            raise ValueError(f"loop signal chain mismatch for {key}: {p[anchor(p, 'core-controller'):]}")
    loop_chain = " ".join(f"> {sel}" for sel in LOOP_CHAIN)
    css, n_loop = re.subn(
        r"\.core-controller:where\(:has\((#loop-(?:captured|advanced)-\d+\.done)\)\)",
        lambda m: f".core-controller:where(:has({loop_chain} > {m[1]}))",
        css,
    )

    # 2. token boundary rules: :where(body:has(#token-N-advanced.done)) .core-controller
    p = paths[f"token-1-advanced"]
    bi = anchor(p, "body")
    token_chain = [f".{c[0]}" if c else t for t, c in p[bi + 1 :]]
    if not (token_chain[0] == ".detached-head-reader" and token_chain[-1] == ".native-signals"):
        raise ValueError(f"unexpected token signal chain {token_chain}")
    for t in range(2, capacity):
        if paths[f"token-{t}-advanced"][bi + 1 :] != p[bi + 1 :]:
            raise ValueError(f"token-{t}-advanced sits in a different chain")
    tc = " ".join(f"> {sel}" for sel in token_chain)
    css, n_token = re.subn(
        r":where\(body:has\((#token-\d+-advanced\.done)\)\) \.core-controller",
        lambda m: f":where(body:has({tc} > {m[1]})) .core-controller",
        css,
    )

    # 3. core-block visibility: body:has(#fonts-loaded.done):has(#run-latched.done) .core-block
    pf, pr = paths["fonts-loaded"], paths["run-latched"]
    fchain = [f".{c[0]}" for t, c in pf[anchor(pf, "body") + 1 :]]
    rchain = [f".{c[0]}" for t, c in pr[anchor(pr, "body") + 1 :]]
    fc = " ".join(f"> {s}" for s in fchain)
    rc = " ".join(f"> {s}" for s in rchain)
    css, n_block = re.subn(
        re.escape("body:has(#fonts-loaded.done):has(#run-latched.done) .core-block"),
        f"body:has({fc} > #fonts-loaded.done):has({rc} > #run-latched.done) .core-block",
        css,
    )

    stats = {"loopRules": n_loop, "tokenRules": n_token, "coreBlockRules": n_block,
             "loopChain": loop_chain, "tokenChain": tc, "fontsChain": fc, "runChain": rc}
    if n_loop == 0 or n_token != capacity - 1 or n_block != 1:
        raise ValueError(f"unexpected :has() rule counts {stats}")
    return css, stats
