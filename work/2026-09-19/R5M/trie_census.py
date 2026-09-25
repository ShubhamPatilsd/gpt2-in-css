# R5M: where do custom-property tries and per-restyle garbage live? Static pass over combined7 (and bundles/R5M for the head rows).
# (B') elements that DECLARE custom properties (inline or via a class rule whose subject class they carry) -> each such element owns a path-copied
#      inherited/non-inherited trie; (B) inherited custom-property declarations on the ancestor chain of the head rows and the V leaves;
# (A) garbage budget per token from R4W's pass histogram (restyles per token by population) x bytes per restyle.
import re, sys, collections
from html.parser import HTMLParser
B = sys.argv[1] if len(sys.argv) > 1 else 'bundles/combined7'
css = open(f'{B}/runtime.css').read(); html = open(f'{B}/index.html').read()
props = {m.group(1): m.group(2) for m in re.finditer(r'@property\s+(--[\w-]+)\s*\{([^}]*)\}', css)}
INH = {p for p, b in props.items() if 'inherits:true' in b.replace(' ', '')}
def is_inh(p): return p in INH or p not in props   # unregistered custom properties inherit
# rules: subject class -> list of (inherited decl names, noninherited decl names, has var)
subj = collections.defaultdict(lambda: [set(), set(), 0])
for m in re.finditer(r'([^{}@;]+)\{([^{}]*)\}', css):
    sel, body = m.group(1).strip(), m.group(2)
    if not body or sel.startswith('@') or 'from' == sel or 'to' == sel or sel.endswith('%'): continue
    for s in sel.split(','):
        last = s.strip().split()[-1] if s.strip() else ''
        classes = re.findall(r'\.([\w-]+)', last.split(':')[0])
        if not classes: continue
        decl = re.findall(r'(?:^|;)\s*(--[\w-]+)\s*:', body)
        e = subj[classes[-1]]
        for d in decl: (e[0] if is_inh(d) else e[1]).add(d)
        e[2] += body.count('var(')
class P(HTMLParser):
    def __init__(s): super().__init__(); s.stack = []; s.el = []  # el: (idx, parent, classes, inline_props, tag)
    def handle_starttag(s, tag, attrs):
        a = dict(attrs); cls = a.get('class', '').split(); st = a.get('style', '')
        ip = re.findall(r'(?:^|;)\s*(--[\w-]+)\s*:', st)
        idx = len(s.el); parent = s.stack[-1] if s.stack else -1
        s.el.append((idx, parent, cls, ip, tag, 'var(' in st))
        if tag not in ('meta', 'link', 'br', 'input', 'img'): s.stack.append(idx)
    def handle_endtag(s, tag):
        if s.stack: s.stack.pop()
p = P(); p.feed(html); E = p.el
print('elements', len(E))
# (B') declaring elements
decl_by = collections.Counter(); inh_decl_elems = 0; noninh_decl_elems = 0; total_inh_entries = 0
for idx, par, cls, ip, tag, _ in E:
    inh = {d for d in ip if is_inh(d)}; non = {d for d in ip if not is_inh(d)}
    for c in cls:
        if c in subj: inh |= subj[c][0]; non |= subj[c][1]
    if inh or non:
        key = re.sub(r'\d+', 'N', ' '.join(cls[:2])) or f'<{tag}>'
        decl_by[key] += 1
    if inh: inh_decl_elems += 1; total_inh_entries += len(inh)
    if non: noninh_decl_elems += 1
print(f'elements declaring inherited custom props: {inh_decl_elems} (entries {total_inh_entries}); declaring non-inherited: {noninh_decl_elems}')
print('declaring elements by class (top 15):', decl_by.most_common(15))
# (B) ancestor-chain inherited declarations for a head row and a V leaf
def chain_inh(idx):
    seen = {}; n = idx; hops = 0
    while n >= 0:
        _, par, cls, ip, tag, _ = E[n]
        d = {x for x in ip if is_inh(x)}
        for c in cls:
            if c in subj: d |= subj[c][0]
        for x in d: seen.setdefault(x, re.sub(r'\d+', 'N', ' '.join(cls[:2])) or tag)
        n = par; hops += 1
    return seen, hops
for name, pred in (('head-row', lambda e: 'head-row' in e[2]), ('fvs-v leaf', lambda e: any(c.startswith('fvs-v-') for c in e[2])), ('metric carrier', lambda e: e[2][:1] == ['metric']), ('shared-fc consumer', lambda e: any(c.startswith('shared-fc-c') for c in e[2]))):
    el = next(e for e in E if pred(e)); seen, hops = chain_inh(el[0])
    by = collections.Counter(seen.values())
    print(f'{name}: depth {hops}, inherited custom props declared on self+ancestors = {len(seen)} ; by declaring class: {by.most_common(8)}')
# (A) garbage budget: restyles per token by population (R4W trace histogram of the widths-family page: value subtree 25,351 x12, whole doc x1, 414/782/3089/2324 x12; head 51,138 in the whole-doc pass)
pops = [('V-leaf subtree (6,144 leaves + 768 rows + wrappers)', 25351, 12, 3.5, 'R4W: 1,069 B list copy + 65-entry CSSValueList + FontVariationSettings + ComputedStyle'),
        ('head rows (50,257 unique inline styles)', 50257, 1, 2.5, 'ComputedStyle + var(--base) substitution + calc-size parse + 2-entry trie path copy'),
        ('query/bank/reader passes (414+782+3,089+2,324)', 414 + 782 + 3089 + 2324, 12, 3.0, 'K-list/alias substitutions dominate (12.7 KB per score glyph)'),
        ('rest of the whole-document pass', 67569 - 51138 - 25351, 1, 1.5, 'carriers/consumers/controller')]
tot = 0
print('\n(A) garbage budget per token (KB per restyle are estimates from R4W/R5A, not measured here):')
for name, n, k, kb, why in pops:
    mb = n * k * kb / 1024; tot += mb
    print(f'  {name:60s} {n:6d} x {k:2d} restyles x {kb:.1f} KB = {mb:7.0f} MB/token  ({why})')
print(f'  total ≈ {tot:.0f} MB/token; R5A: Oilpan +130–730 MB/token net, 3.0 GB committed-but-free at the end')
