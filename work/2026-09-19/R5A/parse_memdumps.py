#!/usr/bin/env python3
"""R5A: memory-infra dumps from a (gzip) Chromium trace. Streams events; keeps ph=='v' (periodic/explicit memory dumps) per process:
process_totals (resident_set_bytes, private_footprint_bytes, peak...), allocators (name -> size/effective_size + selected attrs), level of detail, guid.
Joins dump guid -> harness tag (run.json memdumps[].dumpGuid) and dump ts -> token window (--saved-token-N Animation 'b' events, as parse_trace.py).
usage: parse_memdumps.py trace.json.gz run.json out_prefix
"""
import gzip, json, sys, collections, re, time
trace, run_json, out = sys.argv[1], sys.argv[2], sys.argv[3]
run = json.load(open(run_json)) if run_json != "-" else {}
DEC = json.JSONDecoder(); T0 = time.time()
def events(path, chunk=1 << 24):
    f = gzip.open(path, "rt", encoding="utf-8", errors="replace")
    buf = f.read(chunk); i = buf.find("["); idx = i + 1
    while True:
        while True:
            while idx < len(buf) and buf[idx] in " \r\n\t,": idx += 1
            if idx >= len(buf):
                more = f.read(chunk)
                if not more: return
                buf = buf[idx:] + more; idx = 0; continue
            break
        if buf[idx] == "]": return
        try: obj, end = DEC.raw_decode(buf, idx)
        except json.JSONDecodeError:
            more = f.read(chunk)
            if not more: return
            buf = buf[idx:] + more; idx = 0; continue
        idx = end
        if idx > len(buf) // 2 and len(buf) > chunk:
            buf = buf[idx:]; idx = 0
            more = f.read(chunk)
            if more: buf += more
        yield obj
def hexval(a):
    if a is None: return None
    v = a.get("value") if isinstance(a, dict) else a
    if isinstance(v, str):
        try: return int(v, 16)
        except ValueError: return None
    return v
dumps = []; proc_names = {}; thread_names = {}; saved = collections.defaultdict(list); ult = collections.Counter(); marks = {}; n = 0
for e in events(trace):
    n += 1
    if n % 5_000_000 == 0: print(f"{n} events {time.time()-T0:.0f}s", file=sys.stderr, flush=True)
    ph = e.get("ph"); nm = e.get("name")
    if ph == "M":
        if nm == "process_name": proc_names[e.get("pid")] = (e.get("args") or {}).get("name")
        elif nm == "thread_name": thread_names[(e.get("pid"), e.get("tid"))] = (e.get("args") or {}).get("name")
        continue
    if nm == "UpdateLayoutTree": ult[e.get("pid")] += 1
    if nm == "Animation" and ph == "b":
        d = (e.get("args") or {}).get("data") or {}
        m = re.match(r"^--saved-token-(\d+)$", d.get("name") or d.get("displayName") or "")
        if m: saved[int(m.group(1))].append(e["ts"])
    if ph == "R" and "blink.user_timing" in (e.get("cat") or ""): marks.setdefault(nm, e["ts"])
    if ph != "v": continue
    a = e.get("args") or {}; d = a.get("dumps") or {}
    pt = d.get("process_totals") or {}
    totals = {k: hexval(v) for k, v in pt.items() if k in ("resident_set_bytes", "peak_resident_set_bytes", "private_footprint_bytes", "shared_footprint_bytes", "is_peak_rss_resetable")}
    allocs = {}
    for name, ad in (d.get("allocators") or {}).items():
        attrs = ad.get("attrs") or {}
        row = {"size": hexval(attrs.get("size")), "effective_size": hexval(attrs.get("effective_size"))}
        for k in ("allocated_objects_size", "object_count", "resident_size", "virtual_size", "committed_size", "free_size", "decommitted_size", "wasted", "fragmentation_size", "count", "blink_objects_count", "malloc_size"):
            if k in attrs: row[k] = hexval(attrs[k])
        allocs[name] = row
    dumps.append({"ts": e["ts"], "pid": e.get("pid"), "proc": proc_names.get(e.get("pid")), "id": e.get("id"), "level": d.get("level_of_detail"), "totals": totals, "allocators": allocs,
                  "n_allocators": len(allocs)})
print(f"streamed {n} events; {len(dumps)} dump events; procs {proc_names}", file=sys.stderr)
renderer_pid = ult.most_common(1)[0][0] if ult else None
bounds = sorted((k, min(v)) for k, v in saved.items())
def token_of(ts):
    # token window k = (bound(k-1), bound(k)]; before first bound -> "load/pre-1"
    prev = None
    for k, t in bounds:
        if ts <= t: return f"tok{k}" if prev is not None or True else "?"
        prev = k
    return f"after-tok{bounds[-1][0]}" if bounds else "?"
guid_tag = {}
for m in (run.get("memdumps") or []):
    g = m.get("dumpGuid")
    if g: guid_tag[g] = m.get("tag")
T_FIRST = min(d["ts"] for d in dumps) if dumps else 0
for dmp in dumps:
    dmp["tag"] = guid_tag.get(dmp["id"]); dmp["t_rel_s"] = round((dmp["ts"] - T_FIRST) / 1e6, 1)
# collapse allocator tree to top-level and selected 2nd-level nodes (sizes at top-level already include children in memory-infra: top-level 'size' is the sum)
TOP = ["blink_gc", "blink_objects", "partition_alloc", "malloc", "skia", "v8", "discardable", "font_caches", "cc", "gpu", "web_cache", "shared_memory", "sqlite", "leveldatabase", "media", "site_storage", "ui", "components", "net", "tracing"]
def top_table(dmp):
    al = dmp["allocators"]; row = {}
    for k, v in al.items():
        parts = k.split("/")
        if len(parts) == 1: row[k] = v.get("effective_size") if v.get("effective_size") is not None else v.get("size")
    return row
def sub_table(dmp, prefix, depth=2):
    al = dmp["allocators"]; row = {}
    for k, v in al.items():
        parts = k.split("/")
        if parts[0] == prefix and 1 < len(parts) <= depth: row[k] = v.get("size")
    return row
# merge dump events sharing (pid, id): Chrome emits process_totals and allocators as separate 'v' events of the same dump
merged = {}
for dmp in sorted(dumps, key=lambda d: d["ts"]):
    key = (dmp["pid"], dmp["id"])
    if key not in merged: merged[key] = dmp
    else:
        m = merged[key]; m["totals"] = {**m["totals"], **{k: v for k, v in dmp["totals"].items() if v}}; m["allocators"].update(dmp["allocators"]); m["level"] = m["level"] or dmp["level"]
dumps = list(merged.values())
# window label: harness tag if known (post-load, token-k, final), else the periodic dump's position between tagged dumps
tagged = sorted([(d["ts"], d["tag"]) for d in dumps if d["tag"] and d["pid"] == renderer_pid])
def window_from_tags(ts):
    prev = "pre-load"
    for t, tag in tagged:
        if ts < t: return f"before {tag}"
        prev = tag
    return f"after {prev}"
for dmp in dumps: dmp["token_window"] = window_from_tags(dmp["ts"])
rows = []
for dmp in sorted(dumps, key=lambda d: d["ts"]):
    if dmp["pid"] != renderer_pid: continue
    rows.append({"tag": dmp["tag"], "token_window": dmp["token_window"], "t_rel_s": dmp["t_rel_s"], "level": dmp["level"], "totals": dmp["totals"], "top": top_table(dmp),
                 "blink_gc": sub_table(dmp, "blink_gc", 3), "partition_alloc": sub_table(dmp, "partition_alloc", 3), "malloc": sub_table(dmp, "malloc", 2), "skia": sub_table(dmp, "skia", 3),
                 "font_caches": sub_table(dmp, "font_caches", 3), "blink_objects": sub_table(dmp, "blink_objects", 2), "v8": sub_table(dmp, "v8", 3), "discardable": sub_table(dmp, "discardable", 2)})
other = collections.defaultdict(list)
for dmp in sorted(dumps, key=lambda d: d["ts"]):
    if dmp["pid"] == renderer_pid: continue
    other[str(dmp["proc"] or dmp["pid"])].append({"tag": dmp["tag"], "token_window": dmp["token_window"], "t_rel_s": dmp["t_rel_s"], "totals": dmp["totals"], "top": top_table(dmp)})
json.dump({"renderer_pid": renderer_pid, "procs": proc_names, "token_bounds_rel_s": [(k, round((t - (marks.get("P2-run") or t)) / 1e6, 1)) for k, t in bounds], "renderer_dumps": rows, "other_process_dumps": other,
           "allocator_names_sample": sorted({k for d in dumps if d["pid"] == renderer_pid for k in d["allocators"]})[:400]}, open(out + "-memdumps.json", "w"), indent=1)
MB = lambda b: (b or 0) / 2**20
L = [f"# memory-infra dumps — {trace}\n", f"renderer pid {renderer_pid}; {len(rows)} renderer dumps; token bounds (s after Run): {[(k, round((t - (marks.get('P2-run') or t)) / 1e6, 1)) for k, t in bounds]}\n"]
tops = sorted({k for r in rows for k in r["top"]}, key=lambda k: -max(r["top"].get(k) or 0 for r in rows))
L.append("| dump | window | t (s) | level | RSS MB | PrivFoot MB | " + " | ".join(tops) + " |")
L.append("|---|---|---:|---|---:|---:|" + "---:|" * len(tops))
for r in rows:
    L.append(f"| {r['tag']} | {r['token_window']} | {r['t_rel_s']} | {r['level']} | {MB(r['totals'].get('resident_set_bytes')):,.0f} | {MB(r['totals'].get('private_footprint_bytes')):,.0f} | " + " | ".join(f"{MB(r['top'].get(k)):,.0f}" for k in tops) + " |")
for sect in ("blink_gc", "partition_alloc", "malloc", "skia", "font_caches", "blink_objects", "v8", "discardable"):
    keys = sorted({k for r in rows for k in r[sect]}, key=lambda k: -max(r[sect].get(k) or 0 for r in rows))[:24]
    if not keys: continue
    L.append(f"\n## {sect} (MB; blink_objects = counts)\n")
    L.append("| dump | " + " | ".join(k.replace(sect + "/", "") for k in keys) + " |"); L.append("|---|" + "---:|" * len(keys))
    for r in rows:
        L.append(f"| {r['tag'] or r['token_window']} | " + " | ".join((f"{(r[sect].get(k) or 0):,}" if sect == "blink_objects" else f"{MB(r[sect].get(k)):,.1f}") for k in keys) + " |")
L.append("\n## other processes (RSS MB per dump)\n")
for pname, lst in other.items():
    L.append(f"- {pname}: " + ", ".join(f"{x['tag'] or x['token_window']}={MB(x['totals'].get('resident_set_bytes')):,.0f}" for x in lst))
open(out + "-memdumps.md", "w").write("\n".join(L)); print("\n".join(L[:14]))
