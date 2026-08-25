#!/usr/bin/env python3
"""Compile one KV-cached TinyStories transformer token to CSS."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import build_output_head_benchmark as HEAD


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tinystories"
WIDTH = 64
HEADS = 16
HEAD_WIDTH = WIDTH // HEADS
LAYERS = 8
CONTEXT = 4
EPSILON = 1e-5


def number(value: float) -> str:
    return HEAD.css_number(float(value))


def tokenizer() -> object:
    return HEAD.BUILDER.Gpt2Tokenizer(
        ROOT / "data" / "tiny-gpt2" / "vocab.json",
        ROOT / "data" / "tiny-gpt2" / "merges.txt",
    )


def fixed_contexts(state: dict[str, np.ndarray]) -> list[list[int]]:
    codec = tokenizer()
    embeddings = state["transformer.wte.weight"]
    contexts = []
    for prompt in HEAD.PROMPTS:
        tokens = codec.encode(prompt)
        while len(tokens) < CONTEXT:
            hidden = HEAD.final_hidden(tokens, state)
            tokens.append(int((embeddings @ hidden).argmax()))
        contexts.append(tokens[-CONTEXT:])
    return contexts


def incremental_trace(
    token_ids: list[int], state: dict[str, np.ndarray]
) -> dict[str, object]:
    """Run GPT-2 token by token and retain the cache before the final token."""
    keys: list[list[np.ndarray]] = [[] for _ in range(LAYERS)]
    values: list[list[np.ndarray]] = [[] for _ in range(LAYERS)]
    input_vector = None
    prior_keys = None
    prior_values = None
    final = None
    for position, token in enumerate(token_ids):
        x = (
            state["transformer.wte.weight"][token].astype(np.float64)
            + state["transformer.wpe.weight"][position].astype(np.float64)
        )
        if position == len(token_ids) - 1:
            input_vector = x.copy()
            prior_keys = [[item.copy() for item in layer] for layer in keys]
            prior_values = [[item.copy() for item in layer] for layer in values]
        for layer in range(LAYERS):
            prefix = f"transformer.h.{layer}"
            normalized = HEAD.layer_norm(
                x,
                state[f"{prefix}.ln_1.weight"],
                state[f"{prefix}.ln_1.bias"],
            )
            qkv = (
                normalized @ state[f"{prefix}.attn.c_attn.weight"]
                + state[f"{prefix}.attn.c_attn.bias"]
            )
            query, key, value = [
                part.reshape(HEADS, HEAD_WIDTH)
                for part in np.split(qkv, 3)
            ]
            keys[layer].append(key)
            values[layer].append(value)
            attended = np.empty((HEADS, HEAD_WIDTH), dtype=np.float64)
            key_array = np.stack(keys[layer])
            value_array = np.stack(values[layer])
            for head in range(HEADS):
                scores = (
                    key_array[:, head] @ query[head] / math.sqrt(HEAD_WIDTH)
                )
                probabilities = np.exp(scores - scores.max())
                probabilities /= probabilities.sum()
                attended[head] = probabilities @ value_array[:, head]
            x = (
                x
                + attended.reshape(WIDTH)
                @ state[f"{prefix}.attn.c_proj.weight"]
                + state[f"{prefix}.attn.c_proj.bias"]
            )
            normalized = HEAD.layer_norm(
                x,
                state[f"{prefix}.ln_2.weight"],
                state[f"{prefix}.ln_2.bias"],
            )
            hidden = HEAD.gelu_new(
                normalized @ state[f"{prefix}.mlp.c_fc.weight"]
                + state[f"{prefix}.mlp.c_fc.bias"]
            )
            x = (
                x
                + hidden @ state[f"{prefix}.mlp.c_proj.weight"]
                + state[f"{prefix}.mlp.c_proj.bias"]
            )
        final = HEAD.layer_norm(
            x,
            state["transformer.ln_f.weight"],
            state["transformer.ln_f.bias"],
        )
    assert input_vector is not None
    assert prior_keys is not None
    assert prior_values is not None
    assert final is not None
    dense_reference = HEAD.final_hidden(token_ids, state)
    if not np.allclose(final, dense_reference, atol=2e-5):
        raise RuntimeError(
            f"incremental reference differs by {np.max(np.abs(final - dense_reference))}"
        )
    return {
        "tokens": token_ids,
        "input": input_vector,
        "keys": prior_keys,
        "values": prior_values,
        "full_keys": [[item.copy() for item in layer] for layer in keys],
        "full_values": [[item.copy() for item in layer] for layer in values],
        "final": final,
    }


class CssCompiler:
    def __init__(self) -> None:
        self.names: list[str] = []
        self.inherited_names: set[str] = set()
        self.declarations: list[str] = []

    @staticmethod
    def ref(name: str) -> str:
        return f"var(--{name})"

    def input(self, name: str) -> str:
        self.names.append(name)
        self.inherited_names.add(name)
        return self.ref(name)

    def raw(self, name: str, expression: str) -> str:
        self.names.append(name)
        self.declarations.append(f"--{name}:{expression};")
        return self.ref(name)

    def calc(self, name: str, expression: str) -> str:
        return self.raw(name, f"calc({expression})")

    def dot(
        self,
        name: str,
        vector: list[str],
        weights: np.ndarray,
        bias: float = 0,
    ) -> str:
        terms = [number(bias)]
        terms.extend(
            f"({value})*{number(weight)}"
            for value, weight in zip(vector, weights)
        )
        return self.calc(name, " + ".join(terms))

    def maximum(self, name: str, values: list[str]) -> str:
        if len(values) == 1:
            return values[0]
        return self.raw(name, f"max({','.join(values)})")

    def normalize(
        self,
        prefix: str,
        vector: list[str],
        gamma: np.ndarray,
        beta: np.ndarray,
    ) -> list[str]:
        mean = self.calc(
            prefix + "-mean", f"({' + '.join(vector)})/{len(vector)}"
        )
        centered = [
            self.calc(f"{prefix}-center-{index}", f"({value}) - ({mean})")
            for index, value in enumerate(vector)
        ]
        variance = self.calc(
            prefix + "-variance",
            f"({' + '.join(f'({value})*({value})' for value in centered)})/{len(vector)}",
        )
        inverse = self.calc(
            prefix + "-inverse", f"1/sqrt(({variance}) + {EPSILON})"
        )
        return [
            self.calc(
                f"{prefix}-out-{index}",
                f"({value})*({inverse})*{number(gamma[index])} + {number(beta[index])}",
            )
            for index, value in enumerate(centered)
        ]


def compile_core(
    state: dict[str, np.ndarray], traces: list[dict[str, object]]
) -> tuple[str, dict[str, object]]:
    compiler = CssCompiler()
    x = [compiler.input(f"ts-in-{dimension}") for dimension in range(WIDTH)]
    previous = CONTEXT - 1
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
        current_key = qkv[WIDTH : WIDTH * 2]
        current_value = qkv[WIDTH * 2 :]
        attended: list[str] = []
        for head in range(HEADS):
            head_query = query[head * HEAD_WIDTH : (head + 1) * HEAD_WIDTH]
            scores = []
            for source in range(CONTEXT):
                if source < previous:
                    source_key = [
                        compiler.input(f"ts-k-{layer}-{source}-{dimension}")
                        for dimension in range(
                            head * HEAD_WIDTH, (head + 1) * HEAD_WIDTH
                        )
                    ]
                else:
                    source_key = current_key[
                        head * HEAD_WIDTH : (head + 1) * HEAD_WIDTH
                    ]
                scores.append(
                    compiler.calc(
                        f"{node}-score-{head}-{source}",
                        "(" + " + ".join(
                            f"({left})*({right})"
                            for left, right in zip(head_query, source_key)
                        ) + f")/{math.sqrt(HEAD_WIDTH)}",
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
                terms = []
                dimension = head * HEAD_WIDTH + component
                for source, probability in enumerate(probabilities):
                    if source < previous:
                        value = compiler.input(
                            f"ts-v-{layer}-{source}-{dimension}"
                        )
                    else:
                        value = current_value[dimension]
                    terms.append(f"({probability})*({value})")
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

    registrations = [
        "/* Generated KV-cached calum/tinystories-gpt2-3M transformer step. */",
        HEAD.BUILDER.CSS_FUNCTIONS,
    ]
    registrations.extend(
        f'@property --{name}{{syntax:"<number>";inherits:'
        f'{str(name in compiler.inherited_names).lower()};initial-value:0}}'
        for name in dict.fromkeys(compiler.names)
    )
    query_rules = []
    query_payloads = []
    for query, trace in enumerate(traces):
        declarations = []
        input_vector = np.asarray(trace["input"])
        for dimension, value in enumerate(input_vector):
            declarations.append(f"--ts-in-{dimension}:{number(value)}")
        keys = trace["keys"]
        values = trace["values"]
        for layer in range(LAYERS):
            for source in range(previous):
                for dimension in range(WIDTH):
                    declarations.append(
                        f"--ts-k-{layer}-{source}-{dimension}:"
                        f"{number(keys[layer][source].reshape(-1)[dimension])}"
                    )
                    declarations.append(
                        f"--ts-v-{layer}-{source}-{dimension}:"
                        f"{number(values[layer][source].reshape(-1)[dimension])}"
                    )
        query_rules.append(
            f"body:has(#q{query}:checked) .model{{{';'.join(declarations)}}}"
        )
        query_payloads.append(
            {
                "tokens": trace["tokens"],
                "input0": float(input_vector[0]),
                "final": np.asarray(trace["final"]).tolist(),
            }
        )
    circuit = []
    for start in range(0, len(compiler.declarations), 1000):
        circuit.append(
            ".model{" + "".join(compiler.declarations[start : start + 1000]) + "}"
        )
    css = "\n".join(registrations + query_rules + circuit) + "\n"
    metadata = {
        "width": WIDTH,
        "layers": LAYERS,
        "heads": HEADS,
        "context": CONTEXT,
        "properties": len(dict.fromkeys(compiler.names)),
        "css_bytes": len(css.encode()),
        "queries": query_payloads,
    }
    return css, metadata


def benchmark_page(
    metadata: dict[str, object],
    full_head: bool,
    head_stylesheet: str = "clustered-256-embedding-runtime.css",
) -> str:
    query_count = len(metadata["queries"])
    controls = "".join(
        f'<input type="radio" name="query" id="q{query}"'
        f'{" checked" if query == 0 else ""}>'
        for query in range(query_count)
    )
    head_link = (
        '<link rel="stylesheet" href="../output-head-benchmark/generated/'
        f'{head_stylesheet}?v=tinystories-step-4">'
        if full_head
        else ""
    )
    expected_winners = []
    expected_maximums = []
    expected_embeddings = []
    if full_head:
        state = HEAD.load_torch_zip(HEAD.download_checkpoint())
        embeddings = state["transformer.wte.weight"]
        for query in metadata["queries"]:
            final = np.asarray(query["final"])
            scores = embeddings @ final
            winner = int(scores.argmax())
            expected_winners.append(winner)
            expected_maximums.append(float(scores[winner]))
            expected_embeddings.append(embeddings[winner].tolist())
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>TinyStories KV-cached transformer step</title>
  <link rel="stylesheet" href="step.css?v=tinystories-step-2">{f'{chr(10)}  {head_link}' if head_link else ''}
</head>
<body>
  {controls}
  <main class="model"></main>
  <pre id="results">running...</pre>
  <script>
    const model = document.querySelector('.model');
    const inputs = [...document.querySelectorAll('input[name="query"]')];
    const queries = {json.dumps(metadata['queries'])};
    const fullHead = {str(full_head).lower()};
    const expectedWinners = {json.dumps(expected_winners)};
    const expectedMaximums = {json.dumps(expected_maximums)};
    const expectedEmbeddings = {json.dumps(expected_embeddings)};
    function infer(query, perturbation = null) {{
      const started = performance.now();
      inputs[query].checked = true;
      if (perturbation === null) model.style.removeProperty('--ts-in-0');
      else model.style.setProperty('--ts-in-0', String(queries[0].input0 + perturbation));
      const styles = getComputedStyle(model);
      const hidden = Array.from(
        {{length: {WIDTH}}},
        (_, dimension) => Number.parseFloat(styles.getPropertyValue(`--h${{dimension}}`)),
      );
      const maximum = fullHead
        ? Number.parseFloat(styles.getPropertyValue('--maximum'))
        : 0;
      const winner = fullHead
        ? Number.parseFloat(styles.getPropertyValue('--winner-id'))
        : 0;
      const embedding = fullHead
        ? Array.from(
            {{length: {WIDTH}}},
            (_, dimension) => Number.parseFloat(styles.getPropertyValue(`--next${{dimension}}`)),
          )
        : [];
      return {{
        elapsed: performance.now() - started,
        hidden,
        maximum,
        winner,
        embedding,
      }};
    }}
    requestAnimationFrame(() => requestAnimationFrame(() => {{
      let hiddenError = 0;
      let maximumError = 0;
      let embeddingError = 0;
      let wrongWinners = 0;
      for (let query = 0; query < queries.length; query += 1) {{
        const result = infer(query);
        for (let dimension = 0; dimension < result.hidden.length; dimension += 1) {{
          hiddenError = Math.max(
            hiddenError,
            Math.abs(result.hidden[dimension] - queries[query].final[dimension]),
          );
          if (fullHead) {{
            embeddingError = Math.max(
              embeddingError,
              Math.abs(result.embedding[dimension] - expectedEmbeddings[query][dimension]),
            );
          }}
        }}
        if (fullHead) {{
          maximumError = Math.max(
            maximumError,
            Math.abs(result.maximum - expectedMaximums[query]),
          );
          if (result.winner !== expectedWinners[query]) wrongWinners += 1;
        }}
      }}
      infer(0, 0.00001);
      infer(0, 0.00002);
      const samples = [];
      for (let iteration = 0; iteration < 5; iteration += 1) {{
        samples.push(infer(0, (iteration + 10) * 0.00001).elapsed);
      }}
      samples.sort((a, b) => a - b);
      const result = {{
        fullHead,
        sourceBytes: {metadata['css_bytes']},
        properties: {metadata['properties']},
        samples,
        medianMilliseconds: samples[2],
        hiddenError,
        maximumError,
        embeddingError,
        wrongWinners,
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
    contexts = fixed_contexts(state)
    traces = [incremental_trace(tokens, state) for tokens in contexts]
    css, metadata = compile_core(state, traces)
    (OUT / "step.css").write_text(css)
    (OUT / "step.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (OUT / "step.html").write_text(benchmark_page(metadata, False))
    (OUT / "step-with-head.html").write_text(benchmark_page(metadata, True))
    (OUT / "step-with-shared-head.html").write_text(
        benchmark_page(
            metadata,
            True,
            "clustered-256-embedding-shared-runtime.css",
        )
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
