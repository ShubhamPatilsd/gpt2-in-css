#!/usr/bin/env python3
"""Verify the frozen historical best-known static bundles and all their assets."""
import argparse
import hashlib
import json
from pathlib import Path
from launch_browser_gpt2 import ROOT, static_assets

RECIPE=ROOT/'experiments/optimization-followups-2026-09-17/validated-bundles.json'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def freeze():
    if RECIPE.exists():raise FileExistsError(RECIPE)
    records=[]
    for capacity,name in ((8,'demo-font-vector-twelve'),(32,'demo-font-vector-context32')):
        directory=ROOT/'experiments/browser-gpt2'/name
        summary=json.loads((directory/'scaling-summary.json').read_text())
        assert summary['complete']
        paths=static_assets(directory)|{directory/n for n in ('manifest.json','scaling-summary.json','numerical-results.json','pipeline-results.json','verification-vectors.json')}
        records.append({'capacity':capacity,'directory':str(directory.relative_to(ROOT)),
            'historicalCompleteValidation':True,'currentSourceRebuildEquivalent':False,
            'fontVectorOperatorVersion':'v1','heapGrowthPercent':10,
            'files':{str(p.relative_to(ROOT)):{'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(paths)}})
    RECIPE.write_text(json.dumps({'schema':1,'bundles':records},indent=2)+'\n')

def verify(capacity):
    record=next(b for b in json.loads(RECIPE.read_text())['bundles'] if b['capacity']==capacity)
    for name,expected in record['files'].items():
        path=ROOT/name
        if not path.is_file() or path.stat().st_size!=expected['bytes'] or digest(path)!=expected['sha256']:
            raise ValueError(f'Validated bundle asset changed: {name}')
    actual={str(p.relative_to(ROOT)) for p in static_assets(ROOT/record['directory'])}
    assert actual<=record['files'].keys()
    print(json.dumps({'passed':True,'capacity':capacity,'verifiedFiles':len(record['files']),
        'directory':record['directory'],'scope':'Frozen static bytes and historical validation evidence; not a new generation test'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capacity',type=int,choices=(8,32),default=8);p.add_argument('--freeze',action='store_true')
    args=p.parse_args()
    if args.freeze:freeze()
    verify(args.capacity)
