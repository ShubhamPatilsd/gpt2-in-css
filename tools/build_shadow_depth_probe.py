#!/usr/bin/env python3
"""Build a no-JavaScript probe for carrying CSS state across a shadow root."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "shadow-depth-probe.html"
SLOTTED_OUT = ROOT / "experiments" / "slotted-depth-probe.html"
FORWARDED_OUT = ROOT / "experiments" / "forwarded-depth-probe.html"
DEPTH = 400


def nested(content: str) -> str:
    return "<div>" * DEPTH + content + "</div>" * DEPTH


def main() -> None:
    shadow = nested(
        '<output id="end" style="--seen:var(--carried)">shadow boundary</output>'
    )
    host = (
        '<css-state style="--carried:37">'
        '<template shadowrootmode="open">'
        f"{shadow}"
        "</template>"
        "</css-state>"
    )
    OUT.write_text(
        "<!doctype html><meta charset=utf-8><title>Shadow depth probe</title>"
        + nested(host)
    )
    final = (
        '<output id="end" slot="next" style="--seen:var(--measured)">'
        "slotted shadow boundary</output>"
    )
    inner_host = (
        '<css-layer slot="next"><template shadowrootmode="open">'
        + nested('<slot name="next"></slot>')
        + "</template>"
        + final
        + "</css-layer>"
    )
    outer_host = (
        '<css-layer id="outer" style="--carried:37">'
        '<template shadowrootmode="open">'
        '<style>'
        '.metric{position:absolute;width:37px;height:1px;anchor-name:--metric}'
        '.probe{position:absolute;width:anchor-size(--metric width);container:measured/inline-size}'
        '@container measured (width > 0px){slot{--measured:calc(100cqi / 1px)}}'
        '</style><i class="metric"></i><div class="probe">'
        + nested('<slot name="next"></slot>')
        + '</div>'
        + "</template>"
        + inner_host
        + "</css-layer>"
    )
    SLOTTED_OUT.write_text(
        "<!doctype html><meta charset=utf-8><title>Slotted depth probe</title>"
        '<style>@property --measured{syntax:"<number>";inherits:true;initial-value:0}</style>'
        + outer_host
    )
    stage_style = (
        '<style>.metric{position:absolute;width:41px;height:1px;anchor-name:--metric}'
        '.probe{position:absolute;width:anchor-size(--metric width);container:forwarded/inline-size}'
        '@container forwarded (width > 0px){slot{--forwarded:calc(100cqi / 1px)}}'
        '</style><i class="metric"></i><div class="probe">'
    )

    def block(block_id: str, child: str, slot: str = "") -> str:
        return (
            f'<block-stage id="{block_id}"{slot}><template shadowrootmode="open">'
            '<css-layer><template shadowrootmode="open">'
            + stage_style
            + nested('<slot name="next"></slot>')
            + '</div></template><slot name="block-next" slot="next"></slot></css-layer>'
            '</template>'
            + child
            + '</block-stage>'
        )

    forwarded_final = (
        '<output id="forwarded-end" slot="block-next" '
        'style="--seen:var(--forwarded)">forwarded slot</output>'
    )
    second_block = block(
        "second", forwarded_final, ' slot="block-next"'
    )
    forwarded_page = block("forwarded-outer", second_block)
    FORWARDED_OUT.write_text(
        '<!doctype html><meta charset=utf-8><title>Forwarded depth probe</title>'
        '<style>@property --forwarded{syntax:"<number>";inherits:true;initial-value:0}</style>'
        + forwarded_page
    )
    print(
        {
            "shadow_depth_per_tree": DEPTH,
            "html_bytes": OUT.stat().st_size,
            "slotted_html_bytes": SLOTTED_OUT.stat().st_size,
            "forwarded_html_bytes": FORWARDED_OUT.stat().st_size,
        }
    )


if __name__ == "__main__":
    main()
