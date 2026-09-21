"""R3M offline check for R3H_BLOCKFLOW_MAX: <bundle-dir> (flag on) vs <ref-bundle-dir> (same tools, flag off).

Asserts: index.html identical; runtime.css (after normalising the `url("../…")` depth so bundles at different
directory depths compare) equals ref + exactly the two #176 override rules appended at the end of the head sheet
(right after the last `.head-fine-row:nth-child(256)` rule, before the control sheet's first @property); the base
`.head-group` grid rule, the base `.head-row` rule (with R2D's clip swap), the two-pass `.head-row{width}` override
and the `.head-fine` grid rule each occur exactly once in both; no other `.head-group{`/`.head-row{` rule exists.
usage: python3 offline_check_r3h.py <bundle-dir> <ref-bundle-dir>"""
import re, sys
from pathlib import Path

OVERRIDE = (".head-group{display:block;grid-template-columns:none;grid-template-rows:none}"
            ".head-row{grid-area:auto;justify-self:auto;height:0}")
GROUP = (".head-group{position:fixed;left:0;top:-80000px;display:grid;grid-template-columns:max-content;"
         "grid-template-rows:1px;width:max-content;height:calc(var(--head-input-epoch)*1px)}")
ROW = ".head-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:clip;min-width:0;"
ROW2 = ".head-row{width:calc-size(max-content,round(nearest,(size - var(--base)*1px)*120.777609693 + 211968px,4px))}"
FINE = ".head-fine{position:fixed;left:0;top:-80000px;display:grid;grid-template-columns:max-content;grid-template-rows:1px;"

def norm(s):
    return re.sub(r'url\("(?:\.\./)+', 'url("', s)

on, ref = Path(sys.argv[1]), Path(sys.argv[2])
ok = True
def check(cond, msg):
    global ok
    print(("ok   " if cond else "FAIL ") + msg); ok &= bool(cond)

check((on / "index.html").read_bytes() == (ref / "index.html").read_bytes(), "index.html identical")
a, b = norm((on / "runtime.css").read_text()), norm((ref / "runtime.css").read_text())
check(a.count(OVERRIDE) == 1 and b.count(OVERRIDE) == 0, "override rules: once in bundle, absent in ref")
i = a.find(OVERRIDE)
check(a[:i] + a[i + len(OVERRIDE):] == b, "runtime.css == ref + override (URL depth normalised)")
check(a[i - 1] == "}" and re.search(r"\.head-fine-row:nth-child\(256\)\{[^}]*\}$", a[:i]) is not None, "override sits right after the last fine-row rule")
check(a[i + len(OVERRIDE):].startswith("@property --saved-token-1{"), "override sits right before the control sheet")
for name, needle in (("base .head-group grid rule", GROUP), ("base .head-row rule (R2D clip)", ROW), ("two-pass .head-row width rule", ROW2), (".head-fine grid rule", FINE)):
    check(a.count(needle) == 1 and b.count(needle) == 1, f"{name} once in both")
check(len(re.findall(r"\.head-group\{", a)) == 2 and len(re.findall(r"\.head-row\{", a)) == 3, "rule counts: .head-group{ x2, .head-row{ x3 in bundle")
check(len(re.findall(r"\.head-group\{", b)) == 1 and len(re.findall(r"\.head-row\{", b)) == 2, "rule counts: .head-group{ x1, .head-row{ x2 in ref")
check(a.index(GROUP) < a.index(ROW) < a.index(ROW2) < a.index(FINE) < i, "cascade order: base rules precede the override")
print("RESULT:", "ok" if ok else "FAIL"); sys.exit(0 if ok else 1)
