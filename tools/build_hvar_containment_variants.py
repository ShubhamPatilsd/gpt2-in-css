#!/usr/bin/env python3
"""Build HTML/CSS-only containment variants of the connected two-block page."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gpt2-block-css"
SOURCE = OUT / "view-timeline-two-block-full-packed4.html"
STAGE_SELECTORS = (
    "css-stage.norm1,.hybrid-packed4-mlp-stage,.output-packed-stage,"
    ".b1-norm,.b1-stage,.b1q4-stage,.b1proj-stage"
)
SCROLLER_SELECTORS = (
    ".q4-scroller,.proj-scroller,.qo-scroller,.b1-scroller,"
    ".b1q4-scroller,.b1proj-scroller"
)
VARIANTS = {
    "stage-layout": f"{STAGE_SELECTORS}{{contain:layout style}}",
    "scroller-size": f"{SCROLLER_SELECTORS}{{contain:size layout style}}",
    "combined": (
        f"{STAGE_SELECTORS}{{contain:layout style}}"
        f"{SCROLLER_SELECTORS}{{contain:size layout style}}"
    ),
    "stage-style": f"{STAGE_SELECTORS}{{contain:style}}",
}


def stripped_variant(source: str, name: str, removals: dict[str, tuple[str, ...]]) -> None:
    html = source
    removed = 0
    for css_name, prefixes in removals.items():
        css = (OUT / css_name).read_text()
        for prefix in prefixes:
            css, count = re.subn(
                rf'@property {re.escape(prefix)}\d{{3,4}}\{{[^{{}}]*\}}',
                "",
                css,
            )
            removed += count
        destination = OUT / f"view-timeline-two-block-{name}-{css_name}"
        destination.write_text(css)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()[:12]
        html = re.sub(
            rf'{re.escape(css_name)}\?v=[^" ]+',
            f"{destination.name}?v={digest}",
            html,
            count=1,
        )
    path = OUT / f"view-timeline-two-block-{name}.html"
    path.write_text(html)
    print(name, path.stat().st_size, removed)


def preload_links(source: str) -> str:
    stylesheets = re.findall(
        r'<link rel="stylesheet" href="([^"?]+)(?:\?[^" ]*)?">', source
    )
    fonts: set[str] = set()
    for stylesheet in stylesheets:
        css_path = OUT / stylesheet
        if not css_path.exists():
            continue
        fonts.update(
            url.split("?", 1)[0]
            for url in re.findall(r'url\(["\']?([^"\')]+\.woff2(?:\?[^"\')]+)?)', css_path.read_text())
        )
    return "".join(
        f'<link rel="preload" as="font" type="font/woff2" crossorigin href="{font}">'
        for font in sorted(fonts)
    )


def main() -> None:
    source = SOURCE.read_text()
    for name, css in VARIANTS.items():
        css_path = OUT / f"view-timeline-two-block-contain-{name}.css"
        html_path = OUT / f"view-timeline-two-block-contain-{name}.html"
        css_path.write_text(css + "\n")
        digest = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
        link = f'<link rel="stylesheet" href="{css_path.name}?v={digest}">'
        html_path.write_text(source.replace("</title>", f"</title>{link}", 1))
        print(name, html_path.stat().st_size, css_path.stat().st_size)
    preloads = preload_links(source)
    preload_path = OUT / "view-timeline-two-block-preload-fonts.html"
    preload_path.write_text(source.replace("</title>", f"</title>{preloads}", 1))
    print("preload-fonts", preload_path.stat().st_size, preloads.count("rel=\"preload\""))

    full_css_name = "view-timeline-two-block-full-packed4.css"
    full_css = (OUT / full_css_name).read_text()
    unregistered_n2 = re.sub(
        r'@property --b1-n2-\d{3}\{[^{}]*\}', "", full_css
    )
    n2_css_path = OUT / "view-timeline-two-block-unregistered-n2.css"
    n2_css_path.write_text(unregistered_n2)
    n2_digest = hashlib.sha256(n2_css_path.read_bytes()).hexdigest()[:12]
    n2_html = re.sub(
        rf'{re.escape(full_css_name)}\?v=[^" ]+',
        f"{n2_css_path.name}?v={n2_digest}",
        source,
        count=1,
    )
    n2_html_path = OUT / "view-timeline-two-block-unregistered-n2.html"
    n2_html_path.write_text(n2_html)
    print("unregistered-n2", n2_html_path.stat().st_size, full_css.count("@property --b1-n2-") )

    attention_css = "view-timeline-two-block-attention-probe.css"
    block0_css = "view-timeline-block-hybrid-packed4-chain-channel89asym-h15.css"
    stripped_variant(source, "unregistered-layernorm", {
        attention_css: ("--b1-n1-",),
        full_css_name: ("--b1-n2-",),
    })
    stripped_variant(source, "unregistered-states", {
        block0_css: ("--out-",),
        attention_css: ("--b1-out-",),
    })
    stripped_variant(source, "unregistered-intermediates", {
        block0_css: ("--out-",),
        attention_css: ("--b1-n1-", "--b1-out-"),
        full_css_name: ("--b1-n2-",),
    })


if __name__ == "__main__":
    main()
