"""Inventory every font-variation-settings declaration in a built runtime.css.
Groups by selector pattern (digits normalised), reports entries per list, per-entry shape, var()/calc counts.
usage: python3 inventory.py <runtime.css> [--json out.json]"""
import re, sys, json, collections
css_path = sys.argv[1]
css = open(css_path, encoding='utf-8').read()
key = 'font-variation-settings:'
out = collections.OrderedDict()
pos = 0
samples = {}
def split_top(v):
    parts, depth, cur, instr = [], 0, [], False
    for ch in v:
        if ch == '"': instr = not instr
        if not instr:
            if ch == '(': depth += 1
            elif ch == ')': depth -= 1
            elif ch == ',' and depth == 0:
                parts.append(''.join(cur).strip()); cur = []; continue
        cur.append(ch)
    if cur: parts.append(''.join(cur).strip())
    return parts
def shape(e):
    m = re.match(r'^"[^"]*"\s*(.*)$', e)
    body = m.group(1) if m else e
    if re.fullmatch(r'-?[\d.]+(e-?\d+)?', body): return 'literal'
    if re.fullmatch(r'var\(--[\w-]+\)', body): return 'var'
    if body.startswith('round('):
        return 'round(calc(var))' if 'var(' in body else 'round(literal)'
    if body.startswith('calc('): return 'calc(var)' if 'var(' in body else 'calc(lit)'
    if body.startswith('var('): return 'var-list'  # whole-list var
    return 'other:' + body[:40]
while True:
    i = css.find(key, pos)
    if i < 0: break
    j = i + len(key); depth = 0; instr = False
    while j < len(css):
        ch = css[j]
        if ch == '"': instr = not instr
        elif not instr:
            if ch == '(': depth += 1
            elif ch == ')': depth -= 1
            elif ch in ';}' and depth == 0: break
        j += 1
    val = css[i+len(key):j]
    b = css.rfind('{', 0, i)
    s0 = max(css.rfind('}', 0, b), css.rfind('{', 0, b), css.rfind(';', 0, b))
    sel = css[s0+1:b].strip()
    pos = j
    entries = split_top(val)
    shapes = collections.Counter(shape(e) for e in entries)
    nvar = val.count('var(')
    ncalc = val.count('calc(')
    nround = val.count('round(')
    pat = re.sub(r'\d+', 'N', sel)
    rec = out.setdefault(pat, {'rules': 0, 'entries': collections.Counter(), 'shapes': collections.Counter(), 'var': collections.Counter(), 'calc': collections.Counter(), 'round': collections.Counter(), 'bytes': collections.Counter()})
    rec['rules'] += 1
    rec['entries'][len(entries)] += 1
    rec['shapes'].update(shapes)
    rec['var'][nvar] += 1; rec['calc'][ncalc] += 1; rec['round'][nround] += 1; rec['bytes'][len(val)] += 1
    if pat not in samples:
        samples[pat] = {'selector': sel, 'first_entries': entries[:2], 'last_entry': entries[-1][:200] if entries else ''}
for pat, rec in out.items():
    def top(c): return dict(c.most_common(3))
    print(f"\n### {pat}\n rules={rec['rules']} entries={top(rec['entries'])} var()={top(rec['var'])} calc()={top(rec['calc'])} round()={top(rec['round'])} bytes={top(rec['bytes'])}\n shapes={dict(rec['shapes'])}\n sample selector: {samples[pat]['selector'][:160]}\n first: {samples[pat]['first_entries']}\n last: {samples[pat]['last_entry']}")
if '--json' in sys.argv:
    j = sys.argv[sys.argv.index('--json') + 1]
    json.dump({p: {k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in r.items()} for p, r in out.items()}, open(j, 'w'), indent=1)
