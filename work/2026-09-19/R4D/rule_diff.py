#!/usr/bin/env python3
"""R4D: rule-level diff of two runtime.css files. Splits each sheet into leaf rules
(selector/prelude + declaration block, with enclosing @container preludes prefixed),
and reports the differing rules grouped by a coarse family key. Intent check only."""
import re, sys, collections
def leaf_rules(css):
    out = []; stack = []; i = 0; n = len(css); buf_start = 0
    while i < n:
        c = css[i]
        if c == '"':
            j = css.find('"', i + 1); i = j + 1 if j != -1 else n; continue
        if c == '{':
            prelude = css[buf_start:i].strip()
            # is this a leaf block (no nested '{' before matching '}')?
            depth = 0; j = i; leaf = True; k = i + 1
            while k < n:
                ch = css[k]
                if ch == '"':
                    q = css.find('"', k + 1); k = q + 1 if q != -1 else n; continue
                if ch == '{': leaf = False; break
                if ch == '}': break
                k += 1
            if leaf:
                out.append((" > ".join(stack + [prelude]), css[i + 1:k]))
                i = k + 1; buf_start = i
            else:
                stack.append(prelude); i += 1; buf_start = i
            continue
        if c == '}':
            if stack: stack.pop()
            i += 1; buf_start = i; continue
        i += 1
    return out
def family(prelude):
    p = re.sub(r'\d+', 'N', prelude)
    p = re.sub(r'\s+', ' ', p)
    return p[:110]
a, b = sys.argv[1], sys.argv[2]
ra = collections.Counter(leaf_rules(open(a).read())); rb = collections.Counter(leaf_rules(open(b).read()))
only_a = ra - rb; only_b = rb - ra
print(f"{a}: {sum(ra.values())} leaf rules; {b}: {sum(rb.values())}; only in A {sum(only_a.values())}, only in B {sum(only_b.values())}")
for label, d in (("ONLY IN A (removed)", only_a), ("ONLY IN B (added)", only_b)):
    fam = collections.Counter(); byfam = collections.defaultdict(int)
    for (prelude, body), cnt in d.items():
        fam[family(prelude)] += cnt; byfam[family(prelude)] += len(body) * cnt
    print(f"\n## {label}: {len(fam)} families")
    for f, cnt in fam.most_common(60):
        print(f"  {cnt:6d} rules {byfam[f]:>11,d} B  {f}")
