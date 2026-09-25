#!/usr/bin/env python3
"""R5G pair analysis: <label>-ref vs <label>-flag (both bundles/combined7) from R5G/runs/combined7/*.json + R5G.log.md START/END lines.
Per run: per-token s, RSS max per token window, RSS at token 8, RSS peak, recalcs/layouts per token (1 Hz metricSamples differenced
at capture times, ±1 sample; 8-token totals exact), ids, vm_stat/swap before and after, the launch args actually used, V8 flag
warnings in stdout.log. usage: analyze_r5g.py <label> [<label> ...]  (label may carry a -rN retry suffix; the newest complete pair wins)"""
import glob, json, os, re, sys, statistics
W = "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19"
sys.path.insert(0, f"{W}/B0")
from summarize_run import summarize, EXPECTED
RUNS = f"{W}/R5G/runs/combined7"

def extras(path):
    R = json.load(open(path)); ev = R.get("tokenEvents", []); tRun = R["tRun"]
    rss = [s for s in R.get("rssSamples", []) if "rendererMaxMB" in s]
    ms = sorted(R.get("metricSamples", []), key=lambda m: m.get("tResp", 0))
    def rss_at(t):
        c = [s for s in rss if s["t"] <= t]; return c[-1]["rendererMaxMB"] if c else None
    def metric_at(t):
        c = [m for m in ms if m.get("tResp", 0) <= t]; return c[-1] if c else R.get("mBeforeRun") or {}
    rss_tok, rc_tok, lo_tok, rss_cap = [], [], [], []
    prev_t, prev_m = tRun, R.get("mBeforeRun") or {}
    for e in ev:
        t = e["tResp"]; win = [s["rendererMaxMB"] for s in rss if prev_t < s["t"] <= t]
        rss_tok.append(max(win) if win else rss_at(t)); rss_cap.append(rss_at(t))
        m = metric_at(t)
        rc_tok.append((m.get("RecalcStyleCount", 0) or 0) - (prev_m.get("RecalcStyleCount", 0) or 0))
        lo_tok.append((m.get("LayoutCount", 0) or 0) - (prev_m.get("LayoutCount", 0) or 0))
        prev_t, prev_m = t, m
    idle = [s["rendererMaxMB"] for s in rss if s["t"] <= tRun]
    post = [s["rendererMaxMB"] for s in rss if s["t"] > R["tEndWait"]]
    fps = [s for s in R.get("rssSamples", []) if s.get("footprintMB")]
    fp_tok = []; prev_t = tRun
    for e in ev:
        win = [s["footprintMB"] for s in fps if prev_t < s["t"] <= e["tResp"]]; fp_tok.append(max(win) if win else None); prev_t = e["tResp"]
    fp_gen = [s["footprintMB"] for s in fps if tRun <= s["t"] <= R["tEndWait"] + 3000]
    fp_idle = [s["footprintMB"] for s in fps if s["t"] <= tRun]
    st = R.get("settled") or {}
    return {"rssTok": rss_tok, "rssCap": rss_cap, "rss8": rss_at(ev[7]["tResp"]) if len(ev) >= 8 else None,
            "rcTok": rc_tok, "loTok": lo_tok, "rssIdle": idle[-1] if idle else None, "rssPost": post[-1] if post else None,
            "fpTok": fp_tok, "fpPeak": max(fp_gen) if fp_gen else None, "fpIdle": fp_idle[-1] if fp_idle else None,
            "rssSettled": st.get("rssMB"), "fpSettled": st.get("footprintMB"),
            "args": R.get("args"), "jsFlags": R.get("r5gJsFlags"), "extraArgs": R.get("r5gExtraArgs"), "loadMs": round(R["tLoad"] - R["tNav0"]),
            "styleTotal": (R.get("mAfterGen", {}).get("RecalcStyleDuration", 0) - R.get("mBeforeRun", {}).get("RecalcStyleDuration", 0)),
            "layoutTotal": (R.get("mAfterGen", {}).get("LayoutDuration", 0) - R.get("mBeforeRun", {}).get("LayoutDuration", 0)),
            "taskTotal": (R.get("mAfterGen", {}).get("TaskDuration", 0) - R.get("mBeforeRun", {}).get("TaskDuration", 0))}

def loglines(label):
    o = {"start": [], "end": []}
    for ln in open(f"{W}/R5G.log.md"):
        if f"[combined7/{label}]" not in ln: continue
        if " START " in ln: o["start"].append(ln.strip())
        if " END " in ln: o["end"].append(ln.strip())
    return o

def warnings(label):
    p = f"{RUNS}/{label}.stdout.log"
    if not os.path.exists(p): return []
    out = []
    for ln in open(p, errors="replace"):
        if re.search(r"unrecognized flag|non-writable|Warning|Error:|contradictory|cannot be set", ln) and "pw:browser" in ln: out.append(ln.strip()[:200])
    return out[:6]

def run(label):
    p = f"{RUNS}/{label}.json"
    if not os.path.exists(p): return None
    s = summarize(p); x = extras(p); lg = loglines(label)
    return {"label": label, "s": s, **x, "log": lg, "warn": warnings(label)}

def vm_from(lines):
    for ln in lines:
        m = re.search(r"vm_stat: (.*)", ln)
        if m: return m.group(1)[:220]
    return "–"
def swap_from(lines):
    for ln in lines:
        m = re.search(r"swap_used_MB=(\d+)", ln)
        if m: return m.group(1)
    return "–"

def fmt_run(r, tag):
    s = r["s"]
    return (f"| {tag} | {r['label']} | {s['idsOk']} | {' '.join(f'{x:.1f}' for x in s['perToken'])} | {s['median']} | {s['total']} | {r['rssIdle']} | "
            f"{' '.join(str(v) for v in r['rssTok'])} | {r['rss8']} | {s['rssPeakGenMB']} | {r['rssPost']} | {' '.join(str(v) for v in r['rcTok'])} (Σ {s['cdp']['recalcs']}) | "
            f"{' '.join(str(v) for v in r['loTok'])} (Σ {s['cdp']['layouts']}) | {s['cdp']['style_s']} / {s['cdp']['layout_s']} / {s['cdp']['task_s']} | {r['loadMs']} | "
            f"{swap_from(r['log']['start'])} → {swap_from(r['log']['end'])} | {r['fpIdle']} | {' '.join(str(v) for v in r['fpTok'])} | {r['fpPeak']} | {r['rssSettled']} / {r['fpSettled']} |")

def main(labels):
    for label in labels:
        cands = sorted([l for l in [label] + [os.path.basename(p)[:-10] for p in glob.glob(f"{RUNS}/{label}-r*-flag.json")]],
                       key=lambda l: os.path.getmtime(f"{RUNS}/{l}-flag.json") if os.path.exists(f"{RUNS}/{l}-flag.json") else 0)
        base = cands[-1]
        ref, fl = run(f"{base}-ref"), run(f"{base}-flag")
        print(f"## R5G pair `{base}` — combined7 no-flag reference, then combined7 + flags (same CHROME.lock hold)\n")
        if not ref or not fl:
            print(f"incomplete: ref={'ok' if ref else 'MISSING'} flag={'ok' if fl else 'MISSING'}\n"); continue
        print(f"- flag arm launch args: js-flags=`{fl['jsFlags']}` extra=`{' '.join(fl['extraArgs'] or []) or '(none)'}`; ref arm: js-flags=`{ref['jsFlags']}` extra=`{' '.join(ref['extraArgs'] or []) or '(none)'}`")
        print(f"- Chrome stderr flag warnings (flag arm): {'; '.join(fl['warn']) if fl['warn'] else 'none'}; (ref arm): {'; '.join(ref['warn']) if ref['warn'] else 'none'}")
        print(f"- vm_stat before ref: {vm_from(ref['log']['start'])}\n- vm_stat after ref: {vm_from(ref['log']['end'])}\n- vm_stat before flag: {vm_from(fl['log']['start'])}\n- vm_stat after flag: {vm_from(fl['log']['end'])}\n")
        print("| arm | label | ids | per-token s (1–8) | median s/tok | total s | RSS idle MB | RSS max per token MB (1–8) | RSS@tok8 MB | RSS peak MB | RSS after MB | recalcs per token | layouts per token | style / layout / task s (CDP) | load ms | swap used MB START→END | footprint idle MB | footprint max per token MB (1–8, 5 s samples) | footprint peak MB | settled 10 s after token 8: RSS / footprint MB |")
        print("|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|---|---:|---|---:|---|---:|---|")
        print(fmt_run(ref, "ref")); print(fmt_run(fl, "flag"))
        rs, fs_ = ref["s"], fl["s"]
        dper = [b - a for a, b in zip(rs["perToken"], fs_["perToken"])]
        same_passes = (rs["cdp"]["recalcs"] == fs_["cdp"]["recalcs"] and rs["cdp"]["layouts"] == fs_["cdp"]["layouts"])
        drss_tok = [(b - a) if (a is not None and b is not None) else None for a, b in zip(ref["rssTok"], fl["rssTok"])]
        print(f"\nPAIR {base}: Δ RSS peak {fs_['rssPeakGenMB'] - rs['rssPeakGenMB']:+d} MB ({rs['rssPeakGenMB']} → {fs_['rssPeakGenMB']}); "
              f"Δ RSS@tok8 {(fl['rss8'] or 0) - (ref['rss8'] or 0):+d} MB ({ref['rss8']} → {fl['rss8']}); Δ RSS per token {' '.join(f'{d:+d}' for d in drss_tok if d is not None)}; "
              f"Δ median {fs_['median'] - rs['median']:+.1f} s/tok ({rs['median']} → {fs_['median']}); Δ total {fs_['total'] - rs['total']:+.1f} s ({rs['total']} → {fs_['total']}); "
              f"Δ per token {' '.join(f'{d:+.1f}' for d in dper)}; Δ style {fl['styleTotal'] - ref['styleTotal']:+.1f} s, Δ layout {fl['layoutTotal'] - ref['layoutTotal']:+.1f} s, Δ task {fl['taskTotal'] - ref['taskTotal']:+.1f} s; "
              f"Δ load {fl['loadMs'] - ref['loadMs']:+d} ms ({ref['loadMs']} → {fl['loadMs']}); "
              + (f"Δ footprint peak {fl['fpPeak'] - ref['fpPeak']:+d} MB ({ref['fpPeak']} → {fl['fpPeak']}); " if (fl['fpPeak'] and ref['fpPeak']) else "footprint: n/a (harness before 16:40); ")
              + (f"Δ settled RSS {fl['rssSettled'] - ref['rssSettled']:+d} MB ({ref['rssSettled']} → {fl['rssSettled']}), Δ settled footprint {(fl['fpSettled'] or 0) - (ref['fpSettled'] or 0):+d} MB ({ref['fpSettled']} → {fl['fpSettled']}); " if (fl['rssSettled'] and ref['rssSettled']) else "")
              + f"passes {'IDENTICAL' if same_passes else 'DIFFER'} (recalcs {rs['cdp']['recalcs']} vs {fs_['cdp']['recalcs']}, layouts {rs['cdp']['layouts']} vs {fs_['cdp']['layouts']}); ids ref {rs['idsOk']} flag {fs_['idsOk']}; "
              f"contended ref '{rs['contended']}' flag '{fs_['contended']}'\n")

if __name__ == "__main__":
    main(sys.argv[1:])
