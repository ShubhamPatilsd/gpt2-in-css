import re, sys, json, collections
css = open('bundles/combined8/runtime.css', encoding='utf-8').read()
out = {}
# 1. find the @container corestate style(--layer:0) blocks (there may be several)
blocks = []
for m in re.finditer(r'@container corestate style\(--layer:0\)\{', css):
    i = m.end(); depth = 1
    while depth:
        c = css[i]
        if c == '{': depth += 1
        elif c == '}': depth -= 1
        i += 1
    blocks.append(css[m.end():i-1])
print('layer-0 blocks:', len(blocks), 'sizes', [len(b) for b in blocks])
def rules(block):
    # split top-level rules "sel{decls}" (no nesting inside)
    res = []; i = 0; n = len(block)
    while i < n:
        j = block.find('{', i)
        if j < 0: break
        k = block.find('}', j)
        res.append((block[i:j].strip(), block[j+1:k]))
        i = k + 1
    return res
l0 = []
for b in blocks: l0 += rules(b)
print('layer-0 rules:', len(l0))
fam = collections.Counter(re.sub(r'\d+', 'N', s) for s, _ in l0)
for s, c in fam.most_common(40): print(f'  {c:4d} {s[:90]}')
json.dump(l0, open('R7T/fix/l0_rules.json', 'w'))
# chunk rule c0 full text
c0 = [d for s, d in l0 if s == '.shared-fc-c0']
print('\n.shared-fc-c0 rules in layer 0:', len(c0))
for d in c0:
    print(len(d), 'B'); print(d[:400]); print('...'); print(d[-900:])
    print('var refs:', collections.Counter(re.sub(r'\d+', 'N', v) for v in re.findall(r'var\((--[a-z0-9-]+)', d)).most_common(12))
# .shared-fc rules in layer 0
for s, d in l0:
    if s == '.shared-fc': print('\n.shared-fc', len(d), 'B:', d[:300].replace('\n',' '), '...', d[-200:])
# global (non-layer) rules of interest
for pat in [r'@keyframes fck0\{[^}]*\{[^}]*\}[^}]*\{[^}]*\}\}', r'@property --fcp-0\{[^}]*\}', r'@property --fz-0\{[^}]*\}', r'@property --ft-0\{[^}]*\}', r'@property --range-fc\{[^}]*\}', r'@property --fq-fc-000\{[^}]*\}', r'@property --n2-000\{[^}]*\}', r'@property --fcp-0000\{[^}]*\}', r'@property --fz-0000\{[^}]*\}']:
    m = re.search(pat, css); print('\n', pat[:30], '->', m.group(0)[:400] if m else None)
# how fcp names look in keyframes
m = re.search(r'@keyframes fck1155\{.{0,300}', css); print('\nkeyframes fck1155:', m.group(0)[:300] if m else None)
# html timeline-scope for shared-fc names
m = re.search(r'html\{timeline-scope:[^}]{0,200}', css); print('\nhtml timeline-scope head:', m.group(0)[:200] if m else None)
print('shared-fc names in html scope:', len(re.findall(r'--shared-fc-t\d+', ''.join(re.findall(r'html\{timeline-scope:[^}]*\}', css)))))
