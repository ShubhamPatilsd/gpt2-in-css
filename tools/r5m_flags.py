"""R5M memory cuts (round 5). Flags default ON; `0` reproduces combined7 byte-for-byte (R4M/tools7 recipe).

R5M_HEAD_LITERAL: each of the 50,257 coarse head rows (prebuilt `experiments/browser-gpt2/head-two-pass/head-body.html`, read by
  browser_gpt2_runtime.py) carries its width as an inline literal expression
      width:calc-size(max-content,round(nearest,(size - <base>px)*FACTOR + OFFSET,4px))
  instead of the two inline custom properties `--base`/`--tie` that the `.head-row` rules substitute. Exactness: the cascade winner
  for `.head-row{width}` in combined7 is the two-pass rule `(size - var(--base)*1px)*FACTOR + OFFSET` (later than the tie-bearing base
  rule, same specificity); `var(--base)*1px` with `--base:<n>` is the length `<n>px` bit-for-bit, and `--tie` is dead in that rule.
  FACTOR/OFFSET are read from the two-pass rule itself (assert exactly one). Rows declare no custom properties afterwards, so a head
  restyle no longer allocates a StyleInheritedVariables delta, a var() substitution and a calc parse per row (R5M/fx head50k-* fixtures).
"""
import os
import re


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


HEAD_LITERAL = flag("R5M_HEAD_LITERAL")

TWO_PASS_RULE = re.compile(
    r"\.head-row\{width:calc-size\(max-content,round\(nearest,\(size - var\(--base\)\*1px\)\*([\d.]+) \+ ([-\d.]+px),4px\)\)\}"
)
ROW_STYLE = re.compile(r'(<i class="head-row" data-token="\d+" style=")--base:([-\d.]+);--tie:\d+(")')
TIE_RULE_PREFIX = ".head-row{grid-area:1/1"


def head_literal(head_html, head_css):
    """Rewrite the coarse rows' inline styles to the literal two-pass width (verified shape)."""
    rules = TWO_PASS_RULE.findall(head_css)
    if len(rules) != 1:
        raise ValueError(f"R5M: expected 1 two-pass .head-row width rule, found {len(rules)}")
    factor, offset = rules[0]
    two_pass_at = TWO_PASS_RULE.search(head_css).start()
    tie_at = head_css.find(TIE_RULE_PREFIX)
    if not (0 <= tie_at < two_pass_at):
        raise ValueError("R5M: the two-pass rule must follow the tie-bearing base rule (cascade order)")
    n = 0

    def rep(m):
        nonlocal n
        n += 1
        return f"{m.group(1)}width:calc-size(max-content,round(nearest,(size - {m.group(2)}px)*{factor} + {offset},4px)){m.group(3)}"

    out = ROW_STYLE.sub(rep, head_html)
    if n != head_html.count('class="head-row"'):
        raise ValueError(f"R5M: rewrote {n} rows of {head_html.count('class=\"head-row\"')}")
    if "--base" in out or "--tie" in out:
        raise ValueError("R5M: a head row still declares --base/--tie")
    return out
