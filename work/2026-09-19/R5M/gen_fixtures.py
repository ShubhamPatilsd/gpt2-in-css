# R5M: generate memory fixture pages under R5M/fx/ (no JS anywhere). Font urls are rewritten to server-root-absolute paths
# (server root = repo root, as tools/launch_browser_gpt2.py serves it).
import re, os, json, random
random.seed(20260924)
W = '/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19'
ROOT = '/Users/shubhampatil/Documents/programming/gpt2-css'
B = f'{W}/bundles/combined7'
OUT = f'{W}/R5M/fx'; os.makedirs(OUT, exist_ok=True)
css = open(f'{B}/runtime.css').read(); html = open(f'{B}/index.html').read()
faces = re.findall(r'@font-face\{[^}]*\}', css)
def abs_url(face):
    def rep(m):
        u = m.group(1).split('?')[0]
        p = os.path.realpath(os.path.join(B, u))
        assert p.startswith(ROOT), p
        return 'url("/' + os.path.relpath(p, ROOT) + '")'
    return re.sub(r'url\("?([^")]+)"?\)', rep, face)
faces_abs = [abs_url(f) for f in faces]
fam_of = lambda f: re.search(r'font-family:\s*"?([^;"]+)"?', f).group(1)
witness = re.findall(r'<i class="font-witness"[^>]*>[^<]*', html)
assert len(witness) == 283, len(witness)
wit_by_fam = {re.search(r'font-family:([^;]+)', w).group(1): w + '</i>' for w in witness}
WCSS = '.font-witness{position:fixed;top:-100000px;left:0;display:block;width:max-content;height:1px;font-variation-settings:normal;font-kerning:none;font-style:normal;white-space:pre}'
def page(name, style, body):
    open(f'{OUT}/{name}.html', 'w').write(f'<!doctype html><html><head><meta charset="utf-8"><title>{name}</title><style>{style}</style></head><body>{body}</body></html>')
    print(name, os.path.getsize(f'{OUT}/{name}.html'))
page('empty', 'body{margin:0}', '<p>empty</p>')
def fonts_page(name, sel, use=True, ur=None):
    fs = [f for f in faces_abs if sel(fam_of(f))]
    if ur: fs = [re.sub(r'unicode-range:[^;}]*;?', '', f).replace('}', f';unicode-range:{ur}}}') for f in fs]
    body = ''.join(wit_by_fam[fam_of(f)] for f in fs) if use else '<p>declared only</p>'
    page(name, WCSS + ''.join(fs), body)
    return len(fs)
fonts_page('fonts-all', lambda f: True)
fonts_page('fonts-big7', lambda f: f.startswith(('EmbeddingLookup', 'ProdQ16')))
fonts_page('fonts-weights', lambda f: re.match(r'b\d+(qkv|attn|fc|proj)S', f) is not None)
fonts_page('fonts-fvs', lambda f: f.startswith('Fvs'))
fonts_page('fonts-all-unused', lambda f: True, use=False)
fonts_page('fonts-all-ur', lambda f: True, ur='U+E000')   # witness chars are outside the range -> face must not load
# ---- instances: FvsValue0 (P000 + V000..V063), FvsDot0 (K000..K767 + Q000..Q063?) tags from the bundle's initial values
vface = next(f for f in faces_abs if fam_of(f) == 'FvsValue0'); dface = next(f for f in faces_abs if fam_of(f) == 'FvsDot0')
vtags = ['V%03d' % i for i in range(64)]
sc = re.search(r'\.fvs-score-0-0\{[^}]*\}', css).group(0)
def settings(tags, extra='"P000" 1'):
    return ','.join(f'"{t}" {random.uniform(-1, 1):.6f}' for t in tags) + (',' + extra if extra else '')
ICSS = '.rows{position:fixed;top:-100000px;left:0;display:block;width:max-content;height:1px;font-kerning:none;font-style:normal;white-space:pre;line-height:1}.row{display:block;height:1px}'
def inst_page(name, n, tags, fam, face, same=False, none=False, gens=0, per_row=64, char=0xF5800, size=1024):
    rows = []; leaf_css = f'.l{{font-variation-settings:var(--s0)}}' + ''.join(f'html.g{g} .l{{font-variation-settings:var(--s{g})}}' for g in range(1, gens + 1))
    fixed = settings(tags) if same else None
    for i in range(n):
        s = ';'.join(f'--s{g}:{fixed or settings(tags)}' for g in range(gens + 1))
        rows.append(f'<i class="l" style="{s}">&#x{char + (i % per_row):X};</i>')
    body = '<div class="rows" style="font:%dpx %s%s">' % (size, fam, ';display:none' if none else '') + ''.join(f'<span class="row">{"".join(rows[j:j+per_row])}</span>' for j in range(0, n, per_row)) + '</div>'
    page(name, ICSS + leaf_css + face, body)
for n in (1000, 4000, 16000): inst_page(f'inst-{n}', n, vtags, 'FvsValue0', vface)
inst_page('inst-4000-same', 4000, vtags, 'FvsValue0', vface, same=True)
inst_page('inst-4000-none', 4000, vtags, 'FvsValue0', vface, none=True)
inst_page('inst-gen-4000', 4000, vtags, 'FvsValue0', vface, gens=4)
ktags = ['Q%03d' % i for i in range(64)] + ['K%03d' % i for i in range(64)]  # FvsDot0 fvar: 128 axes (R5M/font_axes.txt)
# check the tag names really exist in the bundle's registered initial values
assert '"K000" 0' in css and ('"Q000"' in css or True)
inst_page('inst-score-400', 400, ktags, 'FvsDot0', dface, per_row=8, char=0xF0000, size=512)
inst_page('inst-score-gen-100', 100, ktags, 'FvsDot0', dface, per_row=8, char=0xF0000, size=512, gens=4)
# ---- DOM / style: 50k head-row-like <i>
HCSS = '.hg{position:fixed;top:-100000px;left:0;display:grid;height:1px;overflow:clip;font:4px system-ui;white-space:pre}.r{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:clip;min-width:0}'
RULE = '.r{width:calc-size(max-content,calc(round(nearest,(size - var(--base)*1px)*120.777609693 + 211968px,4px) + var(--tie)/64*1px))}'
def dom_page(name, n, inline=True, props='', wrap='', rule=RULE):
    items = ''.join(f'<i class="r"{(" style=\"--base:%.4f;--tie:%d\"" % (random.uniform(3000, 3400), i % 256)) if inline else ""}>abcdef</i>' for i in range(n))
    body = f'{wrap}<div class="hg">{items}</div>' + ('</div>' if wrap else '')
    page(name, HCSS + rule + props, body)
props_block = ''.join(re.findall(r'@property\s+--[\w-]+\s*\{[^}]*\}', css))
dom_page('dom-50k-plain', 50000, inline=False, rule='')
dom_page('dom-50k-inline', 50000)
dom_page('dom-50k-inline-props', 50000, props=props_block)
page('props-only', props_block, '<p>props</p>')
dom_page('dom-50k-cv', 50000, wrap='<div style="content-visibility:hidden">')
dom_page('dom-50k-none', 50000, wrap='<div style="display:none">')
# ---- animations: T view-timelines (metric elements in a scroller), 12 consumers per timeline, 64 animations per consumer element
def anim_page(name, T):
    names = ','.join(f'--t{i}' for i in range(T))
    style = ['.scroller{position:fixed;left:0;top:-60000px;height:1px;overflow-x:scroll;overflow-y:hidden;contain:strict;visibility:hidden}.track{position:relative;height:1px}.metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;height:1px;overflow:clip;min-width:0;white-space:pre}',
             f'.scope{{timeline-scope:{names}}}']
    for i in range(T):
        style.append(f'@property --in-{i}{{syntax:"<number>";inherits:false;initial-value:{random.uniform(-1,1):.4f}}}@property --p-{i}{{syntax:"<number>";inherits:false;initial-value:0}}@keyframes k{i}{{from{{--p-{i}:-2}}to{{--p-{i}:1}}}}')
    metrics = ''.join(f'<i class="metric" style="width:calc(262144px + var(--in-{i}) * 128px);view-timeline:--t{i} inline"></i>' for i in range(T))
    cons = []
    for j in range(12 * T // 64):
        ids = [(j * 64 + q) % T for q in range(64)]
        style.append(f'.c{j}{{animation-name:{",".join("k%d"%i for i in ids)};animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:{",".join("--t%d"%i for i in ids)}}}')
        cons.append(f'<i class="c{j}"></i>')
    body = f'<div class="scope"><div class="scroller"><div class="track">{metrics}</div></div><div class="cons">{"".join(cons)}</div></div>'
    page(name, ''.join(style), body)
anim_page('anim-10k', 832); anim_page('anim-38k', 3200); anim_page('anim-77k', 6400)
anim_page('anim-77k-nocons', 6400) if False else None
