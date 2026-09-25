#!/bin/zsh
# R5M finisher (R4M/finish_after_run7.sh pattern): wait for run-R5M-run1/DONE, then create READY + append §5 to R5M.md and BUILD.md ONLY if ids == expected and verify rc == 0.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; out=$W/R5M/run-R5M-run1; B=$W/bundles/R5M
log() { echo "- $(date '+%F %T') [R5M finisher] $*" >> $W/R5M.log.md; }
while [[ ! -f $out/DONE ]]; do sleep 30; done; sleep 2
python3 - "$out" "$B" "$W" <<'PY'
import json, re, sys, pathlib, glob, os
out, B, W = map(pathlib.Path, sys.argv[1:4])
exp = [11, 314, 1101, 7926, 11, 475, 314, 1101]
lines = (out / "harness.log").read_text().splitlines() if (out / "harness.log").exists() else []
ev = [json.loads(l) for l in lines if l.startswith("{")]
final = next((e for e in ev if e.get("event") == "final"), None)
caps = [e for e in ev if e.get("event") == "token-captured"]
idle = next((e for e in ev if e.get("event") == "pre-run-idle"), {})
ids = final["tokens"] if final else None; done = final["doneMarkers"] if final else {}
tt = final.get("tokenTimes", {}) if final else {}
loglines = (W / "R5M.log.md").read_text().splitlines()
vl = [l for l in loglines if "[R5M correctness/R5M/run1] verify rc=" in l]; vrc = re.search(r"verify rc=(\d+)", vl[-1]).group(1) if vl else "?"
st = [l for l in loglines if "[R5M correctness/R5M/run1] START" in l]; startinfo = st[-1][:400] if st else "?"
verify = (out / "verify.log").read_text() if (out / "verify.log").exists() else ""
agree = re.search(r"'tokenAgreement': \[[^\]]*\]", verify); resid = re.search(r"'finalResidualError': \{[^}]*\}", verify); text = re.search(r"'text': \"[^\"]*\"", verify)
rss = json.loads((out / "rss.json").read_text()) if (out / "rss.json").exists() else {}
peak = rss.get("peakMB"); tokrss = ", ".join(f"{c['token']}:{c.get('rssMB')}" for c in caps)
times = ", ".join(f"{tt[str(i)]/1000:.1f}" for i in range(1, 9) if str(i) in tt)
deltas = []; prev = 0
for i in range(1, 9):
    if str(i) in tt: deltas.append(f"{(tt[str(i)] - prev)/1000:.1f}"); prev = tt[str(i)]
ok = ids == exp and all(done.get(str(i)) for i in range(1, 9)) and vrc == "0"
# fx3 table rows
fx = []
for name in ("dom-50k-inline", "dom-50k-inline-props", "head50k-vars-gen", "head50k-literal-gen", "head50k-nowall-gen"):
    p = W / "R5M/fx-results" / f"{name}.json"
    if not p.exists(): fx.append(f"| {name} | not run |"); continue
    d = json.loads(p.read_text()); s = {r["tag"]: r for r in d["steps"]}; b = s["blank"]["rssMB"]; l = s["loaded"]
    gens = [r for r in d["steps"] if r["tag"].startswith("gen")]; pv = l["rssMB"]; g = []
    for r in gens: g.append(f"{r['rssMB']-pv:+d} ({r['styleMs']-pv_style if False else r['styleMs']} ms style cum.)"); pv = r["rssMB"]
    gc = s.get("afterGC", {}).get("rssMB"); pr = s.get("afterPressure", {}).get("rssMB")
    fx.append(f"| {name} | {d['loadMs']} | {l['rssMB']-b:+d} | {' / '.join(g)} | {gc} | {pr} | {l['layoutObjects']} |")
sec = f"""
### 5.1 Results (appended by `R5M/finish_after_run.sh`)

fx3 fixtures (`R5M/fx-results/*.json`; RSS MB vs blank tab; gens = successive `--head-fvs` changes on the real 50 k-row head):

| fixture | load ms | Δ loaded | Δ per gen | after GC | after pressure | layoutObjects |
|---|---:|---:|---|---:|---:|---:|
{chr(10).join(fx)}

Correctness run `R5M/run_correctness.sh R5M run1` ({startinfo}):
- ids **{ids}** ({'= required' if ids == exp else 'MISMATCH vs ' + str(exp)}), done markers {sum(1 for i in range(1, 9) if done.get(str(i)))}/8; `verify_browser_gpt2_runtime.py` rc={vrc}: {agree.group(0) if agree else '?'}, {resid.group(0) if resid else '?'}, {text.group(0) if text else '?'}.
- Per-token capture times (5 s poll, indicative): {times} s → per token {', '.join(deltas)} s (combined7's R4M correctness run: 22.6, 11.0, 18.2, 16.9, 19.3, 20.4, 20.3, 18.1 = 146.8 s).
- Renderer RSS (MB): pre-run idle {idle.get('rssMB')}, at token captures {tokrss}, **peak {peak}** (combined7 before: idle 1,846–2,033, token 1 3.5–3.9 GB, peak 5.7–6.0 GB in B5's clean-state runs; 4.3 GB in R5A's swap-pressured run — compare within one memory state only, B6 pairs).
- READY: {'created' if ok else 'NOT created'}.
"""
(W / "R5M.md").write_text((W / "R5M.md").read_text() + sec)
(B / "BUILD.md").write_text((B / "BUILD.md").read_text() + sec)
if ok: (B / "READY").write_text(f"R5M correctness run1: ids {ids} 8/8, verify rc 0, RSS peak {peak} MB; see R5M.md §5.1\n")
print("READY" if ok else "NOT READY", ids, vrc, peak)
PY
log "finisher: $(ls $B/READY 2>/dev/null && echo READY created || echo no READY) — §5.1 appended to R5M.md and BUILD.md"
