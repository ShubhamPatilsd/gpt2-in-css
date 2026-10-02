"""R7T head fixture: the real 50,257-row coarse head (197 block-flow groups, 6 ProdQ16 faces) with its FVS changed per mutation.
H0 = page rows (inline --base/--tie, per-row unique declarations); H1 = declaration-identical rows (no inline style, literal rule)
-> cost proxy for R3H option 2 (values differ, cost representative)."""
import re, os, random
W='/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19'; ROOT='/Users/shubhampatil/Documents/programming/gpt2-css'
html=open(f'{W}/bundles/combined8/index.html',encoding='utf-8').read()
i=html.find('<section class="head-group" style="anchor-name:--head-group-0">'); j=html.rfind('</section>')+len('</section>')
sections=html[i:j]; assert sections.count('<i class="head-row"')==50257 and sections.count('<section')==197
OUT=f'{W}/R7T/fix/pages-head'; os.makedirs(OUT,exist_ok=True)
ff=''.join(f'@font-face{{font-family:ProdQ16{p}{s};src:url("file://{ROOT}/experiments/gpt2-global-q16-layernorm-integer-full/score-{n}-{s}.woff2") format("woff2"){";size-adjust:25600%" if p=="H" else ""}}}' for s in range(3) for p,n in (("H","high"),("R","residual")))
props='@property --head-fvs{syntax:"*";inherits:true;initial-value:"X000" 0}@property --head-input-epoch{syntax:"<number>";inherits:true;initial-value:1}'
base='.full-head{anchor-scope:all;position:relative;width:1px;height:1px;font:62.5px ProdQ16H0,ProdQ16R0,ProdQ16H1,ProdQ16R1,ProdQ16H2,ProdQ16R2;font-variation-settings:var(--head-fvs);font-kerning:none;font-synthesis:none;line-height:1}' \
     '.head-group{position:fixed;left:0;top:-80000px;display:block;width:max-content;height:calc(var(--head-input-epoch)*1px)}'
row_page='.head-row{display:block;justify-self:start;height:1px;white-space:pre;overflow:clip;min-width:0;font-style:normal;width:calc-size(max-content,round(nearest,(size - var(--base)*1px)*120.777609693 + 211968px,4px))}'
row_ident='.head-row{display:block;justify-self:start;height:1px;white-space:pre;overflow:clip;min-width:0;font-style:normal;width:calc-size(max-content,round(nearest,(size - 3400px)*120.777609693 + 211968px,4px))}'
random.seed(11)
tags=[f'{c}{n:03d}'[:4] for c in 'XYZ' for n in range(256)]
tags=[f'X{n:03X}' for n in range(768)]  # X000..X2FF as in the head fonts
inputs=''.join('html.go-%d{--head-fvs:%s}'%(k, ','.join(f'"{t}" {random.randint(-16384,16384)}' for t in tags)) for k in range(8))
sec_ident=re.sub(r' style="--base:[0-9.]+;--tie:\d+"','',sections)
meta={}
for name,row,sec in (('H0_page_rows',row_page,sections),('H1_identical_rows',row_ident,sec_ident)):
    css=ff+props+base+row+inputs
    open(f'{OUT}/{name}.css','w').write(css)
    open(f'{OUT}/{name}.html','w').write(f'<!doctype html><html class="go-0"><head><meta charset="utf-8"><link rel="stylesheet" href="{name}.css"></head><body><div class="full-head">{sec}</div></body></html>')
    meta[name]=dict(file=f'{name}.html',note=name,verify=[{'selector':'.head-row','props':['width']}])
import json; json.dump(meta,open(f'{OUT}/variants.json','w'),indent=1)
for n in meta: print(n, os.path.getsize(f'{OUT}/{n}.html')/1e6,'MB html')
