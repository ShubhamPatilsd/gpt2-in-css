#!/usr/bin/env python3
"""Verify the generated view-timeline FC experiment offline."""

from __future__ import annotations

import json

import numpy as np

from build_gpt2_block_css import MLP_WIDTH, OUT, WIDTH, gelu_new


def main() -> None:
    html = (OUT / "view-timeline-fc.html").read_text()
    css = (OUT / "view-timeline-fc.css").read_text()
    reference = json.loads((OUT / "view-timeline-fc-reference.json").read_text())

    assert "<script" not in html.lower()
    assert html.count('class="metric"') == MLP_WIDTH
    assert html.count('class="scroller"') == MLP_WIDTH
    assert css.count("@keyframes k") == MLP_WIDTH
    assert css.count('@property --p') == MLP_WIDTH
    assert css.count('@property --hidden-') == MLP_WIDTH
    assert "@function --gelu" in css
    assert "timeline-scope:" in css
    assert reference["outputs_per_consumer"] == 128
    assert reference["layout_strategy"] == "flat-named-view-timelines"

    pre = np.asarray(reference["pre"], dtype=np.float64)
    hidden = np.asarray(reference["hidden"], dtype=np.float64)
    np.testing.assert_allclose(gelu_new(pre), hidden, atol=1e-12)
    assert pre.size == MLP_WIDTH
    assert hidden.size == MLP_WIDTH

    mlp_html = (OUT / "view-timeline-mlp.html").read_text()
    mlp_css = (OUT / "view-timeline-mlp.css").read_text()
    mlp_reference = json.loads(
        (OUT / "view-timeline-mlp-reference.json").read_text()
    )
    block_reference = json.loads((OUT / "reference.json").read_text())

    assert "<script" not in mlp_html.lower()
    assert mlp_html.count('class="metric"') == MLP_WIDTH
    assert mlp_html.count('class="proj-metric"') == WIDTH
    assert mlp_html.count('class="scroller"') == 1
    assert mlp_html.count('class="proj-scroller"') == 1
    assert mlp_html.count('class="proj-pack-') == WIDTH * 4
    assert mlp_css.count("@keyframes ok") == WIDTH
    assert mlp_css.count('@property --op') == WIDTH
    assert mlp_css.count('@property --out-') == WIDTH
    assert mlp_css.count("@font-face") == 15
    assert "var(--hidden-000)" in mlp_css
    assert "var(--hidden-3071)" in mlp_css
    assert mlp_reference["layout_strategy"] == "flat-fc-direct-flat-projection"

    output = np.asarray(mlp_reference["output"], dtype=np.float64)
    expected = np.asarray(
        block_reference["composed_quantized_output"], dtype=np.float64
    )
    assert output.size == WIDTH
    np.testing.assert_allclose(output, expected, atol=1e-11)

    block_html = (OUT / "view-timeline-block.html").read_text()
    block_css = (OUT / "view-timeline-block.css").read_text()
    flat_block_reference = json.loads(
        (OUT / "view-timeline-block-reference.json").read_text()
    )
    assert "<script" not in block_html.lower()
    assert block_html.count('class="attn-scroller"') == 1
    assert block_html.count('class="scroller"') == 1
    assert block_html.count('class="proj-scroller"') == 1
    assert block_html.count('class="attn-metric"') == WIDTH
    assert block_html.count('class="metric"') == MLP_WIDTH
    assert block_html.count('class="proj-metric"') == WIDTH
    assert block_css.count("@font-face") == 18
    assert block_css.count("@keyframes ak") == WIDTH
    assert "--mean1:" in block_css
    assert "--var1:" in block_css
    assert "--mean2:" in block_css
    assert "--var2:" in block_css
    assert flat_block_reference["layout_strategy"] == (
        "flat-shared-scroller-complete-block"
    )
    np.testing.assert_allclose(
        np.asarray(flat_block_reference["output"], dtype=np.float64),
        expected,
        atol=1e-11,
    )

    hybrid_html = (OUT / "view-timeline-block-hybrid.html").read_text()
    hybrid_css = (OUT / "view-timeline-block-hybrid.css").read_text()
    attention_prefix_css = (
        OUT / "view-timeline-attention-prefix.css"
    ).read_text()
    assert "<script" not in hybrid_html.lower()
    assert "model-composed.css" not in hybrid_html
    assert "view-timeline-attention-prefix.css" in hybrid_html
    assert "view-timeline-block-hybrid.css" in hybrid_html
    assert hybrid_html.count('id="final"') == 1
    assert hybrid_html.count('class="scroller"') == 1
    assert hybrid_html.count('class="proj-scroller"') == 1
    assert hybrid_css.count("@font-face") == 15
    assert attention_prefix_css.count("@font-face") == 3
    assert len(attention_prefix_css.encode()) < 700_000

    paired_hybrid_html = (
        OUT / "view-timeline-block-hybrid-paired.html"
    ).read_text()
    paired_hybrid_css = (
        OUT / "view-timeline-block-hybrid-paired.css"
    ).read_text()
    assert "<script" not in paired_hybrid_html.lower()
    assert "model-composed.css" not in paired_hybrid_html
    assert "view-timeline-attention-prefix.css" in paired_hybrid_html
    assert "view-timeline-block-hybrid-paired.css" in paired_hybrid_html
    assert paired_hybrid_html.count('id="final"') == 1
    assert paired_hybrid_html.count('class="scroller"') == 1
    assert paired_hybrid_html.count('class="pair"') == MLP_WIDTH // 2
    assert paired_hybrid_html.count('class="pair-subject"') == MLP_WIDTH // 2
    assert paired_hybrid_html.count('class="proj-scroller"') == 1
    assert paired_hybrid_html.count('class="proj-pair"') == WIDTH // 2
    assert paired_hybrid_html.count('class="proj-pair-subject"') == WIDTH // 2
    assert paired_hybrid_css.count("@keyframes pk") == MLP_WIDTH // 2
    assert paired_hybrid_css.count('@property --pc') == MLP_WIDTH // 2
    assert paired_hybrid_css.count('@property --pe') == MLP_WIDTH // 2
    assert paired_hybrid_css.count("entry 100%") == (MLP_WIDTH + WIDTH) // 2
    assert paired_hybrid_css.count("@keyframes pok") == WIDTH // 2
    assert paired_hybrid_css.count('@property --poc') == WIDTH // 2
    assert paired_hybrid_css.count('@property --poe') == WIDTH // 2
    assert paired_hybrid_css.count("@font-face") == 15

    paired_fc_hybrid_html = (
        OUT / "view-timeline-block-hybrid-fc-paired.html"
    ).read_text()
    paired_fc_hybrid_css = (
        OUT / "view-timeline-block-hybrid-fc-paired.css"
    ).read_text()
    assert "<script" not in paired_fc_hybrid_html.lower()
    assert paired_fc_hybrid_html.count('class="pair"') == MLP_WIDTH // 2
    assert paired_fc_hybrid_html.count('class="proj-metric"') == WIDTH
    assert 'class="proj-pair"' not in paired_fc_hybrid_html
    assert paired_fc_hybrid_css.count("@keyframes pk") == MLP_WIDTH // 2
    assert "@keyframes pok" not in paired_fc_hybrid_css

    packed4_hybrid_html = (
        OUT / "view-timeline-block-hybrid-fc-packed4.html"
    ).read_text()
    packed4_hybrid_css = (
        OUT / "view-timeline-block-hybrid-fc-packed4.css"
    ).read_text()
    assert "<script" not in packed4_hybrid_html.lower()
    assert packed4_hybrid_html.count('class="q4-pair"') == MLP_WIDTH // 4
    assert packed4_hybrid_html.count('class="q4-subject"') == MLP_WIDTH // 4
    assert packed4_hybrid_html.count('class="q4-digit ') == MLP_WIDTH
    assert packed4_hybrid_html.count('class="proj-metric"') == WIDTH
    assert packed4_hybrid_css.count("@keyframes q4k") == MLP_WIDTH // 4
    assert packed4_hybrid_css.count('@property --q4c') == MLP_WIDTH // 4
    assert packed4_hybrid_css.count('@property --q4e') == MLP_WIDTH // 4
    assert "@property --hidden-" not in packed4_hybrid_css

    packed4_hvar_html = (
        OUT / "view-timeline-block-hybrid-fc-packed4-hvar.html"
    ).read_text()
    packed4_hvar_css = (
        OUT / "view-timeline-block-hybrid-fc-packed4-hvar.css"
    ).read_text()
    assert "<script" not in packed4_hvar_html.lower()
    assert packed4_hvar_html.count('class="q4-pair"') == MLP_WIDTH // 4
    assert packed4_hvar_html.count('class="packed4-hvar-metric"') == WIDTH
    assert 'class="proj-metric"' not in packed4_hvar_html
    assert packed4_hvar_css.count("@keyframes q4k") == MLP_WIDTH // 4
    assert packed4_hvar_css.count('"X') >= MLP_WIDTH
    assert "@keyframes ok" not in packed4_hvar_css
    assert "@property --out-" not in packed4_hvar_css

    packed4_hvar_gather_html = (
        OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather.html"
    ).read_text()
    packed4_hvar_gather_css = (
        OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather.css"
    ).read_text()
    assert "<script" not in packed4_hvar_gather_html.lower()
    assert packed4_hvar_gather_html.count(
        'class="hvar-gather-source"'
    ) == WIDTH
    assert packed4_hvar_gather_css.count(
        "@property --next-"
    ) == WIDTH
    assert packed4_hvar_gather_css.count("container-type:size") == 1

    packed4_hvar_gather8_html = (
        OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather8.html"
    ).read_text()
    packed4_hvar_gather8_css = (
        OUT / "view-timeline-block-hybrid-fc-packed4-hvar-gather8.css"
    ).read_text()
    assert "<script" not in packed4_hvar_gather8_html.lower()
    assert packed4_hvar_gather8_html.count(
        'class="hvar-gather8-source"'
    ) == WIDTH
    assert packed4_hvar_gather8_css.count(".h8-pack-") == WIDTH // 6

    packed4_transport_html = (
        OUT / "view-timeline-block-hybrid-fc-packed4-transport.html"
    ).read_text()
    packed4_transport_css = (
        OUT / "view-timeline-block-hybrid-fc-packed4-transport.css"
    ).read_text()
    assert "<script" not in packed4_transport_html.lower()
    assert packed4_transport_html.count('class="q4-pair"') == MLP_WIDTH // 4
    assert 'class="proj-metric"' not in packed4_transport_html
    assert "@keyframes ok" not in packed4_transport_css

    packed4_chain_html = (
        OUT / "view-timeline-block-hybrid-packed4-chain.html"
    ).read_text()
    packed4_chain_css = (
        OUT / "view-timeline-block-hybrid-packed4-chain.css"
    ).read_text()
    assert "<script" not in packed4_chain_html.lower()
    assert packed4_chain_html.count('class="q4-pair"') == MLP_WIDTH // 4
    assert packed4_chain_html.count('class="qo-pair"') == WIDTH // 4
    assert packed4_chain_html.count('class="qo-subject"') == WIDTH // 4
    assert packed4_chain_html.count('class="qo-digit ') == WIDTH
    assert packed4_chain_css.count("@keyframes qok") == WIDTH // 4

    channel89_chain_html = (
        OUT / "view-timeline-block-hybrid-packed4-chain-channel89.html"
    ).read_text()
    channel89_chain_css = (
        OUT / "view-timeline-block-hybrid-packed4-chain-channel89.css"
    ).read_text()
    assert "<script" not in channel89_chain_html.lower()
    assert channel89_chain_html.count('class="q4-pair"') == MLP_WIDTH // 4
    assert channel89_chain_html.count('class="qo-pair"') == WIDTH // 4
    assert channel89_chain_html.count('class="qo-subject"') == WIDTH // 4
    assert channel89_chain_html.count('class="qo-digit ') == WIDTH
    assert channel89_chain_css.count("@keyframes qok") == WIDTH // 4
    assert "sqrt(abs((size / 1px - 256))" not in channel89_chain_css

    packed6_hybrid_html = (
        OUT / "view-timeline-block-hybrid-fc-packed6.html"
    ).read_text()
    packed6_hybrid_css = (
        OUT / "view-timeline-block-hybrid-fc-packed6.css"
    ).read_text()
    assert "<script" not in packed6_hybrid_html.lower()
    assert packed6_hybrid_html.count('class="q6-pair"') == MLP_WIDTH // 6
    assert packed6_hybrid_html.count('class="q6-subject"') == MLP_WIDTH // 6
    assert packed6_hybrid_html.count('class="q6-digit ') == MLP_WIDTH
    assert packed6_hybrid_html.count('class="proj-metric"') == WIDTH
    assert packed6_hybrid_css.count("@keyframes q6k") == MLP_WIDTH // 6
    assert packed6_hybrid_css.count('@property --q6c') == MLP_WIDTH // 6
    assert packed6_hybrid_css.count('@property --q6e') == MLP_WIDTH // 6
    assert "@property --hidden-" not in packed6_hybrid_css

    packed6_transport_html = (
        OUT / "view-timeline-block-hybrid-fc-packed6-transport.html"
    ).read_text()
    packed6_transport_css = (
        OUT / "view-timeline-block-hybrid-fc-packed6-transport.css"
    ).read_text()
    assert "<script" not in packed6_transport_html.lower()
    assert packed6_transport_html.count('class="q6-pair"') == MLP_WIDTH // 6
    assert 'class="proj-metric"' not in packed6_transport_html
    assert "@keyframes ok" not in packed6_transport_css

    hetero_html = (
        OUT / "view-timeline-block-hybrid-fc-hetero58.html"
    ).read_text()
    hetero_css = (
        OUT / "view-timeline-block-hybrid-fc-hetero58.css"
    ).read_text()
    assert "<script" not in hetero_html.lower()
    assert hetero_html.count('class="h5-pair"') == (MLP_WIDTH // 2) // 6
    assert hetero_html.count('class="h8-pair"') == (MLP_WIDTH // 2) // 4
    assert hetero_html.count('class="h5-digit ') == MLP_WIDTH // 2
    assert hetero_html.count('class="h8-digit ') == MLP_WIDTH // 2
    assert hetero_html.count('class="proj-metric"') == WIDTH
    assert hetero_css.count("@keyframes h5k") == (MLP_WIDTH // 2) // 6
    assert hetero_css.count("@keyframes h8k") == (MLP_WIDTH // 2) // 4
    assert hetero_css.count('@property --h5c') == (MLP_WIDTH // 2) // 6
    assert hetero_css.count('@property --h8c') == (MLP_WIDTH // 2) // 4
    assert "@property --hidden-" not in hetero_css

    print(
        {
            "outputs": MLP_WIDTH,
            "outputs_per_consumer": reference["outputs_per_consumer"],
            "html_bytes": reference["html_bytes"],
            "css_bytes": reference["css_bytes"],
            "chained_outputs": WIDTH,
            "chained_html_bytes": mlp_reference["html_bytes"],
            "chained_css_bytes": mlp_reference["css_bytes"],
            "full_block_outputs": WIDTH,
            "full_block_html_bytes": flat_block_reference["html_bytes"],
            "full_block_css_bytes": flat_block_reference["css_bytes"],
            "hybrid_block_html_bytes": len(hybrid_html.encode()),
            "hybrid_block_css_bytes": len(hybrid_css.encode()),
            "paired_hybrid_block_html_bytes": len(paired_hybrid_html.encode()),
            "paired_hybrid_block_css_bytes": len(paired_hybrid_css.encode()),
            "paired_fc_hybrid_block_html_bytes": len(paired_fc_hybrid_html.encode()),
            "paired_fc_hybrid_block_css_bytes": len(paired_fc_hybrid_css.encode()),
            "packed4_hybrid_block_html_bytes": len(packed4_hybrid_html.encode()),
            "packed4_hybrid_block_css_bytes": len(packed4_hybrid_css.encode()),
            "packed4_hvar_html_bytes": len(packed4_hvar_html.encode()),
            "packed4_hvar_css_bytes": len(packed4_hvar_css.encode()),
            "packed4_hvar_gather_html_bytes": len(
                packed4_hvar_gather_html.encode()
            ),
            "packed4_hvar_gather_css_bytes": len(
                packed4_hvar_gather_css.encode()
            ),
            "packed4_hvar_gather8_html_bytes": len(
                packed4_hvar_gather8_html.encode()
            ),
            "packed4_hvar_gather8_css_bytes": len(
                packed4_hvar_gather8_css.encode()
            ),
            "packed4_transport_html_bytes": len(packed4_transport_html.encode()),
            "packed4_transport_css_bytes": len(packed4_transport_css.encode()),
            "packed4_chain_html_bytes": len(packed4_chain_html.encode()),
            "packed4_chain_css_bytes": len(packed4_chain_css.encode()),
            "packed6_hybrid_block_html_bytes": len(packed6_hybrid_html.encode()),
            "packed6_hybrid_block_css_bytes": len(packed6_hybrid_css.encode()),
            "packed6_transport_html_bytes": len(packed6_transport_html.encode()),
            "packed6_transport_css_bytes": len(packed6_transport_css.encode()),
            "hetero58_block_html_bytes": len(hetero_html.encode()),
            "hetero58_block_css_bytes": len(hetero_css.encode()),
            "attention_prefix_css_bytes": len(attention_prefix_css.encode()),
            "no_javascript": True,
        }
    )


if __name__ == "__main__":
    main()
