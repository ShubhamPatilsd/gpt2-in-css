"""R4C: what grows with capacity — element / rule / latch populations, combined4 (cap 8) vs combined4-c32 (cap 32)."""
import re, sys, json, collections
B = "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/"
def load(name):
    return open(B + name + "/index.html").read(), open(B + name + "/runtime.css").read()
h8, c8 = load("combined4"); h32, c32 = load("combined4-c32")
out = {}
def both(label, f):
    a, b = f(h8, c8), f(h32, c32)
    out[label] = (a, b, b - a, (b - a) / 24 if b != a else 0)
    print(f"{label:58s} cap8 {a:>10,} cap32 {b:>10,}  delta {b-a:>+10,}  per slot {(b-a)/24:>+9.1f}")
both("bytes index.html", lambda h, c: len(h)); both("bytes runtime.css", lambda h, c: len(c))
both("elements (open tags)", lambda h, c: len(re.findall(r"<[a-zA-Z]", h)))
both("rules (approx '{' count)", lambda h, c: c.count("{"))
both("@property", lambda h, c: c.count("@property"))
both("@property inherits:true", lambda h, c: len(re.findall(r"@property[^{]*\{[^}]*inherits:\s*true", c)))
both("86400s latch declarations", lambda h, c: c.count("86400s"))
both("view-timeline-name declarations", lambda h, c: c.count("view-timeline-name"))
both("animation-timeline declarations", lambda h, c: c.count("animation-timeline"))
both("@keyframes", lambda h, c: c.count("@keyframes"))
both("timeline names declared (timeline-scope entries)", lambda h, c: sum(len(m.split(",")) for m in re.findall(r"timeline-scope:([^;}]*)", c)))
both("font-variation-settings decls", lambda h, c: c.count("font-variation-settings"))
both("`--fc-` (bank latch) tokens in css", lambda h, c: len(re.findall(r"--fc-[kv]s?-\d+", c)))
both("`--fr-` (bank alias) tokens in css", lambda h, c: len(re.findall(r"--fr-[kv]s?-\d+", c)))
both("`--fs-H-S` score tokens", lambda h, c: len(re.findall(r"--fs-\d+-\d+", c)))
both("`--fw-H-S` weight tokens", lambda h, c: len(re.findall(r"--fw-\d+-\d+", c)))
both("`--fe-H-S` exp tokens", lambda h, c: len(re.findall(r"--fe-\d+-\d+", c)))
both("`--fv-S` tokens", lambda h, c: len(re.findall(r"--fv-\d+\b", c)))
both("transition-property name count (all decls)", lambda h, c: sum(len(m.split(",")) for m in re.findall(r"transition-property:([^;}]*)", c)))
both("token-N-captured mentions (css)", lambda h, c: len(re.findall(r"token-\d+-captured", c)))
both(":has( occurrences", lambda h, c: c.count(":has("))
both("@container occurrences", lambda h, c: c.count("@container"))
# element classes
def classes(h):
    cnt = collections.Counter()
    for m in re.finditer(r'class="([^"]*)"', h):
        for cl in m.group(1).split():
            cnt[re.sub(r"\d+", "N", cl)] += 1
    return cnt
k8, k32 = classes(h8), classes(h32)
print("\nclass families (digits -> N) with different counts:")
rows = []
for k in sorted(set(k8) | set(k32)):
    if k8[k] != k32[k]: rows.append((k32[k] - k8[k], k, k8[k], k32[k]))
for d, k, a, b in sorted(rows, reverse=True): print(f"  {k:40s} cap8 {a:>8,} cap32 {b:>8,} delta {d:>+8,} per slot {d/24:>+8.1f}")
# bank rule sizes: transition-property list on the bank and per-slot write rules
def rules_of(c):
    return [r for r in c.split("}") if "{" in r]
RULES = {}
def bank_stats(c):
    RULES.setdefault(id(c), rules_of(c)); rules = RULES[id(c)]
    banks = [r for r in rules if re.match(r"\s*\.fvs-bank-\d+", r)]
    tp = [len(m.split(",")) for b in banks for m in re.findall(r"transition-property:([^;}]*)", b)]
    return len(banks), (sum(tp) / len(tp) if tp else 0), sum(len(b) for b in banks)
for name, c in (("cap8", c8), ("cap32", c32)):
    n, avg, byt = bank_stats(c); print(f"\n{name}: .fvs-bank-* rules {n}, avg transition-property names {avg:.0f}, total bank rule bytes {byt:,}")
# V glyph rows: rules mentioning FvsValue and their total bytes
for name, c in (("cap8", c8), ("cap32", c32)):
    rules = RULES[id(c)]
    v = [r for r in rules if "FvsValue" in r]; print(f"{name}: rules referencing FvsValue {len(v)}, bytes {sum(len(x) for x in v):,}")
    s = [r for r in rules if "FvsDot" in r]; print(f"{name}: rules referencing FvsDot {len(s)}, bytes {sum(len(x) for x in s):,}")
json.dump(out, open("populations.json", "w"), indent=1)
