#!/usr/bin/env python3
"""Build a no-JS GPT-2 FC→GELU→projection numeric-vector experiment."""

from __future__ import annotations

import hashlib
import json

import numpy as np

from build_gpt2_block_css import (
    MLP_WIDTH,
    OUT,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    build_font_group,
    font_faces,
    gelu_new,
    global_axis_tag,
    layer_norm,
    model_data,
    packed_axis_tag,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows
from build_view_timeline_fc import FONT_SIZE, TRACK_WIDTH, VIEWPORT


HTML_PATH = OUT / "additive-vector-mlp.html"
CSS_PATH = OUT / "additive-vector-mlp.css"
REFERENCE_PATH = OUT / "additive-vector-mlp-reference.json"
TRANSPORT_PATH = OUT / "numeric-vector-transport-only.html"
PACKED_HTML_PATH = OUT / "additive-vector-mlp-packed.html"
PACKED_CSS_PATH = OUT / "additive-vector-mlp-packed.css"
PACKED_REFERENCE_PATH = OUT / "additive-vector-mlp-packed-reference.json"
SCALING_REFERENCE_PATH = OUT / "additive-vector-mlp-scaling-reference.json"
FIXED_FC_TRANSPORT_PATH = OUT / "additive-vector-mlp-packed-fixed-fc-transport.html"
PAIRED_FC_TRANSPORT_PATH = OUT / "additive-vector-mlp-paired-fc-transport.html"
PAIRED_FC_CSS_PATH = OUT / "additive-vector-mlp-paired-fc-transport.css"
PAIRED_HTML_PATH = OUT / "additive-vector-mlp-paired.html"
SHARD = 256


def main() -> None:
    data = model_data()
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    q_attention = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    residual = data["x"] + q_attention.reconstructed @ n1 + composed_bias
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])

    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    q_proj = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
    activation_range = float(np.max(np.abs(n2)) * 1.01)
    normalized = n2 / activation_range
    fc_raw = q_fc.codes.astype(np.float64) @ normalized
    fc_pre = fc_raw * activation_range * q_fc.scales + data["fc_bias"]
    hidden = gelu_new(fc_pre)
    hidden_range = float(np.max(np.abs(hidden)) * 1.01)
    projection_raw = q_proj.codes.astype(np.float64) @ (hidden / hidden_range)

    fc_fonts = build_font_group("fc", q_fc.codes, rebuild=False)
    projection_fonts = build_font_group(
        "mlp-proj-rowbase", q_proj.codes, rebuild=False, row_specific_bases=True
    )
    packed_font_ready = all(
        (OUT / f"mlp-proj-run-s{shard}.woff2").exists()
        for shard in range(MLP_WIDTH // SHARD)
    )
    packed_projection_fonts = build_font_group(
        "mlp-proj-run",
        q_proj.codes,
        rebuild=not packed_font_ready,
        row_specific_bases=True,
        global_axis_offset=0,
    )
    if projection_fonts.row_bases is None:
        raise ValueError("projection fonts require row-specific bases")
    base_total = sum(fc_fonts.bases)

    timeline_names = [f"--t{index}" for index in range(MLP_WIDTH)]
    properties: list[str] = []
    keyframes: list[str] = []
    shard_rules: list[str] = []
    all_names: list[str] = []
    hidden_properties: list[str] = []
    for shard, start in enumerate(range(0, MLP_WIDTH, SHARD)):
        stop = start + SHARD
        settings: list[str] = []
        for output in range(start, stop):
            local = output - start
            prop = f"--v{output}"
            name = f"pv{output}"
            properties.append(
                f'@property {prop}{{syntax:"<number>";inherits:true;initial-value:0}}'
            )
            keyframes.append(
                f"@keyframes {name}{{from{{{prop}:0}}to{{{prop}:1}}}}"
            )
            factor = activation_range * q_fc.scales[output]
            all_names.append(name)
            hidden_properties.append(
                f"--h{output}:--hidden(var({prop}),{factor:.12g},"
                f"{float(data['fc_bias'][output]):.12g},{hidden_range:.12g})"
            )
            settings.append(
                f'"{packed_axis_tag(shard % 3, local)}" var(--h{output})'
            )
        shard_rules.append(
            f".vector-{shard}{{font-family:mlpflatS{shard};"
            f"font-variation-settings:{','.join(settings)}}}"
        )

    fc_settings = []
    for shard, start in enumerate(range(0, WIDTH, SHARD)):
        stop = start + SHARD
        fc_settings.extend(
            f'"{packed_axis_tag(shard % 3, local)}" '
            f"{css_number(normalized[start + local])}"
            for local in range(stop - start)
        )
    faces = font_faces("fc", fc_fonts) + font_faces("mlp-flat", projection_fonts)
    css = (
        faces
        + "@function --hidden(--p <number>,--factor <number>,--bias <number>,"
        + "--range <number>) returns <number>{"
        + f"--raw:calc((({VIEWPORT}/var(--p)) - {VIEWPORT})*{UNITS_PER_EM}/{FONT_SIZE} - {base_total});"
        + "--z:calc(var(--raw)*var(--factor) + var(--bias));"
        + "--t:calc(.797884561*(var(--z) + .044715*pow(var(--z),3)));"
        + "result:calc(.5*var(--z)*(1 + (exp(2*var(--t)) - 1)/(exp(2*var(--t)) + 1))/var(--range))}"
        + "".join(properties)
        + "".join(keyframes)
        + f'.scope{{timeline-scope:{",".join(timeline_names)};font-size:{FONT_SIZE}px;'
        + "font-kerning:none;font-style:normal}"
        + f'.fc-stage{{font-family:{",".join(f"fcS{i}" for i in range(len(fc_fonts.names)))};'
        + f'font-variation-settings:{",".join(fc_settings)}}}'
        + ".scroller{position:fixed;left:0;top:-10000px;"
        + f"width:{VIEWPORT}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        + f".track{{position:relative;width:{TRACK_WIDTH}px;height:1px}}"
        + ".fc-metric,.partial,.merged{position:absolute;left:0;top:0;"
        + "display:inline-block;width:max-content;height:1px;overflow:hidden;"
        + "white-space:pre;font-style:normal}"
        + ".vector-state{"
        + ";".join(hidden_properties)
        + ";"
        + f"animation-name:{','.join(all_names)};animation-duration:1s;"
        + "animation-timing-function:linear;"
        + "animation-fill-mode:both;"
        + f"animation-timeline:{','.join(timeline_names)};"
        + "animation-range:cover}"
        + ".vector{position:static}"
        + "".join(shard_rules)
        + "html{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}"
        + "body{margin:2rem}h1{font:600 1.25rem system-ui,sans-serif}"
    )

    fc_glyphs = []
    for output in range(MLP_WIDTH):
        characters = "".join(
            f"&#x{start + output:X};" for start in fc_fonts.codepoint_starts
        )
        fc_glyphs.append(
            f'<i class="fc-metric" style="view-timeline:{timeline_names[output]} inline">'
            f"{characters}</i>"
        )

    vector_branches = []
    for shard in range(len(projection_fonts.names)):
        glyphs = []
        for output in range(WIDTH):
            codepoint = projection_fonts.codepoint_starts[shard] + output
            glyphs.append(
                f'<i class="partial" style="anchor-name:--a{shard}-{output}">'
                f"&#x{codepoint:X};</i>"
            )
        vector_branches.append(
            f'<div class="vector vector-{shard}">{"".join(glyphs)}</div>'
        )

    merged = []
    grouped = []
    expected_widths = []
    for output in range(WIDTH):
        base = sum(int(rows[output]) for rows in projection_fonts.row_bases)
        expected_width = (base + projection_raw[output]) * FONT_SIZE / UNITS_PER_EM
        expected_widths.append(expected_width)
        group_names = []
        for group, first_shard in enumerate(range(0, len(projection_fonts.names), 4)):
            terms = " + ".join(
                f"anchor-size(--a{shard}-{output} width)"
                for shard in range(first_shard, min(first_shard + 4, len(projection_fonts.names)))
            )
            name = f"--g{group}-{output}"
            group_names.append(name)
            grouped.append(
                f'<i class="merged" style="anchor-name:{name};width:calc({terms})"></i>'
            )
        width = " + ".join(f"anchor-size({name} width)" for name in group_names)
        merged.append(
            f'<i class="merged" id="m{output}" data-expected-width="{expected_width:.12g}" '
            f'style="width:calc({width})"></i>'
        )

    diagnostics = []
    for count in range(1, len(projection_fonts.names) + 1):
        terms = " + ".join(
            f"anchor-size(--a{shard}-0 width)" for shard in range(count)
        )
        diagnostics.append(
            f'<i class="merged" id="diag-{count}" style="width:calc({terms})"></i>'
        )

    CSS_PATH.write_text(css)
    tag = hashlib.sha256(CSS_PATH.read_bytes()).hexdigest()[:12]
    HTML_PATH.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Additive-vector GPT-2 MLP</title>'
        f'<link rel="stylesheet" href="{CSS_PATH.name}?v={tag}">'
        '<h1>GPT-2 FC → vector → projection</h1>'
        '<p>No JavaScript. The 3,072-value hidden state remains in twelve font-axis vectors.</p>'
        '<div class="scope"><div class="fc-stage"><div class="scroller"><div class="track">'
        + "".join(fc_glyphs)
        + "</div></div></div>"
        + '<div class="vector-state">'
        + "".join(vector_branches)
        + "".join(diagnostics)
        + '<div class="group-mergers">'
        + "".join(grouped)
        + "</div>"
        + '<div class="mergers">'
        + "".join(merged)
        + "</div></div></div>"
    )
    TRANSPORT_PATH.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>3,072-value numeric transport only</title>'
        f'<link rel="stylesheet" href="{CSS_PATH.name}?v={tag}">'
        '<h1>3,072 geometry values → CSS numeric state</h1>'
        '<div class="scope"><div class="fc-stage"><div class="scroller"><div class="track">'
        + "".join(fc_glyphs)
        + '</div></div></div><div class="vector-state" id="state"></div></div>'
    )
    REFERENCE_PATH.write_text(
        json.dumps(
            {
                "input_width": WIDTH,
                "hidden_width": MLP_WIDTH,
                "output_width": WIDTH,
                "vector_shards": len(projection_fonts.names),
                "axes_per_shard": SHARD,
                "geometry_decoder": "exact CSS reciprocal",
                "hidden": hidden.tolist(),
                "hidden_range": hidden_range,
                "projection_raw": projection_raw.tolist(),
                "expected_widths": expected_widths,
                "html_bytes": HTML_PATH.stat().st_size,
                "css_bytes": CSS_PATH.stat().st_size,
                "transport_html_bytes": TRANSPORT_PATH.stat().st_size,
            },
            indent=2,
        )
        + "\n"
    )

    packed_settings = [
        f'"{global_axis_tag(index)}" var(--h{index})'
        for index in range(MLP_WIDTH)
    ]
    packed_families = ",".join(
        f"mlprunS{shard}" for shard in range(len(packed_projection_fonts.names))
    )
    packed_css = (
        font_faces("fc", fc_fonts)
        + font_faces("mlp-run", packed_projection_fonts)
        + "@function --hidden(--p <number>,--factor <number>,--bias <number>,"
        + "--range <number>) returns <number>{"
        + f"--raw:calc((({VIEWPORT}/var(--p)) - {VIEWPORT})*{UNITS_PER_EM}/{FONT_SIZE} - {base_total});"
        + "--z:calc(var(--raw)*var(--factor) + var(--bias));"
        + "--t:calc(.797884561*(var(--z) + .044715*pow(var(--z),3)));"
        + "result:calc(.5*var(--z)*(1 + (exp(2*var(--t)) - 1)/(exp(2*var(--t)) + 1))/var(--range))}"
        + "".join(properties)
        + "".join(keyframes)
        + f'.scope{{timeline-scope:{",".join(timeline_names)};font-size:{FONT_SIZE}px;'
        + "font-kerning:none;font-style:normal;font-variant-ligatures:none}"
        + f'.fc-stage{{font-family:{",".join(f"fcS{i}" for i in range(len(fc_fonts.names)))};'
        + f'font-variation-settings:{",".join(fc_settings)}}}'
        + ".scroller{position:fixed;left:0;top:-10000px;"
        + f"width:{VIEWPORT}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        + f".track{{position:relative;width:{TRACK_WIDTH}px;height:1px}}"
        + ".fc-metric,.combined{position:absolute;left:0;top:0;"
        + "display:inline-block;width:max-content;height:1px;overflow:hidden;"
        + "white-space:pre;font-style:normal}"
        + ".vector-state{"
        + ";".join(hidden_properties)
        + ";"
        + f"animation-name:{','.join(all_names)};animation-duration:1s;"
        + "animation-timing-function:linear;animation-fill-mode:both;"
        + f"animation-timeline:{','.join(timeline_names)};animation-range:cover}}"
        + f'.projection-run{{font-family:{packed_families};'
        + f'font-variation-settings:{",".join(packed_settings)}}}'
        + "html{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}"
        + "body{margin:2rem}h1{font:600 1.25rem system-ui,sans-serif}"
    )
    packed_outputs = []
    packed_expected_widths = []
    if packed_projection_fonts.row_bases is None:
        raise ValueError("packed projection fonts require row-specific bases")
    for output in range(WIDTH):
        characters = "".join(
            f"&#x{start + output:X};"
            for start in packed_projection_fonts.codepoint_starts
        )
        base = sum(int(rows[output]) for rows in packed_projection_fonts.row_bases)
        expected_width = (base + projection_raw[output]) * FONT_SIZE / UNITS_PER_EM
        packed_expected_widths.append(expected_width)
        packed_outputs.append(
            f'<i class="combined" id="p{output}" '
            f'data-expected-width="{expected_width:.12g}">{characters}</i>'
        )
    PACKED_CSS_PATH.write_text(packed_css)
    packed_tag = hashlib.sha256(PACKED_CSS_PATH.read_bytes()).hexdigest()[:12]
    PACKED_HTML_PATH.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Packed-run GPT-2 MLP</title>'
        f'<link rel="stylesheet" href="{PACKED_CSS_PATH.name}?v={packed_tag}">'
        '<h1>GPT-2 FC → packed fallback run → projection</h1>'
        '<p>No JavaScript. One output element contains all twelve projection glyphs.</p>'
        '<div class="scope"><div class="fc-stage"><div class="scroller"><div class="track">'
        + "".join(fc_glyphs)
        + '</div></div></div><div class="vector-state">'
        + '<div class="projection-run">'
        + "".join(packed_outputs)
        + "</div></div></div>"
    )
    PACKED_REFERENCE_PATH.write_text(
        json.dumps(
            {
                "input_width": WIDTH,
                "hidden_width": MLP_WIDTH,
                "output_width": WIDTH,
                "projection_elements": WIDTH,
                "projection_glyphs": WIDTH * len(packed_projection_fonts.names),
                "vector_shards": len(packed_projection_fonts.names),
                "axes_per_shard": SHARD,
                "geometry_decoder": "exact CSS reciprocal",
                "hidden": hidden.tolist(),
                "hidden_range": hidden_range,
                "projection_raw": projection_raw.tolist(),
                "expected_widths": packed_expected_widths,
                "html_bytes": PACKED_HTML_PATH.stat().st_size,
                "css_bytes": PACKED_CSS_PATH.stat().st_size,
            },
            indent=2,
        )
        + "\n"
    )

    def packed_page(
        title: str,
        description: str,
        outputs: list[str],
        override: str = "",
    ) -> str:
        return (
            '<!doctype html><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f"<title>{title}</title>"
            f'<link rel="stylesheet" href="{PACKED_CSS_PATH.name}?v={packed_tag}">'
            + (f"<style>{override}</style>" if override else "")
            + f"<h1>{title}</h1><p>{description}</p>"
            + '<div class="scope"><div class="fc-stage"><div class="scroller"><div class="track">'
            + "".join(fc_glyphs)
            + '</div></div></div><div class="vector-state">'
            + ('<div class="projection-run">' + "".join(outputs) + "</div>" if outputs else "")
            + "</div></div>"
        )

    scaling_cases = []
    normalized_hidden = hidden / hidden_range
    for shard_count in (1, 2, 4, 8):
        input_stop = shard_count * SHARD
        families = ",".join(
            f"mlprunS{shard}" for shard in range(shard_count)
        )
        settings = ",".join(packed_settings[:input_stop])
        override = (
            f".projection-run{{font-family:{families};"
            f"font-variation-settings:{settings}}}"
        )
        partial_raw = (
            q_proj.codes[:, :input_stop].astype(np.float64)
            @ normalized_hidden[:input_stop]
        )
        outputs = []
        for output in range(WIDTH):
            characters = "".join(
                f"&#x{packed_projection_fonts.codepoint_starts[shard] + output:X};"
                for shard in range(shard_count)
            )
            base = sum(
                int(packed_projection_fonts.row_bases[shard][output])
                for shard in range(shard_count)
            )
            expected_width = (base + partial_raw[output]) * FONT_SIZE / UNITS_PER_EM
            outputs.append(
                f'<i class="combined" data-expected-width="{expected_width:.12g}">'
                f"{characters}</i>"
            )
        path = OUT / f"additive-vector-mlp-packed-{shard_count:02d}.html"
        path.write_text(
            packed_page(
                f"Packed projection: {shard_count} shard(s)",
                f"No JavaScript. {shard_count * WIDTH:,} live variable glyphs.",
                outputs,
                override,
            )
        )
        scaling_cases.append(
            {
                "name": f"live-{shard_count}",
                "path": path.name,
                "shards": shard_count,
                "projection_glyphs": WIDTH * shard_count,
                "variation_values": input_stop,
            }
        )

    fixed_outputs = []
    for output in range(WIDTH):
        characters = "".join(
            f"&#x{start + output:X};"
            for start in packed_projection_fonts.codepoint_starts
        )
        base = sum(int(rows[output]) for rows in packed_projection_fonts.row_bases)
        expected_width = base * FONT_SIZE / UNITS_PER_EM
        fixed_outputs.append(
            f'<i class="combined" data-expected-width="{expected_width:.12g}">'
            f"{characters}</i>"
        )
    fixed_path = OUT / "additive-vector-mlp-packed-fixed.html"
    fixed_path.write_text(
        packed_page(
            "Packed projection: fixed axes",
            "No JavaScript. 9,216 fallback glyphs with variable axes disabled.",
            fixed_outputs,
            ".projection-run{font-variation-settings:normal}",
        )
    )
    scaling_cases.append(
        {
            "name": "fixed-12",
            "path": fixed_path.name,
            "shards": 12,
            "projection_glyphs": WIDTH * 12,
            "variation_values": 0,
        }
    )
    transport_path = OUT / "additive-vector-mlp-packed-transport.html"
    transport_path.write_text(
        packed_page(
            "Packed projection: transport only",
            "No JavaScript. The 3,072-value FC transport without projection glyphs.",
            [],
        )
    )
    scaling_cases.append(
        {
            "name": "transport-only",
            "path": transport_path.name,
            "shards": 0,
            "projection_glyphs": 0,
            "variation_values": 0,
        }
    )
    fixed_fc_glyphs = []
    for output in range(MLP_WIDTH):
        encoded_width = (
            (base_total + float(fc_raw[output])) * FONT_SIZE / UNITS_PER_EM
        )
        fixed_fc_glyphs.append(
            f'<i class="fc-metric" style="width:{encoded_width:.12g}px;'
            f'view-timeline:{timeline_names[output]} inline"></i>'
        )
    FIXED_FC_TRANSPORT_PATH.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>3,072 fixed widths → CSS numeric state</title>'
        f'<link rel="stylesheet" href="{PACKED_CSS_PATH.name}?v={packed_tag}">'
        '<style>.fc-stage{font-family:initial;font-variation-settings:normal}</style>'
        '<h1>Fixed-width transport ablation</h1>'
        '<p>No JavaScript. Same 3,072 timelines and animations, without HVAR shaping.</p>'
        '<div class="scope"><div class="fc-stage"><div class="scroller"><div class="track">'
        + "".join(fixed_fc_glyphs)
        + '</div></div></div><div class="vector-state" id="state"></div></div>'
    )
    scaling_cases.append(
        {
            "name": "fixed-fc-transport",
            "path": FIXED_FC_TRANSPORT_PATH.name,
            "shards": 0,
            "projection_glyphs": 0,
            "variation_values": 0,
        }
    )

    # A view timeline exposes both its subject's position and its extent. Reading
    # the same timeline over the cover and entry ranges lets us recover both, so
    # two consecutive HVAR outputs can share one timeline without bit-packing.
    pair_viewport = 32_768
    pair_origin = -20_000
    pair_names = [f"--tp{index}" for index in range(MLP_WIDTH // 2)]
    pair_properties: list[str] = []
    pair_keyframes: list[str] = []
    pair_animation_names: list[str] = []
    pair_animation_timelines: list[str] = []
    pair_hidden_properties: list[str] = []
    for pair, timeline in enumerate(pair_names):
        cover_prop = f"--c{pair}"
        entry_prop = f"--e{pair}"
        pair_animation = f"pp{pair}"
        pair_properties.extend(
            (
                f'@property {cover_prop}{{syntax:"<number>";inherits:true;initial-value:0}}',
                f'@property {entry_prop}{{syntax:"<number>";inherits:true;initial-value:0}}',
            )
        )
        pair_keyframes.append(
            f"@keyframes {pair_animation}{{"
            f"cover 0%{{{cover_prop}:0;{entry_prop}:0}}"
            f"entry 100%{{{entry_prop}:1}}"
            f"cover 100%{{{cover_prop}:1;{entry_prop}:1}}}}"
        )
        pair_animation_names.append(pair_animation)
        pair_animation_timelines.append(timeline)
        for within_pair in range(2):
            output = pair * 2 + within_pair
            factor = activation_range * q_fc.scales[output]
            function = "--hidden-left" if within_pair == 0 else "--hidden-width"
            pair_hidden_properties.append(
                f"--h{output}:{function}(var({cover_prop}),var({entry_prop}),"
                f"{factor:.12g},{float(data['fc_bias'][output]):.12g},{hidden_range:.12g})"
            )

    paired_css = (
        font_faces("fc", fc_fonts)
        + font_faces("mlp-run", packed_projection_fonts)
        + "@function --pair-width(--p <number>,--q <number>) returns <number>{"
        + f"result:calc(var(--p)*{pair_viewport}/(var(--q) - var(--p)))}}"
        + "@function --hidden-width(--p <number>,--q <number>,--factor <number>,"
        + "--bias <number>,--range <number>) returns <number>{"
        + f"--raw:calc((--pair-width(var(--p),var(--q))*{UNITS_PER_EM}/{FONT_SIZE}) - {base_total});"
        + "--z:calc(var(--raw)*var(--factor) + var(--bias));"
        + "--t:calc(.797884561*(var(--z) + .044715*pow(var(--z),3)));"
        + "result:calc(.5*var(--z)*(1 + (exp(2*var(--t)) - 1)/(exp(2*var(--t)) + 1))/var(--range))}"
        + "@function --hidden-left(--p <number>,--q <number>,--factor <number>,"
        + "--bias <number>,--range <number>) returns <number>{"
        + f"--encoded:calc({pair_viewport} - var(--q)*--pair-width(var(--p),var(--q)) - ({pair_origin}));"
        + f"--raw:calc(var(--encoded)*{UNITS_PER_EM}/{FONT_SIZE} - {base_total});"
        + "--z:calc(var(--raw)*var(--factor) + var(--bias));"
        + "--t:calc(.797884561*(var(--z) + .044715*pow(var(--z),3)));"
        + "result:calc(.5*var(--z)*(1 + (exp(2*var(--t)) - 1)/(exp(2*var(--t)) + 1))/var(--range))}"
        + "".join(pair_properties)
        + "".join(pair_keyframes)
        + f'.scope{{timeline-scope:{",".join(pair_names)};font-size:{FONT_SIZE}px;'
        + "font-kerning:none;font-style:normal;font-variant-ligatures:none}"
        + f'.fc-stage{{font-family:{",".join(f"fcS{i}" for i in range(len(fc_fonts.names)))};'
        + f'font-variation-settings:{",".join(fc_settings)}}}'
        + ".scroller{position:fixed;left:0;top:-10000px;"
        + f"width:{pair_viewport}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        + f".track{{position:relative;width:{TRACK_WIDTH}px;height:1px}}"
        + f".pair{{position:absolute;left:{pair_origin}px;top:0;display:inline-flex;height:1px}}"
        + ".subject{display:inline-block;width:max-content;height:1px;"
        + "overflow:hidden;white-space:pre;font-style:normal}"
        + ".vector-state{"
        + ";".join(pair_hidden_properties)
        + ";"
        + f"animation-name:{','.join(pair_animation_names)};animation-duration:1s;"
        + "animation-timing-function:linear;animation-fill-mode:both;"
        + f"animation-timeline:{','.join(pair_animation_timelines)}}}"
        + f'.projection-run{{font-family:{packed_families};'
        + f'font-variation-settings:{",".join(packed_settings)}}}'
        + ".combined{position:absolute;left:0;top:0;display:inline-block;"
        + "width:max-content;height:1px;overflow:hidden;white-space:pre;font-style:normal}"
    )
    paired_glyphs = []
    for pair, timeline in enumerate(pair_names):
        first = pair * 2
        encoded = []
        for output in (first, first + 1):
            encoded.append(
                "".join(f"&#x{start + output:X};" for start in fc_fonts.codepoint_starts)
            )
        paired_glyphs.append(
            f'<span class="pair">{encoded[0]}'
            f'<i class="subject" style="view-timeline:{timeline} inline">{encoded[1]}</i></span>'
        )
    PAIRED_FC_CSS_PATH.write_text(paired_css)
    paired_tag = hashlib.sha256(PAIRED_FC_CSS_PATH.read_bytes()).hexdigest()[:12]
    PAIRED_FC_TRANSPORT_PATH.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Paired FC geometry transport</title>'
        f'<link rel="stylesheet" href="{PAIRED_FC_CSS_PATH.name}?v={paired_tag}">'
        '<h1>Two HVAR outputs per view timeline</h1>'
        '<p>No JavaScript. Cover and entry progress recover position and width.</p>'
        '<div class="scope"><div class="fc-stage"><div class="scroller"><div class="track">'
        + "".join(paired_glyphs)
        + '</div></div></div><div class="vector-state" id="state"></div></div>'
    )
    PAIRED_HTML_PATH.write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<title>Paired-timeline GPT-2 MLP</title>'
        f'<link rel="stylesheet" href="{PAIRED_FC_CSS_PATH.name}?v={paired_tag}">'
        '<h1>GPT-2 FC → paired timeline transport → projection</h1>'
        '<p>No JavaScript. Two FC outputs share each view timeline.</p>'
        '<div class="scope"><div class="fc-stage"><div class="scroller"><div class="track">'
        + "".join(paired_glyphs)
        + '</div></div></div><div class="vector-state">'
        + '<div class="projection-run">'
        + "".join(packed_outputs)
        + '</div></div></div>'
    )
    scaling_cases.append(
        {
            "name": "paired-fc-transport",
            "path": PAIRED_FC_TRANSPORT_PATH.name,
            "shards": 0,
            "projection_glyphs": 0,
            "variation_values": 0,
            "fc_timelines": MLP_WIDTH // 2,
        }
    )
    scaling_cases.append(
        {
            "name": "paired-live-12",
            "path": PAIRED_HTML_PATH.name,
            "shards": 12,
            "projection_glyphs": WIDTH * 12,
            "variation_values": MLP_WIDTH,
            "fc_timelines": MLP_WIDTH // 2,
        }
    )
    scaling_cases.append(
        {
            "name": "live-12",
            "path": PACKED_HTML_PATH.name,
            "shards": 12,
            "projection_glyphs": WIDTH * 12,
            "variation_values": MLP_WIDTH,
        }
    )
    SCALING_REFERENCE_PATH.write_text(
        json.dumps({"cases": scaling_cases}, indent=2) + "\n"
    )
    print(
        {
            "vector_shards": len(projection_fonts.names),
            "html_bytes": HTML_PATH.stat().st_size,
            "css_bytes": CSS_PATH.stat().st_size,
            "packed_html_bytes": PACKED_HTML_PATH.stat().st_size,
            "packed_css_bytes": PACKED_CSS_PATH.stat().st_size,
            "packed_projection_elements": WIDTH,
            "no_javascript": "<script" not in HTML_PATH.read_text().lower(),
        }
    )


if __name__ == "__main__":
    main()
