#!/usr/bin/env python3
"""Replace mixed-hot2 timeline bucket extraction with a direct anchor maximum."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-mixed-precision-hot2-upper"
OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-direct-outer-max"
PRUNED_OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-direct-outer-max-pruned"
STRIPPED_OUTPUT = ROOT / "experiments" / "gpt2-mixed-hot2-direct-outer-max-stripped"
VOCABULARY = 50_257
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    marker = '<div class="outer-reader">'
    if html.count(marker) != 1:
        raise RuntimeError("direct outer max insertion point changed")
    html = html.replace(
        marker,
        '<i class="direct-outer-max"></i>' + marker,
        1,
    ).replace(
        "Mixed-precision hot-two certified upper head",
        "Mixed hot-two direct outer maximum",
        1,
    )

    terms = ",".join(
        f"anchor-size(--score-group-{group} width)"
        for group in range(GROUPS)
    )
    topology = (SOURCE / "topology.css").read_text() + (
        "\nbody{anchor-scope:all}"
        ".direct-outer-max{position:fixed;left:0;top:-94000px;height:1px;"
        f"anchor-name:--direct-outer-max;width:max({terms})}}"
        ".outer-reader{position-anchor:--direct-outer-max;"
        "width:anchor-size(--direct-outer-max width)}\n"
    )

    source_reference = json.loads((SOURCE / "reference.json").read_text())
    reference = {
        **source_reference,
        "backend": "mixed-hot2-direct-outer-max",
        "sourceMixed": SOURCE.name,
        "directOuterMaximumGroups": GROUPS,
        "topologyStrategy": (
            "replace the 197 view-timeline inverse-width group proxies used for "
            "outer bucket extraction with one direct max(anchor-size(...)) node; "
            "leave score rows and every downstream decoder unchanged"
        ),
        "generatedBytes": {
            "index.html": len(html.encode()),
            "topology.css": len(topology.encode()),
        },
    }
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "topology.css").write_text(topology)
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")

    PRUNED_OUTPUT.mkdir(parents=True, exist_ok=True)
    pruned_html, removed = re.subn(
        r'<i class="group-proxy group-proxy-\d+"></i>',
        "",
        html,
    )
    if removed != GROUPS:
        raise RuntimeError(f"removed {removed} timeline proxies, expected {GROUPS}")
    pruned_html = pruned_html.replace(
        "Mixed hot-two direct outer maximum",
        "Mixed hot-two direct outer maximum, timeline graph pruned",
        1,
    )
    pruned_topology = topology + (
        ".model{timeline-scope:none!important}"
        ".group-wrapper{view-timeline:none!important}"
        ".group-proxy{display:none!important}\n"
    )
    pruned_reference = {
        **reference,
        "backend": "mixed-hot2-direct-outer-max-pruned",
        "sourceDirectOuterMax": OUTPUT.name,
        "removedTimelineProxyElements": removed,
        "topologyStrategy": (
            reference["topologyStrategy"] + "; remove the now-unreferenced 197 "
            "group proxy elements and disable their view timelines/timeline scope"
        ),
        "generatedBytes": {
            "index.html": len(pruned_html.encode()),
            "topology.css": len(pruned_topology.encode()),
        },
    }
    (PRUNED_OUTPUT / "index.html").write_text(pruned_html)
    (PRUNED_OUTPUT / "topology.css").write_text(pruned_topology)
    (PRUNED_OUTPUT / "reference.json").write_text(
        json.dumps(pruned_reference, indent=2) + "\n"
    )

    STRIPPED_OUTPUT.mkdir(parents=True, exist_ok=True)
    stripped_html, inline_timelines = re.subn(
        r";view-timeline:--ogt\d+ inline",
        "",
        pruned_html,
    )
    if inline_timelines != GROUPS:
        raise RuntimeError(
            f"removed {inline_timelines} inline timelines, expected {GROUPS}"
        )
    source_link = (
        '<link rel="stylesheet" '
        'href="../gpt2-hvar-grid-output-head-certified-upper-int10/index.css">'
    )
    if stripped_html.count(source_link) != 1:
        raise RuntimeError("base stylesheet link changed")
    stripped_html = stripped_html.replace(
        source_link,
        '<link rel="stylesheet" href="stripped-base.css">',
        1,
    ).replace(
        "Mixed hot-two direct outer maximum, timeline graph pruned",
        "Mixed hot-two direct outer maximum, timeline stylesheet stripped",
        1,
    )
    base_css = (
        ROOT
        / "experiments"
        / "gpt2-hvar-grid-output-head-certified-upper-int10"
        / "index.css"
    ).read_text()
    stripped_css, registered_timelines = re.subn(
        r"@property --ogp\d+\{[^{}]*\}@keyframes ogk\d+\{from\{[^{}]*\}to\{[^{}]*\}\}",
        "",
        base_css,
    )
    stripped_css, timeline_scopes = re.subn(
        r"timeline-scope:[^;]+;",
        "",
        stripped_css,
    )
    stripped_css, proxy_common = re.subn(
        r"\.group-proxy\{[^{}]*\}",
        "",
        stripped_css,
    )
    stripped_css, proxy_rules = re.subn(
        r"\.group-proxy-\d+\{[^{}]*\}",
        "",
        stripped_css,
    )
    if (
        registered_timelines != GROUPS
        or timeline_scopes != 1
        or proxy_common != 1
        or proxy_rules != GROUPS
    ):
        raise RuntimeError({
            "registeredTimelines": registered_timelines,
            "timelineScopes": timeline_scopes,
            "proxyCommon": proxy_common,
            "proxyRules": proxy_rules,
        })
    stripped_reference = {
        **pruned_reference,
        "backend": "mixed-hot2-direct-outer-max-stripped",
        "sourcePruned": PRUNED_OUTPUT.name,
        "removedInlineViewTimelines": inline_timelines,
        "removedRegisteredTimelines": registered_timelines,
        "removedTimelineScopes": timeline_scopes,
        "removedTimelineProxyRules": proxy_rules,
        "generatedBytes": {
            "index.html": len(stripped_html.encode()),
            "stripped-base.css": len(stripped_css.encode()),
            "topology.css": len(pruned_topology.encode()),
        },
    }
    (STRIPPED_OUTPUT / "index.html").write_text(stripped_html)
    (STRIPPED_OUTPUT / "stripped-base.css").write_text(stripped_css)
    (STRIPPED_OUTPUT / "topology.css").write_text(pruned_topology)
    (STRIPPED_OUTPUT / "reference.json").write_text(
        json.dumps(stripped_reference, indent=2) + "\n"
    )
    print(json.dumps({
        "groups": GROUPS,
        "variants": [
            {
                "directory": OUTPUT.name,
                "htmlBytes": len(html.encode()),
                "cssBytes": len(topology.encode()),
            },
            {
                "directory": PRUNED_OUTPUT.name,
                "htmlBytes": len(pruned_html.encode()),
                "cssBytes": len(pruned_topology.encode()),
                "removedTimelineProxyElements": removed,
            },
            {
                "directory": STRIPPED_OUTPUT.name,
                "htmlBytes": len(stripped_html.encode()),
                "baseCssBytes": len(stripped_css.encode()),
                "topologyCssBytes": len(pruned_topology.encode()),
                "removedRegisteredTimelines": registered_timelines,
            },
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
