#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Two-layer persistent V glyphs with native anchor-size delivery."""
import json
from pathlib import Path
import re
from unittest.mock import patch
import browser_gpt2_font_vector_cache as base
import browser_gpt2_scaling_variants as variants
import investigate_browser_gpt2_scaling as scaling
from benchmark_audit_followups import OUT, ROOT, snapshot, save

ORIGINAL=base.attention

def persistent(*args,**kwargs):
    kwargs['value_layout']='widths'
    html,css,metadata=ORIGINAL(*args,**kwargs)
    capacity=metadata['kvSlots'];layers=args[1]
    value=metadata['operators']['value']
    unit=base.VALUE_SIZE/base.UNITS_PER_EM
    base_pixels=value['base']*unit
    for layer in range(layers):
        glyphs=[];aliases=[]
        for head in range(12):
            for slot in range(capacity):
                aliases.append(f'--pv-{layer}-{head}-{slot}:var(--fc-v-{slot}-{head})')
                selector=f'pv-{layer}-{head}-{slot}'
                css+=f'.{selector}{{font:{base.VALUE_SIZE}px FvsValue;font-variation-settings:var(--{selector}),"P000" 1;font-kerning:none;font-style:normal;position:fixed;left:0;top:-1000px;width:max-content;height:1px;visibility:hidden}}'
                for coordinate in range(64):
                    glyphs.append(f'<i class="{selector}" style="anchor-name:--{selector}-{coordinate}">&#x{base.CODEPOINT_BASE+coordinate:X};</i>')
        css+=f'.fvs-bank-{layer}'+'{'+ ';'.join(aliases)+'}'
        opening=f'<div class="fvs-bank fvs-bank-{layer}" data-layer="{layer}">'
        assert html.count(opening)==1
        html=html.replace(opening,opening+''.join(glyphs))
    index=0
    def row(match):
        nonlocal index,css
        head,coordinate=divmod(index,64)
        for layer in range(layers):
            terms=[f'(anchor-size(--pv-{layer}-{head}-{slot}-{coordinate} width, 0px) - {base_pixels:.12g}px) * var(--fe-{head}-{slot}) * var(--fr-vs-{slot}-{head}) / var(--fd-{head})'
                   for slot in range(capacity)]
            expression=' + '.join(terms)
            css+=f'@container runtime style(--layer:{layer}){{.persistent-row-{index}{{width:calc(262144px + ({expression}) * {128/(value["coefficient"]*unit):.12g})}}}}'
        result=f'<span class="metric fvs-value-row persistent-row-{index}" style="view-timeline:{match[1]} inline"></span>'
        index+=1
        return result
    html,count=re.subn(r'<span class="metric fvs-value-row" style="width:[^;]+;view-timeline:([^ ]+) inline">.*?</span>',row,html)
    assert count==768,count
    # Existing harness waits on a value-font witness. This is an additional
    # glyph only, outside the weighted result and the timing updates.
    html+='<i class="fvs-v-0-0" style="position:fixed;top:-1000px">&#xE000;</i>'
    metadata['persistentValueGlyphs']=layers*capacity*768
    metadata['delivery']='CSS anchor-size into existing context metrics'
    return html,css,metadata

def main():
    snapshot('persistent-v',[Path(__file__),Path(base.__file__),Path(scaling.__file__)])
    scaling.OUT=OUT/'persistent-v'
    variants.VARIANTS['persistent']=variants.Variant(widths=True)
    original_replacement=scaling.replacement
    def replacement(name):return persistent if name=='persistent' else original_replacement(name)
    rows=[]
    with patch.object(scaling,'replacement',replacement):
        for repeat,order in enumerate((('baseline','widths','persistent'),('persistent','widths','baseline'))):
            for name in order:
                observed=[];metric_calls=0;nodes=None
                original_metrics=scaling.metrics
                def metrics(cdp):
                    nonlocal metric_calls,nodes
                    result=original_metrics(cdp)
                    # The second metrics call is after the timer and after its
                    # renderer snapshot. Read persistent producers separately.
                    if metric_calls%2==1 and metric_calls<28:
                        if nodes is None:
                            nodes=[scaling.query(cdp,f'.pv-{layer}-0-{slot}[style="anchor-name:--pv-{layer}-0-{slot}-{coordinate}"]')
                                for layer in range(2) for slot in range(4) for coordinate in (0,17,63)]
                        widths=[]
                        for node in nodes:
                            box=cdp.command('DOM.getBoxModel',{'nodeId':node})['model']['content']
                            widths.append(box[2]-box[0])
                        observed.append(widths)
                    metric_calls+=1
                    return result
                with patch.object(scaling,'metrics',metrics if name=='persistent' else original_metrics):
                    scaling.run_case(name,4,2,4,repeat,query_updates=3)
                path=scaling.OUT/'runs'/f'{name}-c4-l2-p4-r{repeat}'/'results.json'
                r=json.loads(path.read_text())
                if name=='persistent':
                    check=len(observed)==14 and all(widths==observed[7] for widths in observed[8:])
                    r['persistentWidthWitness']={'head':0,'coordinates':[0,17,63],'allLayersAndSlots':True,
                        'outsideTiming':True,'widths':observed,'unchangedAcrossQueryAndLayerRevisits':check}
                    r['passed']=r.get('passed',False) and check
                    save(path,r)
                rows.append({k:v for k,v in r.items() if k not in ('failureDiagnostics','sourceHashes')})
                save(scaling.OUT/'summary.json',rows)
                # A failed capability gate is retained, not timed repeatedly.
                if name=='persistent' and not r.get('passed',False):
                    print('Persistent V failed capability/accuracy gate; stopping its repeated timing.',flush=True)
                    return

if __name__=='__main__':main()
