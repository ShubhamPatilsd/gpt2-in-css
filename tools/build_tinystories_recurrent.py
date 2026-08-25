#!/usr/bin/env python3
"""Build a CSS-only recurrent TinyStories generator with a real KV cache."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import build_output_head_benchmark as HEAD
from build_tinystories_step import (
    EPSILON,
    HEADS,
    HEAD_WIDTH,
    LAYERS,
    WIDTH,
    CssCompiler,
    incremental_trace,
    number,
    tokenizer,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tinystories"
WINDOW = 8
CACHE_CAPACITY = WINDOW - 1
GENERATIONS = 4
CLOCK_MILLISECONDS = 8000


def greedy_reference(
    prompt: list[int], state: dict[str, np.ndarray], steps: int
) -> list[int]:
    embeddings = state["transformer.wte.weight"]
    context = prompt.copy()
    generated = []
    for _ in range(steps):
        hidden = HEAD.final_hidden(context[-WINDOW:], state)
        token = int((embeddings @ hidden).argmax())
        generated.append(token)
        context.append(token)
    return generated


def active_source(
    compiler: CssCompiler, source: int
) -> str:
    cases = ";".join(
        f"style(--ts-length:{length}):1"
        for length in range(source + 1, CACHE_CAPACITY + 1)
    )
    return compiler.raw(
        f"ts-source-active-{source}", f"if({cases};else:0)"
    )


def compile_recurrent_graph(
    state: dict[str, np.ndarray], initial: dict[str, object]
) -> tuple[str, dict[str, object]]:
    compiler = CssCompiler()
    positions = state["transformer.wpe.weight"]
    position_values = []
    for dimension in range(WIDTH):
        cases = ";".join(
            f"style(--ts-position:{position}):{number(positions[position, dimension])}"
            for position in range(WINDOW)
        )
        position_values.append(
            compiler.raw(f"ts-position-value-{dimension}", f"if({cases};else:0)")
        )
    x = [
        compiler.calc(
            f"ts-input-{dimension}",
            f"var(--__1embedding-{dimension}) + ({position_values[dimension]})",
        )
        for dimension in range(WIDTH)
    ]
    active = [active_source(compiler, source) for source in range(CACHE_CAPACITY)]
    current_keys: list[list[str]] = []
    current_values: list[list[str]] = []

    for layer in range(LAYERS):
        prefix = f"transformer.h.{layer}"
        node = f"ts-l{layer}"
        normalized = compiler.normalize(
            node + "-ln1",
            x,
            state[f"{prefix}.ln_1.weight"],
            state[f"{prefix}.ln_1.bias"],
        )
        qkv = [
            compiler.dot(
                f"{node}-qkv-{output}",
                normalized,
                state[f"{prefix}.attn.c_attn.weight"][:, output],
                state[f"{prefix}.attn.c_attn.bias"][output],
            )
            for output in range(WIDTH * 3)
        ]
        query = qkv[:WIDTH]
        layer_key = qkv[WIDTH : WIDTH * 2]
        layer_value = qkv[WIDTH * 2 :]
        current_keys.append(layer_key)
        current_values.append(layer_value)
        attended: list[str] = []
        for head in range(HEADS):
            head_query = query[head * HEAD_WIDTH : (head + 1) * HEAD_WIDTH]
            scores = []
            for source in range(CACHE_CAPACITY):
                source_key = [
                    compiler.input(f"ts-k-{layer}-{source}-{dimension}")
                    for dimension in range(
                        head * HEAD_WIDTH, (head + 1) * HEAD_WIDTH
                    )
                ]
                dot = " + ".join(
                    f"({left})*({right})"
                    for left, right in zip(head_query, source_key)
                )
                scores.append(
                    compiler.calc(
                        f"{node}-score-{head}-{source}",
                        f"({active[source]})*(({dot})/{math.sqrt(HEAD_WIDTH)})"
                        f" + (1 - ({active[source]}))*-999999",
                    )
                )
            current_dot = " + ".join(
                f"({left})*({right})"
                for left, right in zip(
                    head_query,
                    layer_key[
                        head * HEAD_WIDTH : (head + 1) * HEAD_WIDTH
                    ],
                )
            )
            scores.append(
                compiler.calc(
                    f"{node}-score-{head}-current",
                    f"({current_dot})/{math.sqrt(HEAD_WIDTH)}",
                )
            )
            maximum = compiler.maximum(f"{node}-score-max-{head}", scores)
            exponentials = [
                compiler.raw(
                    f"{node}-exp-{head}-{source}",
                    f"exp(({score}) - ({maximum}))",
                )
                for source, score in enumerate(scores)
            ]
            denominator = compiler.calc(
                f"{node}-denominator-{head}", " + ".join(exponentials)
            )
            probabilities = [
                compiler.calc(
                    f"{node}-probability-{head}-{source}",
                    f"({exponential})/({denominator})",
                )
                for source, exponential in enumerate(exponentials)
            ]
            for component in range(HEAD_WIDTH):
                dimension = head * HEAD_WIDTH + component
                terms = [
                    f"({probabilities[source]})*"
                    f"({compiler.input(f'ts-v-{layer}-{source}-{dimension}')})"
                    for source in range(CACHE_CAPACITY)
                ]
                terms.append(f"({probabilities[-1]})*({layer_value[dimension]})")
                attended.append(
                    compiler.calc(
                        f"{node}-attended-{dimension}", " + ".join(terms)
                    )
                )
        projection = [
            compiler.dot(
                f"{node}-attention-projection-{output}",
                attended,
                state[f"{prefix}.attn.c_proj.weight"][:, output],
                state[f"{prefix}.attn.c_proj.bias"][output],
            )
            for output in range(WIDTH)
        ]
        residual = [
            compiler.calc(
                f"{node}-residual1-{dimension}",
                f"({x[dimension]}) + ({projection[dimension]})",
            )
            for dimension in range(WIDTH)
        ]
        normalized_2 = compiler.normalize(
            node + "-ln2",
            residual,
            state[f"{prefix}.ln_2.weight"],
            state[f"{prefix}.ln_2.bias"],
        )
        feed_forward = [
            compiler.dot(
                f"{node}-fc-{unit}",
                normalized_2,
                state[f"{prefix}.mlp.c_fc.weight"][:, unit],
                state[f"{prefix}.mlp.c_fc.bias"][unit],
            )
            for unit in range(WIDTH * 4)
        ]
        activated = [
            compiler.raw(f"{node}-gelu-{unit}", f"--gelu({value})")
            for unit, value in enumerate(feed_forward)
        ]
        mlp_projection = [
            compiler.dot(
                f"{node}-mlp-projection-{output}",
                activated,
                state[f"{prefix}.mlp.c_proj.weight"][:, output],
                state[f"{prefix}.mlp.c_proj.bias"][output],
            )
            for output in range(WIDTH)
        ]
        x = [
            compiler.calc(
                f"{node}-residual2-{dimension}",
                f"({residual[dimension]}) + ({mlp_projection[dimension]})",
            )
            for dimension in range(WIDTH)
        ]

    final = compiler.normalize(
        "ts-final-ln",
        x,
        state["transformer.ln_f.weight"],
        state["transformer.ln_f.bias"],
    )
    for dimension, value in enumerate(final):
        compiler.raw(f"h{dimension}", value)

    next_length = compiler.raw(
        "ts-next-length",
        f"min({CACHE_CAPACITY},calc(var(--ts-length) + 1))",
    )
    next_position = compiler.raw(
        "ts-next-position",
        f"min({WINDOW - 1},calc(var(--ts-position) + 1))",
    )
    next_step = compiler.raw(
        "ts-next-step",
        f"min({GENERATIONS},calc(var(--ts-step) + 1))",
    )
    next_cache: dict[tuple[str, int, int, int], str] = {}
    for kind, current_vectors in (("k", current_keys), ("v", current_values)):
        for layer in range(LAYERS):
            for slot in range(CACHE_CAPACITY):
                for dimension in range(WIDTH):
                    current = f"var(--__1{kind}-{layer}-{slot}-{dimension})"
                    if slot + 1 < CACHE_CAPACITY:
                        shifted = f"var(--__1{kind}-{layer}-{slot + 1}-{dimension})"
                        expression = (
                            f"if(style(--ts-length:{slot}):"
                            f"{current_vectors[layer][dimension]};"
                            f"style(--ts-length:{CACHE_CAPACITY}):{shifted};"
                            f"else:{current})"
                        )
                    else:
                        expression = (
                            f"if(style(--ts-length:{CACHE_CAPACITY - 1}):"
                            f"{current_vectors[layer][dimension]};"
                            f"style(--ts-length:{CACHE_CAPACITY}):"
                            f"{current_vectors[layer][dimension]};else:{current})"
                        )
                    next_cache[(kind, layer, slot, dimension)] = compiler.raw(
                        f"ts-next-{kind}-{layer}-{slot}-{dimension}", expression
                    )

    next_outputs = []
    for output in range(GENERATIONS):
        next_outputs.append(
            compiler.raw(
                f"ts-next-output-{output}",
                f"if(style(--ts-step:{output}):var(--winner-id);"
                f"else:var(--__1output-{output}))",
            )
        )

    initial_keys = initial["keys"]
    initial_values = initial["values"]
    initial_token = initial["tokens"][-1]
    embedding = state["transformer.wte.weight"][initial_token]
    initial_length = len(initial["tokens"]) - 1
    bank_lines = [
        f"--__1length:var(--__2length,{initial_length});",
        f"--__1position:var(--__2position,{initial_length});",
        "--__1step:var(--__2step,0);",
    ]
    interface_lines = [
        "--ts-length:var(--__1length);",
        "--ts-position:var(--__1position);",
        "--ts-step:var(--__1step);",
        "--visible-step:var(--__1step);",
    ]
    execute_lines = [
        f"--__0length:if(style(--generation:0):{initial_length};else:{next_length});",
        f"--__0position:if(style(--generation:0):{initial_length};else:{next_position});",
        f"--__0step:if(style(--generation:0):0;else:{next_step});",
    ]
    store_lines = [
        f"--__2length:var(--__0length,{initial_length});",
        f"--__2position:var(--__0position,{initial_length});",
        "--__2step:var(--__0step,0);",
    ]
    for dimension in range(WIDTH):
        fallback = number(embedding[dimension])
        bank_lines.append(
            f"--__1embedding-{dimension}:"
            f"var(--__2embedding-{dimension},{fallback});"
        )
        execute_lines.append(
            f"--__0embedding-{dimension}:if(style(--generation:0):{fallback};"
            f"else:var(--next{dimension}));"
        )
        store_lines.append(
            f"--__2embedding-{dimension}:"
            f"var(--__0embedding-{dimension},{fallback});"
        )
    for output in range(GENERATIONS):
        bank_lines.append(f"--__1output-{output}:var(--__2output-{output},-1);")
        interface_lines.append(
            f"--visible-output-{output}:var(--__1output-{output});"
        )
        execute_lines.append(
            f"--__0output-{output}:if(style(--generation:0):-1;"
            f"else:{next_outputs[output]});"
        )
        store_lines.append(
            f"--__2output-{output}:var(--__0output-{output},-1);"
        )
    initial_cache = {"k": initial_keys, "v": initial_values}
    for kind in ("k", "v"):
        for layer in range(LAYERS):
            for slot in range(CACHE_CAPACITY):
                for dimension in range(WIDTH):
                    if slot < initial_length:
                        value = initial_cache[kind][layer][slot].reshape(-1)[dimension]
                        fallback = number(value)
                    else:
                        fallback = "0"
                    state_name = f"{kind}-{layer}-{slot}-{dimension}"
                    bank_lines.append(
                        f"--__1{state_name}:var(--__2{state_name},{fallback});"
                    )
                    interface_lines.append(
                        f"--ts-{state_name}:var(--__1{state_name});"
                    )
                    execute_lines.append(
                        f"--__0{state_name}:if(style(--generation:0):{fallback};"
                        f"else:{next_cache[(kind, layer, slot, dimension)]});"
                    )
                    store_lines.append(
                        f"--__2{state_name}:var(--__0{state_name},{fallback});"
                    )

    registrations = [
        "/* CSS-only KV-cached TinyStories recurrent transformer. */",
        HEAD.BUILDER.CSS_FUNCTIONS,
        '@property --clock{syntax:"<integer>";inherits:true;initial-value:0}',
        '@property --generation{syntax:"<integer>";inherits:true;initial-value:0}',
        '@property --ts-length{syntax:"<integer>";inherits:false;initial-value:0}',
        '@property --ts-position{syntax:"<integer>";inherits:false;initial-value:0}',
        '@property --ts-step{syntax:"<integer>";inherits:false;initial-value:0}',
        '@property --visible-step{syntax:"<integer>";inherits:false;initial-value:0}',
    ]
    registrations.extend(
        f'@property --visible-output-{output}'
        '{syntax:"<integer>";inherits:false;initial-value:-1}'
        for output in range(GENERATIONS)
    )
    skip_names = {"ts-length", "ts-position", "ts-step"}
    registrations.extend(
        f'@property --{name}{{syntax:"<number>";inherits:'
        f'{str(name in compiler.inherited_names).lower()};initial-value:0}}'
        for name in dict.fromkeys(compiler.names)
        if name not in skip_names
    )
    circuit = []
    declarations = interface_lines + compiler.declarations
    for start in range(0, len(declarations), 1000):
        circuit.append(".model{" + "".join(declarations[start : start + 1000]) + "}")
    bank_rules = [
        ".model{" + "".join(bank_lines[start : start + 1000]) + "}"
        for start in range(0, len(bank_lines), 1000)
    ]
    animation_chunk = 800
    store_chunks = [
        store_lines[start : start + animation_chunk]
        for start in range(0, len(store_lines), animation_chunk)
    ]
    execute_chunks = [
        execute_lines[start : start + animation_chunk]
        for start in range(0, len(execute_lines), animation_chunk)
    ]
    store_names = [f"ts-store-{index}" for index in range(len(store_chunks))]
    execute_names = [
        f"ts-execute-{index}" for index in range(len(execute_chunks))
    ]
    animation_names = store_names + execute_names
    animation_values = ",".join(
        f"{name} {CLOCK_MILLISECONDS}ms infinite" for name in animation_names
    )
    paused_store = ["paused"] * len(store_names)
    paused_execute = ["paused"] * len(execute_names)
    running_store = ["running"] * len(store_names)
    running_execute = ["running"] * len(execute_names)
    runtime = [
        *bank_rules,
        ".clock{--clock:0;--generation:0}",
        "#stream-toggle:checked~.clock{"
        f"animation:ts-clock {CLOCK_MILLISECONDS}ms steps(4,jump-end) infinite,"
        f"ts-generation {(GENERATIONS + 1) * CLOCK_MILLISECONDS}ms linear 1 both}}",
        f".model{{animation:{animation_values};animation-play-state:"
        + ",".join(paused_store + paused_execute)
        + "}",
        "@container style(--clock:1){.model{animation-play-state:"
        + ",".join(running_store + paused_execute)
        + "}}",
        "@container style(--clock:3){.model{animation-play-state:"
        + ",".join(paused_store + running_execute)
        + "}}",
        "@keyframes ts-clock{0%{--clock:0}25%{--clock:1}"
        "50%{--clock:2}75%{--clock:3}}",
    ]
    generation_frames = []
    for generation in range(GENERATIONS + 1):
        start = generation * 100 / (GENERATIONS + 1)
        end = (generation + 1) * 100 / (GENERATIONS + 1) - 0.001
        generation_frames.append(
            f"{start:.3f}%,{end:.3f}%{{--generation:{generation}}}"
        )
    generation_frames.append(f"100%{{--generation:{GENERATIONS}}}")
    runtime.append("@keyframes ts-generation{" + "".join(generation_frames) + "}")
    runtime.extend(
        f"@keyframes {name}{{0%,100%{{{''.join(lines)}}}}}"
        for name, lines in zip(store_names, store_chunks)
    )
    runtime.extend(
        f"@keyframes {name}{{0%,100%{{{''.join(lines)}}}}}"
        for name, lines in zip(execute_names, execute_chunks)
    )
    css = "\n".join(registrations + circuit + runtime) + "\n"
    metadata = {
        "window": WINDOW,
        "cache_capacity": CACHE_CAPACITY,
        "generations": GENERATIONS,
        "clock_milliseconds": CLOCK_MILLISECONDS,
        "properties": len(dict.fromkeys(compiler.names)),
        "css_bytes": len(css.encode()),
        "prompt": initial["tokens"],
    }
    return css, metadata


def page(metadata: dict[str, object], expected: list[int]) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CSS-only KV-cached TinyStories generator</title>
  <link rel="stylesheet" href="../output-head-benchmark/generated/clustered-256-embedding-shared-runtime.css?v=ts-recurrent-3">
  <link rel="stylesheet" href="recurrent.css?v=ts-recurrent-9">
</head>
<body>
  <input type="checkbox" id="stream-toggle" checked>
  <label for="stream-toggle">run / pause</label>
  <div class="clock"><main class="model"></main></div>
  <pre id="results">running...</pre>
  <script>
    const model = document.querySelector('.model');
    const toggle = document.querySelector('#stream-toggle');
    const expected = {json.dumps(expected)};
    const started = performance.now();
    const transitions = [];
    let previousStep = -1;
    function observe() {{
      const styles = getComputedStyle(model);
      const step = Number.parseFloat(styles.getPropertyValue('--visible-step'));
      if (step !== previousStep) {{
        transitions.push({{step, milliseconds: performance.now() - started}});
        previousStep = step;
      }}
      if (step >= {GENERATIONS}) {{
        toggle.checked = false;
        const outputs = Array.from(
          {{length: {GENERATIONS}}},
          (_, index) => Number.parseFloat(
            styles.getPropertyValue(`--visible-output-${{index}}`)
          ),
        );
        const result = {{
          expected,
          outputs,
          wrongTokens: outputs.filter((token, index) => token !== expected[index]).length,
          transitions,
          totalMilliseconds: performance.now() - started,
          sourceBytes: {metadata['css_bytes']},
          properties: {metadata['properties']},
        }};
        document.querySelector('#results').textContent = JSON.stringify(result, null, 2);
        document.documentElement.dataset.benchmarkComplete = 'true';
        return;
      }}
      requestAnimationFrame(observe);
    }}
    requestAnimationFrame(observe);
  </script>
</body>
</html>
"""


def state_benchmark_page(
    metadata: dict[str, object], initial: dict[str, object], expected: list[int]
) -> str:
    slot = len(initial["tokens"]) - 1
    expected_keys = [
        initial["full_keys"][layer][-1].reshape(-1).tolist()
        for layer in range(LAYERS)
    ]
    expected_values = [
        initial["full_values"][layer][-1].reshape(-1).tolist()
        for layer in range(LAYERS)
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>TinyStories recurrent state benchmark</title>
  <link rel="stylesheet" href="../output-head-benchmark/generated/clustered-256-embedding-shared-runtime.css?v=ts-state-3">
  <link rel="stylesheet" href="recurrent.css?v=ts-state-3">
  <style>.model{{animation:none!important}}</style>
</head>
<body>
  <input type="checkbox" id="stream-toggle">
  <div class="clock"><main class="model"></main></div>
  <pre id="results">running...</pre>
  <script>
    const model = document.querySelector('.model');
    const expectedKeys = {json.dumps(expected_keys)};
    const expectedValues = {json.dumps(expected_values)};
    requestAnimationFrame(() => requestAnimationFrame(() => {{
      const started = performance.now();
      const styles = getComputedStyle(model);
      const winner = Number.parseFloat(styles.getPropertyValue('--winner-id'));
      let cacheError = 0;
      let checksum = 0;
      for (const kind of ['k', 'v']) {{
        for (let layer = 0; layer < {LAYERS}; layer += 1) {{
          for (let cacheSlot = 0; cacheSlot < {CACHE_CAPACITY}; cacheSlot += 1) {{
            for (let dimension = 0; dimension < {WIDTH}; dimension += 1) {{
              const value = Number.parseFloat(
                styles.getPropertyValue(`--ts-next-${{kind}}-${{layer}}-${{cacheSlot}}-${{dimension}}`)
              );
              checksum += value;
              if (cacheSlot === {slot}) {{
                const reference = kind === 'k'
                  ? expectedKeys[layer][dimension]
                  : expectedValues[layer][dimension];
                cacheError = Math.max(cacheError, Math.abs(value - reference));
              }}
            }}
          }}
        }}
      }}
      const embedding = Array.from(
        {{length: {WIDTH}}},
        (_, dimension) => Number.parseFloat(styles.getPropertyValue(`--next${{dimension}}`)),
      );
      const elapsed = performance.now() - started;
      const result = {{
        elapsed,
        winner,
        expectedWinner: {expected[0]},
        wrongWinner: winner !== {expected[0]},
        cacheError,
        checksum,
        embeddingFinite: embedding.every(Number.isFinite),
      }};
      document.querySelector('#results').textContent = JSON.stringify(result, null, 2);
      document.documentElement.dataset.benchmarkComplete = 'true';
    }}));
  </script>
</body>
</html>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    state = HEAD.load_torch_zip(HEAD.download_checkpoint())
    codec = tokenizer()
    prompt = codec.encode("Once upon a time")
    initial = incremental_trace(prompt, state)
    expected = greedy_reference(prompt, state, GENERATIONS)
    css, metadata = compile_recurrent_graph(state, initial)
    metadata["expected"] = expected
    metadata["completion"] = "".join(codec.decode_token(token) for token in expected)
    (OUT / "recurrent.css").write_text(css)
    (OUT / "recurrent.html").write_text(page(metadata, expected))
    (OUT / "recurrent-state-benchmark.html").write_text(
        state_benchmark_page(metadata, initial, expected)
    )
    (OUT / "recurrent.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
