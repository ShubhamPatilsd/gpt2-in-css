# R5M: third fixture set — the REAL head subtree (197 head-group sections = 50,257 rows from combined7/index.html) under the real runtime.css,
# with per-generation --head-fvs changes (= one head pass per token). Variants: rows as today (inline --base/--tie custom props), rows with the
# same width as an inline literal expression (no custom props), and today's rows without the .head-isolation wall.
import re, os, random
random.seed(11)
W = '/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19'; B = f'{W}/bundles/combined7'; OUT = f'{W}/R5M/fx'
css = open(f'{B}/runtime.css').read(); html = open(f'{B}/index.html').read()
sections = re.findall(r'<section class="head-group"[^>]*>.*?</section>', html, re.S)
assert len(sections) == 197 and sum(s.count('class="head-row"') for s in sections) == 50257
B36 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
xtags = ['X' + B36[i // 1296] + B36[i // 36 % 36] + B36[i % 36] for i in range(256)]
gens = 3
# effective .head-row width rule = the LAST unconditional .head-row width declaration in the sheet (R3H): no --tie term
rules = [m.group(0) for m in re.finditer(r'\.head-row\{[^{}]*\}', css)]
eff = [r for r in rules if 'width:' in r][-1]
print('effective width rule:', eff)
assert eff == '.head-row{width:calc-size(max-content,round(nearest,(size - var(--base)*1px)*120.777609693 + 211968px,4px))}'
def literal_rows(sec):
    return re.sub(r'style="--base:([-\d.]+);--tie:(\d+)"', lambda m: f'style="width:calc-size(max-content,round(nearest,(size - {m.group(1)}px)*120.777609693 + 211968px,4px))"', sec)
extra = ''.join(f'html.g{g} .head-input-bank{{--head-fvs:{",".join(f"""&quot;{t}&quot; {random.randint(0, 16384)}""" for t in xtags)}}}' for g in range(1, gens + 1))
extra = extra.replace('&quot;', '"')
def page(name, wall, rows_fn):
    body = ('<div class="final-normalization"><div class="head-input-bank"><div class="' + ('head-isolation' if wall else 'no-wall') + '"><div class="full-head" style="content-visibility:visible">'
            + ''.join(rows_fn(s) for s in sections) + '</div></div></div></div>')
    doc = f'<!doctype html><html><head><meta charset="utf-8"><title>{name}</title><link rel="stylesheet" href="/work/2026-09-19/bundles/combined7/runtime.css"><style>{extra}</style></head><body>{body}</body></html>'
    open(f'{OUT}/{name}.html', 'w').write(doc); print(name, os.path.getsize(f'{OUT}/{name}.html'))
page('head50k-vars-gen', True, lambda s: s)
page('head50k-literal-gen', True, literal_rows)
page('head50k-nowall-gen', False, lambda s: s)
