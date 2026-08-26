"""Native remembered-layout KV storage and anchor-arithmetic attention.

Past K/V live in contain-intrinsic-size's remembered dimensions, not custom
property transitions. An outer wrapper keeps each hidden latch anchor-readable.
Only current Q/K/V and per-head scales are CSS numbers. Stored K/V, scores,
softmax weights and weighted sums are consumed directly as layout dimensions.
The caller transports the resulting context expressions into the next stage.
"""

import build_hybrid_twelve_block as hybrid

BASE = 65536
GAIN = 32768
SCALE_GAIN = 1024
SCORE_GAIN = 1024
WEIGHT_GAIN = 131072


def sum_terms(terms, balanced=False):
    terms = list(terms)
    if not terms:
        return "0"
    if not balanced:
        return " + ".join(terms)
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return f"({sum_terms(terms[:middle], True)} + {sum_terms(terms[middle:], True)})"


def attention(
    capacity,
    heads=12,
    head_width=64,
    prefix="geo",
    epoch="--epoch",
    split=False,
    balanced=False,
):
    width = heads * head_width

    def anchor(name, axis="width"):
        return f"anchor-size(--{prefix}-{name} {axis},0px)"

    def value(slot, kind, coordinate):
        axis = "width" if kind == "k" else "height"
        head = coordinate // head_width
        return (
            f"(({anchor(f'value-{slot}-{coordinate}', axis)} - {BASE}px) / {GAIN}px"
            f" * {anchor(f'scale-{slot}-{head}', axis)} / {SCALE_GAIN}px)"
        )

    def score(slot, head):
        return (
            f"(({anchor(f'score-{slot}-{head}')} - {anchor(f'score-{slot}-{head}', 'height')})"
            f" / {SCORE_GAIN}px)"
        )

    css = hybrid.regs(
        [f"--{prefix}-{kind}s-{head}" for kind in ("k", "v") for head in range(heads)]
        + [f"--{prefix}-valid-{slot}" for slot in range(capacity)]
    )
    css += (
        f".{prefix}-bank{{anchor-scope:{'none' if split else 'all'}}}"
        f".{prefix}-holder{{position:absolute;left:0;top:0;width:max-content;height:max-content;visibility:hidden}}"
        f".{prefix}-latch{{display:block;width:max-content;height:max-content;contain-intrinsic-size:auto 0px;content-visibility:hidden}}"
        f".{prefix}-value{{display:block}}"
        f".{prefix}-arithmetic{{position:absolute;left:0;top:0;display:block;visibility:hidden}}"
    )
    for head in range(heads):
        for kind, offset in (("k", width), ("v", 2 * width)):
            coordinates = ",".join(
                f"abs(var(--qkv-{offset + head * head_width + i:03d}))"
                for i in range(head_width)
            )
            css += f".{prefix}-bank{{--{prefix}-{kind}s-{head}:max(.000001,{coordinates})}}"
    storage, arithmetic = [], []
    value_rules = {}

    def latch(name, slot, x, y, value_class):
        value_rules[value_class] = (
            f".{prefix}-{value_class}{{width:calc({x});height:calc({y})}}"
        )
        return (
            f'<div class="{prefix}-holder {prefix}-slot-{slot}" style="anchor-name:--{prefix}-{name}">'
            f'<div class="{prefix}-latch"><i class="{prefix}-value {prefix}-{value_class}"></i></div></div>'
        )

    def box(name, declarations):
        return f'<i class="{prefix}-arithmetic" style="anchor-name:--{prefix}-{name};{declarations}"></i>'

    for slot in range(capacity):
        css += (
            f".{prefix}-bank,.{prefix}-mix{{--{prefix}-valid-{slot}:clamp(0,sign(var({epoch}) - {slot + 1}) + 1,1)}}"
            f"@container runtime style({epoch}:{slot + 1}){{.{prefix}-slot-{slot}>.{prefix}-latch{{content-visibility:visible}}}}"
        )
        for head in range(heads):
            storage.append(
                latch(
                    f"scale-{slot}-{head}",
                    slot,
                    f"var(--{prefix}-ks-{head}) * {SCALE_GAIN}px",
                    f"var(--{prefix}-vs-{head}) * {SCALE_GAIN}px",
                    f"scale-component-{head}",
                )
            )
        for coordinate in range(width):
            head = coordinate // head_width
            storage.append(
                latch(
                    f"value-{slot}-{coordinate}",
                    slot,
                    f"{BASE}px + var(--qkv-{width + coordinate:03d}) / var(--{prefix}-ks-{head}) * {GAIN}px",
                    f"{BASE}px + var(--qkv-{2 * width + coordinate:03d}) / var(--{prefix}-vs-{head}) * {GAIN}px",
                    f"component-{coordinate}",
                )
            )
        for head in range(heads):
            terms = sum_terms(
                [
                    f"var(--qkv-{head * head_width + i:03d}) * {value(slot, 'k', head * head_width + i)}"
                    for i in range(head_width)
                ],
                balanced,
            )
            arithmetic.append(
                box(
                    f"score-{slot}-{head}",
                    f"--geo-dot:calc(({terms}) / sqrt({head_width}));"
                    f"width:calc(max(0,var(--geo-dot))*{SCORE_GAIN}px);height:calc(max(0,-1 * var(--geo-dot))*{SCORE_GAIN}px)",
                )
            )
    for head in range(heads):
        maximum = (
            "max("
            + ",".join(
                f"if(style(--{prefix}-valid-{slot}:1):calc({score(slot, head)});else:-infinity)"
                for slot in range(capacity)
            )
            + ")"
        )
        arithmetic.append(
            box(
                f"max-{head}",
                f"--geo-max:{maximum};width:calc(max(0,var(--geo-max))*{SCORE_GAIN}px);height:calc(max(0,-1 * var(--geo-max))*{SCORE_GAIN}px)",
            )
        )
        max_score = f"(({anchor(f'max-{head}')} - {anchor(f'max-{head}', 'height')}) / {SCORE_GAIN}px)"
        for slot in range(capacity):
            arithmetic.append(
                box(
                    f"weight-{slot}-{head}",
                    f"width:if(style(--{prefix}-valid-{slot}:1):calc(exp({score(slot, head)} - {max_score}) * {WEIGHT_GAIN}px);else:0px);height:1px",
                )
            )
        denominator = sum_terms(
            [anchor(f"weight-{slot}-{head}") for slot in range(capacity)], balanced
        )
        arithmetic.append(
            box(f"den-{head}", f"width:calc(({denominator}) / {capacity});height:1px")
        )
    contexts = []
    for coordinate in range(width):
        head = coordinate // head_width
        terms = sum_terms(
            [
                f"{anchor(f'weight-{slot}-{head}')} * {value(slot, 'v', coordinate)}"
                for slot in range(capacity)
            ],
            balanced,
        )
        contexts.append(
            f"(({terms}) / ({capacity} * max(.000001px,{anchor(f'den-{head}')})))"
        )
    css += "".join(value_rules.values())
    if split:
        return (
            f'<div class="{prefix}-bank">' + "".join(storage) + "</div>",
            f'<div class="{prefix}-mix">' + "".join(arithmetic) + "{child}</div>",
            css,
            contexts,
        )
    return (
        f'<div class="{prefix}-bank">'
        + "".join(storage + arithmetic)
        + "{child}</div>",
        css,
        contexts,
    )


def context_source(source, expressions, stem="out"):
    """Substitute layout math into bridge widths; never into typed CSS numbers."""
    for coordinate, expression in enumerate(expressions):
        old = f"var(--{stem}-{coordinate:03d})"
        if source.count(old) != 1:
            raise ValueError(f"Missing unique context carrier {old}")
        source = source.replace(old, expression)
    return source


def in_plane(source, content):
    """Keep anchor producers and consumers in one positioning context.

    Chromium cannot resolve these out-of-flow anchors from a metric whose separate
    scroll-track containing block was laid out first. Sharing the track makes the
    dependency order explicit, while preserving the original view-timeline bridge.
    """
    opening = '<div class="track">'
    closing = "</div></div>"
    if (
        source.count(opening) != 1
        or not source.endswith(closing)
        or content.count("{child}") != 1
    ):
        raise ValueError("Unexpected native bridge plane shape")
    prefix, metrics = source.split(opening, 1)
    return (
        prefix
        + opening
        + content.replace("{child}", metrics[: -len(closing)])
        + closing
    )
