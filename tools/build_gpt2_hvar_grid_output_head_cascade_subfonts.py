#!/usr/bin/env python3
"""Split the fine GPT-2 head into lazily selected 256-token font groups.

This scaling probe emits groups 0 and 1, which cover every checked browser
fixture. The remaining groups deliberately fall back to the existing full
fonts so the page remains inspectable while the on-demand layout is measured.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fontTools import subset


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-hvar-grid-output-head-cascade-subfonts"
COMPACT = ROOT / "experiments" / "gpt2-hvar-grid-output-head-cascade-compact"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
GROUPS = (0, 1)
GROUP_SIZE = 256
FONT_SPECS = tuple(
    (f"Score{plane.upper()}{shard}", f"score-{plane}{shard}.woff2", index)
    for shard in range(6)
    for plane, index in (("h", shard * 2), ("l", shard * 2 + 1))
)


def subset_font(source: Path, destination: Path, unicodes: set[int]) -> None:
    if destination.exists() and destination.stat().st_mtime >= source.stat().st_mtime:
        return
    options = subset.Options()
    options.flavor = "woff2"
    options.recalc_average_width = False
    options.recalc_max_context = False
    options.notdef_outline = True
    options.recommended_glyphs = True
    options.layout_features = "*"
    font = subset.load_font(str(source), options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)
    subset.save_font(font, str(destination), options)


def family_list(group: int | None = None) -> str:
    suffix = "" if group is None else f"G{group}"
    return ",".join(f"{family}{suffix}" for family, _, _ in FONT_SPECS)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    compact_reference = json.loads((COMPACT / "reference.json").read_text())
    fine_html = (FINE / "index.html").read_text()
    records = re.findall(
        r'<i class="candidate"[^>]*>(.*?)</i>',
        fine_html,
    )
    if len(records) != 50_257:
        raise RuntimeError(f"expected 50,257 candidates, found {len(records)}")
    if any(len(glyphs) != len(FONT_SPECS) for glyphs in records):
        raise RuntimeError("unexpected fine candidate glyph count")

    for group in GROUPS:
        start = group * GROUP_SIZE
        stop = min(start + GROUP_SIZE, len(records))
        group_records = records[start:stop]
        for family, filename, glyph_index in FONT_SPECS:
            source = FINE / filename
            destination = OUTPUT / filename.replace(".woff2", f"-g{group}.woff2")
            unicodes = {ord(glyphs[glyph_index]) for glyphs in group_records}
            subset_font(source, destination, unicodes)

    html = (COMPACT / "index.html").read_text().replace(
        "Compact coarse-to-fine GPT-2 CSS output head",
        "On-demand-font coarse-to-fine GPT-2 CSS output head",
    )
    html = html.replace('href="index.css"', 'href="../gpt2-hvar-grid-output-head-cascade-subfonts/index.css"')
    (OUTPUT / "index.html").write_text(html)

    compact_css = (COMPACT / "index.css").read_text()
    _, rest = compact_css.split("\n", 1)
    faces: list[str] = []
    for group in GROUPS:
        for family, filename, _ in FONT_SPECS:
            subset_name = filename.replace(".woff2", f"-g{group}.woff2")
            size_adjust = ";size-adjust:25600%" if "ScoreH" in family else ""
            faces.append(
                f'@font-face{{font-family:{family}G{group};src:url("{subset_name}") '
                f'format("woff2"){size_adjust}}}'
            )
    for family, filename, _ in FONT_SPECS:
        size_adjust = ";size-adjust:25600%" if "ScoreH" in family else ""
        faces.append(
            f'@font-face{{font-family:{family};src:url("../gpt2-hvar-grid-output-head-'
            f'global16-twoplane/{filename}") format("woff2"){size_adjust}}}'
        )
    selected_families = (
        f"if(style(--group:0):{family_list(0)};"
        f"style(--group:1):{family_list(1)};else:{family_list()})"
    )
    rest = rest.replace(f"font-family:{family_list()};", f"font-family:{selected_families};", 1)
    css = "".join(faces) + "\n" + rest
    (OUTPUT / "index.css").write_text(css)

    subset_font_bytes = sum(
        path.stat().st_size for path in OUTPUT.glob("score-*-g*.woff2")
    )
    reference = dict(compact_reference)
    reference.update({
        "backend": "global-int11-coarse-plus-on-demand-group-int16",
        "implementedFineGroups": list(GROUPS),
        "subsetFontFiles": len(GROUPS) * len(FONT_SPECS),
        "subsetFontBytes": subset_font_bytes,
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
        "cssBytes": (OUTPUT / "index.css").stat().st_size,
    })
    reference["initialWorkingSetBytes"] = (
        reference["coarseRuntimeBytes"]
        + reference["htmlBytes"] + reference["cssBytes"]
        + subset_font_bytes // len(GROUPS)
    )
    reference["prototypeRuntimeBytes"] = (
        reference["coarseRuntimeBytes"]
        + reference["htmlBytes"] + reference["cssBytes"] + subset_font_bytes
    )
    reference["totalRuntimeBytes"] = reference["prototypeRuntimeBytes"]
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        key: value for key, value in reference.items() if key != "validation"
    }, indent=2))


if __name__ == "__main__":
    main()
