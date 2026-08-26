#!/usr/bin/env python3
"""Collapse each 256-candidate Grid shard into one multiline text run."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "gpt2-hvar-grid-output-head-global11-shard256-inline-tie"
OUTPUT_NAME = "gpt2-hvar-grid-output-head-multiline"
SOURCE = ROOT / "experiments" / SOURCE_NAME
OUTPUT = ROOT / "experiments" / OUTPUT_NAME


def collapse_group(match: re.Match[str]) -> str:
    group = match.group(1)
    body = match.group(2)
    rows = re.findall(r"<i style=--local-tie:\d+>(.*?)</i>", body)
    if not rows:
        raise RuntimeError(f"group {group} has no rows")
    return f'<div class="group-grid group-{group}">{"<br>".join(rows)}</div>'


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    css = (SOURCE / "index.css").read_text()
    reference = json.loads((SOURCE / "reference.json").read_text())

    pattern = re.compile(
        r'<div class="group-grid group-(\d+)">(.*?)</div>',
        re.DOTALL,
    )
    html, groups = pattern.subn(collapse_group, html)
    if groups != reference["groups"]:
        raise RuntimeError(f"collapsed {groups} groups, expected {reference['groups']}")
    if "<i style=--local-tie:" in html:
        raise RuntimeError("candidate elements remain")
    html = html.replace(
        "Compact global-int11 GPT-2 HVAR + Grid output head",
        "Multiline intrinsic-width GPT-2 output-head probe",
        1,
    )

    candidate = re.search(r"\.group-grid>i\{([^}]*)\}", css)
    if candidate is None:
        raise RuntimeError("candidate rule missing")
    width = re.search(r"width:(calc-size\(.+\))", candidate.group(1))
    if width is None:
        raise RuntimeError("candidate width transform missing")
    score_width = width.group(1).replace(" + var(--local-tie)/64*1px", "")
    if "local-tie" in score_width:
        raise RuntimeError("failed to remove local tie")
    css += (
        "\n.group-grid{display:block;margin:0;white-space:pre;width:max-content;"
        "height:auto;overflow:visible;font-family:inherit;font-size:inherit;"
        "font-variation-settings:inherit;font-style:normal;line-height:1px}"
        f".group-wrapper{{width:{score_width}}}\n"
    )

    reference.update({
        "backend": "three-shard-global-int11-multiline-intrinsic-width-probe",
        "source": SOURCE_NAME,
        "candidateElements": 0,
        "textRuns": groups,
        "lineBreakElements": reference["vocabulary"] - groups,
        "limitation": "probe recovers the winning 256-token group, not the local token",
    })
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "index.css").write_text(css)
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "groups": groups,
        "htmlBytes": len(html.encode()),
        "cssBytes": len(css.encode()),
    }, indent=2))


if __name__ == "__main__":
    main()
