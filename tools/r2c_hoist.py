"""R2C: hoist per-axis arithmetic out of consumer `font-variation-settings` lists.

Every list entry of the form `"TAG" calc(var(--src) / var(--scale))` (the four stage
lists `.shared-{qkv,attn,fc,proj}`, the twelve `--fvs-query-H` lists on `.fvs-query`)
and the two `round()`/`mod()` entries of `.embedding-source` become `"TAG" var(--fq-…)`,
where `--fq-…` is a registered `<number>` (`inherits:false`) declared ONCE on the element
that carries the list and whose expression is the ORIGINAL entry arithmetic verbatim (the
declaration text is produced from the matched entry, so the double operations and their
order are unchanged; the only new rounding is Blink's 6-significant-digit serialisation of
the typed number when it is substituted into the list — the same 1e-6 class as F4's
numeric K/V entries).

Flags (environment, default ON): R2C_HOIST_FVS (master); R2C_HOIST_STAGES,
R2C_HOIST_QUERY, R2C_HOIST_EMBEDDING (per population, only effective with the master ON).
"""
import os
import re


def flag(name):
    return os.environ.get(name, "1") not in ("0", "false", "no", "off")


HOIST_FVS = flag("R2C_HOIST_FVS")
HOIST_STAGES = HOIST_FVS and flag("R2C_HOIST_STAGES")
HOIST_QUERY = HOIST_FVS and flag("R2C_HOIST_QUERY")
HOIST_EMBEDDING = HOIST_FVS and flag("R2C_HOIST_EMBEDDING")

PREFIX = "--fq-"
# one list entry: a quoted tag, a space, a quotient of two var() references
ENTRY = re.compile(r'"([^"]+)" (calc\(var\((--[\w-]+)\) / var\((--[\w-]+)\)\))')


_REGISTERED = set()


def private_regs(names):
    """One registration per name: matvec() is called once per layer with the same names."""
    fresh = [p for p in names if p not in _REGISTERED]
    _REGISTERED.update(fresh)
    return "".join(
        f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}' for p in fresh
    )


def hoist_settings(settings, namer):
    """Rewrite every `"TAG" calc(var(a) / var(b))` entry of `settings` to `"TAG" var(name)`.

    `namer(source_var, entry_index)` returns the hoisted property name. Returns
    (new_settings, [(name, expression)]) with `expression` the matched text verbatim.
    Raises if any entry did not match (no silent partial hoists)."""
    hoisted = []

    def swap(match):
        name = namer(match[3], len(hoisted))
        hoisted.append((name, match[2]))
        return f'"{match[1]}" var({name})'

    new = ENTRY.sub(swap, settings)
    entries = settings.count('"') // 2
    if len(hoisted) != entries or "calc(" in new:
        raise ValueError(f"R2C hoist: {entries - len(hoisted)} entries did not match")
    return new, hoisted


def declarations(hoisted):
    return ";".join(f"{name}:{expression}" for name, expression in hoisted)


_SEEN = set()
_STAGE_RULE = re.compile(
    r"\.shared-(?:qkv|attn|fc|proj)\{(?:--fq-(?:qkv|attn|fc|proj)-\d{3,4}:calc\(var\(--[\w-]+\) / var\(--range-\w+\)\);?)+\}"
)


def lift_stage_rules(css):
    """The hoisted stage declarations are identical for every layer; keep ONE copy
    outside the per-layer `@container` blocks. Returns (css_without, lifted_once)."""
    lifted = []

    def take(match):
        if match[0] not in _SEEN:
            _SEEN.add(match[0])
            lifted.append(match[0])
        return ""

    return _STAGE_RULE.sub(take, css), "".join(lifted)
