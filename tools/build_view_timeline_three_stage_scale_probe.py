#!/usr/bin/env python3
"""Build a static three-stage scaling probe from the fastest two-block page.

The appended stage deliberately reuses block 1's weights and CSS names. Nested
timeline scopes isolate the duplicate names. This is a browser lifecycle
scaling fixture, not a numerical GPT-2 block-2 reference.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-block-css"
SOURCE = OUT / (
    "view-timeline-two-block-full-exact-b0-global-projection-"
    "fc-easing-gelu-s513-projection-easing-s257-global-projection.html"
)
OUTPUT = OUT / "view-timeline-three-block-structural-scale.html"
REFERENCE = OUT / "view-timeline-three-block-structural-scale-reference.json"
UNIQUE_OUTPUT = OUT / "view-timeline-three-block-unique-scale.html"
UNIQUE_ATTENTION_CSS = OUT / "view-timeline-three-block-b2-attention.css"
UNIQUE_FULL_CSS = OUT / "view-timeline-three-block-b2-full.css"
UNIQUE_REFERENCE = OUT / "view-timeline-three-block-unique-scale-reference.json"
SHADOW_LAST_OUTPUT = OUT / "view-timeline-three-block-shadow-last-mlp.html"
SHADOW_LAST_REFERENCE = (
    OUT / "view-timeline-three-block-shadow-last-mlp-reference.json"
)
SIBLING_OUTPUT = OUT / "view-timeline-three-block-sibling-boundary.html"
SIBLING_CSS = OUT / "view-timeline-three-block-sibling-boundary.css"
SIBLING_REFERENCE = (
    OUT / "view-timeline-three-block-sibling-boundary-reference.json"
)
STAGE_START = '<div class="b1-norm">'
LEAF = (
    '<output id="two-block-full" class="b1proj-result-5">'
    "two complete blocks</output>"
)


def balanced_div(source: str, start: int) -> str:
    depth = 0
    for match in re.finditer(r"<div\b[^>]*>|</div>", source[start:], re.I):
        token = match.group(0).lower()
        depth += -1 if token.startswith("</") else 1
        if depth == 0:
            return source[start : start + match.end()]
    raise ValueError("unterminated block stage")


def main() -> None:
    source = SOURCE.read_text()
    stage_offset = source.index(STAGE_START)
    stage = balanced_div(source, stage_offset)
    if stage.count(LEAF) != 1 or source.count(LEAF) != 1:
        raise ValueError("two-block output leaf was not found exactly once")

    third_stage = stage.replace(
        LEAF,
        '<output id="three-block-full" class="b1proj-result-5">'
        "three structural blocks</output>",
        1,
    )
    aliases = ";".join(
        f"--out-{index:03d}:var(--b1-final-{index:03d})"
        for index in range(768)
    )
    replacement = (
        f'<div class="b1proj-result-5 repeated-block-input" style="{aliases}">'
        f"{third_stage}</div>"
    )
    page = source.replace(LEAF, replacement, 1).replace(
        "</title>", " — three-stage structural scaling</title>", 1
    )
    if page.count('id="three-block-full"') != 1:
        raise ValueError("failed to attach the repeated stage")
    if "<script" in page.lower() or "javascript:" in page.lower():
        raise ValueError("runtime fixture must remain HTML/CSS-only")
    OUTPUT.write_text(page)
    REFERENCE.write_text(
        json.dumps(
            {
                "source": SOURCE.name,
                "stage_count": 3,
                "real_weight_blocks": [0, 1],
                "repeated_weight_block": 1,
                "timeline_boundaries": 6,
                "html_bytes": OUTPUT.stat().st_size,
                "runtime_javascript": False,
            },
            indent=2,
        )
        + "\n"
    )

    linked_css = re.findall(r'<link rel="stylesheet" href="([^"?]+)', source)
    b1_css_names = [name for name in linked_css if "two-block" in name]
    if len(b1_css_names) != 2:
        raise ValueError("expected block-1 attention and full stylesheets")
    renamed_css_paths = [UNIQUE_ATTENTION_CSS, UNIQUE_FULL_CSS]
    unique_links = []
    for source_name, destination in zip(
        b1_css_names, renamed_css_paths, strict=True
    ):
        renamed = (OUT / source_name).read_text().replace("b1", "b2")
        # Keep the existing block-1 font files; only CSS identifiers are new.
        renamed = renamed.replace('url("b2-', 'url("b1-')
        destination.write_text(renamed)
        tag = hashlib.sha256(destination.read_bytes()).hexdigest()[:12]
        unique_links.append(
            f'<link rel="stylesheet" href="{destination.name}?v={tag}">'
        )

    unique_stage = third_stage.replace("b1", "b2").replace(
        'id="three-block-full"', 'id="three-block-unique-full"', 1
    )
    unique_replacement = (
        f'<div class="b1proj-result-5 repeated-block-input" style="{aliases}">'
        f"{unique_stage}</div>"
    )
    unique_page = source.replace(LEAF, unique_replacement, 1).replace(
        "</title>",
        " — three-stage unique-name scaling</title>" + "".join(unique_links),
        1,
    )
    if unique_page.count('id="three-block-unique-full"') != 1:
        raise ValueError("failed to attach unique-name repeated stage")
    if "<script" in unique_page.lower() or "javascript:" in unique_page.lower():
        raise ValueError("unique runtime fixture must remain HTML/CSS-only")
    UNIQUE_OUTPUT.write_text(unique_page)
    UNIQUE_REFERENCE.write_text(
        json.dumps(
            {
                "source": SOURCE.name,
                "stage_count": 3,
                "real_weight_blocks": [0, 1],
                "repeated_weight_block": 1,
                "repeated_identifier_prefix": "b2",
                "timeline_boundaries": 6,
                "html_bytes": UNIQUE_OUTPUT.stat().st_size,
                "css_bytes": sum(path.stat().st_size for path in renamed_css_paths),
                "runtime_javascript": False,
            },
            indent=2,
        )
        + "\n"
    )

    b2_mlp_start = '<div class="b2-ln2">'
    b2_mlp_offset = unique_page.index(b2_mlp_start)
    b2_mlp = balanced_div(unique_page, b2_mlp_offset)
    b2_leaf = (
        '<output id="three-block-unique-full" class="b2proj-result-5">'
        "three structural blocks</output>"
    )
    if b2_mlp.count(b2_leaf) != 1:
        raise ValueError("unique third-stage MLP leaf was not found")
    b2_full_href = next(
        href
        for href in re.findall(
            r'<link rel="stylesheet" href="([^"]+)', unique_page
        )
        if UNIQUE_FULL_CSS.name in href
    )
    b2_shadow_inner = b2_mlp[len(b2_mlp_start) : -len("</div>")].replace(
        b2_leaf,
        '<slot name="b2-mlp-next" class="b2proj-result-5"></slot>',
        1,
    )
    b2_shadow = (
        '<css-mlp-b2 class="b2-ln2" style="display:block">'
        '<template shadowrootmode="open">'
        f'<link rel="stylesheet" href="{b2_full_href}">'
        f"{b2_shadow_inner}</template>"
        '<output id="three-block-shadow-last-full" slot="b2-mlp-next">'
        "three structural blocks</output></css-mlp-b2>"
    )
    shadow_last_page = unique_page.replace(b2_mlp, b2_shadow, 1).replace(
        "</title>", " — shadow last MLP</title>", 1
    )
    if shadow_last_page.count('id="three-block-shadow-last-full"') != 1:
        raise ValueError("failed to wrap the last MLP")
    SHADOW_LAST_OUTPUT.write_text(shadow_last_page)
    SHADOW_LAST_REFERENCE.write_text(
        json.dumps(
            {
                "source": UNIQUE_OUTPUT.name,
                "shadow_boundary": "repeated-block-mlp",
                "html_bytes": SHADOW_LAST_OUTPUT.stat().st_size,
                "runtime_javascript": False,
            },
            indent=2,
        )
        + "\n"
    )

    repeated_wrapper_start = (
        '<div class="b1proj-result-5 repeated-block-input"'
    )
    repeated_wrapper_offset = unique_page.index(repeated_wrapper_start)
    repeated_wrapper = balanced_div(unique_page, repeated_wrapper_offset)
    b2_stage_offset = repeated_wrapper.index('<div class="b2-norm">')
    b2_stage = balanced_div(repeated_wrapper, b2_stage_offset)

    boundary_width = 65536
    boundary_min = -128.0
    boundary_max = 768.0
    boundary_scale = (
        boundary_width * 0.5 / (boundary_max - boundary_min)
    )
    boundary_offset = boundary_width * 0.25 - boundary_scale * boundary_min
    boundary_timelines = [f"--b2it{index}" for index in range(768)]
    boundary_keyframes = [f"b2ik{index}" for index in range(768)]
    boundary_metrics = "".join(
        f'<i class="b2-input-metric" style="view-timeline:{timeline} inline;'
        f"width:calc(({boundary_offset:.12g} + {boundary_scale:.12g} * "
        f'var(--b1-final-{index:03d})) * 1px)"></i>'
        for index, timeline in enumerate(boundary_timelines)
    )
    boundary_source = (
        '<div class="b1proj-result-5">'
        '<div class="b2-input-scroller"><div class="b2-input-track">'
        f"{boundary_metrics}</div></div></div>"
    )
    sibling_page = unique_page.replace(repeated_wrapper, boundary_source, 1)

    boundary_consumer_count = 6
    boundary_tree = b2_stage
    for consumer in reversed(range(boundary_consumer_count)):
        boundary_tree = (
            f'<div class="b2-input-result-{consumer}">{boundary_tree}</div>'
        )
    sibling_page = sibling_page.replace(
        "</css-stage>", "</css-stage>" + boundary_tree, 1
    )

    boundary_points = []
    for point in range(257):
        z = boundary_max - (boundary_max - boundary_min) * point / 256
        progress = boundary_width / (
            boundary_width + boundary_offset + boundary_scale * z
        )
        value = (z - boundary_min) / (boundary_max - boundary_min)
        boundary_points.append(f"{value:.12g} {progress * 100:.12g}%")
    boundary_curve = "linear(1 0%," + ",".join(boundary_points) + ")"
    boundary_rules = []
    for index, keyframe in enumerate(boundary_keyframes):
        boundary_rules.append(
            f"@keyframes {keyframe}{{"
            f"from{{--out-{index:03d}:{boundary_min:g}}}"
            f"to{{--out-{index:03d}:{boundary_max:g}}}}}"
        )
    for consumer in range(boundary_consumer_count):
        start = consumer * 128
        stop = start + 128
        boundary_rules.append(
            f".b2-input-result-{consumer}{{"
            f"animation-name:{','.join(boundary_keyframes[start:stop])};"
            "animation-duration:1s;"
            f"animation-timing-function:{boundary_curve};"
            "animation-fill-mode:both;"
            f"animation-timeline:{','.join(boundary_timelines[start:stop])};"
            "animation-range:cover}"
        )
    sibling_css = (
        f"html{{timeline-scope:{','.join(boundary_timelines)}}}"
        ".b2-input-scroller{position:fixed;left:0;top:-90000px;"
        f"width:{boundary_width}px;height:1px;overflow-x:scroll;overflow-y:hidden}}"
        f".b2-input-track{{position:relative;width:{boundary_width * 3}px;height:1px}}"
        ".b2-input-metric{position:absolute;left:0;top:0;display:inline-flex;"
        "height:1px;overflow:hidden;white-space:pre}"
        + "".join(boundary_rules)
    )
    SIBLING_CSS.write_text(sibling_css)
    sibling_css_tag = hashlib.sha256(SIBLING_CSS.read_bytes()).hexdigest()[:12]
    sibling_page = sibling_page.replace(
        "</title>",
        " — sibling boundary</title>"
        f'<link rel="stylesheet" href="{SIBLING_CSS.name}?v={sibling_css_tag}">',
        1,
    )
    if sibling_page.count('id="three-block-unique-full"') != 1:
        raise ValueError("sibling third-stage output was not found")
    SIBLING_OUTPUT.write_text(sibling_page)
    SIBLING_REFERENCE.write_text(
        json.dumps(
            {
                "source": UNIQUE_OUTPUT.name,
                "boundary_values": 768,
                "boundary_timelines": 768,
                "stage_relationship": "document-siblings",
                "timeline_boundaries": 7,
                "html_bytes": SIBLING_OUTPUT.stat().st_size,
                "css_bytes": SIBLING_CSS.stat().st_size,
                "runtime_javascript": False,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        {
            "shared_names": json.loads(REFERENCE.read_text()),
            "unique_names": json.loads(UNIQUE_REFERENCE.read_text()),
            "shadow_last": json.loads(SHADOW_LAST_REFERENCE.read_text()),
            "sibling_boundary": json.loads(SIBLING_REFERENCE.read_text()),
        }
    )


if __name__ == "__main__":
    main()
