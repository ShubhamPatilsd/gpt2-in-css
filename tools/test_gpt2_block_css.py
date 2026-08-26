#!/usr/bin/env python3
"""Verify the one-token GPT-2 block's font math and generated page offline."""

from __future__ import annotations

import json

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer

from build_gpt2_block_css import (
    EPSILON,
    MLP_WIDTH,
    OUT,
    QUANT_BITS,
    SHARD,
    WIDTH,
    gelu_new,
    layer_norm,
    model_data,
)
from build_matrix_backend_prototypes import output_glyph
from build_signed_hvar_chain import quantize_float_rows


def font_delta(path, vector: np.ndarray, output_count: int) -> np.ndarray:
    font = TTFont(path)
    location = {
        axis.axisTag: float(value)
        for axis, value in zip(font["fvar"].axes, vector)
    }
    instancer = VarStoreInstancer(
        font["HVAR"].table.VarStore, font["fvar"].axes, location
    )
    return np.asarray(
        [instancer[font.getGlyphID(output_glyph(i))] for i in range(output_count)],
        dtype=np.float64,
    )


def sharded_delta(stem: str, vector: np.ndarray, output_count: int) -> np.ndarray:
    result = np.zeros(output_count, dtype=np.float64)
    for shard, start in enumerate(range(0, vector.size, SHARD)):
        result += font_delta(
            OUT / f"{stem}-s{shard}.woff2",
            vector[start : start + SHARD],
            output_count,
        )
    return result


def main() -> None:
    metadata = json.loads((OUT / "reference.json").read_text())
    data = model_data()
    q_v = quantize_float_rows(data["v_weight"], bits=QUANT_BITS)
    q_attn = quantize_float_rows(data["attn_proj_weight"], bits=QUANT_BITS)
    q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
    q_mlp = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    q_composed = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    ranges = metadata["ranges"]

    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    v_raw = sharded_delta("v", n1 / ranges["n1_range"], WIDTH)
    v = v_raw * ranges["n1_range"] * q_v.scales + data["v_bias"]
    attn_raw = sharded_delta("attn-proj", v / ranges["v_range"], WIDTH)
    attn = (
        attn_raw * ranges["v_range"] * q_attn.scales
        + data["attn_proj_bias"]
    )
    r1 = data["x"] + attn
    n2 = layer_norm(r1, data["ln2_gamma"], data["ln2_beta"])
    fc_raw = sharded_delta("fc", n2 / ranges["n2_range"], MLP_WIDTH)
    hidden = gelu_new(fc_raw * ranges["n2_range"] * q_fc.scales + data["fc_bias"])
    mlp_raw = np.zeros(WIDTH, dtype=np.float64)
    for hidden_shard, start in enumerate(range(0, MLP_WIDTH, SHARD)):
        delta = font_delta(
            OUT / f"mlp-proj-s{hidden_shard}.woff2",
            hidden[start : start + SHARD] / ranges["hidden_range"],
            WIDTH,
        )
        mlp_raw += delta
    mlp = mlp_raw * ranges["hidden_range"] * q_mlp.scales
    actual = r1 + mlp + data["mlp_proj_bias"]
    expected = np.asarray(metadata["quantized_output"], dtype=np.float64)
    np.testing.assert_allclose(actual, expected, atol=1e-11)

    composed_ranges = metadata["composed_ranges"]
    composed_raw = sharded_delta(
        "attn-composed",
        n1 / composed_ranges["n1_range"],
        WIDTH,
    )
    composed_attn = (
        composed_raw
        * composed_ranges["n1_range"]
        * q_composed.scales
        + composed_bias
    )
    composed_r1 = data["x"] + composed_attn
    composed_n2 = layer_norm(
        composed_r1, data["ln2_gamma"], data["ln2_beta"]
    )
    composed_fc_raw = sharded_delta(
        "fc",
        composed_n2 / composed_ranges["n2_range"],
        MLP_WIDTH,
    )
    composed_hidden = gelu_new(
        composed_fc_raw
        * composed_ranges["n2_range"]
        * q_fc.scales
        + data["fc_bias"]
    )
    composed_mlp_raw = sharded_delta(
        "mlp-proj",
        composed_hidden / composed_ranges["hidden_range"],
        WIDTH,
    )
    composed_actual = (
        composed_r1
        + composed_mlp_raw
        * composed_ranges["hidden_range"]
        * q_mlp.scales
        + data["mlp_proj_bias"]
    )
    composed_expected = np.asarray(
        metadata["composed_quantized_output"], dtype=np.float64
    )
    np.testing.assert_allclose(composed_actual, composed_expected, atol=1e-11)

    packed_r1 = (
        data["x"]
        + np.round(composed_raw)
        * composed_ranges["n1_range"]
        * q_composed.scales
        + composed_bias
    )
    packed_n2 = layer_norm(
        packed_r1, data["ln2_gamma"], data["ln2_beta"]
    )
    packed_fc_raw = sharded_delta(
        "fc", packed_n2 / composed_ranges["n2_range"], MLP_WIDTH
    )
    packed_hidden = gelu_new(
        np.round(packed_fc_raw)
        * composed_ranges["n2_range"]
        * q_fc.scales
        + data["fc_bias"]
    )
    packed_mlp_raw = sharded_delta(
        "mlp-proj",
        packed_hidden / composed_ranges["hidden_range"],
        WIDTH,
    )
    packed_actual = (
        packed_r1
        + np.round(packed_mlp_raw)
        * composed_ranges["hidden_range"]
        * q_mlp.scales
        + data["mlp_proj_bias"]
    )
    assert float(np.max(np.abs(packed_actual - composed_expected))) < 0.11

    html = (OUT / "index.html").read_text()
    model_css = (OUT / "model.css").read_text()
    assert "<script" not in html.lower()
    assert html.count('shadowrootmode="open"') == 7
    assert html.count('<slot name="next"></slot>') == 7
    assert html.count('<i class="pack ') == 3072
    assert "sqrt(" in model_css
    assert "exp(" in model_css
    assert model_css.count("@font-face") == 21
    for stage in ("value", "attn", "fc00", "fc01", "fc02", "fc03", "mlp"):
        stage_css = (OUT / f"stage-{stage}.css").read_text()
        assert "@font-face" not in stage_css
        assert ".metric{position:fixed" in stage_css
        assert ".probe{position:fixed" in stage_css
    assert metadata["font_count"] == 21
    assert metadata["font_size"] == 512
    assert metadata["layout_strategy"] == "fixed-to-viewport"
    assert metadata["font_face_scope"] == "document"
    composed_html = (OUT / "composed.html").read_text()
    composed_css = (OUT / "model-composed.css").read_text()
    assert "<script" not in composed_html.lower()
    assert composed_html.count('shadowrootmode="open"') == 6
    assert composed_css.count("@font-face") == 18
    assert metadata["composed_font_count"] == 18
    packed_html = (OUT / "composed-packed.html").read_text()
    assert "<script" not in packed_html.lower()
    assert packed_html.count('shadowrootmode="open"') == 6
    assert packed_html.count('class="probe ') == 1152
    assert metadata["packed_readback_outputs_per_container"] == 4
    for stage in (
        "packed-composed-attn",
        "packed-composed-fc00",
        "packed-composed-fc01",
        "packed-composed-fc02",
        "packed-composed-fc03",
        "packed-composed-mlp",
    ):
        stage_css = (OUT / f"stage-{stage}.css").read_text()
        assert "round(nearest" in stage_css
        assert "mod(" in stage_css
    collapsed_html = (OUT / "composed-packed-collapsed-fc.html").read_text()
    two_fc_html = (OUT / "composed-packed-two-fc.html").read_text()
    assert "Negative limit probe" in collapsed_html
    assert collapsed_html.count('shadowrootmode="open"') == 3
    assert two_fc_html.count('shadowrootmode="open"') == 4
    assert two_fc_html.count('class="probe ') == 1152
    assert metadata["packed_collapsed_stage_count"] == 3
    assert metadata["packed_two_fc_stage_count"] == 4
    assert metadata["packed_two_fc_max_container_depth"] == 384
    print(
        {
            "width": WIDTH,
            "font_count": metadata["font_count"],
            "quantized_block_max_error": float(np.max(np.abs(actual - expected))),
            "quantized_vs_float_max_error": metadata["quantization_max_error"],
            "no_javascript": True,
            "slotted_stages": 7,
            "packed_term_elements": 3072,
            "packed_readback_max_error": float(
                np.max(np.abs(packed_actual - composed_expected))
            ),
            "packed_readback_containers": 1152,
        }
    )


if __name__ == "__main__":
    main()
