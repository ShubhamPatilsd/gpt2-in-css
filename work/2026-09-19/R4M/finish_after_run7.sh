#!/bin/zsh
# R4M finisher (= R2H's with R4M/${BUNDLE:-combined7} paths): wait for run-${BUNDLE:-combined7}/DONE, then create READY + fill BUILD.md / R4M.md ONLY if ids == expected and verify rc == 0.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
BUNDLE=${1:-combined7}; out=$W/R4M/run-$BUNDLE; B=$W/bundles/$BUNDLE
log() { echo "- $(date '+%F %T') [R4M finisher] $*" >> $W/R4M.log.md; }
while [[ ! -f $out/DONE ]]; do sleep 30; done
sleep 2
python3 - "$out" "$B" "$W" "$BUNDLE" <<'PY'
import json, re, sys, pathlib
out, B, W = map(pathlib.Path, sys.argv[1:4]); BN = sys.argv[4]
exp = [11, 314, 1101, 7926, 11, 475, 314, 1101]
final = [json.loads(l) for l in (out / "harness.log").read_text().splitlines() if l.startswith("{") and '"event":"final"' in l]
metrics = [json.loads(l) for l in (out / "harness.log").read_text().splitlines() if l.startswith("{") and '"event":"metrics-after"' in l]
ids = final[0]["tokens"] if final else None
done = final[0]["doneMarkers"] if final else {}
tt = final[0].get("tokenTimes", {}) if final else {}
verify = (out / "verify.log").read_text() if (out / "verify.log").exists() else ""
loglines = [l for l in (W / "R4M.log.md").read_text().splitlines() if "[R4M correctness/" + BN + "] verify rc=" in l]
vrc = re.search(r"verify rc=(\d+)", loglines[-1]).group(1) if loglines else "?"
start = [l for l in (W / "R4M.log.md").read_text().splitlines() if "[R4M correctness/" + BN + "] START" in l]
power = re.search(r"power=(.*?) load=", start[-1]).group(1) if start else "?"
load = re.search(r"load=(.*)$", start[-1]).group(1) if start else "?"
m = metrics[0] if metrics else {}
ok = ids == exp and all(done.get(str(i)) for i in range(1, 9)) and vrc == "0"
agree = re.search(r"'tokenAgreement': \[[^\]]*\]", verify); resid = re.search(r"'finalResidualError': \{[^}]*\}", verify); text = re.search(r"'text': \"[^\"]*\"", verify)
times = ", ".join(f"{tt[str(i)]/1000:.1f}" for i in range(1, 9) if str(i) in tt)
section = f"""## Chrome correctness run

ONE passive run (NOT a timing run), `R4M/run_correctness.sh {BN}` (R3M's watchdog harness with R4M paths: owner marker, toucher killed before a marker-checked release; F4's
`correctness_run.mjs`: headless Chrome, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), under `CHROME.lock`.
Power: {power}; load {load}. Results in `work/2026-09-19/R4M/run-{BN}/`.

- ids **{ids}** ({'= required' if ids == exp else 'MISMATCH vs ' + str(exp)}), done markers {sum(1 for i in range(1, 9) if done.get(str(i)))}/8; `verify_browser_gpt2_runtime.py` rc={vrc}: {agree.group(0) if agree else '?'}, {resid.group(0) if resid else '?'}, {text.group(0) if text else '?'}.
- Whole-run counters (harness idle -> end): RecalcStyleCount {m.get('RecalcStyleCount')}, LayoutCount {m.get('LayoutCount')} (combined4: 985 / 629; R4S alone: 3,759 / 535 — with R4S the RecalcStyleCount includes interleaved container recalcs, R4S.md §6); Nodes {m.get('Nodes')}.
- Per-token capture times (5 s poll granularity — indicative only, not a timing run; combined4's run: 22.0, 17.1, 17.2, 18.0, 24.2, 17.8, 24.7, 17.6 = 158.6 s; R4S's: 23.4, 11.9, 17.1, 18.7, 17.6, 18.6, 19.8, 19.2 = 146.3 s): {times} s.
- READY: {'created' if ok else 'NOT created'}.
"""
b = (B / "BUILD.md").read_text()
b = re.sub(r"## Chrome correctness run\n\nPENDING[^\n]*\n\n", section + "\n", b, flags=re.S)
(B / "BUILD.md").write_text(b)
r = (W / "R4M.md").read_text()
r = r.replace("PENDING-CHROME7-SECTION", section.replace("## Chrome correctness run", "### 6.2 Chrome — combined7 (capacity 8) correctness run"))
(W / "R4M.md").write_text(r)
if ok:
    (B / "READY").write_text(f"{BN} READY {__import__('datetime').datetime.now():%F %T}: ids {ids} 8/8, verify rc 0, RecalcStyleCount {m.get('RecalcStyleCount')} LayoutCount {m.get('LayoutCount')}\n")
print("OK" if ok else "FAIL", ids, vrc, m.get("RecalcStyleCount"), m.get("LayoutCount"))
PY
rc=$?
log "finisher done: $(tail -1 $out/DONE 2>/dev/null) READY=$([[ -f $B/READY ]] && echo yes || echo no)"
