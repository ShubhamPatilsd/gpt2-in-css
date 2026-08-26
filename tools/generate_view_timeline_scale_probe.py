#!/usr/bin/env python3
"""Generate a static, JavaScript-free named-view-timeline scale probe."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("count", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    count = args.count
    names = [f"--t{i}" for i in range(count)]
    props = [f"--p{i}" for i in range(count)]
    keyframes = [f"k{i}" for i in range(count)]

    registrations = "".join(
        f'@property {prop}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f"@keyframes {keyframe}{{from{{{prop}:0}}to{{{prop}:1}}}}"
        for prop, keyframe in zip(props, keyframes, strict=True)
    )
    subjects = "".join(
        f'<div class="s"><div class="track"><i class="m" '
        f'style="width:{20 + index % 60}px;view-timeline:{name} inline"></i>'
        f"</div></div>"
        for index, name in enumerate(names)
    )

    page = f"""<!doctype html>
<meta charset="utf-8">
<title>{count} parallel view-timeline readbacks</title>
<style>
{registrations}
.scope{{timeline-scope:{','.join(names)}}}
.s{{position:fixed;left:-10000px;top:0;width:100px;height:1px;overflow-x:scroll;overflow-y:hidden}}
.track{{width:300px;height:1px}}
.m{{display:block;height:1px}}
.consumer{{animation-name:{','.join(keyframes)};animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:{','.join(names)};animation-range:cover}}
</style>
<div class="scope">
{subjects}
<output class="consumer" data-count="{count}"></output>
</div>
"""
    args.output.write_text(page)


if __name__ == "__main__":
    main()
