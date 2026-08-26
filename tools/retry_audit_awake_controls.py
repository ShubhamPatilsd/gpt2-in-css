#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Replace display/sleep-interrupted comparisons, preserving original evidence."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
from unittest.mock import patch
from benchmark_audit_followups import OUT,ROOT,save,digest,snapshot

def main():
    import benchmark_selective_loop as loop
    import probe_browser_gpt2_head_locality as head
    snapshot('awake-retries',[Path(__file__),Path(loop.__file__),Path(head.__file__)])
    fixtures={(f['variant'],f['steps']):f for f in json.loads((OUT/'loop/manifest.json').read_text())}
    rows=[]
    for pair,order in enumerate((('baseline','static-readers','local-scope','static-local'),('static-local','local-scope','static-readers','baseline'))):
        cases={}
        for variant in order:
            started=datetime.now(timezone.utc).isoformat()
            r=loop.run_case(fixtures[variant,24],OUT/'awake-retries/loop'/f'pair{pair}'/variant)
            r['startedAtUTC']=started;r['endedAtUTC']=datetime.now(timezone.utc).isoformat()
            cases[variant]=r
            rows.append({'pair':pair,**{k:v for k,v in r.items() if k!='actual'}})
        comparisons={v:loop.compare(cases['baseline'],r) if cases['baseline']['passed'] and r['passed'] else {'passed':False} for v,r in cases.items()}
        save(OUT/'awake-retries/loop'/f'pair{pair}/comparisons.json',comparisons)
        save(OUT/'awake-retries/loop/summary.json',rows)
    original=head.compile_fixture
    canonical=OUT/'head/pair0/baseline/reference.json'
    reference_hash=digest(canonical)
    selected=(0,1,5,10,15,20,30,37)
    def compile_fixture(directory,mode):
        reference,metadata=original(directory,mode)
        target=directory/'reference.json'
        assert digest(target)==reference_hash
        target.unlink();os.link(canonical,target)
        reference={**reference,'hidden':[reference['hidden'][i] for i in selected],
            'fixtures':[reference['fixtures'][i] for i in selected],
            'sourceStates':[reference['sourceStates'][i] for i in selected]}
        metadata['selectedOriginalIndices']=selected
        metadata['retryScope']='Eight fixed inputs from the previously complete38-input sweep, full50257-row scorer, all three modes in reverse order'
        return reference,metadata
    rows=[]
    with patch.object(head,'compile_fixture',compile_fixture):
        for mode in ('private-inputs','settings','baseline'):
            started=datetime.now(timezone.utc).isoformat()
            directory=OUT/'awake-retries/head'/mode
            r=head.run_case(directory,mode,2,60)
            r['startedAtUTC']=started;r['endedAtUTC']=datetime.now(timezone.utc).isoformat()
            save(directory/'results.json',r)
            rows.append({k:v for k,v in r.items() if k!='memorySamples'})
            save(OUT/'awake-retries/head/summary.json',rows)
            print(json.dumps({'mode':mode,'passed':r['passed'],'ms':r.get('medianMilliseconds'),'exception':r.get('exception')}),flush=True)

if __name__=='__main__':main()
