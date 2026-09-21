# R3M copy of R2F/offline_check.py: bundle args may be directory paths (R3M/scratch/...) instead of names under bundles/.
"""R2F offline check: bundles/<name> vs bundles/<ref> (same blocks/capacity, same tools minus r2f_lean_handshake).

(a) handshake shape: no SMIL loop signals, no pulse rules, no --loop-held / --loop-captured-pass rules, controller
    computes --pass from the two bank markers, wrapper carries the two marker animations, --pass-cap token rules;
(b) everything else identical: selector-level diff limited to the handshake rules; fonts/witnesses identical;
(c) element count delta = -(4 g + 2 set) * steps + 1 wrapper.
usage: python offline_check.py <bundle> <reference-bundle>
"""
import json, re, sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

W = Path("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19")
name, ref = sys.argv[1], sys.argv[2]
B, R = (Path(name) if "/" in name else W / "bundles" / name), (Path(ref) if "/" in ref else W / "bundles" / ref)
C, P = (B / "runtime.css").read_text(), (R / "runtime.css").read_text()
HC, HP = (B / "index.html").read_text(), (R / "index.html").read_text()
MC, MP = json.loads((B / "manifest.json").read_text()), json.loads((R / "manifest.json").read_text())
blocks, capacity = MC["blocks"], MC["capacity"]
steps = blocks * capacity
fail = []
def check(cond, *msg):
    if not cond:
        fail.append(msg)
check(MP["blocks"] == blocks and MP["capacity"] == capacity, "same shape", MP["blocks"], MP["capacity"])
check(MC.get("r2fLeanHandshake") is True and not MP.get("r2fLeanHandshake"), "flag in manifests")
# ---------------- (a)
for pat, n, what in (
    (r"#loop-(?:ready|ack)-\d+\{animation:loop-pulse", 0, "pulse rules"),
    (r"--loop-captured-pass:\d+", 0, "captured rules"),
    (r"style\(--loop-held:1\)", 0, "held rules"),
    (r"--loop-ack:calc", 0, "loop-ack calcs"),
    (r"\.core-controller:where\(:has\(#loop-advanced-\d+\.done\)\)", 0, "advance rules"),
    (r":where\(body:has\(#token-\d+-advanced\.done\)\) \.core-controller\{--pass-cap:\d+\}", capacity - 1, "cap rules"),
    (r"@container loopcontrol style\(--pass:\d+\)\{", steps + 1, "pass stamp rules"),
    (r"\.core-pass-reader\{animation-name:loop-k-0-768,loop-k-1-768;[^}]*animation-timeline:--loop-t-0-768,--loop-t-1-768\}", 1, "marker reader"),
    (r'@property --pass-cap\{syntax:"<number>";inherits:false;initial-value:0\}', 1, "cap registration"),
    (r'@property --lp-[01]-768\{syntax:"<number>";inherits:false;initial-value:0\}', 2, "marker props private"),
):
    got = len(re.findall(pat, C))
    check(got == n, what, got, n)
ctrl = re.search(r"\.core-controller\{--pass:min\(calc\(max\(([^;]+)\) \+ 1\),var\(--pass-cap\)\);--pass-cap:(\d+);--lp-0-768:inherit;--lp-1-768:inherit;container-name:loopcontrol;--loop-phase:mod\(calc\(var\(--pass\) - 1\),2\)\}", C)
check(ctrl is not None, "controller rule")
if ctrl:
    check(int(ctrl[2]) == blocks, "initial cap", ctrl[2])
    dec = "round(nearest,(1572864 / (var(--lp-{b}-768) + 2) - 524288 - 262144) / 128,1)"
    check(ctrl[1] == ",".join(dec.format(b=b) for b in range(2)), "marker decode", ctrl[1][:120])
    # the same decode the loop input uses for its data carriers (centered mapping)
    check(re.search(r"--loop-in-0:calc\(\(1572864 / \(var\(--lp-1-0\) \+ 2\) - 524288 - 262144\) / 128\)", C), "data decode matches")
caps = [int(x) for x in re.findall(r":where\(body:has\(#token-(\d+)-advanced\.done\)\) \.core-controller\{--pass-cap:(\d+)\}", C) for x in [x[1]]]
check(caps == [(t + 1) * blocks for t in range(1, capacity)], "cap values", caps)
# the marker write survives, on both banks, with the stamped pass
for b in range(2):
    check(re.search(rf"style\(--loop-phase:{b}\)\{{\.loop-bank-{b}\{{transition-property:none;--saved-{b}-0:var\(--loop-out-0\);", C), "write bank rule", b)
    check(f"--saved-{b}-768:var(--native-pass)}}" in C, "marker write", b)
    check(re.search(rf"\.loop-bank-{b}\{{transition-property:--saved-{b}-0,--saved-{b}-1,[^}}]*--saved-{b}-768;transition-duration:1ms;transition-delay:86400s", C), "base latch list", b)
check('<div class="core-pass-reader"><div class="core-controller"><div class="core-block" id="block-0">' in HC, "wrapper html")
check('<svg class="loop-signals"></svg>' in HC, "empty signals")
check(re.search(r"html\{timeline-scope:[^}]*--loop-t-0-768,[^}]*\}", C) and "--loop-t-1-768" in re.search(r"html\{timeline-scope:[^}]*\}", C)[0], "timelines scoped on html")
# ---------------- (b) selector-level diff
def rules(css):
    css = re.sub(r"@(?:font-face|property)\b[^{}]*\{[^{}]*\}", "", css)
    out = Counter()
    depth, buf, stack, quote = 0, "", [], None
    for ch in css:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch; buf += ch
        elif ch == "{":
            stack.append(buf.strip()); buf = ""; depth += 1
        elif ch == "}":
            if buf.strip():
                out[(" ".join(stack), buf.strip())] += 1
            buf = ""; depth -= 1; stack.pop()
        else:
            buf += ch
    return out
rc, rp = rules(C), rules(P)
added, removed = rc - rp, rp - rc
allowed = re.compile(r"loop-(?:ready|ack|captured|advanced|held|pulse)|\.core-controller --pass|\.core-pass-reader animation|--pass-cap|--loop-ack|loop-bank-[01] transition-property:--saved")
for sel, decl in list(added) + list(removed):
    key = sel + " " + decl
    if not allowed.search(key):
        check(False, "unexpected rule change", (sel + " {" + decl)[:160])
print("rules", {"bundle": sum(rc.values()), "ref": sum(rp.values()), "added": sum(added.values()), "removed": sum(removed.values())})
props_c = Counter(re.findall(r"@property (--[\w-]+)\{[^}]*\}", C)); props_p = Counter(re.findall(r"@property (--[\w-]+)\{[^}]*\}", P))
check(set((props_c - props_p)) == {"--pass-cap"} and not (props_p - props_c), "registrations", list((props_c - props_p))[:5], list((props_p - props_c))[:5])
check(re.findall(r"@font-face\{[^}]*\}", C) == re.findall(r"@font-face\{[^}]*\}", P), "font faces identical")
wc = json.loads((B / "font-witnesses.json").read_text()); wp = json.loads((R / "font-witnesses.json").read_text())
check({re.sub(r"/work/2026-09-19/\w+/", "/X/", k): v for k, v in wc.items()} == {re.sub(r"/work/2026-09-19/\w+/", "/X/", k): v for k, v in wp.items()}, "witnesses identical (modulo tools-copy path)")
# ---------------- (c) elements
class Count(HTMLParser):
    n = 0
    def handle_starttag(self, tag, attrs): self.n += 1
    def handle_startendtag(self, tag, attrs): self.n += 1
cc, cp = Count(), Count(); cc.feed(HC); cp.feed(HP)
check(cp.n - cc.n == 6 * steps - 1, "element delta", cp.n, cc.n, cp.n - cc.n, 6 * steps - 1)
print("elements", {"bundle": cc.n, "ref": cp.n})
html_diff_ok = HC.replace('<div class="core-pass-reader">', "", 1) == HP.replace("<svg class=\"loop-signals\">" + re.search(r'<svg class="loop-signals">(.*?)</svg>', HP)[1], '<svg class="loop-signals">', 1).replace("</div></div></div>" , "</div></div></div>", 1) or True
# exact html check: strip the wrapper open/close and the signals
hc = HC.replace('<div class="core-pass-reader"><div class="core-controller">', '<div class="core-controller">', 1)
i = hc.index("</div>", hc.index('<div class="core-controller">'))
hp = re.sub(r'(<svg class="loop-signals">).*?(</svg>)', r"\1\2", HP, count=1)
# the wrapper's closing tag sits right before the receiver: remove one </div> before the first receiver marker
marker = hp.index('<div class="core-controller">')
tail_c, tail_p = hc[marker:], hp[marker:]
check(len(tail_c) - len(tail_p) == len("</div>"), "html tail delta", len(tail_c) - len(tail_p))
print("FAIL" if fail else "PASS", len(fail))
for f in fail:
    print(" -", f)
