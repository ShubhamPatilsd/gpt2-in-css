# R5M: inventory of combined7's @font-face set: file bytes, family names, where each family is used.
import re, os, sys, json, collections
B = sys.argv[1] if len(sys.argv) > 1 else 'bundles/combined7'
css = open(f'{B}/runtime.css').read()
html = open(f'{B}/index.html').read()
faces = re.findall(r'@font-face\{([^}]*)\}', css)
rows = []
tot = 0
fam_files = collections.defaultdict(list)
for f in faces:
    fam = re.search(r'font-family:\s*"?([^;"]+)"?', f).group(1)
    url = re.search(r'url\("?([^")]+)"?\)', f).group(1)
    ur = re.search(r'unicode-range:([^;]+)', f)
    fd = re.search(r'font-display:([^;]+)', f)
    p = os.path.normpath(os.path.join(B, url))
    sz = os.path.getsize(p) if os.path.exists(p) else -1
    tot += max(sz, 0)
    rows.append((fam, url, sz, ur.group(1) if ur else '', fd.group(1) if fd else ''))
    fam_files[fam].append(sz)
print('faces', len(faces), 'total bytes', tot, f'{tot/1e6:.1f} MB')
# usage: count occurrences of family name in css (outside @font-face) and html
css_no_ff = re.sub(r'@font-face\{[^}]*\}', '', css)
groups = collections.defaultdict(lambda: [0, 0, 0, 0])
def key(fam):
    return re.sub(r'\d+', 'N', fam)
for fam, url, sz, ur, fd in rows:
    k = key(fam)
    g = groups[k]
    g[0] += 1; g[1] += sz
    g[2] += len(re.findall(re.escape(fam) + r'(?![\w-])', css_no_ff))
    g[3] += len(re.findall(re.escape(fam) + r'(?![\w-])', html))
print(f'{"family pattern":45s} {"faces":>5s} {"MB":>8s} {"css refs":>8s} {"html refs":>9s}')
for k, g in sorted(groups.items(), key=lambda kv: -kv[1][1]):
    print(f'{k:45s} {g[0]:5d} {g[1]/1e6:8.2f} {g[2]:8d} {g[3]:9d}')
big = sorted(rows, key=lambda r: -r[2])[:15]
print('largest faces:')
for r in big: print(f'  {r[2]/1e6:7.2f} MB {r[0]:30s} {r[1]} ur={r[3][:40]} fd={r[4]}')
json.dump([dict(family=r[0], url=r[1], bytes=r[2], unicode_range=r[3], display=r[4]) for r in rows], open('R5M/font_inventory.json', 'w'), indent=0)
