"""R6P: print the rule containing each anchor string (fast: str.find + scan to the enclosing braces)."""
import sys, json, re
path = sys.argv[1]; s = open(path).read()
def rule_at(anchor, occurrence=0, width=1200):
    i = -1
    for _ in range(occurrence + 1):
        i = s.find(anchor, i + 1)
        if i < 0: return None
    a = s.rfind('}', 0, i) + 1; b = s.find('}', i) + 1
    return s[a:b][:width]
for anchor in sys.argv[2:]:
    n = s.count(anchor)
    print(f"=== {anchor!r} ({n} occurrences)"); r = rule_at(anchor); print(r if r else "(none)")
