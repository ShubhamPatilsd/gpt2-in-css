# R5M: tabulate fixture results (R5M/fx-results/*.json) -> markdown rows: RSS deltas vs the blank tab, per-generation steps, GC/pressure effects.
import json, glob, os
order = ['empty','fonts-all','fonts-big7','fonts-weights','fonts-fvs','fonts-all-unused','fonts-all-ur','inst-1000','inst-4000','inst-16000','inst-4000-same','inst-4000-none','inst-gen-4000','inst-score-400','inst-score-gen-100','inst-fc-8','inst-fc-gen','inst-proj-gen','inst-embed-gen','inst-head-gen','props-only','dom-50k-plain','dom-50k-inline','dom-50k-inline-props','dom-50k-cv','dom-50k-none','anim-10k','anim-38k','anim-77k','bundle-load']
print('| fixture | load ms | blank MB | loaded MB | Δload | gens (Δ per gen MB) | after GC | after critical pressure | nodes | layoutObjects | style ms | layout ms |')
print('|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|')
for name in order:
    p = f'R5M/fx-results/{name}.json'
    if not os.path.exists(p): continue
    d = json.load(open(p)); s = {r['tag']: r for r in d['steps']}
    b = s['blank']['rssMB']; l = s['loaded']
    gens = [r for r in d['steps'] if r['tag'].startswith('gen')]
    prev = l['rssMB']; gtxt = []
    for g in gens: gtxt.append(f"{g['rssMB']-prev:+d}"); prev = g['rssMB']
    gc = s.get('afterGC', {}).get('rssMB'); pr = s.get('afterPressure', {}).get('rssMB')
    last = gens[-1] if gens else l
    print(f"| {name} | {d['loadMs']} | {b} | {l['rssMB']} | {l['rssMB']-b:+d} | {' '.join(gtxt) if gtxt else ''} | {gc} ({gc-last['rssMB']:+d}) | {pr} ({pr-gc:+d}) | {l['nodes']} | {l['layoutObjects']} | {last['styleMs']-s['blank']['styleMs']} | {last['layoutMs']-s['blank']['layoutMs']} |")
