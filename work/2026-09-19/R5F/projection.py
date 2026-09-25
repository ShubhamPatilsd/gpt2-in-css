# R5F: project the identical-numerics savings over all 283 faces of combined7 from the woff2 table directories (no decompression)
import json, re, os, sys, collections
sys.path.insert(0, 'R5M'); 
from woff2_tables import tables  # R5M's woff2 directory reader
rows = json.load(open('R5M/font_inventory.json')); B = 'bundles/combined7'
def fam_key(f): return re.sub(r'\d+', 'N', f)
# axes / regions per family pattern (from R5F anatomy)
AX = {'bNqkvSN': (256, 512), 'bNattnSN': (256, 512), 'bNfcSN': (256, 512), 'bNprojSN': (256, 512), 'ProdQNRN': (256, 512), 'ProdQNHN': (256, 512),
      'EmbeddingLookup': (2, 50257), 'FvsDotN': (128, 256), 'FvsValueN': (65, 256)}
tot = collections.defaultdict(lambda: collections.Counter())
for r in rows:
    p = os.path.normpath(os.path.join(B, r['url'])); k = fam_key(r['family']); t = dict(tables(p))
    a, rg = AX[k]; region_list = 4 + a * rg * 6
    c = tot[k]; c['faces'] += 1; c['sfnt'] += sum(t.values()); c['HVAR'] += t.get('HVAR', 0); c['regions'] += region_list
    # strippable: glyf (all but .notdef ≈ all), post (→ 3.0: 32 B), name (→ ~200 B), STAT
    c['strip'] += t.get('glyf', 0) + max(0, t.get('post', 0) - 32) + max(0, t.get('name', 0) - 200) + t.get('STAT', 0) + max(0, t.get('loca', 0) - 2 * 1)
    c['items'] += t.get('HVAR', 0) - region_list
print(f"{'family':16s} {'faces':>5s} {'sfnt MB':>8s} {'HVAR MB':>8s} {'regionlist MB':>13s} {'items MB':>9s} {'strip MB':>8s}")
S = collections.Counter()
for k, c in sorted(tot.items(), key=lambda kv: -kv[1]['sfnt']):
    print(f"{k:16s} {c['faces']:5d} {c['sfnt']/1e6:8.1f} {c['HVAR']/1e6:8.1f} {c['regions']/1e6:13.1f} {c['items']/1e6:9.1f} {c['strip']/1e6:8.1f}")
    for f in ('faces', 'sfnt', 'HVAR', 'regions', 'items', 'strip'): S[f] += c[f]
print(f"{'TOTAL':16s} {S['faces']:5d} {S['sfnt']/1e6:8.1f} {S['HVAR']/1e6:8.1f} {S['regions']/1e6:13.1f} {S['items']/1e6:9.1f} {S['strip']/1e6:8.1f}")
# merge plan: same-tag groups → files (≤ 65,535 glyphs each)
stage = {'A': [], 'B': [], 'C': []}; proj = collections.defaultdict(list)
for r in rows:
    f = r['family']; m = re.match(r'b(\d+)(qkv|attn|fc|proj)S(\d+)', f)
    if not m: continue
    L, st, s = int(m.group(1)), m.group(2), int(m.group(3))
    rows_n = {'qkv': 2304, 'attn': 768, 'fc': 3072, 'proj': 768}[st]
    (proj[s] if st == 'proj' else stage['ABC'[s]]).append((f, rows_n))
files = 0; faces_merged = 0
def plan(name, lst):
    global files, faces_merged
    n = 0; k = 1
    for f, rn in lst:
        if n + rn + 1 > 65535: k += 1; n = 0
        n += rn
    files += k; faces_merged += len(lst); return k
for g, lst in stage.items(): print(f"group {g}: {len(lst)} faces, {sum(r for _, r in lst)} rows → {plan(g, lst)} file(s)")
for s, lst in sorted(proj.items()): print(f"proj shard {s}: {len(lst)} faces, {sum(r for _, r in lst)} rows → {plan(s, lst)} file(s)")
saved_regions = (faces_merged - files) * (4 + 256 * 512 * 6)
per_face_fixed = 5136 + 2068 + 96 + 54 + 36 + 32 + 80 + 12  # fvar STAT OS/2 head hhea maxp cmap(min) header ≈ per dropped face after strip
print(f"merge plan: {faces_merged} stage faces → {files} files; region lists saved {saved_regions/1e6:.1f} MB (+ ≈{(faces_merged-files)*per_face_fixed/1e6:.1f} MB fixed tables)")
emb = 769 * 17489 * 2  # LONG_WORDS → 16-bit: 2 bytes per wide column per item
print(f"embedding LONG_WORDS fix: −{emb/1e6:.1f} MB")
total = S['sfnt']; a = S['strip']; b = emb; c = saved_regions
print(f"identical-numerics, font-only swap (strip + embedding): −{(a+b)/1e6:.1f} MB = −{100*(a+b)/total:.1f} % of {total/1e6:.0f} MB sfnt")
print(f"+ merge (needs codepoint re-allocation in the emitter): −{(a+b+c)/1e6:.1f} MB = −{100*(a+b+c)/total:.1f} %")
