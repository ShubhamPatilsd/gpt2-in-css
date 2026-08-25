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
STREAM_DELAY_SECONDS = 2


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
            ".token-output::after{content:var(--token-piece);}",
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


def streaming_css() -> str:
    return f"""@property --gate-open{{syntax:\"<integer>\";inherits:false;initial-value:0}}
@keyframes ts-open-gate{{to{{--gate-open:1}}}}
.streaming-page .handoff{{
  --gate-open:0;
  display:inline-block;
  content-visibility:if(style(--gate-open:1):visible;else:hidden);
  contain-intrinsic-size:auto 1lh;
}}
.streaming-page .story{{white-space:pre-wrap}}
@container style(--winner-id){{
  .streaming-page .handoff{{animation:ts-open-gate 1ms {STREAM_DELAY_SECONDS}s both}}
}}
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
    handoff = f'<div class="handoff">{child}</div>' if child else ""
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
  <p class="status">Expected reference: <code>Once upon a time, there was a</code></p>
</body>
</html>
"""


def streaming_page(packed_feedback: bool = False) -> str:
    head_name = (
        "clustered-256-embedding-packed8-shared-runtime.css"
        if packed_feedback
        else "clustered-256-embedding-shared-runtime.css"
    )
    suffix = " (packed 8-bit feedback)" if packed_feedback else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Streaming CSS-only TinyStories generation{suffix}</title>
  <link rel="stylesheet" href="../output-head-benchmark/generated/{head_name}?v=ts-streaming-1">
  <link rel="stylesheet" href="recurrent.css?v=ts-streaming-1">
  <link rel="stylesheet" href="nested-runtime.css?v=ts-streaming-1">
  <link rel="stylesheet" href="streaming.css?v=ts-streaming-1">
</head>
<body class="streaming-page">
  <h1>Streaming CSS-only TinyStories generation{suffix}</h1>
  <p class="status">Each later transformer stage stays render-skipped until the previous token is ready. No JavaScript.</p>
  <input id="pause-generation" type="checkbox">
  <div class="generation-controls">
    <label class="pause-control" for="pause-generation" aria-label="Pause or play generation"></label>
    <span class="control-status" aria-live="polite"></span>
    <label for="show-token-ids">Show token IDs</label>
  </div>
  <input id="show-token-ids" type="checkbox">
  <main class="story">Once upon a time{nested_models(GENERATIONS)}</main>
  <p class="status">Expected reference: <code>Once upon a time, there was a</code></p>
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
    print(
        {
            "generations": GENERATIONS,
            "state_values_per_handoff": len(state_pairs()),
            "css_bytes": len(css.encode()),
            "streaming_css_bytes": len(stream_css.encode()),
            "stream_delay_seconds": STREAM_DELAY_SECONDS,
            "javascript": False,
        }
    )


if __name__ == "__main__":
    main()
