#!/usr/bin/env python3
"""Refine the winning consumer size before choosing the native candidate."""
import json
import os
from pathlib import Path
import statistics
from unittest.mock import patch
from benchmark_audit_followups import OUT,ROOT,save,snapshot

def main():
    import probe_browser_gpt2_dense_stage_locality as dense
    import build_hybrid_twelve_block as hybrid
    snapshot('dense-refinement',[Path(__file__),Path(dense.__file__),Path(hybrid.__file__)])
    dest=OUT/'dense-refinement';fixtures={};original=hybrid.matvec
    for stage in ('qkv','mlp'):
        for chunk in (32,64,128):
            def matvec(*args,**kwargs):
                args=list(args);args[7]=chunk
                return original(*args,**kwargs)
            directory=dest/'fixtures'/f'chunk{chunk}-{stage}'
            with patch.object(hybrid,'matvec',matvec):
                fixture=dense.compile_fixture(directory,'baseline',stage,[0,11])
            fixture['consumerChunk']=chunk
            fixtures[chunk,stage]=fixture
            save(directory/'fixture.json',fixture)
    rows=[]
    for pair in (0,1):
        for stage in ('qkv','mlp'):
            cases={}
            for chunk in ((128,64,32) if pair==0 else (32,64,128)):
                source=dest/'fixtures'/f'chunk{chunk}-{stage}';directory=dest/f'pair{pair}'/source.name
                directory.mkdir(parents=True,exist_ok=False)
                for name in ('index.html','component.css','fixture.json'):os.link(source/name,directory/name)
                cases[chunk]=dense.run_case(directory,fixtures[chunk,stage])
            for chunk,r in cases.items():
                differences=[dense.error(a['actual'],b['actual'])['maximum'] for a,b in zip(cases[128]['samples'],r['samples'])]
                rows.append({'pair':pair,'stage':stage,'chunk':chunk,
                    'passed':r['passed'] and cases[128]['passed'] and len(differences)==6 and all(d is not None and d<=1e-6 for d in differences),
                    'maxBaselineDifference':max(differences) if differences and all(d is not None for d in differences) else None,
                    'freshMs':statistics.median(s['milliseconds'] for s in r['samples'][1:4]) if len(r['samples'])>=4 else None,
                    'revisitMs':statistics.median(s['milliseconds'] for s in r['samples'][4:]) if len(r['samples'])==6 else None,
                    'exception':r.get('exception')})
            save(dest/'summary.json',rows)
    # Require improvements in both opposite orders and in both complete stages.
    eligible=[128]
    for chunk in (32,64):
        comparisons=[]
        for stage in ('qkv','mlp'):
            for pair in (0,1):
                a=next(r for r in rows if (r['chunk'],r['stage'],r['pair'])==(128,stage,pair))
                b=next(r for r in rows if (r['chunk'],r['stage'],r['pair'])==(chunk,stage,pair))
                comparisons.append(a['passed'] and b['passed'] and b['freshMs'] < a['freshMs']*.98 and b['revisitMs'] <= a['revisitMs']*1.02)
        if all(comparisons):eligible.append(chunk)
    chosen=min(eligible,key=lambda c:sum(r['freshMs'] or float('inf') for r in rows if r['chunk']==c))
    save(dest/'selection.json',{'chosenChunk':chosen,'eligible':eligible,'rule':'Exact outputs; >=2% fresh improvement over128 in both stages and orders; no >2% revisit regression. Then smallest sum of fresh medians.'})
    print(json.dumps({'chosenChunk':chosen,'rows':rows}),flush=True)

if __name__=='__main__':main()
