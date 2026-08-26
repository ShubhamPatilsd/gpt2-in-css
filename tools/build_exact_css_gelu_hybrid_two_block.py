#!/usr/bin/env python3
"""Build hybrid serial/parallel block-1 MLP graphs with exact CSS GELU.

Each page partitions the 13 FC slices into a small number of parallel branches.
Slices inside one branch are nested serially so their hidden coordinates meet at
one projection node.  The branch emits 768 partial widths; a final anchor sum
combines the branches.  This directly explores the dependency-depth versus DOM
object-count tradeoff between the existing all-serial and all-parallel pages.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build_exact_css_gelu_two_block import (
    BASE_ADVANCE,
    B1_CODEPOINT,
    B1_OUTPUT_SCALE,
    B1_PREACTIVATION_SCALE,
    GROUP_STARTS,
    GROUP_WIDTHS,
    GROUPS,
    HIDDEN,
    OUTPUTS,
    OUT,
    build_b0_css,
    exact_gelu_function,
)
from build_gpt2_block_css import global_axis_tag, model_data
from build_pretrained_gpt2 import css_number


SOURCE = OUT / "connected-two-block-shadow-staged-layoutless.html"
SOURCE_B1_CSS = OUT / "stage-connected-mlp-b1.css"
OUTPUT_B0_CSS = OUT / "stage-exact-css-gelu-mlp-b0.css"
BRANCH_COUNTS = (2, 3, 4, 5, 7)


def balanced_div(source: str, start: int) -> tuple[str, int]:
    depth = 0
    for match in re.finditer(r"<div\b|</div>", source[start:]):
        token = match.group(0)
        depth += 1 if token.startswith("<div") else -1
        if depth == 0:
            end = start + match.end()
            return source[start:end], end
    raise ValueError(f"unclosed div at offset {start}")


def source_groups(html: str) -> list[str]:
    groups = []
    for group in range(GROUPS):
        marker = f'<div class="b1-group b1-group-{group}">'
        start = html.find(marker)
        if start < 0:
            raise ValueError(f"missing source group {group}")
        groups.append(balanced_div(html, start)[0])
    return groups


def replace_terminal_projection(group_html: str, group: int, child: str) -> str:
    marker = f'<div class="b1-projection b1-projection-{group}">'
    start = group_html.find(marker)
    if start < 0:
        raise ValueError(f"missing terminal projection for group {group}")
    _, end = balanced_div(group_html, start)
    wrapper = f'<div class="b1-projection-{group}">{child}</div>'
    return group_html[:start] + wrapper + group_html[end:]


def partitions(branch_count: int) -> list[list[int]]:
    quotient, remainder = divmod(GROUPS, branch_count)
    result = []
    start = 0
    for branch in range(branch_count):
        width = quotient + (1 if branch < remainder else 0)
        result.append(list(range(start, start + width)))
        start += width
    return result


def font_faces() -> tuple[str, int]:
    faces = []
    total_bytes = 0
    for block in (0, 1):
        for group in range(GROUPS):
            woff2 = OUT / f"exact-css-gelu-b{block}-projection-{group}.woff2"
            if not woff2.exists():
                raise FileNotFoundError(
                    f"{woff2} is missing; run build_exact_css_gelu_two_block.py first"
                )
            digest = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
            family = f"ExactCssGeluB{block}Projection{group}"
            if block == 1:
                start = B1_CODEPOINT + group * OUTPUTS
                unicode_range = f";unicode-range:U+{start:X}-{start + OUTPUTS - 1:X}"
            else:
                unicode_range = ""
            faces.append(
                f'@font-face{{font-family:{family};'
                f'src:url("{woff2.name}?v={digest}") format("woff2")'
                f'{unicode_range}}}'
            )
            total_bytes += woff2.stat().st_size
    return "".join(faces), total_bytes


def registrations() -> str:
    b0 = "".join(
        f'@property --b0-g{index}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for index in range(max(GROUP_WIDTHS))
    )
    z_values = "".join(
        f'@property --hybrid-z-{index:04d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(HIDDEN)
    )
    gelu_values = "".join(
        f'@property --hybrid-g-{index:04d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(HIDDEN)
    )
    return b0 + z_values + gelu_values


def group_rules(source_css: str, group: int) -> str:
    start = GROUP_STARTS[group]
    selected = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", source_css):
        selector = match.group(1).strip()
        body = match.group(2)
        belongs = (
            selector.startswith(f".b1-metric-{group}-")
            or selector.startswith(f".b1-probe-{group}-")
            or selector == f".b1-projection-{group}"
        )
        if not belongs or "font-family:B1GeluProjection" in body:
            continue
        rule = f"{selector}{{{body}}}"
        rule = re.sub(
            r"--b1-z(\d+)",
            lambda found: f"--hybrid-z-{start + int(found.group(1)):04d}",
            rule,
        )
        selected.append(rule)
    expected = GROUP_WIDTHS[group] + GROUP_WIDTHS[group] // 2 * 2
    if len(selected) != expected:
        raise ValueError(
            f"group {group}: expected {expected} metric/probe rules, got {len(selected)}"
        )
    return "".join(selected)


def branch_projection(branch: int, groups: list[int]) -> tuple[str, str]:
    hidden_indices = [
        hidden
        for group in groups
        for hidden in range(GROUP_STARTS[group], GROUP_STARTS[group] + GROUP_WIDTHS[group])
    ]
    declarations = "".join(
        f"--hybrid-g-{hidden:04d}:--exact-gelu-hybrid-b1("
        f"calc(var(--hybrid-z-{hidden:04d}) * "
        f"{css_number(B1_PREACTIVATION_SCALE)}));"
        for hidden in hidden_indices
    )
    settings = ",".join(
        f'"{global_axis_tag(hidden)}" var(--hybrid-g-{hidden:04d})'
        for hidden in hidden_indices
    )
    families = ",".join(
        f"ExactCssGeluB1Projection{group}" for group in groups
    )
    rules = [
        f".hybrid-projection-{branch}{{{declarations}font-family:{families};"
        f"font-variation-settings:{settings}}}"
    ]
    partials = []
    for output in range(OUTPUTS):
        characters = "".join(
            f"&#x{B1_CODEPOINT + group * OUTPUTS + output:X};" for group in groups
        )
        partials.append(
            f'<i class="hybrid-partial hybrid-partial-{branch}-{output}">'
            f"{characters}</i>"
        )
        rules.append(
            f".hybrid-partial-{branch}-{output}"
            f"{{anchor-name:--hybrid-b{branch}o{output}}}"
        )
    html = (
        f'<div class="hybrid-projection hybrid-projection-{branch}">'
        f'{"".join(partials)}</div>'
    )
    return html, "".join(rules)


def build_stage(branch_count: int, groups_html: list[str], source_css: str) -> tuple[str, str]:
    branch_html = []
    branch_css = []
    grouping = partitions(branch_count)
    for branch, groups in enumerate(grouping):
        child, projection_css = branch_projection(branch, groups)
        for group in reversed(groups):
            child = replace_terminal_projection(groups_html[group], group, child)
        branch_html.append(
            f'<div class="hybrid-branch hybrid-branch-{branch}">{child}</div>'
        )
        branch_css.append(projection_css)
        branch_css.extend(group_rules(source_css, group) for group in groups)

    data = model_data(1)
    outputs = "".join(
        f'<i class="b1-output b1-output-{output}"></i>'
        for output in range(OUTPUTS)
    )
    combined_rules = []
    base_subtraction = (GROUPS - 1) * BASE_ADVANCE
    for output in range(OUTPUTS):
        anchors = " + ".join(
            f"anchor-size(--hybrid-b{branch}o{output} width)"
            for branch in range(branch_count)
        )
        combined_rules.append(
            f".b1-output-{output}{{width:calc({anchors} - {base_subtraction}px + "
            f"(var(--b1-r1-{output:03d}) + "
            f"{css_number(float(data['mlp_proj_bias'][output]))}) * "
            f"{css_number(B1_OUTPUT_SCALE)}px)}}"
        )

    base_css = source_css[: source_css.find(".b1-metric-0-0")]
    stage_css = (
        exact_gelu_function("exact-gelu-hybrid-b1", B1_PREACTIVATION_SCALE)
        + base_css
        + ".hybrid-projection{font-size:1000px;font-kerning:none;line-height:1}"
        + ".hybrid-partial{position:fixed;inset:0 auto auto 0;display:inline-flex;"
        + "height:1px;overflow:hidden;white-space:pre;font-style:normal;width:max-content}"
        + "".join(branch_css)
        + "".join(combined_rules)
    )
    stage_html = (
        '<css-stage class="b1-mlp"><template shadowrootmode="open">'
        f'<link rel="stylesheet" href="stage-exact-css-gelu-hybrid-b1-{branch_count}.css">'
        f'<div class="b1-root">{"".join(branch_html)}'
        f'<div class="b1-combined">{outputs}</div></div></template></css-stage>'
    )
    return stage_html, stage_css


def replace_b1_stage(html: str, replacement: str) -> str:
    start = html.find('<css-stage class="b1-mlp">')
    if start < 0:
        raise ValueError("missing block-1 MLP stage")
    end = html.find("</css-stage>", start)
    if end < 0:
        raise ValueError("unclosed block-1 MLP stage")
    end += len("</css-stage>")
    return html[:start] + replacement + html[end:]


def main() -> None:
    source_html = SOURCE.read_text()
    source_css = SOURCE_B1_CSS.read_text()
    groups_html = source_groups(source_html)
    OUTPUT_B0_CSS.write_text(build_b0_css())
    b0_digest = hashlib.sha256(OUTPUT_B0_CSS.read_bytes()).hexdigest()[:12]
    faces, font_bytes = font_faces()
    created = []

    for branch_count in BRANCH_COUNTS:
        stage_html, stage_css = build_stage(
            branch_count, groups_html, source_css
        )
        css_path = OUT / f"stage-exact-css-gelu-hybrid-b1-{branch_count}.css"
        css_path.write_text(stage_css)
        css_digest = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
        stage_html = stage_html.replace(
            f'{css_path.name}">', f'{css_path.name}?v={css_digest}">'
        )

        html = replace_b1_stage(source_html, stage_html)
        html = html.replace(
            "<title>Layoutless shadow-staged two-block GPT-2</title>",
            f"<title>{branch_count}-branch exact-CSS-GELU two-block GPT-2</title>",
            1,
        )
        html, b0_links = re.subn(
            r"stage-connected-mlp-b0\.css\?v=[0-9a-f]+",
            f"{OUTPUT_B0_CSS.name}?v={b0_digest}",
            html,
            count=1,
        )
        if b0_links != 1:
            raise ValueError(f"unexpected block-0 link count: {b0_links}")
        html = html.replace("</style>", faces + registrations() + "</style>", 1)
        output = OUT / f"connected-two-block-hybrid-{branch_count}-exact-css-gelu-layoutless.html"
        output.write_text(html)
        created.append(
            {
                "branches": branch_count,
                "groupsPerBranch": partitions(branch_count),
                "output": output.name,
                "htmlBytes": output.stat().st_size,
                "stageCssBytes": css_path.stat().st_size,
                "runtimeContainsJavaScript": "<script" in html.lower(),
            }
        )

    manifest = {
        "source": SOURCE.name,
        "variants": created,
        "pureProjectionFontBytes": font_bytes,
        "groupWidths": GROUP_WIDTHS,
        "tradeoff": "fewer branches reduce partial DOM outputs but increase serial group depth",
    }
    (OUT / "exact-css-gelu-hybrid-two-block-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    for entry in created:
        print(
            f"built {entry['output']}: {entry['htmlBytes'] / 1e6:.2f} MB HTML, "
            f"{entry['branches']} branches"
        )


if __name__ == "__main__":
    main()
