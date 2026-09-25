# R5M: second fixture set — per-instance memory of the BIG faces (head ProdQ16 6-face list, EmbeddingLookup, b0fcS*, b0projS0) via generations.
import re, os, random
random.seed(7)
W = '/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19'; ROOT = '/Users/shubhampatil/Documents/programming/gpt2-css'
B = f'{W}/bundles/combined7'; OUT = f'{W}/R5M/fx'
css = open(f'{B}/runtime.css').read(); html = open(f'{B}/index.html').read()
faces = re.findall(r'@font-face\{[^}]*\}', css)
def abs_url(face):
    def rep(m):
        p = os.path.realpath(os.path.join(B, m.group(1).split('?')[0])); return 'url("/' + os.path.relpath(p, ROOT) + '")'
    return re.sub(r'url\("?([^")]+)"?\)', rep, face)
fam_of = lambda f: re.search(r'font-family:\s*"?([^;"]+)"?', f).group(1)
F = {fam_of(f): abs_url(f) for f in faces}
def page(name, style, body):
    open(f'{OUT}/{name}.html', 'w').write(f'<!doctype html><html><head><meta charset="utf-8"><title>{name}</title><style>{style}</style></head><body>{body}</body></html>')
    print(name, os.path.getsize(f'{OUT}/{name}.html'))
B36 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def b36(i): return B36[i // 1296] + B36[i // 36 % 36] + B36[i % 36]
xtags = ['X' + b36(i) for i in range(256)]; atags = ['A%03d' % i for i in range(256)]
def st(tags, lo=-1, hi=1): return ','.join(f'"{t}" {random.uniform(lo, hi):.6f}' for t in tags)
BASE = '.box{position:fixed;top:-100000px;left:0;display:block;width:max-content;height:1px;font-kerning:none;font-synthesis:none;font-style:normal;white-space:pre;line-height:1}.row{display:block;height:1px;white-space:pre}'
def gen_rules(gens): return '.box{font-variation-settings:var(--s0)}' + ''.join(f'html.g{g} .box{{font-variation-settings:var(--s{g})}}' for g in range(1, gens + 1))
def vars_(gens, mk): return ';'.join(f'--s{g}:{mk()}' for g in range(gens + 1))
# head: 6 faces, 64 real head rows
rows = re.findall(r'<i class="head-row"[^>]*>([^<]*)', html)[:64]
famlist = 'ProdQ16H0,ProdQ16R0,ProdQ16H1,ProdQ16R1,ProdQ16H2,ProdQ16R2'
page('inst-head-gen', BASE + gen_rules(4) + ''.join(F[f] for f in famlist.split(',')),
     f'<div class="box" style="font:62.5px {famlist};{vars_(4, lambda: st(xtags))}">' + ''.join(f'<span class="row">{r}</span>' for r in rows) + '</div>')
# embedding: 2 axes, 768 glyphs
page('inst-embed-gen', BASE + gen_rules(4) + F['EmbeddingLookup'],
     f'<div class="box" style="font:1000px EmbeddingLookup;{vars_(4, lambda: f"""&quot;GRUP&quot; {random.randint(0,195)},&quot;LOCL&quot; {random.randint(0,255)}""")}">' + ''.join(f'<span class="row">&#x{0xE000 + i:X};</span>' for i in range(768)) + '</div>')
# fc: 3 faces (12 MB sfnt), 256 A axes, 64 glyphs
page('inst-fc-gen', BASE + gen_rules(4) + F['b0fcS0'] + F['b0fcS1'] + F['b0fcS2'],
     f'<div class="box" style="font:1000px b0fcS0,b0fcS1,b0fcS2;{vars_(4, lambda: st(atags))}">' + ''.join(f'<span class="row">&#x{0xF0000 + i:X};</span>' for i in range(64)) + '</div>')
# proj: 1 face (1.6 MB sfnt), 256 X axes
page('inst-proj-gen', BASE + gen_rules(4) + F['b0projS0'],
     f'<div class="box" style="font:1000px b0projS0;{vars_(4, lambda: st(xtags))}">' + ''.join(f'<span class="row">&#x{0xF0000 + i:X};</span>' for i in range(64)) + '</div>')
# fc: 8 distinct instances at once (marginal per instance within one pass)
page('inst-fc-8', BASE + F['b0fcS0'] + F['b0fcS1'] + F['b0fcS2'],
     ''.join(f'<div class="box" style="font:1000px b0fcS0,b0fcS1,b0fcS2;font-variation-settings:{st(atags)}">' + ''.join(f'<span class="row">&#x{0xF0000 + i:X};</span>' for i in range(64)) + '</div>' for _ in range(8)))
