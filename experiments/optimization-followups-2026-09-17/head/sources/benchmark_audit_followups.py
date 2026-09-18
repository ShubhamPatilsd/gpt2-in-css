#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Bounded audit follow-ups. Run under run_unconventional_isolated.py."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/optimization-followups-2026-09-17"

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def snapshot(group, paths):
    directory = OUT/group/"sources"
    directory.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for path in [Path(__file__), *paths]:
        target = directory/path.name
        if target.exists():
            assert target.read_bytes() == path.read_bytes(), target
        else:
            shutil.copy2(path, target)
        hashes[str(path.relative_to(ROOT))] = digest(path)
    save(OUT/group/"source-hashes.json", hashes)

def dense_run():
    import probe_browser_gpt2_dense_stage_locality as dense
    import build_hybrid_twelve_block as hybrid
    snapshot("dense", [ROOT/"tools"/n for n in (
        "probe_browser_gpt2_dense_stage_locality.py", "browser_gpt2_dense_locality.py",
        "build_hybrid_twelve_block.py", "browser_gpt2_reused_core.py")])
    groups = {"mlp": ["baseline", "proj-settings", "chunk128", "chunk256"],
              "qkv": ["baseline", "chunk128", "chunk256"]}
    fixtures = {}
    original = hybrid.matvec
    for stage, variants in groups.items():
        for variant in variants:
            chunk = int(variant[5:]) if variant.startswith("chunk") else 512
            def matvec(*args, **kwargs):
                args = list(args)
                args[7] = chunk
                return original(*args, **kwargs)
            directory = OUT/"dense"/"fixtures"/f"{variant}-{stage}"
            with patch.object(hybrid, "matvec", matvec):
                fixture = dense.compile_fixture(directory, "proj-settings" if variant == "proj-settings" else "baseline", stage, [0, 11])
            fixture["variant"] = variant
            fixture["chunkSize"] = chunk
            save(directory/"fixture.json", fixture)
            fixtures[variant, stage] = fixture
            print(json.dumps({"compiled": directory.name}), flush=True)
    rows = []
    for pair in range(2):
        for stage, variants in groups.items():
            cases = {}
            for variant in (variants if pair == 0 else list(reversed(variants))):
                source = OUT/"dense"/"fixtures"/f"{variant}-{stage}"
                dest = OUT/"dense"/f"pair{pair}"/source.name
                dest.mkdir(parents=True, exist_ok=False)
                for name in ("index.html", "component.css", "fixture.json"):
                    os.link(source/name, dest/name)
                result = dense.run_case(dest, fixtures[variant, stage])
                cases[variant] = result
            baseline = cases["baseline"]
            for variant, result in cases.items():
                differences = [dense.error(a["actual"], b["actual"])["maximum"]
                    for a,b in zip(baseline["samples"], result["samples"], strict=True)]
                row = {"stage":stage,"pair":pair,"variant":variant,
                       "passed":result["passed"] and baseline["passed"] and len(differences)==6 and max(differences)<=1e-6,
                       "maxBaselineDifference":max(differences),
                       "peak":result.get("sampledPeak"),
                       "groups":{name:{"medianMs":statistics.median(s["milliseconds"] for s in samples),
                                      "sumMs":sum(s["milliseconds"] for s in samples),
                                      "styleSeconds":sum(s["rendererDelta"].get("RecalcStyleDuration",0) for s in samples)}
                                 for name,samples in (("cold",result["samples"][:1]),("fresh",result["samples"][1:4]),("revisit",result["samples"][4:]))}}
                rows.append(row)
            save(OUT/"dense"/"summary.json", rows)
    print(json.dumps(rows, indent=2), flush=True)

def head_run():
    import probe_browser_gpt2_head_locality as head
    snapshot("head", [Path(head.__file__), ROOT/"tools/browser_gpt2_head_locality.py"])
    rows=[]
    for pair, order in enumerate((('baseline','settings','private-inputs'),('private-inputs','settings','baseline'))):
        for mode in order:
            r=head.run_case(OUT/"head"/f"pair{pair}"/mode,mode,pair,60)
            rows.append({k:v for k,v in r.items() if k not in ('memorySamples','sourceHashes','sourceHeadHashes','artifactHashes')})
            save(OUT/"head"/"summary.json",rows)
            print(json.dumps({"pair":pair,"mode":mode,"passed":r["passed"],"ms":r.get("medianMilliseconds"),"exception":r.get("exception")}),flush=True)

def loop_run():
    import benchmark_selective_loop as loop
    from probe_native_reused_loop import loop_parts
    snapshot("loop",[Path(loop.__file__),ROOT/"tools/probe_native_reused_loop.py"])
    width=loop.WIDTH
    variants=('baseline','static-readers','local-scope','static-local')
    fixtures={}
    for steps in loop.PREFIXES:
        for variant in variants:
            source,output,css=loop_parts(width,steps,centered=True)
            if variant in ('static-readers','static-local'):
                rule=[]
                for bank in range(2):
                    rule.append(f'.loop-reader-{bank}{{animation-name:'+','.join(f'loop-k-{bank}-{i}' for i in range(width+1))+
                        ';animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:'+
                        ','.join(f'--loop-t-{bank}-{i}' for i in range(width+1))+';}')
                css,count=re.subn(r'\.loop-reader\{[^{}]+\}', ''.join(rule),css)
                assert count==1
                source=source.replace('<div class="loop-reader">','<div class="loop-reader-0"><div class="loop-reader-1">')+'</div>'
            if variant in ('local-scope','static-local'):
                css=css.replace('html{timeline-scope:', '.core-block{timeline-scope:')
            css=loop.scoped_loop(css,steps)
            if variant in ('static-readers','static-local'):
                css+='.loop-reader-1{'+ ';'.join(f'--lp-0-{i}:inherit' for i in range(width+1))+'}'
            css+='.core-block{'+ ';'.join(f'--initial-{i}:{x}' for i,x in enumerate(loop.reference(0)[0]))+'}'
            css+='.compute{'+ ';'.join(f'--loop-out-{i}:calc(-.5 * var(--loop-in-{i}) + ({((i*13)%37-18)/128}) + mod(var(--native-pass),3) / 32)' for i in range(width))+';width:1px;height:1px}'
            body=source.replace('{child}','<div class="compute">'+output.replace('{child}','<i id="result"></i>')+'</div>')
            page='<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\';object-src \'none\'"><link rel="stylesheet" href="style.css"><body><div class="core-controller"><div class="core-block">'+body+'</div></div></body>'
            directory=OUT/"loop"/"fixtures"/f'{variant}-p{steps}'
            directory.mkdir(parents=True,exist_ok=False)
            (directory/'style.css').write_text(css)
            (directory/'index.html').write_text(page)
            fixtures[variant,steps]={'variant':variant,'steps':steps,'directory':str(directory.relative_to(ROOT)),
                'hashes':{n:digest(directory/n) for n in ('index.html','style.css')}}
    save(OUT/'loop'/'manifest.json',list(fixtures.values()))
    gates={v:True for v in variants}
    comparisons=[]
    for steps in loop.PREFIXES:
        baseline=loop.run_case(fixtures['baseline',steps],OUT/'loop'/'gate'/f'baseline-p{steps}')
        if not baseline['passed']:
            raise RuntimeError('Baseline gate failed')
        for variant in variants[1:]:
            if not gates[variant]:continue
            r=loop.run_case(fixtures[variant,steps],OUT/'loop'/'gate'/f'{variant}-p{steps}')
            comparison=loop.compare(baseline,r) if r['passed'] else {'passed':False}
            gates[variant]=r['passed'] and comparison['passed']
            comparisons.append({'steps':steps,'variant':variant,**comparison})
        save(OUT/'loop'/'gates.json',{'passed':gates,'comparisons':comparisons})
    rows=[]
    for pair in range(4):
        order=[v for v in variants if gates[v]]
        if pair%2:order.reverse()
        for variant in order:
            r=loop.run_case(fixtures[variant,24],OUT/'loop'/'timing'/f'pair{pair}'/variant)
            rows.append({'pair':pair,**{k:v for k,v in r.items() if k!='actual'}})
            save(OUT/'loop'/'summary.json',rows)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('experiment',choices=('dense','head','loop'))
    args=parser.parse_args()
    {'dense':dense_run,'head':head_run,'loop':loop_run}[args.experiment]()
