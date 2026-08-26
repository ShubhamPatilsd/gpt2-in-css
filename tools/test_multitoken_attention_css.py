#!/usr/bin/env python3
"""Verify the generated two-token causal-attention experiment offline."""

from __future__ import annotations

import json

import numpy as np

from build_gpt2_block_css import OUT, WIDTH
from build_multitoken_attention_css import HEADS, QKV_WIDTH, TOKEN_COUNT


def main() -> None:
    html = (OUT / "view-timeline-attention-2token.html").read_text()
    css = (OUT / "view-timeline-attention-2token.css").read_text()
    reference = json.loads(
        (OUT / "view-timeline-attention-2token-reference.json").read_text()
    )

    assert "<script" not in html.lower()
    assert html.count('class="qkv-scroller"') == TOKEN_COUNT
    assert html.count('class="projection-scroller"') == TOKEN_COUNT
    assert html.count('class="qkv-metric"') == TOKEN_COUNT * QKV_WIDTH
    assert html.count('class="projection-metric"') == TOKEN_COUNT * WIDTH
    assert css.count("@font-face") == 6
    assert reference["token_ids"] == [15496, 995]
    assert reference["heads"] == HEADS

    qkv = np.asarray(reference["qkv"], dtype=np.float64)
    probabilities = np.asarray(reference["probabilities"], dtype=np.float64)
    context = np.asarray(reference["context"], dtype=np.float64)
    residual = np.asarray(reference["residual"], dtype=np.float64)
    assert qkv.shape == (TOKEN_COUNT, QKV_WIDTH)
    assert probabilities.shape == (TOKEN_COUNT, HEADS, TOKEN_COUNT)
    assert context.shape == (TOKEN_COUNT, WIDTH)
    assert residual.shape == (TOKEN_COUNT, WIDTH)
    np.testing.assert_allclose(probabilities[0, :, 0], 1, atol=1e-12)
    np.testing.assert_allclose(probabilities[0, :, 1], 0, atol=1e-12)
    np.testing.assert_allclose(probabilities[1].sum(axis=1), 1, atol=1e-12)
    np.testing.assert_allclose(context[0], qkv[0, 2 * WIDTH :], atol=1e-12)

    bilinear_html = (OUT / "view-timeline-attention-2token-bilinear.html").read_text()
    bilinear_css = (OUT / "view-timeline-attention-2token-bilinear.css").read_text()
    bilinear_reference = json.loads(
        (OUT / "view-timeline-attention-2token-bilinear-reference.json").read_text()
    )
    assert "<script" not in bilinear_html.lower()
    assert bilinear_html.count('class="score-metric ') == HEADS * TOKEN_COUNT
    assert bilinear_css.count("@font-face") == 7
    assert bilinear_reference["score_backend"] == "bilinear"
    np.testing.assert_allclose(bilinear_reference["residual"], residual, atol=1e-12)

    container_html = (
        OUT / "view-timeline-attention-2token-qkv-container.html"
    ).read_text()
    container_reference = json.loads(
        (
            OUT / "view-timeline-attention-2token-qkv-container-reference.json"
        ).read_text()
    )
    assert "<script" not in container_html.lower()
    assert container_html.count('shadowrootmode="open"') == TOKEN_COUNT
    assert container_html.count('class="packet ') == TOKEN_COUNT * (QKV_WIDTH // 6)
    assert container_reference["qkv_transport"] == "container"
    assert container_reference["score_backend"] == "css"
    container_qkv = np.asarray(container_reference["qkv"], dtype=np.float64)
    container_unpacked = np.asarray(
        container_reference["qkv_unpacked"], dtype=np.float64
    )
    assert container_qkv.shape == (TOKEN_COUNT, QKV_WIDTH)
    assert float(np.sqrt(np.mean((container_qkv - container_unpacked) ** 2))) < 0.01

    print(
        {
            "tokens": TOKEN_COUNT,
            "heads": HEADS,
            "qkv_values": int(qkv.size),
            "residual_values": int(residual.size),
            "html_bytes": reference["html_bytes"],
            "css_bytes": reference["css_bytes"],
            "no_javascript": True,
            "score_backends": ["css", "bilinear"],
            "qkv_transports": ["timeline", "container"],
        }
    )


if __name__ == "__main__":
    main()
