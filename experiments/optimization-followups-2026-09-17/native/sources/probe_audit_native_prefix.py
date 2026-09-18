#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Matched 32-slot native prefixes with post-timing retained-state checks."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch
import numpy as np
from benchmark_audit_followups import OUT,ROOT,save,snapshot,digest

DEST=OUT/'native'
VARIANTS=('baseline','small-chunks','static-readers','combined')

def compile_all():
    # Six head trials save the same 56 MB reference. Preserve every pathname
    # and byte while avoiding six physical copies on this nearly full disk.
    references=sorted((OUT/'head').glob('pair*/*/reference.json'))
    if references:
        source=references[0];sha=digest(source);shared=[]
        for path in references[1:]:
            if digest(path)==sha:
                temporary=path.with_suffix('.dedup.tmp')
                os.link(source,temporary);os.replace(temporary,path)
                shared.append(str(path.relative_to(ROOT)))
        save(OUT/'head/reference-deduplication.json',{'sha256':sha,'canonical':str(source.relative_to(ROOT)),
             'sameBytesHardlinked':shared,'logicalArtifactsPreserved':True})
    from probe_audit_consumer_refinement import main as refine
    refine()
    chunk=json.loads((OUT/'dense-refinement/selection.json').read_text())['chosenChunk']
    import browser_gpt2_runtime as runtime
    import browser_gpt2_reused_core as reused
    import build_hybrid_twelve_block as hybrid
    snapshot('native',[Path(__file__),Path(runtime.__file__),Path(reused.__file__),Path(hybrid.__file__),ROOT/'tools/benchmark_native_token_prefix.py'])
    original=hybrid.matvec;original_loop=reused.loop_parts
    for variant in VARIANTS:
        def matvec(*args,**kwargs):
            args=list(args)
            if variant in ('small-chunks','combined') and args[1] in ('qkv','fc','proj'):args[7]=chunk
            return original(*args,**kwargs)
        def loop(*args,**kwargs):
            source,output,css=original_loop(*args,**kwargs)
            if variant not in ('static-readers','combined'):return source,output,css
            width=args[0]
            rules=[]
            for bank in range(2):
                rules.append(f'.audit-reader-{bank}{{animation-name:'+','.join(f'loop-k-{bank}-{i}' for i in range(width+1))+
                    ';animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:'+
                    ','.join(f'--loop-t-{bank}-{i}' for i in range(width+1))+';}')
            css,count=re.subn(r'\.loop-reader\{[^{}]+\}', ''.join(rules),css)
            assert count==1
            css+='.audit-reader-1{'+ ';'.join(f'--lp-0-{i}:inherit' for i in range(width+1))+'}'
            source=source.replace('<div class="loop-reader">','<div class="loop-reader audit-reader-0"><div class="audit-reader-1">')+'</div>'
            return source,output,css
        directory=DEST/'fixtures'/variant
        directory.mkdir(parents=True,exist_ok=False)
        with patch.object(hybrid,'matvec',matvec),patch.object(reused,'loop_parts',loop):
            runtime.compile_runtime(directory,12,32,autostart=False,isolate_head=True,cache_layout='flat',
                cache_codec='font-vector',scoped_state=True,reuse_core=True,detached_output=True)
        save(directory/'audit-provenance.json',{'variant':variant,'currentSource':True,'comparisonToPreservedV1':False,
             'hashes':{n:digest(directory/n) for n in ('index.html','runtime.css','manifest.json')},
             'scopedCompilePatches':{'consumerChunk':chunk if variant in ('small-chunks','combined') else 512,
                                   'staticBankReaders':variant in ('static-readers','combined')}})
    source=(ROOT/'tools/benchmark_native_token_prefix.py').read_text()
    old='                atomic_json(output, report)\n                break'
    new='                from probe_audit_native_prefix import capture\n                report["numericalReadback"] = capture(cdp, report)\n                atomic_json(output, report)\n                break'
    assert source.count(old)==1
    source=source.replace(old,new)
    (DEST/'prefix_observer.py').write_text(source)

def capture(cdp,report):
    from probe_native_value_latch import props
    from profile_hybrid_twelve_block import query
    from decode_css_cache_diagnostic import decode_cache
    head=query(cdp,'.head-input-bank');before=props(cdp,head)
    count=report['observedTokenTarget']
    result={'headEpochBefore':float(before['--head-input-epoch']),
            'hidden':[float(before[f'--h{i}']) for i in range(768)],'caches':[]}
    after=props(cdp,head)
    result['headEpochAfter']=float(after['--head-input-epoch'])
    result['headStable']=result['headEpochBefore']==result['headEpochAfter']==count and result['hidden']==[float(after[f'--h{i}']) for i in range(768)]
    # Prefix slots remain retained while the next token writes a new slot.
    # Check the head snapshot before these more expensive cache reads.
    for layer in range(12):
        values=props(cdp,query(cdp,f'.fvs-bank[data-layer="{layer}"]'))
        for slot in range(count):
            result['caches'].append({'layer':layer,'position':slot,
                'values':decode_cache(values,slot,'font-vector',active=False)})
    return result

def verify(directory):
    from analyze_full_gpt2 import MODEL_PATH,SafeTensors
    from browser_gpt2_core import reference_sequence
    import build_gpt2_block_css as b
    from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS,SCORE_GAIN,WEIGHT_SCALE,R
    from profile_hybrid_twelve_block import error
    report=json.loads((directory/'prefix-results.json').read_text())
    if not report.get('completedObservedPrefix') or 'numericalReadback' not in report:
        save(directory/'numerical-results.json',{'passed':False,'reason':'Prefix did not complete with retained readback'})
        return
    outputs=[int(t) for t in report['retainedTokens']]
    tokens=[15496]+outputs[:-1]
    reference=reference_sequence(tokens,12)
    t=SafeTensors(MODEL_PATH)
    gamma=np.asarray(t.tensor('ln_f.weight'),dtype=np.float64);beta=np.asarray(t.tensor('ln_f.bias'),dtype=np.float64)
    weights=np.asarray(t.tensor('wte.weight'),dtype=np.float64)
    qweights=np.rint(weights/WEIGHT_SCALE)*WEIGHT_SCALE
    hidden=np.stack([b.layer_norm(np.asarray(x),gamma,beta) for x in reference['outputs']])
    rounded=np.rint(hidden/R*AXIS_STEPS)/AXIS_STEPS*R
    expected=np.rint(rounded@qweights.T*SCORE_GAIN*256).argmax(1).tolist()
    read=report['numericalReadback']
    actual=np.asarray(read['hidden'])
    winner=int(np.rint((np.rint(actual/R*AXIS_STEPS)/AXIS_STEPS*R)@qweights.T*SCORE_GAIN*256).argmax())
    errors=[{'layer':c['layer'],'position':c['position'],**error(c['values'],reference['layers'][c['layer']]['qkv'][c['position']][768:])} for c in read['caches']]
    hidden_error=error(actual,hidden[-1])
    floating=reference_sequence(tokens,12,quantized=False)
    float_hidden=np.stack([b.layer_norm(np.asarray(x),gamma,beta) for x in floating['outputs']])
    float_winners=(float_hidden@weights.T).argmax(1).tolist()
    passed=read['headStable'] and outputs==expected and winner==outputs[-1] and hidden_error['rmse']<.05 and len(errors)==24 and all(e['rmse']<.05 for e in errors)
    save(directory/'numerical-results.json',{'passed':passed,'tokens':outputs,'q9Q16Winners':expected,'floatWinners':float_winners,
        'headStable':read['headStable'],'actualHeadWinner':winner,'hiddenError':hidden_error,'cacheErrors':errors,
        'scope':'Two-token native prefix; all retained K/V at both positions and final retained head input. No residual snapshot during next-token execution.'})
    report['runnerBrowserValidated']=True
    report['numericalVerificationPerformed']=True
    report['numericalVerificationPassed']=passed
    report['verificationScope']='Independent token-reference agreement, both positions of all 12 K/V banks, and the retained final head input after the timed two-token prefix.'
    save(directory/'prefix-results.json',report)

def run(variant,pair):
    directory=DEST/'runs'/f'pair{pair}'/variant
    command=[sys.executable,str(DEST/'prefix_observer.py'),'--directory',str(DEST/'fixtures'/variant),'--output',str(directory),
             '--tokens','2','--wall-seconds','360','--heap-growth-percent','10']
    result=subprocess.run(command)
    verify(directory)
    print(json.dumps({'variant':variant,'pair':pair,'exitStatus':result.returncode,
         'numerical':json.loads((directory/'numerical-results.json').read_text())['passed']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('compile','run'));p.add_argument('--variant',choices=VARIANTS);p.add_argument('--pair',type=int,default=0)
    a=p.parse_args()
    if a.phase=='compile':compile_all()
    else:run(a.variant,a.pair)
