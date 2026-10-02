"""R7T fixture: decompose the fc-stage WRITE pass (3,141 elements, ~139 ms in combined7/8) using the real layer-0 fc stage
(3 shard fonts, 3,072 carriers x 3 glyphs, 48 nested consumer chunks x 64 view-timeline animations, receipt/gate) copied
from bundles/combined8. Arms differ only in structure; inputs (768 --n2-*) come from html.go-k classes (16 states)."""
import re, json, os, random, html as H
W = '/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19'
ROOT = '/Users/shubhampatil/Documents/programming/gpt2-css'
css = open(f'{W}/bundles/combined8/runtime.css', encoding='utf-8').read()
l0 = json.load(open(f'{W}/R7T/fix/l0_rules.json'))
seg = open(f'{W}/R7T/fix/fc_stage_segment.html').read()
assert seg.startswith('<div class="shared-fc">'); scroller_html = seg[len('<div class="shared-fc">'):]
assert scroller_html.count("<i class=\"metric") == 3073  # 3072 carriers + marker
OUT = f'{W}/R7T/fix/pages'; os.makedirs(OUT, exist_ok=True)

def toplevel_rules(css):
    i=0; n=len(css); res=[]
    while i<n:
        j=css.find('{',i)
        if j<0: break
        sel=css[i:j].strip(); k=j+1; d=1
        while d:
            c=css[k]; d += (c=='{') - (c=='}'); k+=1
        res.append((sel, css[j+1:k-1])); i=k
    return res
top = toplevel_rules(css)
base_fc = [b for s,b in top if s=='.shared-fc']            # --fq-fc-* (38 KB)
assert len(base_fc)==1
fontfaces = [f'@font-face{{font-family:b0fcS{s};src:url("file://{ROOT}/experiments/hybrid-12block-profile/fonts/b0-fc-s{s}.woff2") format("woff2");unicode-range:{r}}}'
             for s,r in ((0,'U+F0000-F0BFF'),(1,'U+F0C00-F17FF'),(2,'U+F1800-F23FF'))]
static_rules = ''.join(f'{s}{{{b}}}' for s,b in top if s in ('.metric','.metric i','.scroller','.track'))
l0_fc_stage = [(s,b) for s,b in l0 if s in ('.shared-fc','.shared-fc>.scroller','.shared-fc>.scroller>.track','.shared-fc-receipt','.shared-fc-gate')]
l0_gate_open = [(s,b) for s,b in l0 if s.startswith('@container shared-fc-receipt')]
chunks = {s:b for s,b in l0 if re.fullmatch(r'\.shared-fc-c\d+', s)}
# the parser split "}.shared-fc-c47" because the previous rule was an @container block; recover it
for s,b in l0:
    m = re.fullmatch(r'\}(\.shared-fc-c\d+)', s)
    if m: chunks[m.group(1)] = b
assert len(chunks)==48, len(chunks)
range_rule = [b for s,b in l0_fc_stage if s=='.shared-fc' and b.startswith('--range-fc')][0]
scope_font_rule = [b for s,b in l0_fc_stage if s=='.shared-fc' and b.startswith('timeline-scope')][0]
fvs_rule = [b for s,b in l0_fc_stage if s=='.shared-fc' and b.startswith('font-family')][0]
marker_rule = [b for s,b in l0_fc_stage if s=='.shared-fc' and b.startswith('--markerbase')][0]
scope_decl = scope_font_rule.split(';')[0]; font_decl = ';'.join(scope_font_rule.split(';')[1:])
assert scope_decl.startswith('timeline-scope:')
kf = ''.join(f'@keyframes fck{n}{{from{{--fcp-{n:03d}:0}}to{{--fcp-{n:03d}:1}}}}' for n in range(3072)) + '@keyframes fcstamp{from{--stamp-fc:0}to{--stamp-fc:1}}'
def prop(name, inh, syntax='"<number>"', init='0'): return f'@property {name}{{syntax:{syntax};inherits:{inh};initial-value:{init}}}'
props = [prop(f'--n2-{n:03d}','true') for n in range(768)] + [prop(f'--fq-fc-{n:03d}','false') for n in range(768)]
props += [prop(f'--fcp-{n:03d}','false') for n in range(3072)] + [prop(f'--fz-{n:03d}','false') for n in range(3072)] + [prop(f'--ft-{n:03d}','false') for n in range(3072)] + [prop(f'--hidden-{n:03d}','true') for n in range(3072)]
props += [prop('--range-fc','true'), prop('--stamp-fc','false'), prop('--gate-fc','false'), prop('--epoch','false'), prop('--layer','false'), prop('--markerbase-fc','true','"<length>"','0px')]
random.seed(7)
inputs = ''.join('html.go-%d{%s}' % (k, ''.join(f'--n2-{n:03d}:{random.uniform(-2,2):.4f};' for n in range(768))) for k in range(16))
core = '.core{container-name:corestate;--layer:0}.pass-reader,.shared-fc-receipt{--epoch:1}'
core_ep = '.core{container-name:corestate;--layer:0}.pass-reader,.shared-fc-receipt{--epoch:var(--ep)}' + prop('--ep','true','"<number>"','1')
inputs_ep = ''.join('html.go-%d{--ep:%d}' % (k, k+1) for k in range(16))

def stage_rules(variants, with_scope=True, with_range=True):
    out=''
    for L in range(variants):
        body = []
        if with_range: body.append(f'.shared-fc{{{range_rule}}}')
        body.append(f'.shared-fc{{{(scope_decl+";") if with_scope else ""}{font_decl}}}'.replace('b0fcS0', f'b{L}fcS0'))
        body.append(f'.shared-fc{{{fvs_rule.replace("b0fcS", f"b{L}fcS")}}}')
        body.append(f'.shared-fc{{{marker_rule}}}')
        body += [f'{s}{{{b}}}' for s,b in l0_fc_stage if s!='.shared-fc']
        body += ['@container shared-fc-receipt style(--gate-fc:1){.shared-fc-gate{content-visibility:visible}}']
        out += f'@container corestate style(--layer:{L}){{{"".join(body)}}}'
    return out
def chunk_rules(variants, anims=True):
    out=''
    for L in range(variants):
        body=''
        for s,b in chunks.items():
            if not anims: b = ';'.join(d for d in b.split(';') if not d.startswith('animation'))
            body += f'{s}{{{b}}}'
        out += f'@container corestate style(--layer:{L}){{{body}}}'
    return out
chain_open = ''.join(f'<div class="shared-fc-c{i}">' for i in range(48)) + '<div class="shared-fc-receipt"><div class="shared-fc-gate"><div class="probe"></div></div></div>'
chain_close = '</div>'*48
chain_in_gate = '<div class="shared-fc-receipt"><div class="shared-fc-gate">' + ''.join(f'<div class="shared-fc-c{i}">' for i in range(48)) + '<div class="probe"></div>' + '</div>'*48 + '</div></div>'
bigmap_props = ''.join(prop(f'--bm-{n:04d}','true') for n in range(4000)); bigmap_rule = '.bigmap{' + ''.join(f'--bm-{n:04d}:{n};' for n in range(4000)) + '}'

ARMS_ALL = {
 'A0e_page_epoch': dict(chain='nested', variants=12, anims=True, vt=True, bigmap=False, epoch=True, note='A0 + epoch advances per mutation (gate closes at write, opens at readback) — control for A7'),
 'A7_chain_in_gate': dict(chain='ingate', variants=12, anims=True, vt=True, bigmap=False, epoch=True, note='chunk chain INSIDE the receipt/gate (content-visibility:hidden during the write pass), epoch advancing'),
 'A0_page':      dict(chain='nested', variants=12, anims=True,  vt=True,  bigmap=False, note='page topology: chunk chain under .shared-fc (sibling of scroller), 12 @container layer variants'),
 'A1_sibling':   dict(chain='sibling',variants=12, anims=True,  vt=True,  bigmap=False, note='chunk chain as SIBLING of .shared-fc under .fcwrap (timeline-scope + --range-fc hoisted to .fcwrap)'),
 'A2_novt_nochain': dict(chain='none', variants=12, anims=True, vt=False, bigmap=False, note='carriers only, no view-timeline, no chain: pure inherited-font-change restyle + layout floor'),
 'A3_vt_nochain':dict(chain='none',   variants=12, anims=True,  vt=True,  bigmap=False, note='carriers with view-timeline, no chain: + timeline subject bookkeeping'),
 'A4_noanim':    dict(chain='nested', variants=12, anims=False, vt=True,  bigmap=False, note='page topology but chunk rules without animation-*: isolates the 48 x 192 var() decode decls'),
 'A5_1variant':  dict(chain='nested', variants=1,  anims=True,  vt=True,  bigmap=False, note='page topology with ONE layer variant (no 12x @container rule matching)'),
 'A6_bigmap':    dict(chain='nested', variants=12, anims=True,  vt=True,  bigmap=True,  note='page topology + 4,000 inherited registered numbers declared on the ancestor'),
}
import sys
ARMS = {k:v for k,v in ARMS_ALL.items() if (len(sys.argv)<2 or k in sys.argv[1].split(','))}
OUT = OUT if len(sys.argv)<3 else f'{W}/R7T/fix/{sys.argv[2]}'; os.makedirs(OUT, exist_ok=True)
meta = {}
for name, a in ARMS.items():
    sc = scroller_html if a['vt'] else re.sub(r' style="view-timeline:--shared-fc-t\d+ inline"', '', scroller_html)
    if a['chain']=='nested': body = f'<div class="shared-fc">{sc}{chain_open}{chain_close}</div>'
    elif a['chain']=='ingate': body = f'<div class="shared-fc">{sc}{chain_in_gate}</div>'
    elif a['chain']=='sibling': body = f'<div class="fcwrap"><div class="shared-fc">{sc}</div>{chain_open}{chain_close}</div>'
    else: body = f'<div class="shared-fc">{sc}</div><div class="probe"></div>'
    sib = a['chain']=='sibling'
    rules = ''.join(fontfaces) + ''.join(props) + (bigmap_props if a['bigmap'] else '') + kf + static_rules + inputs + (core_ep + inputs_ep if a.get('epoch') else core)
    rules += f'.shared-fc{{{base_fc[0]}}}'
    rules += stage_rules(a['variants'], with_scope=not sib, with_range=not sib)
    if sib: rules += f'.fcwrap{{{scope_decl};{range_rule}}}'
    if a['chain']!='none': rules += chunk_rules(a['variants'], a['anims'])
    if a['bigmap']: rules += bigmap_rule
    open(f'{OUT}/{name}.css','w').write(rules)
    doc = f'<!doctype html><html class="go-0"><head><meta charset="utf-8"><link rel="stylesheet" href="{name}.css"></head><body><div class="core{" bigmap" if a["bigmap"] else ""}">{body}</div></body></html>'
    open(f'{OUT}/{name}.html','w').write(doc)
    meta[name] = dict(file=f'{name}.html', note=a['note'], css_bytes=len(rules), html_bytes=len(doc),
                      verify=[{'selector':'.probe','props':['--hidden-000','--hidden-001','--hidden-1155','--hidden-3071']}] if a['chain']!='none' else [{'selector':'.shared-fc','props':['--fq-fc-000','--fq-fc-767','--range-fc']}])
json.dump(meta, open(f'{OUT}/variants.json','w'), indent=1)
for k,v in meta.items(): print(f"{k:18s} css {v['css_bytes']/1e6:5.1f} MB html {v['html_bytes']/1e6:4.1f} MB  {v['note']}")
