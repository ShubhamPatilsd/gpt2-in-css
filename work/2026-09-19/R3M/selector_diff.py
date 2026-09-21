# R3M copy of R2H/selector_diff.py: args may be directory paths instead of names under bundles/.
"""R2H: selector-level (rule-text) diff of two bundles' runtime.css. usage: selector_diff.py <bundle> <ref>"""
import sys, re
from collections import Counter
from pathlib import Path
W = Path(__file__).resolve().parents[1] / "bundles"  # R3M/ is one level below work/2026-09-19, like R2H/
def rules(css):
    # split at top-level and nested rule boundaries: every `selector{decls}` leaf, keyed by the full text
    out, depth, start, stack = Counter(), 0, 0, []
    i = 0
    while i < len(css):
        c = css[i]
        if c == '"':
            i = css.index('"', i + 1)
        elif c == "{":
            stack.append(css[start:i].strip()); depth += 1; start = i + 1
        elif c == "}":
            body = css[start:i].strip()
            if body: out[" > ".join(stack) + "{" + body + "}"] += 1
            stack.pop(); depth -= 1; start = i + 1
        i += 1
    return out
a, b = (rules(((Path(n) if "/" in n else W / n) / "runtime.css").read_text()) for n in sys.argv[1:3])
added, removed = a - b, b - a
print("rules", sum(a.values()), "ref", sum(b.values()), "added", sum(added.values()), "removed", sum(removed.values()))
for k, n in removed.items(): print("- x%d %s" % (n, k[:220]))
for k, n in added.items(): print("+ x%d %s" % (n, k[:220]))
