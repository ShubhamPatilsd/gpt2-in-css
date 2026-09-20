#!/bin/zsh
# R2H finisher: wait for run-combined3/DONE, then create READY + fill BUILD.md / R2H.md ONLY if ids == expected and verify rc == 0.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
out=$W/R2H/run-combined3; B=$W/bundles/combined3
log() { echo "- $(date '+%F %T') [R2H finisher] $*" >> $W/R2H.log.md; }
while [[ ! -f $out/DONE ]]; do sleep 30; done
sleep 2
python3 - "$out" "$B" "$W" <<'PY'
import json, re, sys, pathlib
out, B, W = map(pathlib.Path, sys.argv[1:4])
exp = [11, 314, 1101, 7926, 11, 475, 314, 1101]
final = [json.loads(l) for l in (out / "harness.log").read_text().splitlines() if l.startswith("{") and '"event":"final"' in l]
metrics = [json.loads(l) for l in (out / "harness.log").read_text().splitlines() if l.startswith("{") and '"event":"metrics-after"' in l]
ids = final[0]["tokens"] if final else None
done = final[0]["doneMarkers"] if final else {}
tt = final[0].get("tokenTimes", {}) if final else {}
verify = (out / "verify.log").read_text() if (out / "verify.log").exists() else ""
loglines = [l for l in (W / "R2H.log.md").read_text().splitlines() if "[R2H correctness/combined3] verify rc=" in l]
vrc = re.search(r"verify rc=(\d+)", loglines[-1]).group(1) if loglines else "?"
start = [l for l in (W / "R2H.log.md").read_text().splitlines() if "[R2H correctness/combined3] START" in l]
power = re.search(r"power=(.*?) load=", start[-1]).group(1) if start else "?"
load = re.search(r"load=(.*)$", start[-1]).group(1) if start else "?"
m = metrics[0] if metrics else {}
ok = ids == exp and all(done.get(str(i)) for i in range(1, 9)) and vrc == "0"
agree = re.search(r"'tokenAgreement': \[[^\]]*\]", verify); resid = re.search(r"'finalResidualError': \{[^}]*\}", verify); text = re.search(r"'text': \"[^\"]*\"", verify)
times = ", ".join(f"{tt[str(i)]/1000:.1f}" for i in range(1, 9) if str(i) in tt)
section = f"""## Chrome correctness run

ONE passive run (NOT a timing run), `R2H/run_correctness.sh combined3` (R2D's watchdog harness: wall cap, Chrome-exit watchdog, 30 s lock toucher; F4's
`correctness_run.mjs`: headless Chrome, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), under `CHROME.lock`.
Power: {power}; load {load}. Results in `work/2026-09-19/R2H/run-combined3/`.

- ids **{ids}** ({'= required' if ids == exp else 'MISMATCH vs ' + str(exp)}), done markers {sum(1 for i in range(1, 9) if done.get(str(i)))}/8; `verify_browser_gpt2_runtime.py` rc={vrc}: {agree.group(0) if agree else '?'}, {resid.group(0) if resid else '?'}, {text.group(0) if text else '?'}.
- Whole-run counters (harness idle -> end): RecalcStyleCount {m.get('RecalcStyleCount')}, LayoutCount {m.get('LayoutCount')} (R2F alone: 1,109 / 712; combined: 1,420 / 888); Nodes {m.get('Nodes')}.
- Per-token capture times (5 s poll granularity, battery, loaded machine — indicative only): {times} s.
- READY: {'created' if ok else 'NOT created'}.
"""
b = (B / "BUILD.md").read_text()
b = re.sub(r"## Chrome correctness run\n\nPENDING.*?\n\n", section + "\n", b, flags=re.S)
(B / "BUILD.md").write_text(b)
r = (W / "R2H.md").read_text()
r = r.replace("PENDING-CHROME-SECTION", section.replace("## Chrome correctness run", "## 4. Chrome correctness run"))
(W / "R2H.md").write_text(r)
if ok:
    (B / "READY").write_text(f"combined3 READY {__import__('datetime').datetime.now():%F %T}: ids {ids} 8/8, verify rc 0, RecalcStyleCount {m.get('RecalcStyleCount')} LayoutCount {m.get('LayoutCount')}\n")
print("OK" if ok else "FAIL", ids, vrc, m.get("RecalcStyleCount"), m.get("LayoutCount"))
PY
rc=$?
log "finisher done: $(tail -1 $out/DONE 2>/dev/null) READY=$([[ -f $B/READY ]] && echo yes || echo no)"
