#!/usr/bin/env python3
"""Build ideal-vector-carrier upper-bound probes for real GPT-2 matrices.

The runtime pages contain HTML/CSS only.  An external benchmark toggles one
class to select between two exact, offline-computed vectors.  The variants
separate custom-property installation, variable substitution, and the next
real HVAR matrix stage.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_avar2_hvar_real_gpt2_tile import block_zero_mlp_input
from build_gpt2_block_css import (
    FONT_SIZE,
    MLP_WIDTH,
    PACKED_CODEPOINT_BASE,
    QUANT_BITS,
    UNITS_PER_EM,
    WIDTH,
    FontGroup,
    font_faces,
    gelu_new,
    global_axis_tag,
    model_data,
    packed_axis_tag,
)
from build_pretrained_gpt2 import css_number
from build_matrix_backend_prototypes import build_direct_font_backend
from build_signed_hvar_chain import quantize_float_rows, safe_base_advance


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "ideal-vector-carrier"
TOKEN_IDS = (11, 612)


def properties(count: int) -> str:
    return "".join(
        f'@property --v-{index:04d}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for index in range(count)
    )


def declarations(vector: np.ndarray) -> str:
    return "".join(
        f"--v-{index:04d}:{css_number(value)};"
        for index, value in enumerate(vector)
    )


def settings(tags: list[str], vector: np.ndarray | None) -> str:
    values = (
        (f"var(--v-{index:04d})" for index in range(len(tags)))
        if vector is None
        else (css_number(value) for value in vector)
    )
    return ",".join(f'"{tag}" {value}' for tag, value in zip(tags, values))


def build_local_font_group(
    name: str,
    codes: np.ndarray,
    *,
    row_specific_bases: bool = False,
    globally_unique_tags: bool = False,
) -> FontGroup:
    names: list[str] = []
    hashes: list[str] = []
    bases: list[int] = []
    codepoint_starts: list[int] = []
    row_bases: list[np.ndarray] = []
    for shard, start in enumerate(range(0, codes.shape[1], 256)):
        stop = min(start + 256, codes.shape[1])
        shard_codes = codes[:, start:stop]
        base = safe_base_advance(shard_codes)
        per_row = (
            np.sum(np.abs(shard_codes.astype(np.int64)), axis=1).astype(np.int32)
            + 32
        )
        stem = f"{name}-s{shard}"
        ttf = OUT / f"{stem}.ttf"
        woff2 = ttf.with_suffix(".woff2")
        codepoint_start = PACKED_CODEPOINT_BASE + shard * codes.shape[0]
        if not woff2.exists():
            build_direct_font_backend(
                shard_codes,
                ttf,
                signed_axes=True,
                base_advance=per_row if row_specific_bases else base,
                codepoint_start=codepoint_start,
                axis_tags=[
                    global_axis_tag(start + local)
                    if globally_unique_tags
                    else packed_axis_tag(shard, local)
                    for local in range(stop - start)
                ],
            )
        names.append(stem)
        hashes.append(hashlib.sha256(woff2.read_bytes()).hexdigest()[:12])
        bases.append(base)
        codepoint_starts.append(codepoint_start)
        row_bases.append(per_row)
    return FontGroup(
        tuple(names),
        tuple(hashes),
        tuple(bases),
        tuple(codepoint_starts),
        codes.shape[0],
        tuple(row_bases) if row_specific_bases else None,
    )


def faces_for(stage: str, group: FontGroup) -> str:
    return font_faces(stage, group)


def shell(css: str, body: str, title: str) -> str:
    return f"""<!doctype html>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
<body>
{body}
</body>
"""


def common_css(faces: str = "") -> str:
    return (
        faces
        + "html,body{margin:0;padding:0}"
        + "#state{position:fixed;left:-20000px;top:0}"
        + "#axis-sink{position:fixed;left:-20000px;top:0}"
        + f"#bank{{position:fixed;left:-20000px;top:0;font-size:{FONT_SIZE}px;"
        + "font-style:normal;font-kerning:none;font-variant-ligatures:none;"
        + "line-height:1;white-space:pre;display:grid;align-items:start}}"
        + ".output{display:block;width:max-content;height:1px;overflow:hidden;"
        + "font:inherit;white-space:pre}"
    )


def output_markup(codepoint_starts: tuple[int, ...], output_count: int) -> str:
    rows = []
    for output in range(output_count):
        chars = "".join(
            f"&#x{start + output:X};" for start in codepoint_starts
        )
        rows.append(f'<i class="output" data-output="{output}">{chars}</i>')
    return '<div id="bank">' + "".join(rows) + "</div>"


def build_stage(
    *,
    name: str,
    vectors: np.ndarray,
    tags: list[str],
    family: str,
    faces: str,
    codepoint_starts: tuple[int, ...],
    output_count: int,
    columns: int,
    expected_widths: np.ndarray,
) -> dict[str, object]:
    count = vectors.shape[1]
    registered = properties(count)
    state_rules = (
        f"#state{{{declarations(vectors[0])}}}"
        f"body.case1 #state{{{declarations(vectors[1])}}}"
    )
    inherited_vars = settings(tags, None)
    literal0 = settings(tags, vectors[0])
    literal1 = settings(tags, vectors[1])
    markup = output_markup(codepoint_starts, output_count)
    matrix_base = (
        common_css(faces)
        + f"#bank{{grid-template-columns:repeat({columns},max-content);font-family:{family}}}"
    )

    pages = {
        "state": shell(
            registered + common_css() + state_rules,
            '<div id="state"></div>',
            f"{name}: ideal vector state",
        ),
        "axis": shell(
            registered
            + common_css()
            + state_rules
            + f"#axis-sink{{font-variation-settings:{inherited_vars}}}",
            '<div id="state"><span id="axis-sink">.</span></div>',
            f"{name}: vector substitution",
        ),
        "vars": shell(
            registered
            + matrix_base
            + state_rules
            + f"#bank{{font-variation-settings:{inherited_vars}}}",
            f'<div id="state">{markup}</div>',
            f"{name}: variables into real matrix",
        ),
        "literal": shell(
            matrix_base
            + f"#bank{{font-variation-settings:{literal0}}}"
            + f"body.case1 #bank{{font-variation-settings:{literal1}}}",
            markup,
            f"{name}: literals into real matrix",
        ),
        "fixed": shell(
            matrix_base
            + "#bank{font-variation-settings:normal}"
            + f'body.case1 #bank{{font-variation-settings:"{tags[0]}" 0}}',
            markup,
            f"{name}: matrix shaping control",
        ),
    }
    for variant, html in pages.items():
        (OUT / f"{name}-{variant}.html").write_text(html)

    reference = {
        "name": name,
        "inputCount": count,
        "outputCount": output_count,
        "glyphsPerOutput": len(codepoint_starts),
        "glyphCount": output_count * len(codepoint_starts),
        "tokenIds": list(TOKEN_IDS),
        "expectedWidths": expected_widths.tolist(),
        "files": [f"{name}-{variant}.html" for variant in pages],
    }
    (OUT / f"{name}-reference.json").write_text(
        json.dumps(reference, indent=2) + "\n"
    )
    return reference


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    data = model_data()
    inputs = np.stack(
        [block_zero_mlp_input(token_id, tensors) for token_id in TOKEN_IDS]
    )

    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    q_proj = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)

    input_range = float(np.max(np.abs(inputs)) * 1.01)
    normalized_inputs = inputs / input_range
    fc_raw = normalized_inputs @ q_fc.codes.astype(np.float64).T
    fc_pre = (
        fc_raw * (input_range * q_fc.scales)[None, :]
        + data["fc_bias"][None, :]
    )
    hidden = gelu_new(fc_pre)
    hidden_range = float(np.max(np.abs(hidden)) * 1.01)
    normalized_hidden = hidden / hidden_range
    projection_raw = normalized_hidden @ q_proj.codes.astype(np.float64).T

    fc_fonts = build_local_font_group("ideal-fc", q_fc.codes)
    projection_fonts = build_local_font_group(
        "ideal-projection",
        q_proj.codes,
        row_specific_bases=True,
        globally_unique_tags=True,
    )
    if projection_fonts.row_bases is None:
        raise ValueError("projection fonts must have row-specific bases")

    fc_tags = [
        packed_axis_tag(shard, local)
        for shard in range(WIDTH // 256)
        for local in range(256)
    ]
    projection_tags = [global_axis_tag(index) for index in range(MLP_WIDTH)]

    fc_expected = (
        (sum(fc_fonts.bases) + fc_raw) * FONT_SIZE / UNITS_PER_EM
    )
    projection_bases = np.sum(
        np.stack(projection_fonts.row_bases), axis=0
    )
    projection_expected = (
        projection_bases[None, :] + projection_raw
    ) * FONT_SIZE / UNITS_PER_EM

    references = [
        build_stage(
            name="fc",
            vectors=normalized_inputs,
            tags=fc_tags,
            family=",".join(f"idealfcS{i}" for i in range(len(fc_fonts.names))),
            faces=faces_for("ideal-fc", fc_fonts),
            codepoint_starts=fc_fonts.codepoint_starts,
            output_count=MLP_WIDTH,
            columns=64,
            expected_widths=fc_expected,
        ),
        build_stage(
            name="projection",
            vectors=normalized_hidden,
            tags=projection_tags,
            family=",".join(
                f"idealprojectionS{i}" for i in range(len(projection_fonts.names))
            ),
            faces=faces_for("ideal-projection", projection_fonts),
            codepoint_starts=projection_fonts.codepoint_starts,
            output_count=WIDTH,
            columns=32,
            expected_widths=projection_expected,
        ),
    ]
    manifest = {
        "description": "Ideal whole-vector CSS carrier upper-bound probes",
        "fontSize": FONT_SIZE,
        "unitsPerEm": UNITS_PER_EM,
        "stages": references,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(OUT),
                "stages": [
                    {
                        key: stage[key]
                        for key in (
                            "name",
                            "inputCount",
                            "outputCount",
                            "glyphCount",
                        )
                    }
                    for stage in references
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
