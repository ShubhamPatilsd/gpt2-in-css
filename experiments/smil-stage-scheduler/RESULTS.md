# SVG SMIL as a CSS-only stage scheduler

Chrome 153 can use an SVG SMIL class animation as a timer signal for ordinary
HTML. The runtime pages contain no JavaScript; Playwright is only the external
measurement harness.

The working bridge is:

```html
<svg><g id="signal">
  <set attributeName="class" to="ready" begin="0.15s" fill="freeze">
</g></svg>
```

```css
html:not(:has(#signal.ready)) .downstream { display: none }
```

SMIL updates `SVGAnimatedString.animVal`, Chrome invalidates `:has()`, and the
normal HTML subtree becomes active. SMIL cannot target an HTML element's class
directly: `<set href="#html-element" attributeName="class">` leaves it hidden.

## Synthetic scaling

The source custom property animates for 100 ms. Every downstream node depends
on that value. Medians are three fresh pages:

| Nodes | Connected task | SVG-gated task | Connected layouts | SVG-gated layouts |
| ---: | ---: | ---: | ---: | ---: |
| 1,000 | 24.2 ms | 14.8 ms | 7 | 2 |
| 5,000 | 59.2 ms | 24.4 ms | 7 | 2 |
| 20,000 | 155.3 ms | 56.4 ms | 5 | 2 |

The result width is exactly 37 px after activation, proving that inherited CSS
numeric state survives the boundary. A direct SMIL gate around an HTML
`foreignObject` is cheaper in this synthetic case (88.4 ms task time at 20k),
but that wrapper has a substantial tax in the real model.

## Exact two-block model

The SVG signal is emitted after block 1's markup. Until the signal class is
animated, block 1 stays in its original HTML location but is inactive. All
variants return the same 768 outputs: RMSE 0.007255 and maximum error 0.12624
against the saved reference.

Three fresh-page medians:

| Gate | Completion | Change vs connected |
| --- | ---: | ---: |
| Connected | 5.830 s | — |
| `display:none`, 50 ms | **4.536 s** | **-22.2%** |
| `display:none`, 250 ms | 4.607 s | -21.0% |
| `display:none`, 1,000 ms | 5.167 s | -11.4% |
| `display:none`, 2,000 ms | 6.391 s | +9.6% |
| `content-visibility`, 250 ms | 4.676 s | -19.8% |
| `content-visibility`, 1,000 ms | 5.460 s | -6.3% |

The 50 and 250 ms display gates are the same practical optimum. A second
three-round batch put 250 ms first at 4.460 seconds versus a 6.063-second
control; combining both batches gives 4.607 versus 6.063 seconds, a 24.0%
reduction. The same 250 ms delay through a
`foreignObject` wrapper regresses from 5.301 to 5.647 seconds, confirming that
the useful trick is the animated-SVG-class/HTML-selector handoff, not SVG
layout containment.

## Dependency-driven handoffs

A fixed delay is not required. A CSS animation attached to an offscreen SVG
`g` can follow the final view timeline in a stage. Its `animationend` event can
then start the SMIL `set`, which makes the downstream HTML selector match:

```html
<svg><g id="css-ready"></g><g id="signal">
  <set attributeName="class" to="ready"
       begin="css-ready.animationend+0.05s" fill="freeze">
</g></svg>
```

```css
#css-ready {
  animation: stage-ready 1s linear both;
  animation-timeline: --last-upstream-value;
}
```

On the exact two-block graph this adaptive handoff reaches block 1 at 4.06
seconds and finishes at 4.63 seconds, with the same numeric error as the
fixed-delay variants. The event comes from actual upstream timeline progress,
not an assumed machine-specific duration.

Container-query activation provides the equivalent event at the output-head
boundaries. Chaining view-timeline and container-query CSS animations through
five SMIL signals automatically opens block 1, coarse vocabulary scoring,
fine scoring, near-score selection, and dithering. The runtime page contains
no JavaScript and returns the correct token 11 in two of two fresh runs:

| Milestone | Later of two runs |
| --- | ---: |
| Block 1 active | 2.263 s |
| Coarse head active | 4.532 s |
| Coarse scan complete / fine active | 59.218 s |
| Fine complete / near active | 71.739 s |
| Near complete / dither active | 75.185 s |
| Final result read | 78.149 s |

The two totals are 78.122 and 78.149 seconds. Layout accounts for 69.94-70.12
seconds, while style recalculation takes 2.66-2.67 seconds. This demonstrates
a fully dependency-driven declarative scheduler; it also makes clear that the
50,257-row vocabulary scan, not scheduling, is now the dominant cold-path
problem.

## Output-head limit

Automatically opening the non-staged selective GPT-2 head after the two blocks
returns the correct refined token, 11, but takes 91.1 seconds on a cold page;
78.5 seconds is layout. The dependency-driven internal sequence lowers that to
about 78.1 seconds and eliminates all external checkbox intervention. Internal
staging is therefore useful, but it does not remove the full coarse scan.

SMIL signals are also one-shot. They improve initial declarative evaluation;
after activation, later input mutations see the connected graph again. A
recurrent CSS inference loop still needs a repeatable state machine or separate
documents for successive tokens.

## Reproduce

```sh
make test-smil-stage-scheduler
make test-two-block-smil-selector-stage
make test-full-inference-event-scheduler
```

The exploratory `foreignObject` and full-head probes are available as
`test-two-block-smil-stage` and `test-full-inference-smil-scheduler`.
