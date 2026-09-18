"""Opt-in scaling ablations over the existing native attention compiler.

The production compiler is deliberately unchanged. Each experiment supplies a
replacement through a scoped unittest.mock.patch at compile time only. Generated
pages have no runtime JavaScript. See experiments/browser-gpt2-scaling/README.md.
"""

import re
from dataclasses import asdict, dataclass

import browser_gpt2_font_vector_cache as base


@dataclass(frozen=True)
class Variant:
    widths: bool = False
    empty_slots: bool = False
    selective_fields: bool = False
    materialize_inputs: bool = False
    local_timelines: bool = False
    containment: str | None = None


VARIANTS = {
    "baseline": Variant(),
    "widths": Variant(widths=True),
    "empty": Variant(empty_slots=True),
    "fields": Variant(selective_fields=True),
    "materialize": Variant(materialize_inputs=True),
    "timelines": Variant(local_timelines=True),
    "contain-layout": Variant(containment="size layout"),
    "contain-none": Variant(containment="none"),
    "combined": Variant(True, True, True, True, True),
    "lean": Variant(
        widths=True, empty_slots=True, materialize_inputs=True, local_timelines=True
    ),
}

# Capture before any compile-time injection to avoid recursive calls.
ORIGINAL = base.attention


def transformed_attention(variant, *args, **kwargs):
    config = VARIANTS[variant] if isinstance(variant, str) else variant
    if config.widths:
        kwargs["value_layout"] = "widths"
    html, css, metadata = ORIGINAL(*args, **kwargs)
    capacity = metadata["kvSlots"]
    positions = args[0] if args else kwargs["capacity"]
    epoch = args[3] if len(args) > 3 else kwargs.get("write_epoch", "--epoch")
    fields = [name.replace("--fc-", "--fr-") for name in base.storage_names(capacity)]
    if config.selective_fields:
        # Keep private cache storage unchanged. Make exported aliases local and
        # explicitly relay them only along the storage/consumer spine. Each score
        # leaf receives two fields; each value leaf receives its own V and scale.
        # Place forwarding BEFORE active-layer aliases, which must win cascade.
        forward = ";".join(f"{p}:inherit" for p in fields)
        carriers = (
            ".fvs-bank,.fvs-score-source,.fvs-score-source>.track,"
            ".fvs-score-reader,.fvs-score-receipt,.fvs-score-gate,.fvs-softmax,"
            ".fvs-softmax>.scroller,.fvs-softmax>.scroller>.track"
        )
        prefix = f"{carriers}{{{forward}}}"
        for head in range(base.HEADS):
            own = [p for p in fields if p.endswith(f"-{head}")]
            # The row needs all V contributions for this head, never other heads.
            prefix += (
                f".scale-row-{head}{{"
                + ";".join(f"{p}:inherit" for p in own if "--fr-v" in p)
                + "}"
            )
            for slot in range(capacity):
                prefix += f".fvs-score-{head}-{slot}{{--fr-k-{slot}-{head}:inherit;--fr-ks-{slot}-{head}:inherit}}"
                prefix += f".fvs-v-{head}-{slot}{{--fr-v-{slot}-{head}:inherit;--fr-vs-{slot}-{head}:inherit}}"
        css = re.sub(
            r"(@property --fr-[^{}]+\{[^{}]*inherits:)true",
            r"\g<1>false",
            css,
        )
        css = prefix + css
        row_count = 0

        def tag_row(match):
            nonlocal row_count
            head = row_count // base.DIM
            row_count += 1
            return f'class="metric fvs-value-row scale-row-{head}"'

        html = re.sub(r'class="metric fvs-value-row"', tag_row, html)
        if row_count != base.WIDTH:
            raise ValueError(f"Expected 768 output rows, found {row_count}")
    if config.materialize_inputs:
        # The source computes axis lists and numeric scales once. K/V storage,
        # font shaping, softmax and weighted V do not need raw QKV coordinates.
        # This removes only fields whose last consumer precedes the first bank.
        dead = [f"--qkv-{i:03d}" for i in range(3 * base.WIDTH)]
        css += ".fvs-query>.fvs-bank{" + ";".join(f"{p}:initial" for p in dead) + "}"
    if config.empty_slots:
        if capacity != positions:
            raise ValueError("Empty-slot ablation currently requires full causal cache")
        css += (
            ".fvs-query{container-name:fvscache;"
            + ";".join(
                f"--scale-valid-{s}:clamp(0,sign(var({epoch}) - {s + 1}) + 1,1)"
                for s in range(capacity)
            )
            + "}"
        )
        for s in range(capacity):
            css += f'@property --scale-valid-{s}{{syntax:"<number>";inherits:false;initial-value:0}}'
            selectors = ",".join(
                f".fvs-score-{h}-{s},.fvs-v-{h}-{s}" for h in range(base.HEADS)
            )
            css += f"{selectors}{{display:none}}@container fvscache style(--scale-valid-{s}:1){{{selectors}{{display:block}}}}"
        # Every V glyph includes a positive base. Removing unused glyphs also
        # requires removing THEIR base contribution from the final subtraction.
        base_pixels = (
            metadata["operators"]["value"]["base"] * base.VALUE_SIZE / base.UNITS_PER_EM
        )
        old = f"size - {capacity * base_pixels:.12g}px"
        new = f"size - min(var({epoch}),{capacity}) * {base_pixels:.12g}px"
        if html.count(old) != base.WIDTH:
            raise ValueError("Missing weighted-value base compensation")
        html = html.replace(old, new)
    if config.local_timelines:
        # Score producers/receivers share this ancestor. Output timelines still
        # cross to the core and remain globally visible as before.
        css, count = re.subn(
            r"html\{timeline-scope:(--fvs-score-[^}]+)\}",
            r".fvs-query{timeline-scope:\1}",
            css,
        )
        if count != 1:
            raise ValueError("Expected one attention-internal timeline scope")
    if config.containment is not None:
        css += f".fvs-query .scroller{{contain:{config.containment}}}"
    metadata = {**metadata, "scalingVariant": asdict(config)}
    return html, css, metadata


def replacement(name):
    def compile_attention(*args, **kwargs):
        return transformed_attention(name, *args, **kwargs)

    return compile_attention
