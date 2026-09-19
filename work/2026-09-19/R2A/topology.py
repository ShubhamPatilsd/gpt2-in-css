#!/usr/bin/env python3
"""R2A: element topology of a bundle's index.html (html.parser walk, no DOM library).
Prints: total elements; for every element with >= MIN descendants (or with an id / a 'structural' class)
its depth, tag, id, classes, #children, #descendants (elements), and a per-class element count.
usage: topology.py index.html [min_desc]
"""
import sys, collections
from html.parser import HTMLParser
path = sys.argv[1]; MIN = int(sys.argv[2]) if len(sys.argv) > 2 else 100
VOID = {"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr","set","animate","stop","use","path","circle","rect"}
class N:
    __slots__ = ("tag","attrs","children","parent","depth","desc","idx","inline_fvs")
    def __init__(s, tag, attrs, parent, depth, idx):
        s.tag, s.attrs, s.parent, s.depth, s.idx = tag, attrs, parent, depth, idx; s.children = []; s.desc = 0
class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.root = N("#root", {}, None, -1, 0); s.cur = s.root; s.n = 0; s.all = []
    def handle_starttag(s, tag, attrs):
        s.n += 1; a = dict(attrs); node = N(tag, a, s.cur, s.cur.depth + 1, s.n); s.cur.children.append(node); s.all.append(node)
        if tag not in VOID: s.cur = node
    def handle_startendtag(s, tag, attrs):
        s.n += 1; a = dict(attrs); node = N(tag, a, s.cur, s.cur.depth + 1, s.n); s.cur.children.append(node); s.all.append(node)
    def handle_endtag(s, tag):
        c = s.cur
        while c is not s.root and c.tag != tag: c = c.parent
        if c is not s.root: s.cur = c.parent
p = P(); p.feed(open(path, encoding="utf-8", errors="replace").read())
def count(n):
    d = 0
    for c in n.children: d += 1 + count(c)
    n.desc = d; return d
count(p.root)
print(f"elements {p.n}; max depth {max(n.depth for n in p.all)}")
tags = collections.Counter(n.tag for n in p.all); print("tags", tags.most_common(12))
cls = collections.Counter()
for n in p.all:
    for c in (n.attrs.get("class") or "").split(): cls[c] += 1
print("classes (top 60):");
for c, k in cls.most_common(60): print(f"  {k:6d} {c}")
# inline style stats
inl = collections.Counter()
for n in p.all:
    st = n.attrs.get("style") or ""
    if "view-timeline" in st: inl["view-timeline"] += 1
    if "font-variation-settings" in st: inl["font-variation-settings"] += 1
    if "anchor-name" in st: inl["anchor-name"] += 1
print("inline:", dict(inl))
print(f"\nstructural elements (desc >= {MIN} or has id) — depth tag#id.classes children desc")
def walk(n):
    if n is not p.root and (n.desc >= MIN or n.attrs.get("id")):
        cl = ".".join((n.attrs.get("class") or "").split()[:4]); i = n.attrs.get("id")
        print(f"{'  '*min(n.depth,60)}d{n.depth} {n.tag}{'#'+i if i else ''}{'.'+cl if cl else ''} ch={len(n.children)} desc={n.desc}")
    for c in n.children: walk(c)
walk(p.root)
