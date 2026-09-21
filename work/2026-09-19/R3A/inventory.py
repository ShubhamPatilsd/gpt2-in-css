#!/usr/bin/env python3
"""R3A: inventory of (cat, name, ph) on the renderer main thread of a gzip trace: count, sum dur. Streams the whole file.
usage: inventory.py trace.json.gz out.tsv [max_events]"""
import gzip, json, sys, collections, time
path, out = sys.argv[1], sys.argv[2]; maxev = int(sys.argv[3]) if len(sys.argv) > 3 else 0
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
ult = collections.Counter(); rows = collections.defaultdict(lambda: [0, 0]); n = 0
tmin = None; tmax = None
for e in events(path):
    n += 1
    if maxev and n > maxev: break
    if n % 5_000_000 == 0: print(n, f"{time.time()-T0:.0f}s", file=sys.stderr, flush=True)
    nm = e.get("name"); ph = e.get("ph")
    if nm == "UpdateLayoutTree": ult[(e.get("pid"), e.get("tid"))] += 1
    key = (e.get("pid"), e.get("tid"), e.get("cat"), nm, ph)
    r = rows[key]; r[0] += 1; r[1] += e.get("dur", 0) if ph == "X" else 0
    ts = e.get("ts")
    if ts: tmin = ts if tmin is None or ts < tmin else tmin; tmax = ts if tmax is None or ts > tmax else tmax
(PID, TID), _ = ult.most_common(1)[0]
with open(out, "w") as f:
    f.write(f"# events {n}; main pid {PID} tid {TID}; ts range {tmin}..{tmax} ({(tmax-tmin)/1e6:.1f} s)\n")
    f.write("pid\ttid\tmain\tcat\tname\tph\tcount\tsum_dur_ms\n")
    for (pid, tid, cat, nm, ph), (c, d) in sorted(rows.items(), key=lambda kv: -kv[1][0]):
        f.write(f"{pid}\t{tid}\t{int(pid==PID and tid==TID)}\t{cat}\t{nm}\t{ph}\t{c}\t{d/1000:.1f}\n")
print("done", n, f"{time.time()-T0:.0f}s", file=sys.stderr)
