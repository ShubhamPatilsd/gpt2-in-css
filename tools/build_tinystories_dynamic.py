#!/usr/bin/env python3
"""Build a no-script editable-prompt TinyStories generation page."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

import build_output_head_benchmark as HEAD
from build_tinystories_nested import decoder_css, runtime_css, state_pairs, streaming_css
from build_tinystories_recurrent import (
    CACHE_CAPACITY,
    LAYERS,
    WIDTH,
    compile_recurrent_graph,
)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tinystories"
HEAD_PATH = (
    ROOT
    / "output-head-benchmark"
    / "generated"
    / "clustered-256-embedding-packed8-row-int10-shared-runtime.css"
)
TOKEN_FONTS = tuple(OUT / f"gpt2-token-id-{part}-full.ttf" for part in range(2))
MAX_PROMPT_TOKENS = 4
GENERATED_TOKENS = 32
TOTAL_STAGES = MAX_PROMPT_TOKENS + GENERATED_TOKENS - 1
TOKEN_BUCKET_SIZE = 256
TOKEN_ID_BASE = 32_767
END_OF_TEXT_TOKEN_ID = 50_256
DETAILED_TRACE_MILLISECONDS = 1


def cluster_labels_from_head(path: Path) -> list[int]:
    """Recover the exact token-to-cluster mapping used by the built head."""
    source = path.read_text()
    labels = [-1] * 50_257
    blocks = re.finditer(
        r"@function --pe(\d+)x0\(\) returns <number>\{\n"
        r"result:if\((.*?)\);\n\}",
        source,
        re.DOTALL,
    )
    for block in blocks:
        cluster = int(block.group(1))
        for token in map(int, re.findall(r"style\(--winner-id:(\d+)\)", block.group(2))):
            if labels[token] != -1:
                raise ValueError(f"token {token} appears in multiple feedback clusters")
            labels[token] = cluster
    missing = [token for token, cluster in enumerate(labels) if cluster < 0]
    if missing:
        raise ValueError(f"feedback head omitted {len(missing)} tokens")
    return labels


def cluster_lookup_css(labels: list[int]) -> str:
    functions = []
    buckets = (len(labels) + TOKEN_BUCKET_SIZE - 1) // TOKEN_BUCKET_SIZE
    for bucket in range(buckets):
        start = bucket * TOKEN_BUCKET_SIZE
        end = min(len(labels), start + TOKEN_BUCKET_SIZE)
        cases = ";".join(
            f"style(--winner-id:{token}):{labels[token]}"
            for token in range(start, end)
        )
        functions.append(
            f"@function --prompt-cluster-{bucket}() returns <integer>"
            f"{{result:if({cases};else:0);}}"
        )
    outer = ";".join(
        f"style(--prompt-id-bucket:{bucket}):--prompt-cluster-{bucket}()"
        for bucket in range(buckets)
    )
    functions.extend(
        [
            '@property --prompt-id-bucket{syntax:"<integer>";inherits:false;initial-value:0}',
            '.prompt-embedding{'
            '--prompt-id-bucket:round(down,calc(var(--winner-id)/256),1);'
            f'--winner-cluster:if({outer};else:0);'
            '}',
        ]
    )
    return "\n".join(functions)


def tokenizer_css(labels: list[int], embeddings: np.ndarray) -> str:
    feedback_bits = 8
    feedback_base = 2**feedback_bits
    feedback_offset = 2 ** (feedback_bits - 1) - 1
    coordinates_per_pack = 3
    feedback_packs = (
        embeddings.shape[1] + coordinates_per_pack - 1
    ) // coordinates_per_pack
    feedback_scales = np.max(np.abs(embeddings), axis=0) / feedback_offset
    lines = [
        cluster_lookup_css(labels),
        '@font-face{font-family:gpt2-token-id-0;src:url("gpt2-token-id-0-full.ttf?v=2") format("truetype")}',
        '@font-face{font-family:gpt2-token-id-1;src:url("gpt2-token-id-1-full.ttf?v=2") format("truetype")}',
        '@property --prompt-count{syntax:"<integer>";inherits:true;initial-value:0}',
    ]
    lines.extend(
        f'@property --prompt-token-id-{slot}'
        '{syntax:"<integer>";inherits:true;initial-value:0}'
        for slot in range(MAX_PROMPT_TOKENS)
    )
    lines.extend(
        f'@property --prompt-token-low-{slot}'
        '{syntax:"<integer>";inherits:true;initial-value:0}'
        for slot in range(MAX_PROMPT_TOKENS)
    )
    lines.extend(
        f'@property --prompt-token-high-{slot}'
        '{syntax:"<integer>";inherits:true;initial-value:0}'
        for slot in range(MAX_PROMPT_TOKENS)
    )
    lines.extend(
        [
            '.token-metric{position:absolute;opacity:0;display:inline-block;'
            'width:max-content;height:1px;overflow:hidden;font-size:1px;line-height:1;'
            'white-space:pre}',
            '.token-metric::before{content:var(--prompt)}',
            '.token-probe{position:absolute;inset:0 auto auto 0;height:1px}',
            '.token-part-0{font-family:gpt2-token-id-0}',
            '.token-part-1{font-family:gpt2-token-id-1}',
            '.prompt-embedding{display:contents}',
        ]
    )
    for pack in range(feedback_packs):
        lines.append(
            f'@property --prompt-feedback-pack-{pack}'
            '{syntax:"<number>";inherits:false;initial-value:0}'
        )
        cases = ";".join(
            f"style(--winner-cluster:{cluster}):--pe{cluster}x{pack}()"
            for cluster in range(256)
        )
        lines.append(
            f'.prompt-embedding{{--prompt-feedback-pack-{pack}:'
            f'if({cases};else:0)}}'
        )
    feedback_expressions = []
    for dimension in range(WIDTH):
        pack = dimension // coordinates_per_pack
        offset = dimension % coordinates_per_pack
        divisor = feedback_base**offset
        code = (
            f"mod(round(down,calc(var(--prompt-feedback-pack-{pack})/"
            f"{divisor}),1),{feedback_base})"
        )
        scale = HEAD.BUILDER.css_number(float(feedback_scales[dimension]))
        feedback_expressions.append(
            f"calc(({code} - {feedback_offset})*{scale})"
        )
    for slot in range(MAX_PROMPT_TOKENS):
        lines.extend(
            [
                f'.token-position-{slot}{{font-feature-settings:"p{slot:03d}" 1}}',
                f'.token-position-{slot}.token-part-0'
                f'{{anchor-name:--prompt-token-anchor-{slot}-0}}',
                f'.token-position-{slot}.token-part-1'
                f'{{anchor-name:--prompt-token-anchor-{slot}-1}}',
                f'.token-probe-{slot}-0'
                f'{{position-anchor:--prompt-token-anchor-{slot}-0;'
                f'container:prompt-token-{slot}-0/inline-size;'
                f'width:anchor-size(--prompt-token-anchor-{slot}-0 width)}}',
                f'.token-probe-{slot}-1'
                f'{{position-anchor:--prompt-token-anchor-{slot}-1;'
                f'container:prompt-token-{slot}-1/inline-size;'
                f'width:anchor-size(--prompt-token-anchor-{slot}-1 width)}}',
                f'@container prompt-token-{slot}-0 (width > 0px){{'
                f'.token-part-bridge-{slot}{{--prompt-token-low-{slot}:'
                'round(nearest,calc(100cqi/1px*64 - 1),1)}}',
                f'@container prompt-token-{slot}-1 (width > 0px){{'
                f'.token-high-bridge-{slot}{{--prompt-token-high-{slot}:'
                'round(nearest,calc(100cqi/1px*64 - 1),1);'
                f'--prompt-count:{slot + 1}'
                '}}',
                f'.prompt-embedding.slot-{slot}{{--prompt-token-id-{slot}:'
                f'calc(var(--prompt-token-low-{slot}) + {TOKEN_ID_BASE}*'
                f'var(--prompt-token-high-{slot}))}}',
                f'.prompt-embedding.slot-{slot}'
                f'{{--winner-id:var(--prompt-token-id-{slot});'
                + "".join(
                    f'--prompt-token-{slot}-{dimension}:'
                    f'{feedback_expressions[dimension]};'
                    for dimension in range(WIDTH)
                )
                + '}',
            ]
        )
    return "\n".join(lines) + "\n"


def stage_css() -> str:
    lines = [
        '@property --draft-prompt{syntax:"<string>";inherits:true;initial-value:""}',
        '@property --inference-active{syntax:"<integer>";inherits:true;initial-value:0}',
        '@property --stage-ready{syntax:"<integer>";inherits:false;initial-value:0}',
        '@property --input-token-id{syntax:"<integer>";inherits:true;initial-value:0}',
        '@property --next-input-token-id{syntax:"<integer>";inherits:true;initial-value:0}',
        '@property --context-length{syntax:"<integer>";inherits:true;initial-value:0}',
        '@keyframes activate-inference{to{--inference-active:1}}',
        '.prompt-source:has(#run-generation:checked,#pause-generation:checked)'
        '{animation:activate-inference 1ms 150ms steps(1,end) both;'
        '--prompt:if(style(--inference-active:1):var(--draft-prompt);else:"")}',
        f'.streaming-page{{--inspection-delay:{DETAILED_TRACE_MILLISECONDS}ms}}',
        '.model{'
        '--stage-delay:if(style(--emit-token:1):var(--inspection-delay);else:1ms);'
        '--stage-ready:if(style(--inference-active:0):0;'
        'style(--emit-token:1):calc(1 + 0*var(--winner-id));'
        'else:calc(1 + 0*var(--h0)))}',
        '.dynamic-app{position:fixed;inset:0;z-index:1;overflow:auto;background:#fff;'
        'padding:1.75rem max(1rem,calc((100vw - 58rem)/2));font:15px/1.5 system-ui,sans-serif;color:#111}',
        '.dynamic-app h1{margin:.25rem 0 1rem;font:650 1.35rem/1.2 system-ui,sans-serif}',
        '.dynamic-app .editor-shell{position:relative;display:block;box-sizing:border-box;'
        'block-size:6rem;min-block-size:6rem;overflow:hidden;'
        'border:1px solid #aaa;border-radius:.35rem;background:#fff;cursor:text;transition:.12s}',
        '.dynamic-app .editor-shell:hover{border-color:#222;background:#fff}',
        '.dynamic-app .editor{display:block;box-sizing:border-box;min-inline-size:100%;'
        'min-block-size:100%;margin:0;padding:1rem;cursor:text;color:#111;'
        'background:transparent;white-space:pre;'
        'font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;caret-color:#111}',
        '.dynamic-app .editor:focus{outline:0}',
        '.dynamic-app .editor-shell:has(.editor:focus){outline:3px solid Highlight;outline-offset:2px}',
        '.dynamic-app .story{position:relative;margin:.75rem 0 2rem;padding:1.5rem 0 0;'
        'font:500 1.08rem/1.75 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap}',
        '.prompt-text::after{content:var(--draft-prompt)}',
        '.dynamic-app .limits{margin-block-start:1rem;color:#777;font-size:.75rem}',
        '.dynamic-app .generation-controls{margin:1rem 0;gap:.65rem;flex-wrap:wrap}',
        '.dynamic-app .generation-controls>label{min-inline-size:auto;padding:.35rem .65rem;'
        'border-color:#aaa;border-radius:.3rem;font-weight:600}',
        '.nested-model,.handoff,.token-output,.token-output::after{'
        'font:inherit!important;line-height:inherit!important;letter-spacing:inherit!important}',
        '.streaming-page .handoff{animation-duration:var(--stage-delay,1ms)!important}',
        '@container style(--stage-ready:1){'
        '.streaming-page .handoff{animation-name:ts-open-gate;animation-timing-function:steps(1,end);'
        'animation-fill-mode:both}'
        '}',
        '#pause-generation:checked~.story .model>.token-output{animation-play-state:paused}',
        '@media(max-width:640px){.dynamic-app .story{padding-top:1rem}}',
        f'.nested-model .token-output{{display:if('
        'style(--inference-active:0):none;'
        'style(--emit-token:0):none;'
        f'style(--winner-id:{END_OF_TEXT_TOKEN_ID}):none;else:inline)}}',
        '#edit-prompt,#run-generation{position:absolute;inline-size:1px;block-size:1px;opacity:0}',
        '#edit-prompt:checked~.story{display:none}',
        '#edit-prompt:checked~.story .handoff{animation:none!important;content-visibility:hidden}',
        '.generation-controls .edit-control::after{content:"Reset"}',
        '.generation-controls .run-control::after{content:"Generate"}',
        '#edit-prompt:checked~.generation-controls .edit-control,'
        '#edit-prompt:checked~.generation-controls .pause-control,'
        '#run-generation:checked~.generation-controls .run-control,'
        '#pause-generation:checked~.generation-controls .pause-control{display:none}',
        '#edit-prompt:focus-visible~.generation-controls .run-control,'
        '#run-generation:focus-visible~.generation-controls .run-control,'
        '#pause-generation:focus-visible~.generation-controls .pause-control'
        '{outline:3px solid Highlight;outline-offset:3px}',
    ]
    for source in range(CACHE_CAPACITY):
        lines.extend(
            [
                f'@property --context-token-{source}'
                '{syntax:"<integer>";inherits:true;initial-value:-1}',
                f'@property --next-context-token-{source}'
                '{syntax:"<integer>";inherits:true;initial-value:-1}',
            ]
        )
    lines.append(
        '.model{--context-length:var(--ts-length);'
        '--input-token-id:var(--next-input-token-id);'
        + ''.join(
            f'--context-token-{source}:var(--next-context-token-{source});'
            for source in range(CACHE_CAPACITY)
        )
        + '}'
    )
    lines.append(
        '.model.input-stage-0{--input-token-id:var(--prompt-token-id-0)}'
    )
    for stage in range(1, MAX_PROMPT_TOKENS):
        declarations = []
        for dimension in range(WIDTH):
            cases = ";".join(
                f"style(--prompt-count:{count}):var(--prompt-token-{stage}-{dimension})"
                for count in range(stage + 1, MAX_PROMPT_TOKENS + 1)
            )
            declarations.append(
                f"--__1embedding-{dimension}:if({cases};"
                f"else:var(--__2embedding-{dimension},0));"
            )
        lines.append(f'.model.input-stage-{stage}{{{"".join(declarations)}}}')
    for stage in range(TOTAL_STAGES):
        minimum_count = max(1, stage - GENERATED_TOKENS + 2)
        maximum_count = min(MAX_PROMPT_TOKENS, stage + 1)
        cases = ";".join(
            f"style(--prompt-count:{count}):1"
            for count in range(minimum_count, maximum_count + 1)
        )
        lines.append(
            f'.model.input-stage-{stage}'
            f'{{--emit-token:if({cases};else:0)}}'
        )
    for child_stage in range(1, TOTAL_STAGES):
        minimum_count = max(1, child_stage - GENERATED_TOKENS + 1)
        cases = ";".join(
            f"style(--prompt-count:{count}):1"
            for count in range(minimum_count, MAX_PROMPT_TOKENS + 1)
        )
        continue_expression = f"if({cases};else:0)"
        if child_stage >= MAX_PROMPT_TOKENS:
            continue_expression = (
                f"if(style(--winner-id:{END_OF_TEXT_TOKEN_ID}):0;"
                f"{cases};else:0)"
            )
        if child_stage < MAX_PROMPT_TOKENS:
            prompt_input_cases = ";".join(
                f"style(--prompt-count:{count}):var(--prompt-token-id-{child_stage})"
                for count in range(child_stage + 1, MAX_PROMPT_TOKENS + 1)
            )
            next_input = f"if({prompt_input_cases};else:var(--winner-id))"
        else:
            next_input = "var(--winner-id)"
        context_updates = []
        for source in range(CACHE_CAPACITY):
            full_value = (
                f"var(--context-token-{source + 1})"
                if source + 1 < CACHE_CAPACITY
                else "var(--input-token-id)"
            )
            context_updates.append(
                f"--next-context-token-{source}:if("
                f"style(--context-length:{source}):var(--input-token-id);"
                f"style(--context-length:{CACHE_CAPACITY}):{full_value};"
                f"else:var(--context-token-{source}));"
            )
        lines.append(
            f'.streaming-page .handoff.to-stage-{child_stage}'
            f'{{--continue-stream:{continue_expression};'
            f'--next-input-token-id:{next_input};'
            f'{"".join(context_updates)}'
            'display:if(style(--continue-stream:1):'
            'if(style(--gate-open:1):inline;else:inline-block);else:none)!important}'
        )
    return "\n".join(lines) + "\n"


def model_stages(stage: int = 0) -> str:
    child = model_stages(stage + 1) if stage + 1 < TOTAL_STAGES else ""
    handoff = (
        f'<span class="handoff to-stage-{stage + 1}">{child}</span>'
        if child
        else ""
    )
    return (
        f'<span class="model nested-model input-stage-{stage}" data-stage="{stage}">'
        f'<span class="token-output" aria-label="generated token"></span>'
        f'{handoff}</span>'
    )


def app_html() -> str:
    return f'''<main class="dynamic-app">
  <h1>GPT-2 in CSS</h1>
  <input id="edit-prompt" name="generation-mode" type="radio" checked>
  <input id="run-generation" name="generation-mode" type="radio">
  <input id="pause-generation" name="generation-mode" type="radio">
  <div class="editor-shell">
    <style class="editor" contenteditable="plaintext-only" spellcheck="false" role="textbox" aria-label="Editable prompt; the first four tokens are used">.prompt-source {{
  --draft-prompt: "Once upon a time"; /* edit this */
}}</style>
  </div>
  <div class="generation-controls">
    <label class="edit-control" for="edit-prompt" aria-label="Edit or reset generation"> </label>
    <label class="run-control" for="run-generation" aria-label="Generate or resume"> </label>
    <label class="pause-control" for="pause-generation" aria-label="Pause or play generation"></label>
  </div>
  <div class="story"><span class="prompt-text"></span>{model_stages()}</div>
  <p class="limits">No JavaScript.</p>
</main>'''


def tokenizer_chain(slot: int = 0) -> str:
    child = tokenizer_chain(slot + 1) if slot + 1 < MAX_PROMPT_TOKENS else app_html()
    return (
        f'<i class="token-metric token-position-{slot} token-part-0" aria-hidden="true"></i>'
        f'<div class="token-probe token-probe-{slot}-0">'
        f'<div class="token-part-bridge-{slot}">'
        f'<i class="token-metric token-position-{slot} token-part-1" aria-hidden="true"></i>'
        f'<div class="token-probe token-probe-{slot}-1">'
        f'<div class="token-high-bridge-{slot}">'
        f'<div class="prompt-embedding slot-{slot}">{child}</div>'
        f'</div></div></div></div>'
    )


def page() -> str:
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GPT-2 in CSS</title>
  <link rel="stylesheet" href="../output-head-benchmark/generated/clustered-256-embedding-packed8-row-int10-shared-runtime.css?v=ts-dynamic-2">
  <link rel="stylesheet" href="dynamic-recurrent.css?v=ts-dynamic-2">
  <link rel="stylesheet" href="nested-runtime.css?v=ts-dynamic-3">
  <link rel="stylesheet" href="streaming.css?v=ts-dynamic-2">
  <link rel="stylesheet" href="dynamic-prompt.css?v=ts-dynamic-32">
</head>
<body class="prompt-source streaming-page">
  {tokenizer_chain()}
</body>
</html>
'''


def main() -> None:
    if not HEAD_PATH.exists():
        raise SystemExit(f"build the row-int10 output head first: missing {HEAD_PATH}")
    missing_fonts = [path for path in TOKEN_FONTS if not path.exists()]
    if missing_fonts:
        raise SystemExit(f"build the token-ID fonts first: missing {missing_fonts}")
    OUT.mkdir(parents=True, exist_ok=True)
    labels = cluster_labels_from_head(HEAD_PATH)
    state = HEAD.load_torch_zip(HEAD.download_checkpoint())
    empty = {
        "tokens": [],
        "keys": [[] for _ in range(LAYERS)],
        "values": [[] for _ in range(LAYERS)],
    }
    recurrent, metadata = compile_recurrent_graph(
        state,
        empty,
        generations=TOTAL_STAGES,
        track_outputs=False,
    )
    (OUT / "dynamic-recurrent.css").write_text(recurrent)
    (OUT / "nested-runtime.css").write_text(runtime_css())
    (OUT / "streaming.css").write_text(streaming_css(include_winner_gate=False))
    (OUT / "dynamic-prompt.css").write_text(
        tokenizer_css(labels, state["transformer.wte.weight"].astype(np.float64))
        + stage_css()
    )
    (OUT / "dynamic.html").write_text(page())
    print(
        {
            "max_prompt_tokens": MAX_PROMPT_TOKENS,
            "generated_tokens": GENERATED_TOKENS,
            "total_transformer_stages": TOTAL_STAGES,
            "recurrent_css_bytes": len(recurrent.encode()),
            "prompt_css_bytes": (OUT / "dynamic-prompt.css").stat().st_size,
            "html_bytes": (OUT / "dynamic.html").stat().st_size,
            "properties": metadata["properties"],
            "javascript": False,
            "state_values_per_handoff": len(state_pairs()),
        }
    )


if __name__ == "__main__":
    main()
