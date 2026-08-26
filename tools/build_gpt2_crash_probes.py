#!/usr/bin/env python3
"""Build browser crash-isolation variants of the four-stage GPT-2 prefix."""

from __future__ import annotations

from pathlib import Path
import re

from build_gpt2_block_css import OUT


STAGES = ("value", "attn", "fc00", "fc01")
OVERRIDES = {
    "no-font": (
        ".metric,.pack{font-family:monospace!important;"
        "font-variation-settings:normal!important}"
    ),
    "no-containers": (
        ".metric{display:none!important}.probe{container:normal!important;"
        "width:1px!important;height:1px!important}"
    ),
}


def section(css: str, start: str, stop: str | None) -> str:
    after = css.split(start, 1)[1]
    return after if stop is None else after.split(stop, 1)[0]


def main() -> None:
    source_html = (OUT / "prefix-4.html").read_text()
    for mode, override in OVERRIDES.items():
        html = source_html
        for stage in STAGES:
            source_name = f"stage-{stage}.css"
            target_name = f"stage-{stage}-{mode}.css"
            source_css = (OUT / source_name).read_text()
            (OUT / target_name).write_text(source_css + override)
            html = html.replace(source_name, target_name)
        (OUT / f"prefix-4-{mode}.html").write_text(html)
    no_model = re.sub(
        r'<link rel="stylesheet" href="model\.css\?v=[^"]+">',
        "",
        source_html,
    )
    for stage in STAGES:
        source_name = f"stage-{stage}.css"
        target_name = f"stage-{stage}-no-containers.css"
        no_model = no_model.replace(source_name, target_name)
    (OUT / "prefix-4-no-model.html").write_text(no_model)
    no_css = re.sub(r'<link rel="stylesheet" href="[^"]+">', "", source_html)
    (OUT / "prefix-4-structure-only.html").write_text(no_css)
    component_modes = {
        "layout-only": ("base",),
        "font-only": ("faces", "base", "fonts"),
        "query-only": ("base", "probes", "queries"),
    }
    markers = {
        "faces": ("/* faces */", "/* base */"),
        "base": ("/* base */", "/* fonts */"),
        "fonts": ("/* fonts */", "/* probes */"),
        "probes": ("/* probes */", "/* queries */"),
        "queries": ("/* queries */", None),
    }
    for mode, included in component_modes.items():
        html = re.sub(
            r'<link rel="stylesheet" href="model\.css\?v=[^"]+">',
            "",
            source_html,
        )
        for stage in STAGES:
            source_name = f"stage-{stage}.css"
            target_name = f"stage-{stage}-{mode}.css"
            source_css = (OUT / source_name).read_text()
            target_css = "".join(
                section(source_css, *markers[name]) for name in included
            )
            (OUT / target_name).write_text(target_css)
            html = html.replace(source_name, target_name)
        (OUT / f"prefix-4-{mode}.html").write_text(html)
    geometry_modes = {
        "layout-static": (
            ("base",),
            ".probe{position:static!important;inset:auto!important}",
            True,
        ),
        "layout-no-metrics": (
            ("base",),
            ".metric{display:none!important}",
            True,
        ),
        "full-static": (
            ("faces", "base", "fonts", "probes", "queries"),
            ".probe{position:static!important;inset:auto!important}",
            False,
        ),
        "full-relative": (
            ("faces", "base", "fonts", "probes", "queries"),
            ".probe{position:relative!important;inset:auto!important}",
            False,
        ),
        "full-fixed": (
            ("faces", "base", "fonts", "probes", "queries"),
            ".probe{position:fixed!important;inset:0 auto auto 0!important}",
            False,
        ),
        "full-fixed-all": (
            ("faces", "base", "fonts", "probes", "queries"),
            ".probe,.metric{position:fixed!important;inset:0 auto auto 0!important}",
            False,
        ),
        "full-flex": (
            ("faces", "base", "fonts", "probes", "queries"),
            ".probe{display:flex!important}",
            False,
        ),
        "full-grid": (
            ("faces", "base", "fonts", "probes", "queries"),
            ".probe{display:grid!important}",
            False,
        ),
    }
    for mode, (included, override, remove_model) in geometry_modes.items():
        html = source_html
        if remove_model:
            html = re.sub(
                r'<link rel="stylesheet" href="model\.css\?v=[^"]+">',
                "",
                html,
            )
        for stage in STAGES:
            source_name = f"stage-{stage}.css"
            target_name = f"stage-{stage}-{mode}.css"
            source_css = (OUT / source_name).read_text()
            target_css = (
                "".join(section(source_css, *markers[name]) for name in included)
                + override
            )
            (OUT / target_name).write_text(target_css)
            html = html.replace(source_name, target_name)
        (OUT / f"prefix-4-{mode}.html").write_text(html)
    fixed_stages = source_html.replace(
        "</title>",
        '</title><style>css-stage[slot="next"]{position:fixed!important;'
        "inset:0 auto auto 0!important}</style>",
    )
    (OUT / "prefix-4-fixed-stages.html").write_text(fixed_stages)
    contained_stages = source_html.replace(
        "</title>",
        '</title><style>css-stage[slot="next"]{contain:layout!important}</style>',
    )
    (OUT / "prefix-4-contained-stages.html").write_text(contained_stages)
    fixed_small = source_html
    for stage in STAGES:
        source_name = f"stage-{stage}.css"
        target_name = f"stage-{stage}-fixed-small.css"
        css = (OUT / source_name).read_text()
        css = css.replace("font-size:512px", "font-size:8px")
        css = css.replace(" / 512 - ", " / 8 - ")
        css += ".probe,.metric{position:fixed!important;inset:0 auto auto 0!important}"
        (OUT / target_name).write_text(css)
        fixed_small = fixed_small.replace(source_name, target_name)
    (OUT / "prefix-4-fixed-small.html").write_text(fixed_small)
    global_faces = "".join(
        section((OUT / f"stage-{stage}.css").read_text(), "/* faces */", "/* base */")
        for stage in STAGES
    )
    global_font_html = source_html.replace(
        "</title>", f"</title><style>{global_faces}</style>"
    )
    (OUT / "prefix-4-global-fonts.html").write_text(global_font_html)
    fixed_small_global = fixed_small.replace(
        "</title>", f"</title><style>{global_faces}</style>"
    )
    (OUT / "prefix-4-fixed-small-global.html").write_text(fixed_small_global)
    prefix_one = (OUT / "prefix-1.html").read_text().replace(
        "</title>",
        "</title><style>"
        + section(
            (OUT / "stage-value.css").read_text(),
            "/* faces */",
            "/* base */",
        )
        + "</style>",
    )
    (OUT / "prefix-1-global-fonts.html").write_text(prefix_one)
    print({"stages": len(STAGES), "variants": list(OVERRIDES)})


if __name__ == "__main__":
    main()
