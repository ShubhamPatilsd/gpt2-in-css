#!/usr/bin/env python3
"""Per-pass element census from a run_bundle.mjs trace with invalidationTracking:
for every UpdateLayoutTree (and, separately, style recalcs interleaved in Layout), histogram the restyled
elements' node names (StyleRecalcInvalidationTracking events) by normalised class. usage: pass_census.py <run-dir> [out.md]"""
import gzip, json, re, sys, collections, bisect
run = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else f"{run}/pass_census.md"
tr = json.load(gzip.open(f"{run}/trace.json.gz", "rt"))["traceEvents"]
pr = json.load(open(f"{run}/pipeline-results.json"))
tok_ts = {int(k): v["ts"] * 1e6 for k, v in pr["tokenMetrics"].items()}
cnt = collections.Counter((e.get("pid"), e.get("tid")) for e in tr if e.get("name") == "UpdateLayoutTree" and e.get("ph") == "X")
(PID, TID), _ = cnt.most_common(1)[0]
X = sorted((e for e in tr if e.get("pid") == PID and e.get("tid") == TID and e.get("ph") == "X" and e["name"] in ("UpdateLayoutTree", "Layout")), key=lambda e: e["ts"])
ult = [e for e in X if e["name"] == "UpdateLayoutTree"]; lay = [e for e in X if e["name"] == "Layout"]
inv = [e for e in tr if e.get("pid") == PID and e.get("name") == "StyleRecalcInvalidationTracking"]
print(f"UpdateLayoutTree {len(ult)}, Layout {len(lay)}, StyleRecalcInvalidationTracking {len(inv)}", file=sys.stderr)
def norm_name(n):
    m = re.match(r"(\w+)(?: id='([^']*)')?(?: class='([^']*)')?", n or "")
    if not m: return n
    tag, ident, cls = m.group(1).lower(), m.group(2), m.group(3)
    key = "." + ".".join(cls.split()) if cls else ("#" + ident if ident else tag)
    return re.sub(r"\d+", "N", key)
starts = [e["ts"] for e in ult]
lay_starts = [e["ts"] for e in lay]
def enclosing(ts):
    i = bisect.bisect_right(starts, ts) - 1
    if i >= 0 and ts <= ult[i]["ts"] + ult[i].get("dur", 0): return ("ult", i)
    j = bisect.bisect_right(lay_starts, ts) - 1
    if j >= 0 and ts <= lay[j]["ts"] + lay[j].get("dur", 0): return ("lay", j)
    # invalidation events are stamped when the element is DIRTIED (before the pass): attribute to the next UpdateLayoutTree
    k = bisect.bisect_left(starts, ts)
    if k < len(ult): return ("ult", k)
    return ("none", -1)
per_pass = collections.defaultdict(collections.Counter); per_pass_reason = collections.defaultdict(collections.Counter)
inter = collections.defaultdict(collections.Counter); orphan = collections.Counter()
for e in inv:
    d = (e.get("args") or {}).get("data") or {}
    kind, i = enclosing(e["ts"])
    key = norm_name(d.get("nodeName"))
    if kind == "ult": per_pass[i][key] += 1; per_pass_reason[i][d.get("reason")] += 1
    elif kind == "lay": inter[i][key] += 1
    else: orphan[key] += 1
def token_of(ts): return next((k for k in sorted(tok_ts) if ts <= tok_ts[k]), None)
# group passes by (elementCount) and print the population of the first few of each size
by_size = collections.defaultdict(list)
for i, e in enumerate(ult):
    a = e.get("args") or {}; ec = a.get("elementCount", (a.get("endData") or {}).get("elementCount", -1))
    by_size[ec].append(i)
tot_by_class = collections.Counter(); tot_by_class_tok = collections.defaultdict(collections.Counter)
for i, c in per_pass.items():
    tot_by_class.update(c); t = token_of(ult[i]["ts"])
    if t: tot_by_class_tok[t].update(c)
w = open(out, "w")
w.write(f"# pass census — {run}\n\n{len(ult)} UpdateLayoutTree, {len(lay)} Layout, {len(inv)} StyleRecalcInvalidationTracking events ({sum(orphan.values())} outside any pass/layout, {sum(sum(c.values()) for c in inter.values())} inside Layout = interleaved container recalcs)\n\n")
w.write("## Recurring pass sizes and their populations (elementCount: passes, mean ms; population of one representative pass, tracked elements by class)\n\n")
for ec in sorted(by_size, key=lambda k: -sum(ult[i].get("dur", 0) for i in by_size[k])):
    ids = by_size[ec]; ms = sum(ult[i].get("dur", 0) for i in ids) / 1000
    rep = max(ids, key=lambda i: sum(per_pass[i].values()))
    pop = per_pass[rep]; reasons = per_pass_reason[rep]
    w.write(f"- **{ec}** elements × {len(ids)} passes, {ms:.0f} ms total ({ms/len(ids):.1f} ms/pass); tracked {sum(pop.values())}: " + ", ".join(f"{k} {v}" for k, v in pop.most_common(14)) + f"; reasons: {dict(reasons.most_common(4))}\n")
w.write("\n## Interleaved recalcs inside Layout events (container queries): classes restyled\n\n")
agg = collections.Counter()
for c in inter.values(): agg.update(c)
w.write(f"{len(inter)} Layout events contain restyles; total tracked {sum(agg.values())}: " + ", ".join(f"{k} {v}" for k, v in agg.most_common(20)) + "\n")
w.write("\n## Restyles per token by class (UpdateLayoutTree passes only)\n\n| class | " + " | ".join(f"tok {t}" for t in sorted(tot_by_class_tok)) + " |\n|---|" + "---:|" * len(tot_by_class_tok) + "\n")
for k, _ in tot_by_class.most_common(40):
    w.write(f"| `{k}` | " + " | ".join(str(tot_by_class_tok[t][k]) for t in sorted(tot_by_class_tok)) + " |\n")
w.close(); print(out)
