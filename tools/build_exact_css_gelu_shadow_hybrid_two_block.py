#!/usr/bin/env python3
"""Build parser-depth-safe hybrid MLP branches using nested shadow stages.

Each FC slice keeps its existing shadow root, which resets HTML parser depth and
passes its 236-238 values to a slotted light-DOM child.  Several slices meet at
one light-DOM partial projection.  The partial outputs remain in a shared outer
shadow tree, allowing a final anchor-size sum across parallel branches.
"""

from __future__ import annotations

import hashlib
import json
import re

from build_exact_css_gelu_hybrid_two_block import (
    font_faces,
    partitions,
    replace_b1_stage,
)
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


PARALLEL_SOURCE = OUT / "connected-two-block-shadow-staged-layoutless.html"
SERIAL_SOURCE = OUT / "connected-two-block-serial-projection-layoutless.html"
OUTPUT_B0_CSS = OUT / "stage-exact-css-gelu-mlp-b0.css"
BRANCH_COUNTS = (1, 2, 3, 4)


def group_templates(serial_html: str) -> list[str]:
    templates = []
    for group in range(GROUPS):
        marker = f'<css-stage class="serial-group-{group}"'
        host = serial_html.find(marker)
        if host < 0:
            raise ValueError(f"missing serial group host {group}")
        start = serial_html.find('<template shadowrootmode="open">', host)
        end = serial_html.find("</template>", start)
        if start < 0 or end < 0:
            raise ValueError(f"missing serial group template {group}")
        templates.append(serial_html[start : end + len("</template>")])
    return templates


def registrations() -> str:
    b0 = "".join(
        f'@property --b0-g{index}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for index in range(max(GROUP_WIDTHS))
    )
    serial = "".join(
        f'@property --serial-z-{index:04d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(HIDDEN)
    )
    gelu = "".join(
        f'@property --shadow-g-{index:04d}'
        '{syntax:"<number>";inherits:true;initial-value:0}'
        for index in range(HIDDEN)
    )
    return b0 + serial + gelu


def projection(
    branch: int, groups: list[int], direct_output: bool = False
) -> tuple[str, str]:
    hidden_indices = [
        hidden
        for group in groups
        for hidden in range(GROUP_STARTS[group], GROUP_STARTS[group] + GROUP_WIDTHS[group])
    ]
    declarations = "".join(
        f"--shadow-g-{hidden:04d}:--exact-gelu-shadow-b1("
        f"calc(var(--serial-z-{hidden:04d}) * "
        f"{css_number(B1_PREACTIVATION_SCALE)}));"
        for hidden in hidden_indices
    )
    settings = ",".join(
        f'"{global_axis_tag(hidden)}" var(--shadow-g-{hidden:04d})'
        for hidden in hidden_indices
    )
    families = ",".join(
        f"ExactCssGeluB1Projection{group}" for group in groups
    )
    rules = [
        f".shadow-projection-{branch}{{{declarations}font-family:{families};"
        f"font-variation-settings:{settings}}}"
    ]
    partials = []
    data = model_data(1)
    for output in range(OUTPUTS):
        characters = "".join(
            f"&#x{B1_CODEPOINT + group * OUTPUTS + output:X};" for group in groups
        )
        if direct_output:
            partials.append(
                f'<i class="shadow-partial b1-output b1-output-{output}">'
                f"{characters}</i>"
            )
            rules.append(
                f".b1-output-{output}{{width:calc-size(max-content,size + "
                f"(var(--b1-r1-{output:03d}) + "
                f"{css_number(float(data['mlp_proj_bias'][output]))}) * "
                f"{css_number(B1_OUTPUT_SCALE)}px)}}"
            )
        else:
            partials.append(
                f'<i class="shadow-partial shadow-partial-{branch}-{output}">'
                f"{characters}</i>"
            )
            rules.append(
                f".shadow-partial-{branch}-{output}"
                f"{{anchor-name:--shadow-b{branch}o{output}}}"
            )
    html = (
        f'<div class="shadow-projection shadow-projection-{branch}" slot="next">'
        f'{"".join(partials)}</div>'
    )
    return html, "".join(rules)


def build_stage(branch_count: int, templates: list[str]) -> tuple[str, str]:
    branch_html = []
    branch_rules = []
    grouping = partitions(branch_count)
    for branch, groups in enumerate(grouping):
        child, rules = projection(
            branch, groups, direct_output=branch_count == 1
        )
        for offset, group in enumerate(reversed(groups)):
            is_outermost = offset == len(groups) - 1
            slot = "" if is_outermost else ' slot="next"'
            child = (
                f'<css-stage class="shadow-hybrid-group-{group}"{slot}>'
                f'{templates[group]}{child}</css-stage>'
            )
        branch_html.append(
            f'<div class="shadow-branch shadow-branch-{branch}">{child}</div>'
        )
        branch_rules.append(rules)

    data = model_data(1)
    outputs = "" if branch_count == 1 else "".join(
        f'<i class="b1-output b1-output-{output}"></i>'
        for output in range(OUTPUTS)
    )
    combined_rules = []
    base_subtraction = (GROUPS - 1) * BASE_ADVANCE
    for output in range(OUTPUTS) if branch_count > 1 else ():
        anchors = " + ".join(
            f"anchor-size(--shadow-b{branch}o{output} width)"
            for branch in range(branch_count)
        )
        combined_rules.append(
            f".b1-output-{output}{{width:calc({anchors} - {base_subtraction}px + "
            f"(var(--b1-r1-{output:03d}) + "
            f"{css_number(float(data['mlp_proj_bias'][output]))}) * "
            f"{css_number(B1_OUTPUT_SCALE)}px)}}"
        )

    css = (
        exact_gelu_function("exact-gelu-shadow-b1", B1_PREACTIVATION_SCALE)
        + ":host{display:block}.shadow-root{anchor-scope:all}"
        + "css-stage{display:contents!important}"
        + ".shadow-projection{font-size:1000px;font-kerning:none;line-height:1}"
        + ".shadow-partial,.b1-output{position:fixed;inset:0 auto auto 0;"
        + "display:inline-flex;height:1px;overflow:hidden;white-space:pre;"
        + "font-style:normal}.shadow-partial{width:max-content}"
        + (".b1-output{font-family:initial;font-size:1px}" if branch_count > 1 else "")
        + "".join(branch_rules)
        + "".join(combined_rules)
    )
    html = (
        '<css-stage class="b1-mlp"><template shadowrootmode="open">'
        f'<link rel="stylesheet" href="stage-exact-css-gelu-shadow-hybrid-b1-{branch_count}.css">'
        f'<div class="shadow-root">{"".join(branch_html)}'
        f'<div class="b1-combined">{outputs}</div></div></template></css-stage>'
    )
    return html, css


def main() -> None:
    parallel_html = PARALLEL_SOURCE.read_text()
    serial_html = SERIAL_SOURCE.read_text()
    templates = group_templates(serial_html)
    OUTPUT_B0_CSS.write_text(build_b0_css())
    b0_digest = hashlib.sha256(OUTPUT_B0_CSS.read_bytes()).hexdigest()[:12]
    faces, font_bytes = font_faces()
    created = []

    for branch_count in BRANCH_COUNTS:
        stage_html, css = build_stage(branch_count, templates)
        css_path = OUT / f"stage-exact-css-gelu-shadow-hybrid-b1-{branch_count}.css"
        css_path.write_text(css)
        digest = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
        stage_html = stage_html.replace(
            f'{css_path.name}">', f'{css_path.name}?v={digest}">'
        )
        html = replace_b1_stage(parallel_html, stage_html)
        html = html.replace(
            "<title>Layoutless shadow-staged two-block GPT-2</title>",
            f"<title>{branch_count}-branch shadow-reset exact-GELU GPT-2</title>",
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
        output = OUT / (
            f"connected-two-block-shadow-hybrid-{branch_count}-"
            "exact-css-gelu-layoutless.html"
        )
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
        "source": PARALLEL_SOURCE.name,
        "serialGroupSource": SERIAL_SOURCE.name,
        "variants": created,
        "pureProjectionFontBytes": font_bytes,
        "transport": "nested shadow stages with slotted light-DOM branch projections",
    }
    (OUT / "exact-css-gelu-shadow-hybrid-two-block-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    for entry in created:
        print(
            f"built {entry['output']}: {entry['htmlBytes'] / 1e6:.2f} MB HTML, "
            f"{entry['branches']} branches"
        )


if __name__ == "__main__":
    main()
