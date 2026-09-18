#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Sticky native receipt witnesses: complete coverage, not exclusive costs."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote,urlparse
from benchmark_audit_followups import OUT,ROOT,save,digest

DEST=OUT/'boundaries'
GATES={
 'input':('core-reset core-valid reused-input','loopreceipt','--loop-ready'),
 'qkv':('shared-qkv-gate','shared-qkv-receipt','--gate-qkv'),
 'context':('cache-bridge-gate','cache-bridge-receipt','--bridge-ready'),
 'attentionProjection':('shared-attn-gate','shared-attn-receipt','--gate-attn'),
 'fc':('shared-fc-gate','shared-fc-receipt','--gate-fc'),
 'projection':('shared-proj-gate','shared-proj-receipt','--gate-proj'),
}

def prepare():
    source=OUT/'native/fixtures/baseline'
    dest=DEST/'fixture';dest.mkdir(parents=True,exist_ok=False)
    html=(source/'index.html').read_text();css=(source/'runtime.css').read_text()
    def asset(match):
        url=match[1]
        if urlparse(url).scheme:return match[0]
        return 'url("'+os.path.relpath((source/unquote(url)).resolve(),dest)+'")'
    css=re.sub(r'url\("([^\"]+)"\)',asset,css)
    css+='@keyframes audit-boundary-pulse{from{opacity:.99}to{opacity:1}}.audit-boundaries{position:fixed;left:0;top:-100px;width:1px;height:1px}'
    for stage,(gate,container,flag) in GATES.items():
        opening='<div class="'+gate+'">'
        assert html.count(opening)==1,(stage,html.count(opening))
        signals=[]
        for step in range(1,25):
            name=f'audit-mark-{stage}-{step}'
            signals.append(f'<g id="{name}" class="audit-boundary"><set attributeName="class" to="audit-boundary done" begin="{name}.animationend+0.001s" fill="freeze"/></g>')
            css+=f'@container loopcontrol style(--pass:{step}){{@container {container} style({flag}:1){{#{name}{{animation:audit-boundary-pulse 1ms both}}}}}}'
        html=html.replace(opening,opening+'<svg class="audit-boundaries">'+''.join(signals)+'</svg>')
    (dest/'index.html').write_text(html);(dest/'runtime.css').write_text(css)
    shutil.copy2(source/'manifest.json',dest/'manifest.json')
    observer=(OUT/'native/prefix_observer.py').read_text()
    observer=observer.replace('        previous = 0\n','        previous = 0\n        boundary_seen = set()\n        report["boundaryObservations"] = []\n')
    observer=observer.replace('        while True:\n','        while True:\n            from probe_audit_native_boundaries import collect\n            collect(cdp, report, boundary_seen, started)\n',1)
    observer=observer.replace('                from probe_audit_native_prefix import capture','                collect(cdp, report, boundary_seen, started)\n                from probe_audit_native_prefix import capture')
    (DEST/'observer.py').write_text(observer)
    save(DEST/'manifest.json',{'scope':'Sticky CSS-animation/SMIL witnesses inside existing native receipt gates; no token, activation, or scheduling writes',
        'perturbedDiagnostic':True,'exclusiveOperatorCosts':False,'stages':list(GATES),'passes':24,
        'expectedMarkers':144,'hashes':{n:digest(dest/n) for n in ('index.html','runtime.css','manifest.json')}})

def collect(cdp,report,seen,started):
    import time
    nodes=cdp.command('DOM.querySelectorAll',{'nodeId':cdp.root_node,'selector':'.audit-boundary.done'})['nodeIds']
    elapsed=(time.monotonic()-started)*1000
    for node in nodes:
        if node in seen:continue
        attrs=cdp.command('DOM.getAttributes',{'nodeId':node})['attributes']
        name=dict(zip(attrs[::2],attrs[1::2]))['id']
        stage,step=name.removeprefix('audit-mark-').rsplit('-',1)
        report['boundaryObservations'].append({'stage':stage,'pass':int(step),'firstObservedMs':elapsed})
        seen.add(node)

def main():
    prepare()
    command=[sys.executable,str(DEST/'observer.py'),'--directory',str(DEST/'fixture'),'--output',str(DEST/'run'),
        '--tokens','2','--wall-seconds','420','--heap-growth-percent','10']
    result=subprocess.run(command)
    r=json.loads((DEST/'run/prefix-results.json').read_text())
    rows=[]
    for step in range(1,25):
        events={x['stage']:x['firstObservedMs'] for x in r.get('boundaryObservations',[]) if x['pass']==step}
        rows.append({'pass':step,'stageCount':len(events),'complete':set(events)==set(GATES),'firstObservedMs':events})
    save(DEST/'summary.json',{'workerStatus':result.returncode,'prefixComplete':r['completedObservedPrefix'],
        'completePasses':sum(x['complete'] for x in rows),'expectedPasses':24,'rows':rows,
        'exclusiveOperatorCosts':False,'limitations':['Sticky marks retain evidence even when the observer misses a boundary.','Times are first observations after CDP returns, not exclusive execution durations.','Additional animations can perturb scheduling; excluded from speed comparison.']})

if __name__=='__main__':main()
