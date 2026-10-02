import json, sys, statistics as st, collections
rows=collections.defaultdict(list)
for p in sys.argv[1:]:
    for l in open(p):
        r=json.loads(l)
        if r.get('error') or 'anat' not in r: print('ERR', r.get('arm'), r.get('error')); continue
        rows[r['arm']].append(r)
def med(xs): return st.median(xs) if xs else float('nan')
for arm, rs in rows.items():
    A=[r['anat'] for r in rs]
    w=[a['passes'][0][1] for a in A]; rb=[a['passes'][1][1] for a in A if len(a['passes'])>1]
    print(f"{arm:18s} n={len(rs)} write {A[0]['passes'][0][0]} el: {med(w):6.1f} ms [{min(w):.1f}-{max(w):.1f}] | readback: {med(rb) if rb else float('nan'):6.1f} ms (n={len(rb)}) | layout {med([a['layouts'][0][1] for a in A]):5.1f} | shape {med([a['shapeMs'] for a in A]):5.1f} | CI {med([a['compInputs'] for a in A]):5.1f} | paintLC {med([a['paintLCself'] for a in A]):5.1f} | animate {med([a['animate'] for a in A]):5.1f} UL {med([a['ULself'] for a in A]):4.1f} | frames {A[0]['frames']} | vals k={[r['k'] for r in rs]} {[list(r['values'].values())[:2] for r in rs]}")
