"""Opt-in dense-stage lifetime and layer-rule experiments.

Only scoped compile-time helper patches are installed. Existing compilers,
weights, arithmetic, native receipts and generated demos remain unchanged.
Use ``with dense_compile_variant(name) as stats: compile_runtime(...)``.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from unittest.mock import patch

WIDTH = 768


@dataclass(frozen=True)
class DenseVariant:
    private_normalized_inputs: bool = False
    projection_settings: bool = False
    hoist_layer_invariants: bool = False
    selective_loop_reads: bool = False


VARIANTS = {
    "baseline": DenseVariant(),
    "norm-private": DenseVariant(private_normalized_inputs=True),
    "proj-settings": DenseVariant(projection_settings=True),
    "layer-hoist": DenseVariant(hoist_layer_invariants=True),
    "combined": DenseVariant(True, True, True),
    "loop-selective": DenseVariant(selective_loop_reads=True),
    "combined-loop": DenseVariant(True, True, True, True),
}

# Font shorthands/settings, widths, ranges, gains, biases and neural outputs
# deliberately stay conditional. In particular, hoisting font variation before
# a remaining layer-specific font shorthand could reset it and change answers.
HOISTABLE = frozenset(
    {
        "animation",
        "animation-name",
        "animation-duration",
        "animation-timing-function",
        "animation-fill-mode",
        "animation-timeline",
        "animation-range",
        "timeline-scope",
        "container-name",
        "display",
    }
)


def normalized_names():
    return {
        *(f"--n{n}-{i:03d}" for n in (1, 2) for i in range(WIDTH)),
        "--mean1",
        "--var1",
        "--mean2",
        "--var2",
    }


def private_registrations(css, names):
    """One linear scan of registration blocks; assert every requested field."""
    pieces, found, cursor = [], set(), 0
    prefix = "@property "
    while (start := css.find(prefix, cursor)) >= 0:
        opening = css.find("{", start)
        closing = css.find("}", opening)
        if min(opening, closing) < 0:
            raise ValueError("Malformed property registration")
        name = css[start + len(prefix) : opening].strip()
        block = css[start : closing + 1]
        pieces.append(css[cursor:start])
        if name in names:
            if name in found or block.count("inherits:true") != 1:
                raise ValueError(f"Expected one inherited registration for {name}")
            found.add(name)
            block = block.replace("inherits:true", "inherits:false")
        pieces.append(block)
        cursor = closing + 1
    pieces.append(css[cursor:])
    if found != names:
        raise ValueError(f"Missing normalized registrations: {sorted(names - found)[:8]}")
    return "".join(pieces)


def materialize_projection_settings(css):
    """Resolve pack-list variables on the stage; omit broad vector resets.

    This isolates the pack-list preparation already embedded in the older
    isolate_metric_state feature. It is a new independent ablation, not a claim
    that axis-list materialization itself was previously absent from the repo.
    """
    prefix = ".shared-proj-pack"
    pieces, cursor, slots = [], 0, set()
    while (start := css.find(prefix, cursor)) >= 0:
        opening = css.find("{", start)
        closing = css.find("}", opening)
        if min(opening, closing) < 0:
            raise ValueError("Malformed projection pack rule")
        slot = css[start + len(prefix) : opening]
        if not slot.isdigit():
            raise ValueError("Unexpected projection pack selector")
        body = css[opening + 1 : closing]
        family, separator, settings = body.partition(";font-variation-settings:")
        if (
            not separator
            or not family.startswith("font-family:")
            or ";" in settings
            or slot in slots
        ):
            raise ValueError("Expected one plain family/settings rule per pack")
        slots.add(slot)
        name = f"--dense-proj-settings-{slot}"
        pieces.extend(
            [
                css[cursor:start],
                f".shared-proj{{{name}:{settings}}}",
                f"{prefix}{slot}{{{family};font-variation-settings:var({name})}}",
            ]
        )
        cursor = closing + 1
    pieces.append(css[cursor:])
    if slots != {"0", "1", "2", "3"}:
        raise ValueError("Pack materialization requires the standard four-pack MLP projection")
    return "".join(pieces), len(slots)


def declarations(body):
    """Split declarations without splitting semicolons inside CSS functions."""
    start, depth, quote, escaped = 0, 0, None, False
    for index, char in enumerate(body):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == ";" and depth == 0:
            if body[start:index].strip():
                yield body[start:index].strip()
            start = index + 1
    if depth or quote:
        raise ValueError("Unbalanced CSS declaration")
    if body[start:].strip():
        yield body[start:].strip()


def closing_brace(text, opening):
    """Find one rule boundary in linear time, respecting quoted strings."""
    depth, quote, escaped = 1, None, False
    for index in range(opening + 1, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("Unbalanced stage rule")


def hoist_layer_rules(css, layer, kind, known):
    """Handle only the small flat stylesheet of one freshly compiled stage."""
    marker = f"@container runtime style(--layer:{layer}){{"
    if css.count(marker) != 1 or not css.endswith("}"):
        raise ValueError("Expected one final layer-conditional stage stylesheet")
    globals_css, body = css.split(marker)
    body = body[:-1]
    static_rules, conditional_rules, cursor, removed = [], [], 0, 0
    while cursor < len(body):
        opening = body.find("{", cursor)
        if opening < 0:
            if body[cursor:].strip():
                raise ValueError("Unexpected trailing stage CSS")
            break
        closing = closing_brace(body, opening)
        selector = body[cursor:opening].strip()
        if selector == f"@container shared-{kind}-receipt style(--gate-{kind}:1)":
            # Native receipt gating stays intact inside the layer query. This
            # is the one expected nested rule in a dense matvec stylesheet.
            conditional_rules.append(body[cursor : closing + 1])
            cursor = closing + 1
            continue
        if "{" in body[opening + 1 : closing]:
            raise ValueError("Unexpected nested dense-stage rule")
        if not selector.startswith(".shared-"):
            raise ValueError(f"Unexpected stage selector {selector[:100]}")
        static, conditional = [], []
        for declaration in declarations(body[opening + 1 : closing]):
            name, separator, value = declaration.partition(":")
            if not separator:
                raise ValueError("Malformed stage declaration")
            if name in HOISTABLE:
                key = kind, selector, name
                if key in known and known[key] != value:
                    raise ValueError(f"Layer-dependent declaration cannot be hoisted: {key}")
                if key not in known:
                    known[key] = value
                    static.append(declaration)
                removed += 1
            else:
                conditional.append(declaration)
        if static:
            static_rules.append(selector + "{" + ";".join(static) + "}")
        if conditional:
            conditional_rules.append(selector + "{" + ";".join(conditional) + "}")
        cursor = closing + 1
    return (
        globals_css + "".join(static_rules) + marker + "".join(conditional_rules) + "}",
        removed,
    )


@contextmanager
def dense_compile_variant(name):
    """Yield JSON-safe compile statistics while installing opt-in rewrites.

    Patching module globals used by compile_reused also reaches an adapter that
    imported that function earlier. No runtime JavaScript or scheduler is added.
    Compile calls sharing this context must be serial; use a fresh context for
    every artifact so first-layer structural declarations are emitted anew.
    """
    import browser_gpt2_reused_core as reused

    config = VARIANTS[name]
    original_shared, original_specialize = reused.shared_css, reused.specialize
    original_loop = reused.loop_parts
    stats = {
        "variant": name,
        "options": asdict(config),
        "normalizedPrivatePropertyCount": 0,
        "normalizedForwardingPropertyCount": 0,
        "projectionPackListsMaterialized": 0,
        "conditionalDeclarationsHoisted": 0,
        "uniqueHoistedDeclarations": 0,
        "stageStylesheetByteDelta": 0,
        "loopReaderConfigurations": [],
        "runtimeJavaScript": False,
    }
    forwarded, known = set(), {}

    def shared(*args, **kwargs):
        css = original_shared(*args, **kwargs)
        if config.private_normalized_inputs:
            fields = normalized_names()
            css = private_registrations(css, fields)
            stats["normalizedPrivatePropertyCount"] += len(fields)
        return css

    def specialize(html, css, layer, kind):
        html, css = original_specialize(html, css, layer, kind)
        old_size = len(css.encode())
        if config.projection_settings and kind == "proj":
            css, count = materialize_projection_settings(css)
            stats["projectionPackListsMaterialized"] += count
        if config.hoist_layer_invariants:
            css, count = hoist_layer_rules(css, layer, kind, known)
            stats["conditionalDeclarationsHoisted"] += count
            stats["uniqueHoistedDeclarations"] = len(known)
        if (
            config.private_normalized_inputs
            and kind in ("qkv", "fc")
            and kind not in forwarded
        ):
            n = 1 if kind == "qkv" else 2
            css += f".shared-{kind}{{" + ";".join(
                f"--n{n}-{i:03d}:inherit" for i in range(WIDTH)
            ) + "}"
            forwarded.add(kind)
            stats["normalizedForwardingPropertyCount"] += WIDTH
        stats["stageStylesheetByteDelta"] += len(css.encode()) - old_size
        return html, css

    def loop(*args, **kwargs):
        if config.selective_loop_reads:
            width = args[0] if args else kwargs["width"]
            previous = args[3] if len(args) > 3 else kwargs.get("selective", False)
            if len(args) > 3:
                args = (*args[:3], True, *args[4:])
            else:
                kwargs["selective"] = True
            stats["loopReaderConfigurations"].append({
                "width": width,
                "previousSelective": bool(previous),
                "allBankSampledChannels": 2 * (width + 1),
                "selectedSampledChannels": width + 2,
                "preserved": "prior bank vector and generation stamp, plus current bank acknowledgement stamp",
            })
        return original_loop(*args, **kwargs)

    with patch.object(reused, "shared_css", shared), patch.object(
        reused, "specialize", specialize
    ), patch.object(reused, "loop_parts", loop):
        yield stats
