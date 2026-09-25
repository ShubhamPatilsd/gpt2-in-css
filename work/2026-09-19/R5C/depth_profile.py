"""Depth profile of a bundle's index.html: max depth, depth of named elements, deepest leaf below them."""
import sys, re
from html.parser import HTMLParser

class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack = []; self.maxd = 0; self.count = 0; self.marks = {}; self.deep_under = {}
        self.watch = sys.argv[2:]
    def handle_starttag(self, tag, attrs):
        if tag in ("meta", "link", "br", "img", "input", "hr"):
            return
        a = dict(attrs); cls = a.get("class", ""); idv = a.get("id", "")
        self.stack.append((tag, cls, idv)); d = len(self.stack); self.count += 1
        self.maxd = max(self.maxd, d)
        for w in self.watch:
            if (w.startswith("#") and idv == w[1:]) or (w.startswith(".") and w[1:] in cls.split()):
                self.marks.setdefault(w, []).append(d)
        for i, (t, c, iv) in enumerate(self.stack):
            for w in self.watch:
                if (w.startswith("#") and iv == w[1:]) or (w.startswith(".") and w[1:] in c.split()):
                    self.deep_under[w] = max(self.deep_under.get(w, 0), d - (i + 1))
    def handle_startendtag(self, tag, attrs):
        pass
    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        else:
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]; break

p = P(); p.feed(open(sys.argv[1]).read())
print("elements", p.count, "max depth", p.maxd)
for w in p.watch:
    ds = p.marks.get(w, [])
    print(f"{w}: n={len(ds)} depth(first)={ds[0] if ds else None} max={max(ds) if ds else None} deepest-leaf-below={p.deep_under.get(w)}")
