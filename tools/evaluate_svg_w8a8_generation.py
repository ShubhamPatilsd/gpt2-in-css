#!/usr/bin/env python3
"""Evaluate full causal GPT-2 generation under SVG-like W8A8 transport.

This is a numerical screening model for the browser backend. It includes all 12
GPT-2-small blocks, multi-token causal attention, KV caches, 9-bit row plus
8-bit PNG weight quantization, and fixed 32-group activation ranges learned on
disjoint calibration prompts. Every major reusable activation is materialized
to eight bits. The generated report compares teacher-forced next-token agreement
and free-running greedy text.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_svg_quantization_strategies import gelu_new, log_uniform
from build_pretrained_gpt2 import Gpt2Tokenizer


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-w8a8-generation" / "results.json"
WIDTH = 768
HEADS = 12
HEAD_WIDTH = 64
GROUPS = 32
HEADROOM = 1.10
GENERATED_TOKENS = 8

CALIBRATION_PROMPTS = (
    "Once upon a time",
    "The dog ran through the",
    "In a small village",
    "The scientist discovered",
    "I think that",
    "The meaning of life",
    "Alice walked into",
    "The weather today",
)

EVALUATION_PROMPTS = (
    "Hello, my name is",
    "The quick brown fox",
    "Once upon a time there was",
    "In the future, computers",
    "The capital of France is",
    "She opened the door and",
)


@dataclass
class Block:
    ln1_gamma: np.ndarray
    ln1_beta: np.ndarray
    qkv_weight: np.ndarray
    qkv_bias: np.ndarray
    attention_projection_weight: np.ndarray
    attention_projection_bias: np.ndarray
    ln2_gamma: np.ndarray
    ln2_beta: np.ndarray
    fc_weight: np.ndarray
    fc_bias: np.ndarray
    mlp_projection_weight: np.ndarray
    mlp_projection_bias: np.ndarray


@dataclass(frozen=True)
class SurfacePlan:
    zero: np.ndarray
    step: np.ndarray


@dataclass
class Cache:
    keys: list[np.ndarray]
    values: list[np.ndarray]


def layer_norm(vector: np.ndarray, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
    mean = float(np.mean(vector))
    variance = float(np.mean((vector - mean) ** 2))
    return (vector - mean) / math.sqrt(variance + 1e-5) * gamma + beta


def softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values, axis=-1, keepdims=True)
    exponential = np.exp(shifted)
    return exponential / np.sum(exponential, axis=-1, keepdims=True)


def quantize_output_rows(weight: np.ndarray) -> np.ndarray:
    """Quantize a Conv1D matrix independently for each output coordinate."""
    rows = weight.T.astype(np.float64)
    row_maximum = np.maximum(np.max(np.abs(rows), axis=1), 1e-12)
    row_step = row_maximum / 255.0
    rows = np.rint(rows / row_step[:, None]).clip(-255, 255) * row_step[:, None]
    row_maximum = np.maximum(np.max(np.abs(rows), axis=1), 1e-12)
    normalized = rows / row_maximum[:, None]
    rows = (
        np.sign(normalized)
        * (np.rint(np.abs(normalized) * 255.0) / 255.0)
        * row_maximum[:, None]
    )
    return rows.T.astype(np.float32)


def quantize_embedding_rows(weight: np.ndarray) -> np.ndarray:
    rows = weight.astype(np.float64)
    maximum = np.maximum(np.max(np.abs(rows), axis=1), 1e-12)
    step = maximum / 255.0
    rows = np.rint(rows / step[:, None]).clip(-255, 255) * step[:, None]
    maximum = np.maximum(np.max(np.abs(rows), axis=1), 1e-12)
    normalized = rows / maximum[:, None]
    rows = (
        np.sign(normalized)
        * (np.rint(np.abs(normalized) * 255.0) / 255.0)
        * maximum[:, None]
    )
    return rows.astype(np.float32)


def load_model() -> tuple[np.ndarray, np.ndarray, list[Block], np.ndarray, np.ndarray]:
    tensors = SafeTensors(MODEL_PATH)
    embedding = np.asarray(tensors.tensor("wte.weight"), dtype=np.float32)
    position = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float32)
    blocks = []
    for index in range(12):
        prefix = f"h.{index}"
        blocks.append(
            Block(
                ln1_gamma=np.asarray(tensors.tensor(f"{prefix}.ln_1.weight"), dtype=np.float32),
                ln1_beta=np.asarray(tensors.tensor(f"{prefix}.ln_1.bias"), dtype=np.float32),
                qkv_weight=np.asarray(tensors.tensor(f"{prefix}.attn.c_attn.weight"), dtype=np.float32),
                qkv_bias=np.asarray(tensors.tensor(f"{prefix}.attn.c_attn.bias"), dtype=np.float32),
                attention_projection_weight=np.asarray(
                    tensors.tensor(f"{prefix}.attn.c_proj.weight"), dtype=np.float32
                ),
                attention_projection_bias=np.asarray(
                    tensors.tensor(f"{prefix}.attn.c_proj.bias"), dtype=np.float32
                ),
                ln2_gamma=np.asarray(tensors.tensor(f"{prefix}.ln_2.weight"), dtype=np.float32),
                ln2_beta=np.asarray(tensors.tensor(f"{prefix}.ln_2.bias"), dtype=np.float32),
                fc_weight=np.asarray(tensors.tensor(f"{prefix}.mlp.c_fc.weight"), dtype=np.float32),
                fc_bias=np.asarray(tensors.tensor(f"{prefix}.mlp.c_fc.bias"), dtype=np.float32),
                mlp_projection_weight=np.asarray(
                    tensors.tensor(f"{prefix}.mlp.c_proj.weight"), dtype=np.float32
                ),
                mlp_projection_bias=np.asarray(
                    tensors.tensor(f"{prefix}.mlp.c_proj.bias"), dtype=np.float32
                ),
            )
        )
    final_gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float32)
    final_beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float32)
    return embedding, position, blocks, final_gamma, final_beta


def quantized_blocks(blocks: list[Block]) -> list[Block]:
    result = []
    for block in blocks:
        result.append(
            Block(
                ln1_gamma=block.ln1_gamma,
                ln1_beta=block.ln1_beta,
                qkv_weight=quantize_output_rows(block.qkv_weight),
                qkv_bias=block.qkv_bias,
                attention_projection_weight=quantize_output_rows(
                    block.attention_projection_weight
                ),
                attention_projection_bias=block.attention_projection_bias,
                ln2_gamma=block.ln2_gamma,
                ln2_beta=block.ln2_beta,
                fc_weight=quantize_output_rows(block.fc_weight),
                fc_bias=block.fc_bias,
                mlp_projection_weight=quantize_output_rows(
                    block.mlp_projection_weight
                ),
                mlp_projection_bias=block.mlp_projection_bias,
            )
        )
    return result


def fit_surface(values: np.ndarray) -> SurfacePlan:
    values = np.asarray(values, dtype=np.float64)
    bounds = np.maximum(np.max(np.abs(values), axis=0) * HEADROOM, 1e-8)
    ids = log_uniform(bounds, GROUPS)
    scales = np.empty_like(bounds)
    for group in range(GROUPS):
        mask = ids == group
        if np.any(mask):
            scales[mask] = float(np.max(bounds[mask]))
    return SurfacePlan(
        zero=np.full(values.shape[1], 128.0, dtype=np.float64),
        step=2.0 * scales / 255.0,
    )


def apply_surface(values: np.ndarray, plan: SurfacePlan) -> tuple[np.ndarray, int]:
    raw = plan.zero + values / plan.step
    clipped = int(np.count_nonzero((raw < 0.0) | (raw > 255.0)))
    code = np.clip(np.rint(raw), 0.0, 255.0)
    return ((code - plan.zero) * plan.step).astype(np.float32), clipped


class Runner:
    def __init__(
        self,
        embedding: np.ndarray,
        position: np.ndarray,
        blocks: list[Block],
        final_gamma: np.ndarray,
        final_beta: np.ndarray,
        *,
        plans: dict[str, SurfacePlan] | None = None,
        trace: dict[str, list[np.ndarray]] | None = None,
        output_embedding: np.ndarray | None = None,
    ) -> None:
        self.embedding = embedding
        self.position = position
        self.blocks = blocks
        self.final_gamma = final_gamma
        self.final_beta = final_beta
        self.plans = plans
        self.trace = trace
        self.output_embedding = embedding if output_embedding is None else output_embedding
        self.clipped = 0
        self.cache = [Cache([], []) for _ in blocks]
        self.position_index = 0

    def materialize(self, name: str, value: np.ndarray) -> np.ndarray:
        value = np.asarray(value, dtype=np.float32)
        if self.trace is not None:
            self.trace[name].append(value.reshape(-1, value.shape[-1]).copy())
        if self.plans is None:
            return value
        result, clipped = apply_surface(value, self.plans[name])
        self.clipped += clipped
        return result

    def token(self, token_id: int, logits: bool = True) -> np.ndarray | None:
        state = self.materialize(
            "input",
            self.embedding[token_id] + self.position[self.position_index],
        )
        self.position_index += 1
        for index, block in enumerate(self.blocks):
            prefix = f"b{index}"
            normalized = self.materialize(
                f"{prefix}.ln1",
                layer_norm(state, block.ln1_gamma, block.ln1_beta),
            )
            qkv = self.materialize(
                f"{prefix}.qkv",
                normalized @ block.qkv_weight + block.qkv_bias,
            )
            query, key, value = np.split(qkv, 3)
            query = query.reshape(HEADS, HEAD_WIDTH)
            key = key.reshape(HEADS, HEAD_WIDTH)
            value = value.reshape(HEADS, HEAD_WIDTH)
            self.cache[index].keys.append(key)
            self.cache[index].values.append(value)
            keys = np.stack(self.cache[index].keys, axis=1)
            values = np.stack(self.cache[index].values, axis=1)
            scores = np.einsum("hd,htd->ht", query, keys) / math.sqrt(HEAD_WIDTH)
            if self.trace is not None:
                self.trace[f"{prefix}.scores"].append(scores.T.copy())
            if self.plans is not None:
                score_plan = self.plans[f"{prefix}.scores"]
                scores, clipped = apply_surface(scores.T, score_plan)
                scores = scores.T
                self.clipped += clipped
            probabilities = softmax(scores)
            if self.trace is not None:
                self.trace[f"{prefix}.probabilities"].append(probabilities.T.copy())
            if self.plans is not None:
                probabilities = np.rint(np.clip(probabilities, 0, 1) * 255) / 255
            context = self.materialize(
                f"{prefix}.context",
                np.einsum("ht,htd->hd", probabilities, values).reshape(WIDTH),
            )
            learned = self.materialize(
                f"{prefix}.attention",
                context @ block.attention_projection_weight
                + block.attention_projection_bias,
            )
            state = self.materialize(f"{prefix}.residual1", state + learned)
            normalized = self.materialize(
                f"{prefix}.ln2",
                layer_norm(state, block.ln2_gamma, block.ln2_beta),
            )
            pre = self.materialize(
                f"{prefix}.fc",
                normalized @ block.fc_weight + block.fc_bias,
            )
            hidden = self.materialize(f"{prefix}.gelu", gelu_new(pre))
            projected = self.materialize(
                f"{prefix}.projection",
                hidden @ block.mlp_projection_weight + block.mlp_projection_bias,
            )
            state = self.materialize(f"{prefix}.residual2", state + projected)
        final = self.materialize(
            "final", layer_norm(state, self.final_gamma, self.final_beta)
        )
        if not logits:
            return None
        return final @ self.output_embedding.T


def run_prompt(
    prompt_tokens: list[int],
    runner: Runner,
    generated: int,
) -> list[int]:
    logits = None
    for token in prompt_tokens:
        logits = runner.token(token)
    output = []
    for _ in range(generated):
        assert logits is not None
        token = int(np.argmax(logits))
        output.append(token)
        logits = runner.token(token)
    return output


def decode(tokenizer: Gpt2Tokenizer, tokens: list[int]) -> str:
    return "".join(tokenizer.decode_token(token) for token in tokens)


def fit_plans(trace: dict[str, list[np.ndarray]]) -> dict[str, SurfacePlan]:
    return {
        name: fit_surface(np.concatenate(parts, axis=0))
        for name, parts in trace.items()
        if not name.endswith(".probabilities")
    }


def main() -> None:
    tokenizer = Gpt2Tokenizer(ROOT / "data/gpt2/vocab.json", ROOT / "data/gpt2/merges.txt")
    embedding, position, blocks, final_gamma, final_beta = load_model()

    trace: dict[str, list[np.ndarray]] = defaultdict(list)
    calibration_outputs = []
    for prompt in CALIBRATION_PROMPTS:
        prompt_tokens = tokenizer.encode(prompt)
        runner = Runner(
            embedding, position, blocks, final_gamma, final_beta, trace=trace
        )
        generated = run_prompt(prompt_tokens, runner, GENERATED_TOKENS)
        calibration_outputs.append(
            {"prompt": prompt, "generatedTokenIds": generated}
        )
    plans = fit_plans(trace)

    q_blocks = quantized_blocks(blocks)
    q_embedding = quantize_embedding_rows(embedding)
    reports = []
    total_teacher_matches = 0
    total_teacher_steps = 0
    first_divergence_steps = []
    for prompt in EVALUATION_PROMPTS:
        prompt_tokens = tokenizer.encode(prompt)
        exact_runner = Runner(embedding, position, blocks, final_gamma, final_beta)
        exact_generated = run_prompt(prompt_tokens, exact_runner, GENERATED_TOKENS)

        # Teacher-force the exact continuation through the quantized model and
        # compare each next-token decision before free-running feedback diverges.
        teacher_runner = Runner(
            embedding,
            position,
            q_blocks,
            final_gamma,
            final_beta,
            plans=plans,
            output_embedding=q_embedding,
        )
        teacher_logits = None
        for token in prompt_tokens:
            teacher_logits = teacher_runner.token(token)
        teacher_predictions = []
        for token in exact_generated:
            assert teacher_logits is not None
            teacher_predictions.append(int(np.argmax(teacher_logits)))
            teacher_logits = teacher_runner.token(token)
        matches = [
            predicted == expected
            for predicted, expected in zip(teacher_predictions, exact_generated)
        ]
        total_teacher_matches += sum(matches)
        total_teacher_steps += len(matches)

        quantized_runner = Runner(
            embedding,
            position,
            q_blocks,
            final_gamma,
            final_beta,
            plans=plans,
            output_embedding=q_embedding,
        )
        quantized_generated = run_prompt(
            prompt_tokens, quantized_runner, GENERATED_TOKENS
        )
        divergence = next(
            (
                index
                for index, (exact, quantized) in enumerate(
                    zip(exact_generated, quantized_generated)
                )
                if exact != quantized
            ),
            GENERATED_TOKENS,
        )
        first_divergence_steps.append(divergence)
        reports.append(
            {
                "prompt": prompt,
                "promptTokenIds": prompt_tokens,
                "exactTokenIds": exact_generated,
                "quantizedTokenIds": quantized_generated,
                "teacherForcedPredictedTokenIds": teacher_predictions,
                "teacherForcedMatches": matches,
                "firstFreeRunDivergence": divergence,
                "exactText": prompt + decode(tokenizer, exact_generated),
                "quantizedText": prompt + decode(tokenizer, quantized_generated),
                "teacherClippedValues": teacher_runner.clipped,
                "freeRunClippedValues": quantized_runner.clipped,
            }
        )
        print(json.dumps(reports[-1], ensure_ascii=False))

    payload = {
        "model": str(MODEL_PATH),
        "activationBits": 8,
        "weightQuantization": "9-bit signed rows followed by 8-bit normalized PNG",
        "groups": GROUPS,
        "headroom": HEADROOM,
        "calibrationPrompts": list(CALIBRATION_PROMPTS),
        "evaluationPrompts": list(EVALUATION_PROMPTS),
        "generatedTokensPerPrompt": GENERATED_TOKENS,
        "teacherForcedMatches": total_teacher_matches,
        "teacherForcedSteps": total_teacher_steps,
        "teacherForcedMatchFraction": total_teacher_matches / total_teacher_steps,
        "meanFirstFreeRunDivergence": float(np.mean(first_divergence_steps)),
        "calibrationOutputs": calibration_outputs,
        "reports": reports,
        "scope": "full 12-block multi-token causal attention with KV caches; offline SVG numerical screen",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in payload.items() if key != "reports"}, indent=2))


if __name__ == "__main__":
    main()
