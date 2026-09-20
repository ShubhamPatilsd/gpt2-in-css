"""R2E pause-and-hold fixture pages (demo shapes: probe_native_reused_loop.py loop bank + build_hybrid matvec consumers).

hold-N.html: one stage with N carriers `i.metric` (inline `width:calc(262144px + (i + var(--in)) * 128px); view-timeline:--t{i} inline`)
inside `.stage>.scroller>.track` (fixed, overflow:scroll, 524288 px viewport, 3x track), `.stage{timeline-scope:--t0..}`, and a sibling
`.consumer` carrying N view-timeline animations (`@keyframes k{i}{from{--p-i:0}to{--p-i:1}}`, duration 1s, linear, fill both,
`animation-range:cover`) publishing registered numbers `--o-i:calc((524288 / var(--p-i) - 524288 - 262144) / 128)` (= i + in).
A `.tick` element runs a 1 s infinite main-thread custom-property animation so the page produces a frame every vsync (per-frame cost).
States are driven by the <html> class (set via CDP, no JS):
  (none)      live: timelines + running animations
  paused      .consumer{animation-play-state:paused}
  pd-none     paused + .metric{view-timeline:none!important}      (subject loses its timeline name)
  pd-display  paused + .scroller{display:none}                     (subjects lose their box)
  pd-cv       paused + .scroller{content-visibility:hidden}        (subjects display-locked)
  d-none      .metric{view-timeline:none!important} WITHOUT pause  (control: expected value loss)
  d-display   .scroller{display:none} WITHOUT pause                 (what the demo's stage gates do to consumers' ancestors, mirrored on carriers)
usage: python3 gen_hold.py <count> ... -> pages/hold-<count>.html"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def page(n):
    regs = "".join(
        f'@property --p-{i}{{syntax:"<number>";inherits:false;initial-value:0}}'
        f'@property --o-{i}{{syntax:"<number>";inherits:true;initial-value:-1}}'
        f"@keyframes k{i}{{from{{--p-{i}:0}}to{{--p-{i}:1}}}}"
        for i in range(n)
    )
    regs += '@property --in{syntax:"<number>";inherits:true;initial-value:0}@property --tk{syntax:"<number>";inherits:false;initial-value:0}'
    css = (
        regs
        + "html,body{margin:0}.tick{position:fixed;left:0;top:0;width:1px;height:1px;animation:tick 1s linear infinite}@keyframes tick{from{--tk:0}to{--tk:1}}"
        + ".stage{timeline-scope:" + ",".join(f"--t{i}" for i in range(n)) + "}"
        + ".scroller{position:fixed;top:-100000px;left:0;width:524288px;height:1px;overflow:scroll;visibility:hidden}"
        + ".track{width:1572864px;height:1px;position:relative}.metric{position:absolute;top:0;left:0;height:1px}"
        + ".consumer{position:fixed;left:0;top:10px;width:1px;height:1px;animation-name:" + ",".join(f"k{i}" for i in range(n))
        + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:" + ",".join(f"--t{i}" for i in range(n))
        + ";animation-range:cover;" + ";".join(f"--o-{i}:calc((524288 / var(--p-{i}) - 524288 - 262144) / 128)" for i in range(n)) + "}"
        + "html.paused .consumer,html.pd-none .consumer,html.pd-display .consumer,html.pd-cv .consumer{animation-play-state:paused}"
        + "html.pd-none .metric,html.d-none .metric{view-timeline:none!important}"
        + "html.pd-display .scroller,html.d-display .scroller{display:none}"
        + "html.pd-cv .scroller{content-visibility:hidden}"
    )
    metrics = "".join(
        f'<i class="metric" style="width:calc(262144px + ({i} + var(--in)) * 128px);view-timeline:--t{i} inline"></i>' for i in range(n)
    )
    html = (
        "<!doctype html><html><head><meta charset=utf-8><title>hold</title><style>" + css + "</style></head><body>"
        '<div class="tick"></div><div class="stage" id="stage"><div class="scroller"><div class="track" id="track">' + metrics
        + '</div></div><div class="consumer" id="consumer"></div></div></body></html>'
    )
    return html


if __name__ == "__main__":
    (HERE / "pages").mkdir(exist_ok=True)
    for arg in sys.argv[1:]:
        n = int(arg)
        out = HERE / "pages" / f"hold-{n}.html"
        out.write_text(page(n))
        print(out, out.stat().st_size, "B")
