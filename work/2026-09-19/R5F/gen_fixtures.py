# R5F: fonts-only fixture pages (no JS) under R5F/fx/: layer-0 originals vs stripped vs TTF, A-group 3 faces vs merged, embedding orig vs re-encoded.
# Same page skeleton as R5M/gen_fixtures.py (witness elements verbatim from combined7's index.html; urls rewritten to server-root-absolute).
import re, os, json
W = '/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19'; ROOT = '/Users/shubhampatil/Documents/programming/gpt2-css'
B = f'{W}/bundles/combined7'; OUT = f'{W}/R5F/fx'; os.makedirs(OUT, exist_ok=True)
css = open(f'{B}/runtime.css').read(); html = open(f'{B}/index.html').read()
faces = {re.search(r'font-family:\s*"?([^;"]+)"?', f).group(1): f for f in re.findall(r'@font-face\{[^}]*\}', css)}
wit = {re.search(r'font-family:([^;]+)', w).group(1): w for w in re.findall(r'<i class="font-witness"[^>]*>[^<]*</i>', html)}
WCSS = '.font-witness{position:fixed;top:-100000px;left:0;display:block;width:max-content;height:1px;font-variation-settings:normal;font-kerning:none;font-style:normal;white-space:pre}'
def src_path(fam):
    u = re.search(r'url\("?([^")]+)"?\)', faces[fam]).group(1).split('?')[0]
    return os.path.realpath(os.path.join(B, u))
def face_rule(fam, path=None, fmt='woff2', ur=None):
    p = path or src_path(fam); assert os.path.exists(p), p
    rel = '/' + os.path.relpath(p, ROOT)
    m = re.search(r'unicode-range:([^;}]+)', faces[fam]); ur = ur or (m.group(1) if m else None)
    return f'@font-face{{font-family:{fam};src:url("{rel}") format("{fmt}");' + (f'unicode-range:{ur}' if ur else '') + '}'
def witness(fam, cp=None):
    w = wit[fam]
    return w if cp is None else re.sub(r'&#x[0-9A-Fa-f]+;', f'&#x{cp:X};', w)
def page(name, rules, body):
    open(f'{OUT}/{name}.html', 'w').write(f'<!doctype html><html><head><meta charset="utf-8"><title>{name}</title><style>{WCSS}{"".join(rules)}</style></head><body>{body}</body></html>')
    print(name, os.path.getsize(f'{OUT}/{name}.html'))
page('empty', [], '<p>empty</p>')
l0 = [f'b0{s}S{i}' for s, n in (('qkv', 3), ('attn', 3), ('fc', 3), ('proj', 12)) for i in range(n)]
page('l0-orig21', [face_rule(f) for f in l0], ''.join(witness(f) for f in l0))
page('l0-strip21', [face_rule(f, f'{W}/R5F/assets-r5f/{f}-strip.woff2') for f in l0], ''.join(witness(f) for f in l0))
nine = l0[:9]
page('l0-orig9', [face_rule(f) for f in nine], ''.join(witness(f) for f in nine))
page('l0-ttf9', [face_rule(f, src_path(f).replace('.woff2', '.ttf'), 'truetype') for f in nine], ''.join(witness(f) for f in nine))
A = ['b0qkvS0', 'b0attnS0', 'b0fcS0']
page('A-orig3', [face_rule(f) for f in A], ''.join(witness(f) for f in A))
blocks = {'b0qkvS0': ('U+F0000-F08FF', 0xF0000), 'b0attnS0': ('U+F0900-F0BFF', 0xF0900), 'b0fcS0': ('U+F0C00-F17FF', 0xF0C00)}
page('A-merged', [face_rule(f, f'{W}/R5F/assets-r5f/b0-A-merged.woff2', ur=blocks[f][0]) for f in A], ''.join(witness(f, blocks[f][1]) for f in A))
page('emb-orig', [face_rule('EmbeddingLookup')], witness('EmbeddingLookup'))
page('emb-r5f', [face_rule('EmbeddingLookup', f'{W}/R5F/assets-r5f/embedding-lookup-r5f.woff2')], witness('EmbeddingLookup'))
lst = ['l0-orig21', 'l0-strip21', 'l0-orig9', 'l0-ttf9', 'A-orig3', 'A-merged', 'emb-orig', 'emb-r5f', 'l0-orig21', 'l0-strip21']  # last two = repeat for noise
open(f'{W}/R5F/fx.list', 'w').write(''.join(f'{n}{"-rep" if i >= 8 else ""}\twork/2026-09-19/R5F/fx/{n}.html\t0\t4000\n' for i, n in enumerate(lst)))
