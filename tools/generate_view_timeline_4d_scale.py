#!/usr/bin/env python3
"""Generate equal-capacity 2-value and 4-value view-timeline transports."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "view-timeline-4d-scale"
VALUES = 3072
VIEWPORT = 128
ANIMATIONS_PER_CONSUMER = 128


def registrations(names: list[str]) -> str:
    return "".join(
        f'@property {name}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        for name in names
    )


def common_page(css: str, subjects: str, results: str, title: str) -> str:
    return (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        f"<title>{title}</title><style>{css}</style>"
        f'<div class="scope"><div class="scroller"><div class="track">{subjects}'
        f"</div></div>{results}</div>"
    )


def paired_page() -> str:
    pairs = VALUES // 2
    progress = [name for i in range(pairs) for name in (f"--c{i}", f"--e{i}")]
    outputs = [f"--v{i}" for i in range(VALUES)]
    timelines = [f"--t{i}" for i in range(pairs)]
    keyframes = "".join(
        f"@keyframes k{i}{{cover 0%{{--c{i}:0;--e{i}:0}}"
        f"entry 100%{{--e{i}:1}}cover 100%{{--c{i}:1;--e{i}:1}}}}"
        for i in range(pairs)
    )
    subjects = "".join(
        f'<i class="subject" style="left:{VIEWPORT - (20 + i % 17)}px;'
        f'width:{60 + i % 13}px;view-timeline:--t{i} inline"></i>'
        for i in range(pairs)
    )
    result_nodes = []
    result_css = []
    for group, start in enumerate(range(0, pairs, ANIMATIONS_PER_CONSUMER)):
        stop = min(start + ANIMATIONS_PER_CONSUMER, pairs)
        result_nodes.append(f'<i class="result r{group}"></i>')
        result_css.append(
            f".r{group}{{animation-name:{','.join(f'k{i}' for i in range(start, stop))};"
            "animation-duration:1s;animation-timing-function:linear;"
            f"animation-fill-mode:both;animation-timeline:{','.join(timelines[start:stop])};"
            + ";".join(
                f"--v{2*i}:calc(var(--e{i}) * var(--v{2*i+1}));"
                f"--v{2*i+1}:calc(var(--c{i}) * {VIEWPORT} / "
                f"(var(--e{i}) - var(--c{i})))"
                for i in range(start, stop)
            )
            + "}"
        )
    css = (
        registrations(progress + outputs)
        + keyframes
        + f".scope{{timeline-scope:{','.join(timelines)}}}"
        + f".scroller{{position:fixed;top:-2000px;width:{VIEWPORT}px;height:1px;overflow-x:scroll}}"
        + ".track{position:relative;width:512px;height:1px}.subject{position:absolute;height:1px}"
        + "".join(result_css)
    )
    return common_page(css, subjects, "".join(result_nodes), "3072 values, paired timelines")


def fourd_page() -> str:
    quads = VALUES // 4
    progress = [
        name
        for i in range(quads)
        for name in (f"--xc{i}", f"--xe{i}", f"--yc{i}", f"--ye{i}")
    ]
    outputs = [f"--v{i}" for i in range(VALUES)]
    timelines = [name for i in range(quads) for name in (f"--tx{i}", f"--ty{i}")]
    keyframes = "".join(
        f"@keyframes kx{i}{{cover 0%{{--xc{i}:0;--xe{i}:0}}"
        f"entry 100%{{--xe{i}:1}}cover 100%{{--xc{i}:1;--xe{i}:1}}}}"
        f"@keyframes ky{i}{{cover 0%{{--yc{i}:0;--ye{i}:0}}"
        f"entry 100%{{--ye{i}:1}}cover 100%{{--yc{i}:1;--ye{i}:1}}}}"
        for i in range(quads)
    )
    subjects = "".join(
        f'<i class="subject" style="left:{VIEWPORT - (20 + i % 17)}px;'
        f'top:{VIEWPORT - (25 + i % 19)}px;width:{60 + i % 13}px;'
        f'height:{70 + i % 11}px;view-timeline-name:--tx{i},--ty{i};'
        'view-timeline-axis:inline,block"></i>'
        for i in range(quads)
    )
    result_nodes = []
    result_css = []
    timelines_per_group = ANIMATIONS_PER_CONSUMER
    quads_per_group = timelines_per_group // 2
    for group, start in enumerate(range(0, quads, quads_per_group)):
        stop = min(start + quads_per_group, quads)
        result_nodes.append(f'<i class="result r{group}"></i>')
        names = [name for i in range(start, stop) for name in (f"kx{i}", f"ky{i}")]
        group_timelines = [
            name for i in range(start, stop) for name in (f"--tx{i}", f"--ty{i}")
        ]
        declarations = []
        for i in range(start, stop):
            declarations.extend(
                (
                    f"--v{4*i+1}:calc(var(--xc{i}) * {VIEWPORT} / "
                    f"(var(--xe{i}) - var(--xc{i})))",
                    f"--v{4*i}:calc(var(--xe{i}) * var(--v{4*i+1}))",
                    f"--v{4*i+3}:calc(var(--yc{i}) * {VIEWPORT} / "
                    f"(var(--ye{i}) - var(--yc{i})))",
                    f"--v{4*i+2}:calc(var(--ye{i}) * var(--v{4*i+3}))",
                )
            )
        result_css.append(
            f".r{group}{{animation-name:{','.join(names)};animation-duration:1s;"
            "animation-timing-function:linear;animation-fill-mode:both;"
            f"animation-timeline:{','.join(group_timelines)};{';'.join(declarations)}}}"
        )
    css = (
        registrations(progress + outputs)
        + keyframes
        + f".scope{{timeline-scope:{','.join(timelines)}}}"
        + f".scroller{{position:fixed;top:-2000px;width:{VIEWPORT}px;height:{VIEWPORT}px;overflow:scroll}}"
        + ".track{position:relative;width:512px;height:512px}.subject{position:absolute}"
        + "".join(result_css)
    )
    return common_page(css, subjects, "".join(result_nodes), "3072 values, four-dimensional timelines")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "paired.html").write_text(paired_page())
    (OUT / "fourd.html").write_text(fourd_page())
    print({name: (OUT / name).stat().st_size for name in ("paired.html", "fourd.html")})


if __name__ == "__main__":
    main()
