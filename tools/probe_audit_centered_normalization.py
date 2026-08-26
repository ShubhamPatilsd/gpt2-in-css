#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Centered normalization with a fixed sigma<1/8 legacy fallback."""
import argparse
import json
import os
from pathlib import Path
import re
import statistics
from unittest.mock import patch
import numpy as np
import analyze_preserved_weight_normalization as prior
from benchmark_audit_followups import OUT, ROOT, save, snapshot

DEST = OUT/'normalization'

def offline():
    snapshot('normalization',[Path(__file__),Path(prior.__file__)])
    # Reuse the previously audited algebra/rounding implementation exactly.
    source=(ROOT/'experiments/repo-optimization-audit-2026-09-17/screen_centered_normalization.py').read_text()
    source=source.replace('out = Path(__file__).resolve().parent','out = DEST')
    source=source.replace('candidate = raw / sigma + constant',
        'candidate = np.where(sigma < 0.125, baseline, raw / sigma + constant)')
    source=source.replace('variant=c["variant"], coordinateMode=coordinate, advanceMode=advance,',
        'variant=c["variant"], sigma=float(sigma[i,0]), legacyFallback=bool(sigma[i,0] < .125), coordinateMode=coordinate, advanceMode=advance,')
    source=source.replace('formula="Q @ (gamma * (x - mean)) / sigma + Q @ beta + bias",',
        'formula="legacy if sigma < 1/8, otherwise Q @ (gamma * (x - mean)) / sigma + Q @ beta + bias",')
    path=DEST/'offline-screen.py'
    path.write_text(source)
    scope={'__file__':str(path),'__name__':'audit_offline','DEST':DEST}
    exec(compile(source,str(path),'exec'),scope)
    scope['main']()

def browser_run():
    import probe_browser_gpt2_dense_stage_locality as dense
    import build_gpt2_block_css as block
    import build_hybrid_twelve_block as hybrid
    from browser_gpt2_core import layer_matrices
    original_norm=block.norm_declarations
    original_matvec=hybrid.matvec
    tensors=prior.SafeTensors(prior.MODEL_PATH)
    data={layer:layer_matrices(tensors,layer)[0] for layer in (0,11)}
    def norm(source,target,gamma,beta,mean,variance):
        declarations=original_norm(source,target,gamma,beta,mean,variance)
        sigma=f'--audit-sigma-{target}'
        if variant=='sigma-hoist':
            expression=f'sqrt(var(--{variance}) + {block.EPSILON})'
            return [declaration.replace(expression,f'var({sigma})') for declaration in declarations]+[f'{sigma}:{expression}']
        safe=f'--audit-safe-{target}'
        declarations[2:2]=[f'{sigma}:sqrt(calc(var(--{variance}) + {block.EPSILON}))',
            f'{safe}:clamp(0,sign(calc(var({sigma}) - .125)),1)']
        for i in range(768):
            old=declarations[4+i].split(':',1)[1]
            z=f'calc((var(--{source}-{i:03d}) - var(--{mean})) * {block.css_number(gamma[i])})'
            declarations[4+i]=f'--{target}-{i:03d}:if(style({safe}:1):{z};else:{old})'
        return declarations
    def matvec(*args,**kwargs):
        html,css=original_matvec(*args,**kwargs)
        layer,kind,q,bias=args[:4]
        if kind in ('qkv','fc'):
            norm_index=1 if kind=='qkv' else 2
            beta=data[layer][f'ln{norm_index}_beta']
            constant=q.reconstructed@beta+bias
            flag=f'--audit-safe-n{norm_index}'
            sigma=f'--audit-sigma-n{norm_index}'
            css+=hybrid.regs([flag,sigma])
            if variant=='sigma-hoist':return html,css
            # Match by coordinate; repeated bias constants must not alias.
            stem='qkv' if kind=='qkv' else 'hidden'
            def replace_bias(match):
                index=int(match[2])
                assert match[3]==hybrid.num(bias[index])
                return match[1]+f' + (if(style({flag}:1):{hybrid.num(constant[index])};else:{match[3]})))'
            css,count=re.subn(r'(--'+stem+r'-(\d+):[^;{}]*?) \+ \(([+\-0-9.eE]+)\)\)',replace_bias,css)
            assert count==len(bias),(kind,count)
            css=css.replace(f'* var(--range-{kind}) +',f'* var(--range-{kind}) / if(style({flag}:1):var({sigma});else:1) +')
        return html,css
    fixtures={}
    for stage in ('qkv','mlp'):
        for variant in ('baseline','sigma-hoist','centered-safe'):
            directory=DEST/'fixtures'/f'{variant}-{stage}'
            if variant=='baseline':
                fixture=dense.compile_fixture(directory,'baseline',stage,[0,11])
            else:
                with patch.object(block,'norm_declarations',norm),patch.object(hybrid,'matvec',matvec):
                    fixture=dense.compile_fixture(directory,'baseline',stage,[0,11])
            # Keep baseline key to disable the exact-bitwise variant gate; apply
            # the predeclared numerical policy to the readbacks below instead.
            fixture['auditVariant']=variant
            save(directory/'fixture.json',fixture)
            fixtures[variant,stage]=fixture
    rows=[]
    for pair in range(2):
        for stage in ('qkv','mlp'):
            cases={}
            for variant in (('baseline','sigma-hoist','centered-safe') if pair==0 else ('centered-safe','sigma-hoist','baseline')):
                source=DEST/'fixtures'/f'{variant}-{stage}'
                dest=DEST/f'pair{pair}'/source.name
                dest.mkdir(parents=True,exist_ok=False)
                for name in ('index.html','component.css','fixture.json'):os.link(source/name,dest/name)
                cases[variant]=dense.run_case(dest,fixtures[variant,stage])
            for candidate in ('sigma-hoist','centered-safe'):
                a,b=cases['baseline'],cases[candidate]
                checks=[]
                for x,y in zip(a['samples'],b['samples']):
                    difference=dense.error(x['actual'],y['actual'])['maximum']
                    passed=(difference is not None and difference<=1e-6) if candidate=='sigma-hoist' else all(y['error'][k] is not None and x['error'][k] is not None and y['error'][k] <= 1.1*x['error'][k]+1e-5 for k in ('rmse','maximum'))
                    checks.append({'epoch':x['epoch'],'baseline':x['error'],'candidate':y['error'],'baselineMaximumDifference':difference,'passed':passed})
                row={'pair':pair,'stage':stage,'candidate':candidate,'checks':checks,
                    'passed':a['passed'] and b['passed'] and len(checks)==6 and all(c['passed'] for c in checks),
                    'timing':{variant:{'freshMs':statistics.median(s['milliseconds'] for s in r['samples'][1:4]) if len(r['samples'])>=4 else None,
                                      'revisitMs':statistics.median(s['milliseconds'] for s in r['samples'][4:]) if len(r['samples'])==6 else None,
                                      'exception':r.get('exception')} for variant,r in cases.items()}}
                rows.append(row)
                print(json.dumps(row),flush=True)
            save(DEST/'browser-summary.json',rows)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('offline','browser'))
    args=p.parse_args()
    (offline if args.phase=='offline' else browser_run)()
