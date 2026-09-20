"""R2C offline witness for bundles/R2C (and R2C-qonly) vs bundles/combined.

(a) HOIST IDENTITY: for every list whose entries were hoisted, entry i of the R2C list must be
    `"TAG" var(--fq-…)` with the SAME tag as combined's entry i, and the sheet must declare
    `--fq-…:EXPR` on the same element where EXPR is combined's entry-i arithmetic VERBATIM
    (byte-for-byte; the only difference between the two sheets is the var name).
(b) every `--fq-*` is registered exactly once as `<number>` inherits:false; the head-isolation wall
    does not reset them; no `calc(` / `round(` / `mod(` remains inside any hoisted list.
(c) selector-level diff combined -> R2C limited to the intended rules.
(d) font witnesses identical to combined; index.html identical.
usage: python3 offline_check.py [bundle-name]"""
import json, re, sys, collections
from pathlib import Path

W = Path(__file__).resolve().parents[1]
bundle = sys.argv[1] if len(sys.argv) > 1 else "R2C"
ref = sys.argv[2] if len(sys.argv) > 2 else "combined"  # R2H: reference bundle parametrised
C = (W / f"bundles/{ref}/runtime.css").read_text()
N = (W / f"bundles/{bundle}/runtime.css").read_text()
manifest = json.load(open(W / f"bundles/{bundle}/manifest.json"))
fails = 0


def check(cond, *msg):
    global fails
    if not cond:
        fails += 1
        print("FAIL:", *msg)


def split_top(v):
    parts, depth, cur, instr = [], 0, [], False
    for ch in v:
        if ch == '"':
            instr = not instr
        if not instr:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(cur).strip())
                cur = []
                continue
        cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts


def find_values(css, key):
    """All values of `key:` declarations (in sheet order), with the selector of the rule."""
    out, pos = [], 0
    while True:
        i = css.find(key, pos)
        if i < 0:
            return out
        j = i + len(key)
        depth = 0
        instr = False
        while j < len(css):
            ch = css[j]
            if ch == '"':
                instr = not instr
            elif not instr:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                elif ch in ";}" and depth == 0:
                    break
            j += 1
        b = css.rfind("{", 0, i)
        s0 = max(css.rfind("}", 0, b), css.rfind("{", 0, b), css.rfind(";", 0, b))
        out.append((css[s0 + 1 : b].strip(), css[i + len(key) : j]))
        pos = j


def declared(css, name):
    """All `name:value` declaration values in the sheet (custom property)."""
    return [v for _, v in find_values(css, name + ":")]


ENTRY_OLD = re.compile(r'^"([^"]+)" (.+)$', re.S)
ENTRY_NEW = re.compile(r'^"([^"]+)" var\((--fq-[\w-]+)\)$')

# ---------------- (a) hoist identity
lists_c = collections.defaultdict(list)
lists_n = collections.defaultdict(list)
for sel, val in find_values(C, "font-variation-settings:"):
    lists_c[sel].append(val)
for sel, val in find_values(N, "font-variation-settings:"):
    lists_n[sel].append(val)
for sel, vals in find_values(C, "--fvs-query-"):
    pass
query_c = {k: v for k, v in ((m.group(1), m.group(2)) for m in re.finditer(r"(--fvs-query-\d+):([^;}]+)", C))}
query_n = {k: v for k, v in ((m.group(1), m.group(2)) for m in re.finditer(r"(--fvs-query-\d+):([^;}]+)", N))}
check(len(query_c) == 12 and len(query_n) == 12, "12 query lists", len(query_c), len(query_n))

hoisted_lists = []  # (label, element selector, combined value, new value)
stage_on = manifest.get("r2cHoistStages")
query_on = manifest.get("r2cHoistQuery")
embed_on = manifest.get("r2cHoistEmbedding")
for sel in (".shared-qkv", ".shared-attn", ".shared-fc", ".shared-proj"):
    check(len(lists_c[sel]) == 12 and len(lists_n[sel]) == 12, sel, "12 layer rules", len(lists_c[sel]), len(lists_n[sel]))
    for L, (vc, vn) in enumerate(zip(lists_c[sel], lists_n[sel])):
        hoisted_lists.append((f"{sel} layer {L}", sel, vc, vn, stage_on))
for h in range(12):
    hoisted_lists.append((f"--fvs-query-{h}", ".fvs-query", query_c[f"--fvs-query-{h}"], query_n[f"--fvs-query-{h}"], query_on))
hoisted_lists.append((".embedding-source", ".embedding-source", lists_c[".embedding-source"][0], lists_n[".embedding-source"][0], embed_on))

decl_cache = {}
def declaration_on(sel, name):
    key = (sel, name)
    if key not in decl_cache:
        vals = [v for s, v in find_values(N, name + ":") if s == sel or (sel.startswith(".shared-") and s == sel)]
        decl_cache[key] = vals
    return decl_cache[key]

# Build one index of all --fq declarations: name -> list of (selector, value)
fq_decls = collections.defaultdict(list)
for m in re.finditer(r"(--fq-[\w-]+):([^;}]+)", N):
    # skip @property registrations (they have no ':' value form) - the regex only matches declarations
    b = N.rfind("{", 0, m.start())
    s0 = max(N.rfind("}", 0, b), N.rfind("{", 0, b), N.rfind(";", 0, b))
    sel = N[s0 + 1 : b].strip()
    if sel.startswith("@property"):
        continue
    fq_decls[m.group(1)].append((sel, m.group(2)))

total_entries = identical = 0
for label, sel, vc, vn, on in hoisted_lists:
    ec, en = split_top(vc), split_top(vn)
    check(len(ec) == len(en), label, "entry count", len(ec), len(en))
    if not on:
        check(vc == vn, label, "flag off: list must be unchanged")
        continue
    for i, (a, bnew) in enumerate(zip(ec, en)):
        total_entries += 1
        mo, mn = ENTRY_OLD.match(a), ENTRY_NEW.match(bnew)
        if not mn:
            check(False, label, i, "new entry not `\"TAG\" var(--fq-…)`:", bnew[:80]); continue
        check(mo.group(1) == mn.group(1), label, i, "tag", mo.group(1), mn.group(1))
        decls = fq_decls.get(mn.group(2), [])
        check(len(decls) == 1, label, i, mn.group(2), "declared once", len(decls))
        if decls:
            dsel, dval = decls[0]
            check(dsel == sel, label, i, mn.group(2), "declared on the list's element", dsel, sel)
            if dval == mo.group(2):
                identical += 1
            else:
                check(False, label, i, "expression differs:", dval[:80], "!=", mo.group(2)[:80])
    check("calc(" not in vn and "round(" not in vn and "mod(" not in vn, label, "no arithmetic left in the list")
print(f"(a) hoisted lists: {len(hoisted_lists)}; entries compared {total_entries}; expressions byte-identical to combined's entry arithmetic: {identical}")

# ---------------- (b) registrations / wall
regs = re.findall(r'@property (--fq-[\w-]+)\{syntax:"<number>";inherits:false;initial-value:0\}', N)
allregs = re.findall(r"@property (--fq-[\w-]+)\{", N)
check(len(regs) == len(allregs), "all --fq registrations are <number> inherits:false", len(regs), len(allregs))
check(len(set(regs)) == len(regs), "no duplicate --fq registration", len(regs) - len(set(regs)))
used = set(fq_decls)
check(set(regs) == used, "registered set == declared set", len(set(regs) ^ used))
wall = re.search(r"\.head-isolation\{([^}]*)\}", N).group(1)
check("--fq-" not in wall, "head-isolation wall does not reset --fq-*")
core_reset_fq = len(re.findall(r"--fq-[\w-]+:initial", N))
check(core_reset_fq == 0, "no --fq-*:initial anywhere", core_reset_fq)
expected_regs = (768 * 3 + 3072 if stage_on else 0) + (768 if query_on else 0) + (2 if embed_on else 0)
check(len(regs) == expected_regs, "registration count", len(regs), expected_regs)
lifted = {k: N.count(f".{k}{{--fq-{k.split('-')[1]}-000:") for k in ("shared-qkv", "shared-attn", "shared-fc", "shared-proj")}
if stage_on:
    check(all(v == 1 for v in lifted.values()), "one hoist rule per stage (lifted out of the layer blocks)", lifted)
    for k in lifted:
        i = N.find(f".{k}{{--fq-")
        depth = N.count("{", 0, i) - N.count("}", 0, i)
        check(depth == 0, k, "hoist rule at top level (brace depth 0)", depth)
print(f"(b) --fq registrations {len(regs)} (expected {expected_regs}); wall clean; hoist rules per stage {lifted}")

# ---------------- (c) selector-level diff
def inner_rules(css):
    """Multiset of (selector, body) for every innermost rule (linear scan)."""
    rules = collections.Counter()
    stack = []
    i = 0
    n = len(css)
    start = 0
    while i < n:
        ch = css[i]
        if ch == '"':
            j = css.find('"', i + 1)
            i = j + 1 if j > 0 else n
            continue
        if ch == "{":
            stack.append((css[start:i].strip(), i + 1))
            start = i + 1
        elif ch == "}":
            sel, b = stack.pop()
            body = css[b:i]
            if "{" not in body:
                rules[(sel, body)] += 1
            start = i + 1
        i += 1
    return rules

rc, rn = inner_rules(C), inner_rules(N)
removed = rc - rn
added = rn - rc
def selpat(s):
    return re.sub(r"\d+", "N", s)
rem_sel = collections.Counter(selpat(s) for (s, _b) in removed.elements())
add_sel = collections.Counter(selpat(s) for (s, _b) in added.elements())
print("(c) selector-level diff combined -> %s: removed %s" % (bundle, dict(rem_sel)))
print("    added", dict(add_sel))
allowed = {"@property --fq-N-N", "@property --fq-qkv-N", "@property --fq-attn-N", "@property --fq-fc-N", "@property --fq-proj-N", "@property --fq-q-N-N", "@property --fq-token-group", "@property --fq-token-local",
           ".shared-qkv", ".shared-attn", ".shared-fc", ".shared-proj", ".fvs-query", ".embedding-source"}
check(set(rem_sel) <= allowed and set(add_sel) <= allowed, "diff limited to intended rules", (set(rem_sel) | set(add_sel)) - allowed)

# ---------------- (d) witnesses / html
def norm_keys(w):
    # witness keys are absolute font paths through the tools copy's `experiments` symlink
    # (work/2026-09-19/<agent>/experiments/...); compare modulo the agent directory.
    return {re.sub(r"/work/2026-09-19/\w+/", "/work/2026-09-19/AGENT/", k): v for k, v in w.items()}
wc = norm_keys(json.load(open(W / f"bundles/{ref}/font-witnesses.json")))
wn = norm_keys(json.load(open(W / f"bundles/{bundle}/font-witnesses.json")))
check(set(wc) == set(wn) and all(wc[k] == wn[k] for k in wc), "font witnesses identical to combined (keys modulo agent dir)", len(wc), len(wn), len(set(wc) ^ set(wn)))
hc = (W / f"bundles/{ref}/index.html").read_bytes()
hn = (W / f"bundles/{bundle}/index.html").read_bytes()
check(hc == hn, "index.html identical to combined")
print(f"(d) witnesses {len(wn)} identical: {set(wc) == set(wn) and all(wc[k] == wn[k] for k in wc)}; index.html identical: {hc == hn}; runtime.css {len(C):,} -> {len(N):,} chars")

# ---------------- var()/calc counts per list element
def counts(css, sel):
    v = lists_c[sel][0] if css is C else lists_n[sel][0]
    return v.count("var("), v.count("calc(")
print("var()/calc per list element (combined -> %s):" % bundle)
for sel in (".shared-qkv", ".shared-attn", ".shared-fc", ".shared-proj", ".embedding-source"):
    print(f"   {sel}: {counts(C, sel)} -> {counts(N, sel)}")
print(f"   --fvs-query-0 list: {(query_c['--fvs-query-0'].count('var('), query_c['--fvs-query-0'].count('calc('))} -> {(query_n['--fvs-query-0'].count('var('), query_n['--fvs-query-0'].count('calc('))}")
print("RESULT:", "ok" if fails == 0 else f"{fails} failures")
sys.exit(1 if fails else 0)
