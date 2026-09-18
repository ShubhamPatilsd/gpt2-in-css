#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Native 768-value feedback comparison; no page or harness JavaScript.

Run under run_unconventional_isolated.py. This is a handoff/recurrence probe,
not a transformer or a token-speed benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import time

from build_hybrid_twelve_block import regs
from probe_native_reused_loop import loop_parts
from probe_native_value_latch import navigate, props
from profile_hybrid_twelve_block import browser, error, metrics, query

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/style-simplification-review/selective-loop"
WIDTH = 768
PREFIXES = (1, 2, 3, 4, 8, 24)
MAX_ERROR = .003
PAIR_MAX = .0001


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(steps):
    values = [(i % 31 - 15) / 64 for i in range(WIDTH)]
    history = [values]
    for step in range(1, steps + 1):
        values = [-.5 * x + ((i * 13) % 37 - 18) / 128 + (step % 3) / 32
                  for i, x in enumerate(values)]
        history.append(values)
    return history


def scoped_loop(css, steps):
    """Mirror the runtime's private loop fields and local control transport."""
    lp = [f"--lp-{bank}-{i}" for bank in range(2) for i in range(WIDTH + 1)]
    saved = [f"--saved-{bank}-{i}" for bank in range(2) for i in range(WIDTH + 1)]
    outputs = [f"--loop-out-{i}" for i in range(WIDTH)]
    private = set(lp + saved + outputs)
    private.update(("--pass", "--loop-phase", "--loop-captured-pass", "--loop-held"))
    css = re.sub(r"@property (--[\w-]+)\{[^{}]+\}",
                 lambda m: m[0].replace("inherits:true", "inherits:false")
                 if m[1] in private else m[0], css)

    def forward(selector, names):
        return selector + "{" + ";".join(f"{p}:inherit" for p in names) + "}"

    css += forward(".loop-input", lp)
    css += forward(".loop-bank-0,.loop-bank-1", outputs)
    css += forward(".loop-scroll,.loop-track", saved)
    for bank in range(2):
        for i in range(WIDTH + 1):
            css += forward(f".loop-bank-{bank}>.loop-scroll>.loop-track>.loop-metric:nth-child({i+1})",
                           [f"--saved-{bank}-{i}"])
    css = css.replace("var(--pass)", "var(--native-pass)")
    css = re.sub(r"body\{[^{}]*\}",
                 lambda m: m[0].replace("var(--native-pass)", "var(--pass)"), css)
    css += regs(["--native-pass"])
    for step in range(1, steps + 1):
        css += f"@container loopcontrol style(--pass:{step}){{.core-block{{--native-pass:{step}}}}}"
    css = re.sub(r"\bbody(?=[{:\s])", ".core-controller", css)
    css = re.sub(r"\.core-controller:has\((#[^)]+)\)",
                 r".core-controller:where(:has(\1))", css)
    return css


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    sources = [Path(__file__), ROOT / "tools/probe_native_reused_loop.py",
               ROOT / "tools/browser_gpt2_reused_core.py", ROOT / "tools/browser_gpt2_reused_adapter.py",
               ROOT / "tools/profile_hybrid_twelve_block.py", ROOT / "tools/probe_native_value_latch.py",
               ROOT / "tools/build_hybrid_twelve_block.py"]
    source_dir = OUT / "sources"
    source_dir.mkdir(exist_ok=True)
    for path in sources:
        destination = source_dir / path.name
        if destination.exists() and destination.read_bytes() != path.read_bytes():
            raise ValueError(f"Preserve prior source snapshot: {destination}")
        destination.write_bytes(path.read_bytes())
    fixtures = []
    for steps in PREFIXES:
        for variant in ("baseline", "selective"):
            directory = OUT / "fixtures" / f"{variant}-p{steps}"
            directory.mkdir(parents=True, exist_ok=True)
            source, output, css = loop_parts(WIDTH, steps, centered=True, selective=variant == "selective")
            css = scoped_loop(css, steps)
            css += ".core-block{" + ";".join(f"--initial-{i}:{x}" for i, x in enumerate(reference(0)[0])) + "}"
            css += ".compute{" + ";".join(
                f"--loop-out-{i}:calc(-.5 * var(--loop-in-{i}) + ({((i*13)%37-18)/128}) + mod(var(--native-pass),3) / 32)"
                for i in range(WIDTH)) + ";width:1px;height:1px}"
            body = source.replace("{child}", '<div class="compute">' + output.replace("{child}", '<i id="result"></i>') + "</div>")
            page = ('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
                    'content="script-src \'none\';object-src \'none\'"><link rel="stylesheet" href="style.css">'
                    '<body><div class="core-controller"><div class="core-block">' + body + '</div></div></body>')
            for name, contents in (("index.html", page), ("style.css", css)):
                target = directory / name
                if target.exists() and target.read_text() != contents:
                    raise ValueError(f"Refusing changed existing fixture {target}")
                target.write_text(contents)
            fixtures.append({"variant": variant, "steps": steps,
                             "directory": str(directory.relative_to(ROOT)),
                             "hashes": {name: digest(directory/name) for name in ("index.html", "style.css")}})
    manifest = {
        "scope": "Native full-width bank handoff with deterministic recurrent arithmetic; no GPT-2 matrices, KV, vocabulary, or token feedback.",
        "width": WIDTH, "gatePrefixes": list(PREFIXES), "timingSteps": 24,
        "runtimeJavaScript": False, "harnessJavaScript": False, "externalWritesAfterNavigation": 0,
        "scopeMatch": "Existing loop_parts, centered readback, private progress/saved/output fields and local pass controller as in reused native core. Numeric transform is a synthetic recurrence.",
        "oracleMaximumErrorLimit": MAX_ERROR, "pairedMaximumDifferenceLimit": PAIR_MAX,
        "timingProtocol": "Four fresh-process pairs, AB/BA/AB/BA. DOM-only capture queries every20ms. No computed-style or geometry reads until native completion. Report navigation interval and observed first-capture-to-final window separately; renderer counters accompany both.",
        "sourceHashes": {str(p.relative_to(ROOT)): digest(p) for p in sources}, "fixtures": fixtures,
    }
    save(OUT / "manifest.json", manifest)
    print(json.dumps({"prepared": len(fixtures), "width": WIDTH}), flush=True)


def count_captures(cdp):
    return len(cdp.command("DOM.querySelectorAll", {"nodeId": cdp.root_node,
               "selector": '[id^="loop-captured-"].done'})["nodeIds"])


def run_case(fixture, destination, delay=0):
    if destination.exists():
        raise FileExistsError(f"Preserving {destination}")
    destination.mkdir(parents=True)
    directory = ROOT / fixture["directory"]
    for name, expected in fixture["hashes"].items():
        assert digest(directory/name) == expected
    steps = fixture["steps"]
    result = {**fixture, "passed": False, "completionEvents": [],
              "externalWritesAfterNavigation": 0, "observerDelaySeconds": delay}
    try:
        with browser(["--js-flags=--heap-growing-percent=10"]) as cdp:
            cdp.connection.settimeout(60)
            result["browser"] = cdp.command("Browser.getVersion")
            before = metrics(cdp)
            start = time.perf_counter()
            navigate(cdp, directory/"index.html", ".compute", observe_after_seconds=delay, limit=60)
            first_time, first_metrics, last_count = None, None, 0
            deadline = time.monotonic() + 90
            count = 0
            while time.monotonic() < deadline:
                count = count_captures(cdp)
                now = time.perf_counter()
                if count != last_count:
                    result["completionEvents"].append({"completedPasses": count, "milliseconds": (now-start)*1000})
                    last_count = count
                if count and first_time is None:
                    first_time = now
                    result["firstObservedCompletedPasses"] = count
                    first_metrics = metrics(cdp)
                if count == steps:
                    break
                time.sleep(.02)
            finish = time.perf_counter()
            after = metrics(cdp)
            result["completed"] = count == steps
            result["navigationToCompletionMilliseconds"] = (finish-start)*1000
            if first_time is not None:
                result["observedContinuationMilliseconds"] = (finish-first_time)*1000
                result["continuationPassCount"] = steps - result["firstObservedCompletedPasses"]
            counter_names = [k for k in after if k.endswith(("Duration", "Count"))]
            result["rendererDelta"] = {k: after[k]-before.get(k,0) for k in counter_names}
            if first_metrics:
                result["continuationRendererDelta"] = {k: after[k]-first_metrics.get(k,0) for k in counter_names}
            if not result["completed"]:
                raise TimeoutError(f"Native loop completed {count}/{steps} passes")
            # All full-vector reads happen after the timing/renderer snapshots.
            expected = reference(steps)
            checks = []
            actual_by_name = {}
            for name, selector, stem, target in (
                ("output", ".compute", "--loop-out-", expected[-1]),
                ("input", ".loop-input", "--loop-in-", expected[-2]),
            ):
                p = props(cdp, query(cdp, selector))
                actual = [float(p[f"{stem}{i}"]) for i in range(WIDTH)]
                actual_by_name[name] = actual
                checks.append({"name": name, **error(actual, target)})
            stamps = []
            for bank in range(2):
                p = props(cdp, query(cdp, f".loop-bank-{bank}"))
                epoch = steps if bank == (steps-1)%2 else steps-1
                actual = [float(p[f"--saved-{bank}-{i}"]) for i in range(WIDTH)]
                target = expected[epoch] if epoch else [0.0]*WIDTH
                actual_by_name[f"bank{bank}"] = actual
                checks.append({"name": f"bank{bank}", **error(actual, target)})
                stamps.append({"bank": bank, "expected": epoch, "actual": float(p[f"--saved-{bank}-{WIDTH}"])})
            result["checks"] = checks
            result["stamps"] = stamps
            result["actual"] = actual_by_name
            result["passed"] = all(c["maximum"] is not None and c["maximum"] <= MAX_ERROR for c in checks) and all(abs(s["actual"]-s["expected"]) <= .001 for s in stamps)
    except Exception as exc:
        result["exception"] = f"{type(exc).__name__}: {exc}"
    save(destination/"results.json", result)
    print(json.dumps({k:v for k,v in result.items() if k not in ("actual", "hashes", "rendererDelta", "continuationRendererDelta", "completionEvents", "browser")}), flush=True)
    return result


def compare(a, b):
    values = [abs(x-y) for name in a["actual"] for x,y in zip(a["actual"][name],b["actual"][name],strict=True)]
    return {"maximumDifference": max(values), "passed": max(values) <= PAIR_MAX}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "gate", "timing", "summary"))
    parser.add_argument("--attempt", default="r0")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
        return
    manifest = json.loads((OUT/"manifest.json").read_text())
    fixtures = {(f["variant"],f["steps"]):f for f in manifest["fixtures"]}
    group = OUT/f"{args.mode}-{args.attempt}"
    if args.mode == "gate":
        rows, pairs = [], []
        for steps in PREFIXES:
            baseline = run_case(fixtures["baseline",steps], group/f"baseline-p{steps}")
            rows.append(baseline)
            if not baseline["passed"]:
                break
            candidate = run_case(fixtures["selective",steps], group/f"selective-p{steps}")
            rows.append(candidate)
            if not candidate["passed"]:
                break
            pairs.append({"steps":steps, **compare(baseline,candidate)})
            if not pairs[-1]["passed"]:
                break
        complete = len(rows)==2*len(PREFIXES) and all(r["passed"] for r in rows) and all(p["passed"] for p in pairs)
        report = {"passed":complete, "manifestSha256":digest(OUT/"manifest.json"), "pairs":pairs,
                  "rows":[{k:v for k,v in r.items() if k!="actual"} for r in rows],
                  "coordinateChecks":sum(len(r.get("checks",[]))*WIDTH for r in rows)}
        save(group/"results.json",report)
        if not complete:
            raise SystemExit("Correctness gate failed; no timing allowed")
    elif args.mode == "timing":
        gate_path=OUT/f"gate-{args.attempt}"/"results.json"
        gate=json.loads(gate_path.read_text())
        assert gate["passed"] and gate["manifestSha256"]==digest(OUT/"manifest.json")
        rows=[]
        for rep in range(4):
            order=("baseline","selective") if rep%2==0 else ("selective","baseline")
            pair={}
            for variant in order:
                row=run_case(fixtures[variant,24],group/f"pair{rep}-{variant}")
                row["pair"]=rep
                rows.append(row)
                pair[variant]=row
                save(group/"progress.json", {"passed":False,"rows":[{k:v for k,v in r.items() if k!="actual"} for r in rows]})
                if not row["passed"]:
                    raise SystemExit("Timed output correctness failed")
            assert compare(pair["baseline"],pair["selective"])["passed"]
        save(group/"results.json", {"passed":True,"gateSha256":digest(gate_path),
                                    "rows":[{k:v for k,v in r.items() if k!="actual"} for r in rows]})
    else:
        report=json.loads((OUT/f"timing-{args.attempt}"/"results.json").read_text())
        assert report["passed"]
        pairs=[]
        for rep in range(4):
            rows={r["variant"]:r for r in report["rows"] if r["pair"]==rep}
            a,b=rows["baseline"],rows["selective"]
            pair={"pair":rep,"baselineMilliseconds":a["navigationToCompletionMilliseconds"],
                  "selectiveMilliseconds":b["navigationToCompletionMilliseconds"],
                  "ratio":b["navigationToCompletionMilliseconds"]/a["navigationToCompletionMilliseconds"]}
            if a.get("firstObservedCompletedPasses")==b.get("firstObservedCompletedPasses")==1:
                pair.update(baselineContinuationMilliseconds=a["observedContinuationMilliseconds"],
                            selectiveContinuationMilliseconds=b["observedContinuationMilliseconds"],
                            continuationRatio=b["observedContinuationMilliseconds"]/a["observedContinuationMilliseconds"])
            pairs.append(pair)
        summary={"scope":manifest["scope"],"pairs":pairs,
                 "medianNavigationRatio":statistics.median(p["ratio"] for p in pairs),
                 "allNavigationPairsFavorSelective":all(p["ratio"]<1 for p in pairs),
                 "warning":"DOM observation timing includes polling and process variation. This synthetic native recurrence does not establish token speed."}
        save(OUT/f"summary-{args.attempt}.json",summary)
        print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    main()
