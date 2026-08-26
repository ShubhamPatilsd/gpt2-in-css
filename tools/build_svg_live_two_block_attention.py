#!/usr/bin/env python3
"""Chain block 0's complete live output into block 1 attention and residual."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from build_gpt2_block_css import layer_norm, model_data


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    os.environ.get(
        "SVG_TWO_BLOCK_SOURCE", ROOT / "experiments" / "svg-live-block1-input"
    )
).resolve()
BLOCK1 = Path(
    os.environ.get(
        "SVG_TWO_BLOCK_ATTENTION",
        ROOT / "experiments" / "svg-block1-staged-mixed-projection",
    )
).resolve()
OUT = Path(
    os.environ.get(
        "SVG_TWO_BLOCK_OUT",
        ROOT / "experiments" / "svg-live-two-block-attention",
    )
).resolve()
WIDTH = 768
FUSE_INPUT = os.environ.get("SVG_TWO_BLOCK_FUSE_INPUT", "0") == "1"


def filter_body(page: str, filter_id: str) -> str:
    marker = f'<filter id="{filter_id}"'
    marker_start = page.index(marker)
    start = page.index(">", marker_start) + 1
    end = page.index("</filter>", start)
    return page[start:end]


def filter_opening(page: str, filter_id: str) -> str:
    marker = f'<filter id="{filter_id}"'
    start = page.index(marker)
    end = page.index(">", start) + 1
    return page[start:end]


def prefixed_definition(
    page: str, filter_id: str, combined_id: str, relative: str
) -> str:
    marker = f'<filter id="{filter_id}"'
    start = page.index(marker)
    end = page.index("</filter>", start) + len("</filter>")
    definition = page[start:end]
    definition = definition.replace(
        f'id="{filter_id}"', f'id="{combined_id}"', 1
    )
    return definition.replace('href="', f'href="{relative}/')


def prefixed_body(page: str, filter_id: str, relative: str) -> str:
    return filter_body(page, filter_id).replace('href="', f'href="{relative}/')


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_page = (SOURCE / "index.html").read_text()
    block1_page = (BLOCK1 / "index.html").read_text()
    source_relative = os.path.relpath(SOURCE, OUT)
    block1_relative = os.path.relpath(BLOCK1, OUT)
    source_ids = (
        "qkv-stage",
        "attention-stage",
        "projection-stage",
        "ln2-stage",
        "mlp-stage",
        "block1-input-stage",
    )
    source_bodies = {
        stage: prefixed_body(source_page, stage, source_relative)
        for stage in source_ids
    }
    block1_bodies = {
        stage: prefixed_body(block1_page, stage, block1_relative)
        for stage in ("qkv-stage", "attention-stage", "projection-stage")
    }
    qkv_body = block1_bodies["qkv-stage"]
    first_tag_end = qkv_body.index("/>") + 2
    first_tag = qkv_body[:first_tag_end]
    if "normalized-input.png" not in first_tag or 'result="live-input-common"' not in first_tag:
        raise ValueError("Block 1 QKV no longer starts with the normalized input image")
    block1_bodies["qkv-stage"] = (
        (source_bodies["block1-input-stage"] if FUSE_INPUT else "")
        + f'<feOffset in="{"block1-inputs" if FUSE_INPUT else "SourceGraphic"}" '
        'x="0" y="0" width="2" height="768" '
        'result="live-input-common"/>'
        + qkv_body[first_tag_end:]
    )

    filters: list[str] = []
    source_names = {
        "qkv-stage": "block0-qkv",
        "attention-stage": "block0-attention",
        "projection-stage": "block0-projection",
        "ln2-stage": "block0-ln2",
        "mlp-stage": "block0-mlp",
        "block1-input-stage": "block1-input",
    }
    for source_id, combined_id in source_names.items():
        if FUSE_INPUT and source_id == "block1-input-stage":
            continue
        filters.append(
            prefixed_definition(
                source_page, source_id, combined_id, source_relative
            )
        )
    for source_id, combined_id in (
        ("qkv-stage", "block1-qkv"),
        ("attention-stage", "block1-attention"),
        ("projection-stage", "block1-projection"),
    ):
        opening = filter_opening(block1_page, source_id).replace(
            f'id="{source_id}"', f'id="{combined_id}"', 1
        )
        filters.append(f'{opening}{block1_bodies[source_id]}</filter>')
    block0_content = (
        '<g filter="url(#block0-mlp)">'
        '<g filter="url(#block0-ln2)"><g filter="url(#block0-projection)">'
        '<g filter="url(#block0-attention)">'
        '<rect width="2304" height="768" fill="white" '
        'filter="url(#block0-qkv)"/>'
        '</g></g></g></g>'
    )
    qkv_input_content = (
        block0_content
        if FUSE_INPUT
        else f'<g filter="url(#block1-input)">{block0_content}</g>'
    )
    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Live GPT-2 block 0 through block 1 attention</title>'
        '<style>html,body{margin:0;background:black}'
        'svg{display:block;image-rendering:pixelated}</style>'
        f'<svg width="1" height="{WIDTH}" viewBox="63 0 1 {WIDTH}" '
        f'xmlns="http://www.w3.org/2000/svg"><defs>{"".join(filters)}</defs>'
        '<g filter="url(#block1-projection)">'
        '<g filter="url(#block1-attention)"><g filter="url(#block1-qkv)">'
        f'{qkv_input_content}</g></g></g></svg>'
    )
    (OUT / "index.html").write_text(html)
    block1_reference = json.loads((BLOCK1 / "reference.json").read_text())
    expected_residual = np.asarray(
        block1_reference["expectedResidual"], dtype=np.float64
    )
    block1 = model_data(block_index=1, input_vector=expected_residual)
    next_ln_expected = layer_norm(
        expected_residual, block1["ln2_gamma"], block1["ln2_beta"]
    )
    block1_reference.update(
        {
            "source": os.path.relpath(SOURCE, OUT),
            "block1": block1_relative,
            "htmlBytes": len(html.encode()),
            "liveChain": True,
            "fusedBlock1InputQkv": FUSE_INPUT,
            "nextLnGamma": block1["ln2_gamma"].tolist(),
            "nextLnBeta": block1["ln2_beta"].tolist(),
            "nextLnExpected": next_ln_expected.tolist(),
        }
    )
    (OUT / "reference.json").write_text(
        json.dumps(block1_reference, indent=2) + "\n"
    )
    print(
        {
            "html_bytes": len(html.encode()),
            "filter_count": len(filters),
            "source": str(SOURCE),
            "block1": str(BLOCK1),
        }
    )


if __name__ == "__main__":
    main()
