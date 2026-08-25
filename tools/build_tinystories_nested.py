#!/usr/bin/env python3
"""Build a timer-free, script-free nested TinyStories generation page."""

from __future__ import annotations

from pathlib import Path

from build_tinystories_recurrent import (
    CACHE_CAPACITY,
    GENERATIONS,
    LAYERS,
    WIDTH,
)
from build_tinystories_step import tokenizer


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tinystories"
DECODE_BUCKET_SIZE = 256
STREAM_GATE_MILLISECONDS = 1
VISIBLE_BENCHMARK_TOKENS = 15
VISIBLE_BENCHMARK_MILLISECONDS = (12891, 12828)


def css_token_string(value: str) -> str:
    escaped = []
    for character in value:
        codepoint = ord(character)
        if character == "\\":
            escaped.append("\\\\")
        elif character == '"':
            escaped.append('\\"')
        elif codepoint < 32 or codepoint == 127:
            escaped.append(f"\\{codepoint:x} ")
        else:
            escaped.append(character)
    return '"' + "".join(escaped) + '"'


def state_pairs() -> list[tuple[str, str]]:
    pairs = [
        ("ts-next-length", "__2length"),
        ("ts-next-position", "__2position"),
        ("ts-next-step", "__2step"),
    ]
    pairs.extend(
        (f"next{dimension}", f"__2embedding-{dimension}")
        for dimension in range(WIDTH)
    )
    pairs.extend(
        (
            f"ts-next-{kind}-{layer}-{slot}-{dimension}",
            f"__2{kind}-{layer}-{slot}-{dimension}",
        )
        for kind in ("k", "v")
        for layer in range(LAYERS)
        for slot in range(CACHE_CAPACITY)
        for dimension in range(WIDTH)
    )
    return pairs


def decoder_css() -> list[str]:
    codec = tokenizer()
    vocabulary = len(codec.inverse_vocab)
    functions = []
    buckets = (vocabulary + DECODE_BUCKET_SIZE - 1) // DECODE_BUCKET_SIZE
    for bucket in range(buckets):
        start = bucket * DECODE_BUCKET_SIZE
        end = min(vocabulary, start + DECODE_BUCKET_SIZE)
        cases = ";".join(
            f"style(--token-id:{token}):{css_token_string(codec.decode_token(token))}"
            for token in range(start, end)
        )
        functions.append(
            f"@function --decode-token-{bucket}() returns <string>"
            f"{{result:if({cases};else:\"\");}}"
        )
    outer_cases = ";".join(
        f"style(--token-bucket:{bucket}):--decode-token-{bucket}()"
        for bucket in range(buckets)
    )
    functions.extend(
        [
            '@property --winner-id{syntax:"<integer>";inherits:true;initial-value:0}',
            '@property --token-id{syntax:"<integer>";inherits:false;initial-value:0}',
            '@property --token-bucket{syntax:"<integer>";inherits:false;initial-value:0}',
            ".token-output{"
            "--token-id:var(--winner-id);"
            f"--token-bucket:round(down,calc(var(--token-id)/{DECODE_BUCKET_SIZE}),1);"
            f"--token-piece:if({outer_cases};else:\"\");"
            "}",
            ".candidate-token{"
            f"--token-bucket:round(down,calc(var(--token-id)/{DECODE_BUCKET_SIZE}),1);"
            f"--token-piece:if({outer_cases};else:\"\");"
            "}",
            ".token-output::after,.candidate-token::after{content:var(--token-piece);}",
        ]
    )
    return functions


def runtime_css() -> str:
    pairs = state_pairs()
    registrations = [
        "/* Later registrations make model outputs available to a child handoff. */"
    ]
    for source, _target in pairs:
        registrations.append(
            f'@property --{source}{{syntax:"<number>";inherits:true;initial-value:0}}'
        )
    declarations = [f"--{target}:var(--{source});" for source, target in pairs]
    handoff_rules = [
        ".handoff{" + "".join(declarations[start : start + 1000]) + "}"
        for start in range(0, len(declarations), 1000)
    ]
    presentation = [
        ".nested-model{animation:none!important;display:inline;}",
        ".handoff{display:inline;}",
        "body{max-width:48rem;margin:4rem auto;padding:0 1.5rem;font:18px/1.6 system-ui,sans-serif;}",
        ".story{font:700 2rem/1.4 Georgia,serif;padding:1.5rem 0;}",
        ".status{color:#666;}",
    ]
    return "\n".join(
        registrations + handoff_rules + decoder_css() + presentation
    ) + "\n"


def streaming_css(*, include_winner_gate: bool = True) -> str:
    winner_gate = (
        "@container style(--winner-id){"
        ".streaming-page .handoff{animation:ts-open-gate "
        f"{STREAM_GATE_MILLISECONDS}ms steps(1,end) both}}"
        "}"
        if include_winner_gate
        else ""
    )
    return f"""@property --gate-open{{syntax:\"<integer>\";inherits:false;initial-value:0}}
@keyframes ts-open-gate{{to{{--gate-open:1;display:inline}}}}
.streaming-page .handoff{{
  --gate-open:0;
  display:inline-block;
  content-visibility:if(style(--gate-open:1):visible;else:hidden);
  contain-intrinsic-size:auto 1lh;
}}
.streaming-page .story{{white-space:pre-wrap}}
{winner_gate}
#pause-generation:checked ~ .story .handoff{{animation-play-state:paused}}
.generation-controls{{display:flex;align-items:center;gap:.75rem;margin:1.5rem 0}}
#pause-generation,#show-token-ids{{position:absolute;inline-size:1px;block-size:1px;opacity:0}}
.generation-controls label{{
  display:inline-block;
  min-inline-size:4rem;
  padding:.45rem .8rem;
  border:1px solid #777;
  border-radius:.4rem;
  cursor:pointer;
  text-align:center;
  font-weight:700;
}}
.generation-controls .pause-control::after{{content:\"Pause\"}}
#pause-generation:checked + .generation-controls .pause-control::after{{content:\"Play\"}}
#pause-generation:focus-visible + .generation-controls .pause-control{{outline:3px solid Highlight;outline-offset:3px}}
.generation-controls .control-status::after{{content:\"Generation is running\"}}
#pause-generation:checked + .generation-controls .control-status::after{{content:\"Generation is paused before the next stage\"}}
#show-token-ids:checked ~ .story .token-output{{counter-reset:ts-token-id var(--winner-id)}}
#show-token-ids:checked ~ .story .token-output::before{{
  content:\"[\" counter(ts-token-id) \"]\";
  margin-inline:.25rem .1rem;
  color:#666;
  font:600 .75rem/1 system-ui,sans-serif;
}}
"""


def nested_models(remaining: int, step: int = 1) -> str:
    child = nested_models(remaining - 1, step + 1) if remaining > 1 else ""
    handoff_tag = "div" if child else "span"
    completion_class = " completion-marker" if not child else ""
    handoff = (
        f'<{handoff_tag} class="handoff{completion_class}" '
        f'data-after-token="{step}">{child}</{handoff_tag}>'
    )
    return (
        f'<div class="model nested-model" data-step="{step}">'
        f'<span class="token-output" aria-label="generated token {step}"></span>'
        f"{handoff}</div>"
    )


def page() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Timer-free CSS-only TinyStories generation</title>
  <link rel="stylesheet" href="../output-head-benchmark/generated/clustered-256-embedding-shared-runtime.css?v=ts-nested-1">
  <link rel="stylesheet" href="recurrent.css?v=ts-nested-1">
  <link rel="stylesheet" href="nested-runtime.css?v=ts-nested-1">
</head>
<body>
  <h1>Timer-free CSS-only TinyStories generation</h1>
  <p class="status">The text below is generated by nested CSS transformer stages. No JavaScript.</p>
  <main class="story">Once upon a time{nested_models(GENERATIONS)}</main>
  <p class="status">This build predeclares {GENERATIONS} output stages.</p>
</body>
</html>
"""


def streaming_page(
    packed_feedback: bool = False,
    wide_feedback: bool = False,
    score_token_packing: bool = False,
    row_int8_scores: bool = False,
    row_int10_scores: bool = False,
) -> str:
    if row_int10_scores:
        head_name = (
            "clustered-256-embedding-packed8-row-int10-shared-runtime.css"
        )
        suffix = " (row-quantized 10-bit token scores)"
    elif row_int8_scores:
        head_name = (
            "clustered-256-embedding-packed8-row-int8-shared-runtime.css"
        )
        suffix = " (row-quantized 8-bit token scores)"
    elif score_token_packing:
        head_name = (
            "clustered-256-embedding-packed8-score-token-shared-runtime.css"
        )
        suffix = " (packed score and token candidate)"
    elif wide_feedback:
        head_name = (
            "clustered-256-embedding-packed8x6-untyped-shared-runtime.css"
        )
        suffix = " (six-coordinate 48-bit feedback candidate)"
    elif packed_feedback:
        head_name = "clustered-256-embedding-packed8-shared-runtime.css"
        suffix = " (packed 8-bit feedback)"
    else:
        head_name = "clustered-256-embedding-shared-runtime.css"
        suffix = ""
    head_version = (
        "ts-row-int10-1"
        if row_int10_scores
        else "ts-row-int8-1"
        if row_int8_scores
        else "ts-score-token-2"
        if score_token_packing
        else "ts-streaming-2"
    )
    median_milliseconds = sum(VISIBLE_BENCHMARK_MILLISECONDS) / len(
        VISIBLE_BENCHMARK_MILLISECONDS
    )
    visible_tokens_per_second = (
        VISIBLE_BENCHMARK_TOKENS * 1000 / median_milliseconds
    )
    if row_int10_scores:
        benchmark = (
            "Experimental row-quantized 10-bit token scores. Painted "
            "throughput is measured externally; this page contains no script."
        )
    elif row_int8_scores:
        benchmark = (
            "Experimental row-quantized 8-bit token scores. Painted "
            "throughput is measured externally; this page contains no script."
        )
    elif score_token_packing:
        benchmark = (
            "Experimental packed score/token winner recovery. Painted "
            "throughput is measured externally; this page contains no script."
        )
    elif wide_feedback:
        benchmark = (
            "<strong>Measured visible throughput:</strong> 0.85 tokens/second "
            "on Chromium 151 on this machine (15 tokens after Play in "
            "17.649 seconds median). All 16 token IDs matched the reference, "
            "but this is slower than the typed 24-bit page."
        )
    elif packed_feedback:
        benchmark = (
            "<strong>Measured visible throughput:</strong> "
            f"{visible_tokens_per_second:.2f} tokens/second on Chromium 151 "
            f"on this machine ({VISIBLE_BENCHMARK_TOKENS} tokens after Play "
            f"in {median_milliseconds / 1000:.3f} seconds median). The first "
            "token is prepared while paused; stylesheet loading is excluded."
        )
    else:
        benchmark = (
            "No current painted-throughput number is reported for this "
            "uncompressed comparison page. Use the packed 8-bit page for the "
            "measured demo."
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Streaming CSS-only TinyStories generation{suffix}</title>
  <link rel="stylesheet" href="../output-head-benchmark/generated/{head_name}?v={head_version}">
  <link rel="stylesheet" href="recurrent.css?v=ts-streaming-2">
  <link rel="stylesheet" href="nested-runtime.css?v=ts-streaming-2">
  <link rel="stylesheet" href="streaming.css?v=ts-streaming-2">
</head>
<body class="streaming-page">
  <h1>Streaming CSS-only TinyStories generation{suffix}</h1>
  <p class="status">Each later transformer stage stays render-skipped until the previous token is ready. The gate has no pacing delay; its 1 ms transition only separates browser style passes. No JavaScript.</p>
  <input id="pause-generation" type="checkbox" checked>
  <div class="generation-controls">
    <label class="pause-control" for="pause-generation" aria-label="Pause or play generation"></label>
    <span class="control-status" aria-live="polite"></span>
    <label for="show-token-ids">Show token IDs</label>
  </div>
  <input id="show-token-ids" type="checkbox">
  <main class="story">Once upon a time{nested_models(GENERATIONS)}</main>
  <p class="status">{benchmark}</p>
  <p class="status">This build predeclares {GENERATIONS} output stages. Live throughput requires external browser timing because CSS cannot read its own wall clock.</p>
</body>
</html>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    css = runtime_css()
    (OUT / "nested-runtime.css").write_text(css)
    (OUT / "nested.html").write_text(page())
    stream_css = streaming_css()
    (OUT / "streaming.css").write_text(stream_css)
    (OUT / "streaming.html").write_text(streaming_page())
    (OUT / "streaming-packed8.html").write_text(streaming_page(True))
    (OUT / "streaming-packed8x6.html").write_text(
        streaming_page(True, wide_feedback=True)
    )
    (OUT / "streaming-packed8-score-token.html").write_text(
        streaming_page(True, score_token_packing=True)
    )
    (OUT / "streaming-packed8-row-int8.html").write_text(
        streaming_page(True, row_int8_scores=True)
    )
    (OUT / "streaming-packed8-row-int10.html").write_text(
        streaming_page(True, row_int10_scores=True)
    )
    print(
        {
            "generations": GENERATIONS,
            "state_values_per_handoff": len(state_pairs()),
            "css_bytes": len(css.encode()),
            "streaming_css_bytes": len(stream_css.encode()),
            "stream_delay_milliseconds": 0,
            "stream_gate_milliseconds": STREAM_GATE_MILLISECONDS,
            "visible_benchmark_tokens": VISIBLE_BENCHMARK_TOKENS,
            "visible_benchmark_milliseconds": VISIBLE_BENCHMARK_MILLISECONDS,
            "visible_tokens_per_second": round(
                VISIBLE_BENCHMARK_TOKENS
                * 1000
                / (
                    sum(VISIBLE_BENCHMARK_MILLISECONDS)
                    / len(VISIBLE_BENCHMARK_MILLISECONDS)
                ),
                3,
            ),
            "javascript": False,
        }
    )


if __name__ == "__main__":
    main()
