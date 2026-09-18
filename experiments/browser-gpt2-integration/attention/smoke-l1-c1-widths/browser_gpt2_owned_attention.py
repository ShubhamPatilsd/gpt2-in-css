"""Twelve independent attention owners with a detached numeric input boundary.

Use install_native_attention() around the existing runtime compiler. It retains
the QKV producer under the real QKV generation gate and places all consumers next
to the core's loop reader, outside the dense numeric ancestry. No runtime JS.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import re
from unittest.mock import patch

import browser_gpt2_font_vector_cache as base


def rule(selector, body):
    return selector + "{" + body + "}"


def register(name, inherits=False, syntax="<number>", initial="0"):
    return rule("@property " + name, f'syntax:"{syntax}";inherits:{str(inherits).lower()};initial-value:{initial}')


def animation(name, prop):
    return rule("@keyframes " + name, rule("from", f"{prop}:-2") + rule("to", f"{prop}:1"))


def animation_reader(names, timelines):
    return f'animation-name:{",".join(names)};animation-timeline:{",".join(timelines)};animation-duration:1s;animation-fill-mode:both;animation-timing-function:linear'


def decode(progress, scale=1024, rounded=False):
    expression = f"(1572864 / (var({progress}) + 2) - 786432) / {scale}"
    return f"round(nearest,calc({expression}),1)" if rounded else f"calc({expression})"


def metric(width, timeline, body="", classes="oa-metric"):
    return f'<i class="{classes}" style="width:{width};view-timeline:{timeline} inline">{body}</i>'


def scroller(body, classes=""):
    return f'<div class="oa-scroller {classes}"><div class="oa-track">{body}</div></div>'


@dataclass
class AttentionArtifact:
    producer_html: str
    detached_consumers_html: str
    css: str
    metadata: dict


class OwnedAttention:
    """Attention replacement with explicit detached-consumer integration data."""

    def __init__(self, *, expected_epoch="--epoch", input_scope="html", max_generations=None, value_layout=None):
        self.expected_epoch = expected_epoch
        self.input_scope = input_scope
        self.max_generations = max_generations
        self.value_layout = value_layout
        self.artifact = None

    def attention(self, capacity, blocks, context_carrier, write_epoch="--epoch", kv_window=None, kv_sinks=0, value_layout="runs", prewarm_values=False):
        if kv_window not in (None, capacity) or kv_sinks or prewarm_values:
            raise ValueError("Owned attention initially supports full causal cache without sinks/prewarming")
        value_layout = self.value_layout or value_layout
        if value_layout not in ("runs", "widths"):
            raise ValueError("Owned attention supports runs or widths value layouts")
        if capacity < 1 or blocks < 1:
            raise ValueError("Positive capacity and layer count required")
        operators = base.fonts()
        dot, value = operators["dot"], operators["value"]
        dot_unit = base.QK_SIZE / base.UNITS_PER_EM
        value_unit = base.VALUE_SIZE / base.UNITS_PER_EM
        max_generations = self.max_generations or capacity * blocks
        # Match only the small supplied bridge, never a complete generated CSS.
        pattern = r'<i class="metric" style="width:calc\(262144px \+ var\(--(?:ctx|out)-(\d+)\) \* 128px\);view-timeline:([^ ]+) inline"></i>'
        coordinates = {int(m[1]): m[2] for m in re.finditer(pattern, context_carrier)}
        marker = re.search(r'width:calc\(262144px \+ var\(--epoch\) \* 1024px\);view-timeline:([^ ]+) inline', context_carrier)
        if set(coordinates) != set(range(base.WIDTH)) or marker is None:
            raise ValueError("Expected the existing 768-coordinate context bridge and generation marker")
        context_marker = marker[1]
        css = '@keyframes oa-pulse{from{opacity:.99}to{opacity:1}}'
        css += register("--oa-epoch", True) + register("--oa-source-layer", True)
        css += rule('.oa-consumers', f'--oa-epoch:var({self.expected_epoch})')
        css += '.oa-scroller{position:fixed;top:-60000px;left:0;width:524288px;height:1px;overflow:scroll;contain:strict;visibility:hidden}.oa-track{position:relative;width:1572864px;height:1px}.oa-metric{position:absolute;left:0;top:0;height:1px}.oa-value-row{display:inline-flex;gap:0;font:0px monospace;line-height:1}.oa-signals{position:fixed;left:0;top:0;width:1px;height:1px}'
        css += f'@font-face{{font-family:OwnedDot;src:url("{(base.FONT_DIR / "dot.woff2").as_uri()}")}}'
        css += f'@font-face{{font-family:OwnedValue;src:url("{(base.FONT_DIR / "value.woff2").as_uri()}")}}'
        for layer in range(blocks):
            css += rule(f'@container runtime style(--layer:{layer})', rule('.oa-source', f'--oa-source-layer:{layer}'))
        producer_metrics, heads, input_timelines, commit_timelines = [], [], [], []
        zero_axes = ",".join(f'"K{i:03d}" 0' for i in range(base.DIM))
        for head in range(base.HEADS):
            prefix = f"oa-{head}"
            prop = lambda suffix, prefix=prefix: f"--{prefix}-{suffix}"
            controller = f"{prefix}-control"
            incoming_container = f"{prefix}-incoming"
            input_container = f"{prefix}-input"
            output_container = f"{prefix}-output"
            target, captured, held = prop("target"), prop("captured"), prop("held")
            for name in (target, captured, held):
                css += register(name)
            css += rule(f'.oa-head-{head}', f'container-name:{controller};{target}:var(--oa-epoch);{held}:calc(1 - min(1,abs(var({target}) - var({captured}))))')
            read_names, read_timelines, incoming, input_fields = [], [], [], []
            for i in range(3 * base.DIM + 3):
                timeline, key, progress = f"--{prefix}-in-{i}", f"{prefix}-in-{i}", prop(f"progress-{i}")
                input_timelines.append(timeline)
                read_timelines.append(timeline)
                read_names.append(key)
                css += register(progress) + animation(key, progress)
                suffix = f"x-{i}" if i < 3 * base.DIM else ("epoch", "position", "layer")[i - 3 * base.DIM]
                raw, saved = prop("incoming-" + suffix), prop(suffix)
                css += register(raw) + register(saved, True)
                incoming.append(f"{raw}:{decode(progress, rounded=i >= 3 * base.DIM)}")
                input_fields.append((raw, saved))
                if i < 3 * base.DIM:
                    kind, coordinate = divmod(i, base.DIM)
                    source_index = kind * base.WIDTH + head * base.DIM + coordinate
                    source = f"var(--qkv-{source_index:03d})"
                else:
                    source = ("var(--epoch)", f"var({write_epoch})", "var(--oa-source-layer)")[i - 3 * base.DIM]
                producer_metrics.append(metric(f"calc(262144px + {source} * 1024px)", timeline))
            incoming_ready = prop("incoming-ready")
            css += register(incoming_ready)
            css += rule(f'.oa-input-reader-{head}', f'container-name:{incoming_container};' + animation_reader(read_names, read_timelines) + ';' + ';'.join(incoming) + f';{incoming_ready}:calc(1 - min(1,abs(var({prop("incoming-epoch")}) - var(--oa-epoch))))')
            saved_names = [saved for _, saved in input_fields]
            css += rule(f'.oa-input-bank-{head}', f'container-name:{input_container};transition-property:{",".join(saved_names)};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);' + ';'.join(f'{raw}:inherit;{saved}:var({raw})' for raw, saved in input_fields))
            css += rule(f'@container {incoming_container} style({incoming_ready}:1)', rule(f'@container {controller} style({held}:0)', rule(f'.oa-input-bank-{head}', 'transition-property:none')))
            # Numeric inputs and derived settings belong only to this head.
            qscale = f"--fqs-{head}"
            css += register(qscale, True)
            css += rule(f'.oa-input-bank-{head}', qscale + ':max(.000001,' + ','.join(f'abs(var({prop(f"x-{i}")}))' for i in range(base.DIM)) + ')')
            query_axes = ','.join(f'"Q{i:03d}" calc(var({prop(f"x-{i}")}) / var({qscale}))' for i in range(base.DIM))
            css += rule(f'.oa-input-bank-{head}', f'{prop("query")}:{query_axes}')
            for kind, offset in (("k", base.DIM), ("v", 2 * base.DIM)):
                scale = prop(f'live-{kind}s')
                css += register(scale, True)
                axes = ','.join(f'"K{i:03d}" calc(var({prop(f"x-{offset + i}")}) / var({scale}))' for i in range(base.DIM))
                css += rule(f'.oa-input-bank-{head}', f'{scale}:max(.000001,' + ','.join(f'abs(var({prop(f"x-{offset + i}")}))' for i in range(base.DIM)) + f');{prop(f"live-{kind}")}:{axes}')
            cache_fields = []
            for slot in range(capacity):
                for kind in ("k", "v", "ks", "vs"):
                    field = f"--fc-{kind}-{slot}-{head}"
                    cache_fields.append(field)
                    for alias, inherits in (("fc", False), ("fr", True)):
                        name = field.replace('--fc-', '--' + alias + '-')
                        css += register(name, inherits, '*' if kind in ('k', 'v') else '<number>', zero_axes if kind in ('k', 'v') else '0')
            css += rule(f'.oa-bank-{head}', f'transition-property:{",".join(cache_fields)};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete')
            for layer in range(blocks):
                bank_selector = f'.oa-bank-{head}-{layer}'
                selected = f'@container {input_container} style({prop("layer")}:{layer})'
                aliases = ';'.join(f'{name.replace("--fc-", "--fr-")}:var({name})' for name in cache_fields)
                css += rule(selected, rule(bank_selector, aliases))
                for slot in range(capacity):
                    writing = {f'--fc-{kind}-{slot}-{head}' for kind in ('k', 'v', 'ks', 'vs')}
                    retained = ','.join(name for name in cache_fields if name not in writing) or 'none'
                    writes = ';'.join(f'--fc-{kind}-{slot}-{head}:var({prop(f"live-{kind}")})' for kind in ('k', 'v', 'ks', 'vs'))
                    css += rule(selected, rule(f'@container {input_container} style({prop("position")}:{slot + 1})', rule(bank_selector, f'transition-property:{retained};{writes}')))
            score_metrics, score_keys, score_tl, score_reads = [], [], [], []
            for slot in range(capacity):
                key, timeline = f'{prefix}-score-{slot}', f'--{prefix}-score-{slot}'
                progress, score = prop(f'sp-{slot}'), prop(f'score-{slot}')
                score_keys.append(key)
                score_tl.append(timeline)
                css += register(progress) + register(score) + animation(key, progress)
                css += rule(f'.{key}', f'font:{base.QK_SIZE}px OwnedDot;line-height:1;font-kerning:none;font-variation-settings:var(--fr-k-{slot}-{head}),var({prop("query")});width:calc-size(max-content,calc(262144px + (size - {dot["base"] * dot_unit:.12g}px) * var({qscale}) * var(--fr-ks-{slot}-{head}) * {128 / (8 * dot["coefficient"] * dot_unit):.12g}))')
                score_metrics.append(f'<i class="oa-metric {key}" style="view-timeline:{timeline} inline">&#x{base.CODEPOINT_BASE:X};</i>')
                score_reads.append(f'{score}:{decode(progress, scale=128)}')
            stamp_tl, stamp_key, stamp_progress = f'--{prefix}-score-stamp', f'{prefix}-score-stamp', prop('score-stamp')
            score_metrics.append(metric(f'calc(262144px + var({prop("epoch")}) * 1024px)', stamp_tl))
            score_ready = prop('score-ready')
            css += register(stamp_progress) + register(score_ready) + animation(stamp_key, stamp_progress)
            score_container = f'{prefix}-score-receipt'
            css += rule(f'.oa-score-receipt-{head}', f'container-name:{score_container};' + animation_reader([stamp_key], [stamp_tl]) + f';{score_ready}:calc(1 - min(1,abs({decode(stamp_progress, rounded=True)} - var(--oa-epoch))))')
            css += rule(f'.oa-score-gate-{head}', 'content-visibility:hidden;contain-intrinsic-size:0px 0px')
            css += rule(f'@container {score_container} style({score_ready}:1)', rule(f'.oa-score-gate-{head}', 'content-visibility:visible'))
            maximum, denominator, bases = prop('max'), prop('den'), prop('vbase')
            for name in (maximum, denominator, bases):
                css += register(name, name != maximum)
            valid = lambda slot, prop=prop: f'clamp(0,sign(var({prop("position")}) - {slot + 1}) + 1,1)'
            for slot in range(capacity):
                css += register(prop(f'valid-{slot}')) + register(prop(f'exp-{slot}'), True)
                score_reads.append(f'{prop(f"valid-{slot}")}:{valid(slot)}')
            score_reads.append(maximum + ':max(' + ','.join(f'if(style({prop(f"valid-{s}")}:1):var({prop(f"score-{s}")});else:-1000000)' for s in range(capacity)) + ')')
            for slot in range(capacity):
                score_reads.append(f'{prop(f"exp-{slot}")}:if(style({prop(f"valid-{slot}")}:1):exp(calc(var({prop(f"score-{slot}")}) - var({maximum})));else:0)')
            score_reads.append(denominator + ':calc(' + ' + '.join(f'var({prop(f"exp-{s}")})' for s in range(capacity)) + ')')
            score_reads.append(bases + ':max(.000001,' + ','.join(f'var(--fr-vs-{s}-{head})' for s in range(capacity)) + ')')
            css += rule(f'.oa-score-reader-{head}', animation_reader(score_keys, score_tl) + ';' + ';'.join(score_reads))
            for slot in range(capacity):
                weight = f'calc(var({prop(f"exp-{slot}")}) * var(--fr-vs-{slot}-{head}) / var({bases}))'
                probability = '1' if value_layout == 'widths' else weight
                declaration = f'font-family:OwnedValue;font-size:{base.VALUE_SIZE}px;font-variation-settings:var(--fr-v-{slot}-{head}),"P000" {probability};font-kerning:none;font-style:normal;display:block;white-space:pre;flex:none'
                if value_layout == 'widths':
                    base_pixels = value['base'] * value_unit
                    declaration += f';width:calc-size(max-content,calc({base_pixels:.12g}px + (size - {base_pixels:.12g}px) * {weight}));min-width:0'
                css += rule(f'.oa-v-{head}-{slot}', declaration)
            value_rows = []
            for coordinate in range(base.DIM):
                dimension = f'calc-size(max-content,calc(262144px + (size - {capacity * value["base"] * value_unit:.12g}px) * var({bases}) / var({denominator}) * {128 / (value["coefficient"] * value_unit):.12g}))'
                runs = ''.join(f'<i class="oa-v-{head}-{slot}">&#x{base.CODEPOINT_BASE + coordinate:X};</i>' for slot in range(capacity))
                value_rows.append(f'<span class="oa-metric oa-value-row" style="width:{dimension};view-timeline:{coordinates[head * base.DIM + coordinate]} inline">{runs}</span>')
            output_tl, output_key, output_progress = f'--{prefix}-value-done', f'{prefix}-value-done', prop('output-progress')
            output_ready, committed = prop('output-ready'), prop('committed')
            value_rows.append(metric(f'calc(262144px + var({prop("epoch")}) * 1024px)', output_tl))
            css += register(output_progress) + register(output_ready) + register(committed, True) + animation(output_key, output_progress)
            css += rule(f'.oa-output-receipt-{head}', f'container-name:{output_container};' + animation_reader([output_key], [output_tl]) + f';{output_ready}:calc(1 - min(1,abs({decode(output_progress, rounded=True)} - var(--oa-epoch))));{committed}:0')
            css += rule(f'@container {controller} style({held}:1)', rule(f'.oa-output-receipt-{head}', f'{committed}:calc(var(--oa-epoch) * var({output_ready}))'))
            signals = []
            for generation in range(1, max_generations + 1):
                ready_id, done_id = f'{prefix}-capture-{generation}', f'{prefix}-captured-{generation}'
                css += rule(f'@container {controller} style({target}:{generation})', rule(f'@container {output_container} style({output_ready}:1)', rule(f'#{ready_id}', 'animation:oa-pulse 1ms both')))
                css += rule(f'.oa-head-{head}:where(:has(#{done_id}.done))', f'{captured}:{generation}')
                signals.append(f'<g id="{ready_id}"></g><g id="{done_id}"><set attributeName="class" to="done" begin="{ready_id}.animationend+0.001s" fill="freeze"/></g>')
            commit_tl = f'--{prefix}-committed'
            commit_timelines.append(commit_tl)
            output_receipt = f'<div class="oa-output-receipt-{head}"><svg xmlns="http://www.w3.org/2000/svg" class="oa-signals">' + ''.join(signals) + '</svg>' + scroller(metric(f'calc(262144px + var({committed}) * 1024px)', commit_tl)) + '</div>'
            css += rule(f'.oa-head-{head}', 'timeline-scope:' + ','.join(score_tl + [stamp_tl, output_tl]))
            computation = scroller(''.join(score_metrics), f'oa-score-source-{head}') + f'<div class="oa-score-reader-{head}"><div class="oa-score-receipt-{head}"><div class="oa-score-gate-{head}">' + scroller(''.join(value_rows), f'oa-value-source-{head}') + '</div></div></div>'
            for layer in reversed(range(blocks)):
                computation = f'<div class="oa-bank-{head} oa-bank-{head}-{layer}" data-head="{head}" data-layer="{layer}">' + computation + '</div>'
            heads.append(f'<div class="oa-head-{head}"><div class="oa-input-reader-{head}"><div class="oa-input-bank-{head}">' + computation + output_receipt + '</div></div></div>')
        # Only the small per-head completion stamps are joined here. Coordinate
        # context geometry goes directly from each owner to the existing bridge.
        join_keys, join_reads, join_conditions = [], [], []
        css += register('--oa-all-ready') + register('--oa-output-epoch', True)
        for head, timeline in enumerate(commit_timelines):
            key, progress, tag = f'oa-join-{head}', f'--oa-join-p-{head}', f'--oa-join-tag-{head}'
            css += register(progress) + register(tag) + animation(key, progress)
            join_keys.append(key)
            join_reads.append(f'{tag}:{decode(progress, rounded=True)}')
            join_conditions.append(f'1 - min(1,abs(var({tag}) - var(--oa-epoch)))')
        css += rule('.oa-all-heads-join', animation_reader(join_keys, commit_timelines) + ';' + ';'.join(join_reads) + ';--oa-all-ready:min(' + ','.join(f'calc({x})' for x in join_conditions) + ');--oa-output-epoch:calc(var(--oa-epoch) * var(--oa-all-ready))')
        join = '<div class="oa-all-heads-join">' + scroller(metric('calc(262144px + var(--oa-output-epoch) * 1024px)', context_marker)) + '</div>'
        css += rule('.oa-consumers', 'timeline-scope:' + ','.join(commit_timelines))
        css += rule(self.input_scope, 'timeline-scope:' + ','.join(input_timelines))
        metadata = {'ownedHeads': base.HEADS, 'headWidth': base.DIM, 'kvSlots': capacity, 'layers': blocks, 'cacheFieldsPerLayer': len(base.storage_names(capacity)), 'valueLayout': value_layout, 'operators': operators, 'fontVectorOperatorVersion': 2, 'runtimeJavaScript': False, 'detachedInputBoundary': True, 'inputGeometryCoordinates': base.HEADS * (3 * base.DIM + 3), 'allHeadGenerationJoin': True, 'maxGenerations': max_generations, 'cacheSelectors': {str(layer): [f'.oa-bank-{head}-{layer}' for head in range(base.HEADS)] for layer in range(blocks)}, 'contextMarker': context_marker, 'expectedEpochProperty': self.expected_epoch, 'inputTimelineScope': self.input_scope}
        producer_html = scroller(''.join(producer_metrics), 'oa-source')
        detached = '<div class="oa-consumers">' + ''.join(heads) + join + '</div>'
        self.artifact = AttentionArtifact(producer_html, detached, css, metadata)
        return producer_html, css, metadata


def collect_cache_layer(cdp, layer, capacity):
    """Read actual owned banks; merge only each bank's own original FC fields."""
    from probe_native_value_latch import props
    from profile_hybrid_twelve_block import query

    merged = {}
    for head in range(base.HEADS):
        state = props(cdp, query(cdp, f'.oa-bank-{head}-{layer}'))
        for slot in range(capacity):
            for kind in ('k', 'v', 'ks', 'vs'):
                name = f'--fc-{kind}-{slot}-{head}'
                if name not in state:
                    raise ValueError(f'Missing real stored field {name} at head {head}, layer {layer}')
                merged[name] = state[name]
    return merged


@contextmanager
def install_native_attention(*, value_layout="widths"):
    """Compile-time hook; original compiler files and live pages are untouched."""
    import browser_gpt2_reused_adapter as adapter

    compiler = OwnedAttention(expected_epoch='--native-pass', input_scope='.core-block', value_layout=value_layout)
    original = adapter.compile_reused

    def detached_reused(*args, **kwargs):
        body, css = original(*args, **kwargs)
        artifact = compiler.artifact
        if artifact is None or body.count('<div class="loop-reader">') != 1:
            raise ValueError('Expected one reusable core loop and one owned attention artifact')
        guard = '<div class="shared-qkv-gate">' + artifact.producer_html
        if guard not in body:
            raise ValueError('Owned producer must remain inside the actual QKV generation gate')
        artifact.metadata['producerInsideQkvGenerationGate'] = True
        return artifact.detached_consumers_html + body, css

    with patch('browser_gpt2_font_vector_cache.attention', compiler.attention), patch.object(adapter, 'compile_reused', detached_reused):
        yield compiler
