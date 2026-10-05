# T1 — Code walkthrough: MNIST MLP → toy CSS transformer

Date: 2026-10-05. Scope: `tools/build.py`, `index.html`, `model.css`, `styles.css` (MNIST, commit 8f189b3c) and `tools/build_transformer.py`, `transformer/{index.html,model.css,styles.css}` (commit 8a59db0f "Add CSS-only autoregressive transformer", then c328e4cd "Optimize generated CSS inference graphs"). This was a read-only analysis: the large generated CSS files were only sampled. Process log: `T1-code-walkthrough.log.md`.

Citations use `file:line`. `model.css` means the MNIST file at the repo root, and `t/model.css` means `transformer/model.css`.

---

## 0. TL;DR

- **MNIST**: a real, *trained* 784→32→10 ReLU MLP. Weights live in the CSS as custom properties. Each input image is a `:root:has(#sample-N:checked)` block that overrides the 784 `--x-NNN` pixels. The browser computes the forward pass as two layers of giant `calc()` sums, with `max(0, …)` for ReLU. **CSS never computes the argmax.** The page shows ten bars and you read the longest one.
- **Toy transformer**: one GPT-2-style block with vocab 7 (character level, `" abcde."`), d_model 12, 3 heads × 4 dims, d_ff 24 and context 6. **Its body weights are random (seed 19). Only the LM head is fitted**, by closed-form ridge regression, so that the model continues the cycle `␠abcde.`. LayerNorm uses `sqrt()` and `/` in `calc()`. Softmax uses `max()` + `exp()`. GELU is a CSS `@function` that builds tanh out of `exp()`. Argmax is `1 - abs(sign(logit - max))`, which produces one-hot indicators. Those indicators pick the next token's embedding (a dot product with literal `wte` constants) and are fed into **statically unrolled** copies of the whole network (`generation-0/1/2`), each of which recomputes the full prefix with no KV cache. Output is shown by setting the indicators as `opacity` on 7 stacked glyph spans per step.
- **Verification**: the build makes **no automated CSS-vs-Python check**. It prints Python reference generations and embeds them in a `<details>` block. I evaluated the generated `:root` graph in Python myself (scratch script, see log step 12), and it reproduces the reference for all 4 prompts.

---

## 1. MNIST recap

### 1.1 Architecture and training
- Data: the `mnist.npz` download from Google storage, normalised to [0,1] and flattened to 784 (`tools/build.py:14-33`).
- Model: 784 → 32 (ReLU) → 10, He-normal init, trained with hand-written mini-batch Adam and softmax cross-entropy plus L2 0.00005. Batch 256, lr 0.0025/(1+0.08·epoch) (`tools/build.py:36-98`). The defaults are 8 epochs, seed 7 (`tools/build.py:313-314`).
- Test accuracy is baked into the page: 96.14% (`index.html:251`, produced by `tools/build.py:321-324,297`).
- The 10 demo images are the first *correctly classified* test example of each digit (`tools/build.py:326-331`).
- Doc inconsistency: the README step list says "train a multinomial linear classifier" (`README.md:11`), and so do the module docstring "linear MNIST classifier" (`tools/build.py:2`) and the page lede "A real 784-input linear classifier" (`index.html:15`). The code is actually an MLP with one ReLU hidden layer (`tools/build.py:42`, `README.md:4`).

### 1.2 How weights become CSS
`write_model_css` (`tools/build.py:106-180`) emits one `:root {}` block:
- `--x-000 … --x-783: 0;` are the input slots (`tools/build.py:124-125`, `model.css:5-788`).
- Every weight and bias is its **own custom property** with a 7-decimal literal (`css_number`, `tools/build.py:101-103`). Examples are `--hidden-bias-00: 0.1483464;` and `--hidden-w-00-000: 0;` (`tools/build.py:126-133`, `model.css:789-790`).
- Each hidden pre-activation is one 785-term `calc()` (`tools/build.py:134-141`):

```css
/* model.css:1574-1578 … 2359-2361 */
  --hidden-pre-00: calc(
    var(--hidden-bias-00)
    + var(--x-000) * var(--hidden-w-00-000)
    + var(--x-001) * var(--hidden-w-00-001)
    ...
    + var(--x-783) * var(--hidden-w-00-783)
  );
  --hidden-00: max(0, var(--hidden-pre-00));
```
- **ReLU = `max(0, …)`** (`tools/build.py:142-144`, `model.css:2361`). The 32 `max(` occurrences in `model.css` are all ReLUs. None of them is an argmax.
- Output scores: `--score-k = calc(bias + Σ hidden_j * w_kj)` (`tools/build.py:146-159`, `model.css:51158`).
- **No `@property` registrations exist in `model.css`** (count 0). The `:root` values are unregistered token streams that get substituted where they are used. Only `--score` is registered, as `<number>`, in `styles.css:1-5`.

### 1.3 Input selection (radios + `:has`)
- There are ten `<input type="radio" name="sample" id="sample-N">` elements, each with a label that shows a thumbnail (`tools/build.py:229-236`, `index.html:99-148`).
- For each sample the build emits `:root:has(#sample-N:checked) { --x-PPP: value; … }`, and **only non-zero pixels** are written (`tools/build.py:162-167`, `model.css:51806-51810`). Because `:root:has(...)` beats `:root`, these override the zero defaults.
- The same selector toggles the matching `<img>`, caption and reference text to visible (`tools/build.py:168-179`, `model.css:52001-52003`). They are hidden by default (`styles.css:81-82,88-90`). The digit images are build-time SVGs (`tools/build.py:183-205`).

### 1.4 Result display: no CSS argmax
- Each `.score-row` gets `--score: var(--score-k)` through `:nth-child` (`styles.css:205,250-259`).
- Bar width is `clamp(0%, (score − floor)·scale·1%, 100%)` (`styles.css:226-235`). `--score-floor` and `--bar-scale` are build-time constants derived from the demo samples' score range (`tools/build.py:114-123`, `model.css:3-4`).
- The numeric readout is `counter-reset: millilogit calc(var(--score) * 1000)` with `content: counter(millilogit) " mlogit"` (`styles.css:237-248`).
- The prediction is left to the reader: "The longest bar is the CSS prediction" (`tools/build.py:289`). The Python prediction is static text (`tools/build.py:237-243`).

---

## 2. Toy transformer: origin of weights, hyperparameters, tokenizer

### 2.1 Hyperparameters (`tools/build_transformer.py:14-23`)
| constant | value |
|---|---|
| `VOCAB` | `" abcde."` → 7 tokens (ids 0..6 = ␠ a b c d e .) |
| `D_MODEL` | 12 |
| `N_HEAD` / `HEAD_DIM` | 3 / 4 |
| `D_FF` | 24 |
| layers | **1** (a single `forward` call per step; no layer loop) |
| `MAX_CONTEXT` | 6 (size of `wpe`); only 5 positions are ever used (see §5) |
| `EPSILON` | 1e-5 |
| `PROMPTS` | `" ab"`, `"bcd"`, `"de."`, `". a"` (all length 3) |
| `GENERATION_STEPS` | 3 |

### 2.2 Tokenizer
Character-level identity lookup: `VOCAB.index(character)` at build time (`tools/build_transformer.py:392,444,519`). Space is displayed as `␠` (`tools/build_transformer.py:15`). There is no BPE and no runtime tokenizer, because the prompts are a fixed set of 4 radio choices.

### 2.3 Where the weights come from: random body, fitted head
- `make_model(seed=19)` draws **every body weight from a Gaussian** (`tools/build_transformer.py:50-65`): `wte` σ=0.08, `wpe` σ=0.04, `wq/wk/wv/wo` σ=0.10 (12×12), `wfc` 24×12, `bfc`, `wdown` 12×24 and `bdown`.
- Hand-set tweak: `token_embedding[:, :7] += eye(7) * 1.4` (`tools/build_transformer.py:53`). This makes each token's embedding nearly one-hot in the first 7 dims, so tokens stay separable after the random block.
- The architecture has no biases on Q/K/V/O and no LayerNorm γ/β (`layer_norm`, `tools/build_transformer.py:40-41`). LayerNorm is pure standardisation.
- **The only learned part is `lm_head` + `lm_bias`**, fitted by `fit_language_head` (`tools/build_transformer.py:93-112`):
  - Dataset: every contiguous window of the cyclic sequence `␠abcde.` (7 starts × lengths 1..5 = 35 examples). The target is the next character in the cycle (`:96-100`).
  - Features: the final-LayerNormed hidden state of the last position from the random block (`hidden_forward`, `:68-90`, called at `:101`).
  - Targets: +5 for the correct token and −1 for the others (`:102-104`).
  - Closed-form ridge regression, `solve(XᵀX + 1e-4·I, XᵀY)`, with a bias column (`:105-112`).
  - So "training" is linear probing on top of a random-feature transformer. The task is to continue the alphabet cycle. All 4 prompts are windows of that cycle, which means they are in the training set.
- The head is untied from `wte`.

---

## 3. Embeddings and naming

### 3.1 Property naming scheme
- `--prompt-{pos}-{dim}` (pos 0..2, dim 0..11) holds the **already-summed token+position embedding** of prompt character `pos`. It is declared `0` in `:root` (`tools/build_transformer.py:364-370`, `t/model.css:3080`). For example, `prompt-0-1` means "prompt position 0, embedding dimension 1".
- `--generation-{step}-…` is every intermediate of unrolled copy `step` of the network, built through the `prefix` argument (`tools/build_transformer.py:384`). **"generation 0" is the forward pass that predicts the 1st new token** from the 3-token prompt. Generation 1 sees prompt + generated token 0 (4 positions), and generation 2 sees 5 positions.
- Inside a step, names follow `{stage}-{position}-{dim|unit|head}-{source}`. Examples are `generation-0-attn-score-2-0-1` (query position 2, head 0, key position 1) and `generation-0-fc-0-17` (position 0, hidden unit 17).
- There are 3,069 properties in total, each registered as `@property --name { syntax: "<number>"; inherits: true; initial-value: 0; }` (`tools/build_transformer.py:409-416`, `t/model.css:10-3078`). Per-step counts are 756 / 1,008 / 1,269 declarations, growing with sequence length.

### 3.2 Prompt lookup (no JS): enumerated at build time
The build does not do a token-id → row lookup at runtime. For each of the 4 prompts it precomputes `wte[token] + wpe[position]` and writes the 36 numbers into a `:has` block (`tools/build_transformer.py:389-398`):

```css
/* t/model.css:6150-6153, 6188 */
:root:has(#prompt-0:checked) {
  --prompt-0-0: 1.2824757;      /* = wte[' '][0] + wpe[0][0]; 1.4 one-hot bump visible */
  --prompt-0-1: 0.09233358;
  ...
}
:root:has(#prompt-0:checked) .prompt-value[data-prompt="0"] { display: inline; }
```
This is the same mechanism MNIST uses for pixels. I verified the constant `1.2824757` against a Python re-derivation (log step 12). The step-0 inputs then simply alias these values: `--generation-0-x-0-0: calc(var(--prompt-0-0));` (`t/model.css:3116`, from `tools/build_transformer.py:174-180`).

### 3.3 Generated-token lookup: one-hot × literal table
Feedback tokens are looked up with arithmetic. The one-hot indicator vector is dotted with the literal `wte` column (`tools/build_transformer.py:348-357`):

```css
/* t/model.css:3860 */
--generation-0-next-embedding-0: calc((var(--generation-0-is-token-0)) * 1.37039802
   + (var(--generation-0-is-token-1)) * 0.02735421 + … + (var(--generation-0-is-token-6)) * -0.05127017);
```
The positional embedding for the new slot is added as a literal constant (`tools/build_transformer.py:376-383`):

```css
/* t/model.css:3908 */   --generation-1-x-3-0: calc((var(--generation-0-next-embedding-0)) + -0.00364783);
```

---

## 4. Each block, and how it differs from MNIST

All formulas match the NumPy reference `hidden_forward` (`tools/build_transformer.py:68-90`). The CSS builder is `CssCompiler.forward` (`:169-358`). One structural difference from MNIST: **weights are inlined as literal numbers in `calc()`** by `dot()` (`:141-147`) instead of being stored as separate custom properties. The literals use 8 decimals (`:35-37`), against 7 in MNIST.

| stage | builder lines | generated sample |
|---|---|---|
| **LayerNorm**: mean, deltas, variance, `1/sqrt(var+ε)`, scaling | `normalize` `:149-167` | `--generation-0-ln1-0-mean: calc((… 12 terms …) / 12);` (`t/model.css:3152`) · `--generation-0-ln1-0-inverse-std: calc(1 / sqrt((var(--generation-0-ln1-0-variance)) + 1e-05));` (`:3166`) · `--generation-0-ln1-0-value-0: calc((delta-0) * (inverse-std));` (`:3167`) |
| **Q/K/V**: three 12×12 matvecs per position, no bias | `:186-219` | `--generation-0-q-0-0: calc(0 + (var(--generation-0-ln1-0-value-0)) * -0.01020212 + …);` (`:3233`) |
| **Scores**: per-head 4-dim q·k / √4 | `:226-237` | `--generation-0-attn-score-2-0-0: calc(((q-2-0)*(k-0-0) + … + (q-2-3)*(k-0-3)) / 2.0);` (`:3404`) |
| **Causal mask** | `range(position + 1)` at `:227` and `:265` | No masking values exist. Future keys are **never emitted**, so the mask is structural: query 2 only gets scores for sources 0..2 (`:3404-3406`). |
| **Softmax**: max-subtracted `exp` | `:238-259` | `--…-attn-max-2-0: max(score-2-0-0, score-2-0-1, score-2-0-2);` (`:3407`) · `--…-attn-exp-2-0-0: exp((score) - (max));` (`:3408`) · `denom = Σ exp` (`:3411`) · `prob = exp / denom` (`:3412`) |
| **Weighted sum** | `:260-267` | `--generation-0-attn-value-2-0: calc((prob-2-0-0)*(v-0-0) + (prob-2-0-1)*(v-1-0) + (prob-2-0-2)*(v-2-0));` (`:3415`) |
| **Output projection W_o** | `:272-279` | `--generation-0-attn-proj-0-0: calc(0 + (attn-value-0-0) * 0.06692513 + …);` (`:3449`) |
| **Residual 1** | `:280-288` | `--generation-0-residual1-0-0: calc((x-0-0) + (attn-proj-0-0));` (`:3461`) |
| **LN2 → FC (12→24, bias)** | `:290-304` | `--generation-0-fc-0-0: calc(-0.00167323 + (ln2-0-value-0) * -0.01719117 + …);` (`:3602`) |
| **GELU** (tanh approximation) | `CSS_FUNCTIONS` `:25-32`, used at `:305-310` | `--generation-0-gelu-0-0: --gelu(var(--generation-0-fc-0-0));` (`:3626`), with the function at `t/model.css:2-9` (below) |
| **Down-projection (24→12, bias) + residual 2** | `:311-328` | `:3650`, `:3662` |
| **Final LN (last position only)** | `:330` | `--generation-0-final-ln-mean: calc((residual2-2-0 + …) / 12)` (`:3818`) |
| **LM head**: 7 logits | `:331-339` | `--generation-0-logit-0: calc(-0.20680769 + (final-ln-value-0) * -0.26718168 + …);` (`:3845`) |
| **Argmax → one-hot** | `:340-347` | `--generation-0-max-logit: max(logit-0, …, logit-6);` (`:3852`) · `--generation-0-is-token-0: calc(1 - abs(sign((logit-0) - (max-logit))));` (`:3853`) |

GELU as a CSS custom function (`t/model.css:2-9`):
```css
@function --gelu(--x <number>) returns <number> {
  --cube: calc(var(--x) * var(--x) * var(--x));
  --tanh-input: calc(0.7978845608 * (var(--x) + 0.044715 * var(--cube)));
  --bounded: clamp(-10, var(--tanh-input), 10);          /* guards exp overflow */
  --exponential: exp(calc(2 * var(--bounded)));
  --tanh-value: calc((var(--exponential) - 1) / (var(--exponential) + 1));  /* tanh via exp */
  result: calc(0.5 * var(--x) * (1 + var(--tanh-value)));
}
```
In the original commit 8a59db0f, GELU was six separate registered properties per unit (`--…-fc-cube-`, `-gelu-input-`, `-gelu-bounded-`, `-gelu-exp-`, `-gelu-tanh-`, `-gelu-`). Commit c328e4cd folded them into `@function` (diff of `tools/build_transformer.py` in c328e4cd), which cut `t/model.css` from 9,198 to 6,326 lines. `@function` needs Chromium 139+ (`README.md:43-44`).

Notes on the argmax:
- `sign(logit − max)` is 0 only for the maximum, so the indicator is 1 for the winner and 0 for every other token.
- An exact tie would produce a multi-hot vector: the next embedding would be the sum of two rows, and two glyphs would show. On these prompts the top-1 vs top-2 logit margin is about 5.7–6.1 (log step 12), so no tie is possible in practice.

**Dead work:** with one layer, only the last position's `residual2` feeds the head. The LN2/FC/GELU/down/residual2 chain for every non-final position is emitted and registered but unused. `var(--generation-0-residual2-0-0)` has 0 references, against 2 for `residual2-2-0` (log step 14).

---

## 5. Autoregression without JS: static unrolling

- `compile_css` (`tools/build_transformer.py:372-386`) calls `compiler.forward(f"generation-{step}", inputs)` three times.
  - The inputs for step *s* are the 3 prompt vectors plus the `next_embedding` vectors of every previous step, each with its `wpe[position]` constant added (`:375-383`).
  - So the token chosen in step 0 is just a CSS dependency of step 1. The browser's style engine resolves the whole DAG in one pass: prompt → gen-0 → gen-1 → gen-2. No animation, no extra `:has()` and no timing are involved.
- **There is no KV cache.** Each step recomputes the full prefix from scratch. `--generation-1-x-0-0: calc(var(--prompt-0-0));` (`t/model.css:3872`) re-derives position 0 again, which is why per-step property counts grow (756 → 1,008 → 1,269).
- The model produces **3 new tokens**. Only the first 2 are fed back, so the deepest step sees 5 positions. Row 5 of `wpe` (`MAX_CONTEXT = 6`) is never used, and step 2's `next_embedding` (`t/model.css` around `:6137-6148`) is computed but unused.
- **Every property is registered as `<number>`** (`:409-416`). This is what keeps the unrolled graph tractable: each node is computed once at `:root` and inherited as a number.
  - MNIST leaves its intermediates unregistered, so `var()` substitution expands the token stream.
  - With dozens of reuse points per node, as here, unregistered substitution would blow up exponentially.
- Output display (`tools/build_transformer.py:403-408`, `t/model.css:6306-6326`; markup at `transformer/index.html:37-39`):
```css
.generated-token[data-step="0"] .token-option[data-token="1"] { opacity: var(--generation-0-is-token-1); }
```
  - Each step is an `inline-grid` with 7 `.token-option` spans stacked in `grid-area: 1 / 1` at default `opacity: 0` (`transformer/styles.css:125-135`). The one-hot indicator makes exactly one glyph opaque.
  - The prompt text is one of 4 static spans, unhidden by `:has` (`transformer/styles.css:123`, `t/model.css:6188`).
  - `--logit` is registered in `transformer/styles.css:1-5` but never used (leftover).

---

## 6. MNIST had X → transformer needed Y, solved by Z

| MNIST had | Transformer needed | Solved by (citation) |
|---|---|---|
| Trained weights via Adam on real data (`tools/build.py:36-98`) | Weights that do *something* without a training loop | Random block (seed 19) + 1.4·I embedding bump + closed-form ridge-regression LM head on the cyclic `␠abcde.` task (`tools/build_transformer.py:50-65,93-112`) |
| 784-pixel input from a radio (`tools/build.py:162-167`) | Token+position embeddings for a prompt | Same radio + `:root:has()` override, but the precomputed values are `wte[tok]+wpe[pos]` (`:389-398`, `t/model.css:6150`) |
| Single static input, no feedback | Embedding lookup of a *runtime-chosen* token | One-hot indicator · literal `wte` column, `+ wpe` constant (`:348-357,376-383`, `t/model.css:3860,3908`) |
| `calc()` dot products with weights as named custom properties (`tools/build.py:126-141`) | Many more, smaller dot products | `dot()` emits `calc()` with weights inlined as literals (`:141-147`) |
| ReLU = `max(0,x)` (`tools/build.py:142-144`) | GELU (tanh) | CSS `@function --gelu` using `exp()` + `clamp(±10)` (`:25-32`, `t/model.css:2-9`) |
| No normalisation | LayerNorm (mean/var/sqrt/divide) | `calc()` with `sqrt()` and `/` (`:149-167`, `t/model.css:3166`) |
| No cross-position interaction | Q·K scores, causal mask, softmax, weighted V sum | Per-head `calc` dot products. The mask is structural (keys > query are not emitted). Softmax is `max()` + `exp(s−max)` + divide by sum (`:221-267`) |
| No skip connections | Residuals | `calc(x + proj)` (`:280-288,320-328`) |
| Argmax left to the eye ("longest bar", `tools/build.py:289`) | A machine-usable discrete choice | `max()` over logits + `1 - abs(sign(l - max))` one-hot (`:340-347`, `t/model.css:3852-3853`) |
| One forward pass | Autoregressive generation | Static unrolling: 3 full copies `generation-0..2`, chained by `var()` dependencies, no KV cache (`:372-386`) |
| Unregistered intermediates (token substitution); only `--score` registered (`styles.css:1-5`) | A deep, heavily reused DAG | Every one of the 3,069 nodes is `@property` `<number>`, `inherits: true` (`:409-416`) |
| Output = bar widths + counter text (`styles.css:226-248`) | Output = text tokens | 7 stacked glyphs per step with `opacity: var(--…-is-token-k)` (`:403-408`, `transformer/styles.css:125-135`) |
| Display-only Python reference (`tools/build.py:237-243`) | Same | Reference generations in `<details>` (`:442-452`, `transformer/index.html:48-54`) |

---

## 7. Build-time verification

- `build_transformer.py` has **no automated check that the CSS equals the Python output**.
  - `main()` prints Python reference generations (`tools/build_transformer.py:517-525`).
  - `write_html` embeds the same strings in a `<details>` block (`:442-452`): `␠ab → cde`, `bcd → e.␠`, `de. → ␠ab`, `.␠a → bcd` (`transformer/index.html:50-53`).
  - Whoever looks at the page has to compare the two by eye.
- The NumPy reference (`hidden_forward`/`predict`, `:68-118`) mirrors the CSS graph operation by operation. It even matches the CSS's per-position full recompute and the final LN on the last position only. The GELU constants match too: 0.7978845608 ≈ √(2/π) in CSS vs `np.sqrt(2/np.pi)` in NumPy. One difference: the CSS clamps the tanh input to ±10 and NumPy does not, which has no effect at these magnitudes.
- Independent check performed for this audit (scratchpad script, log step 12). I parsed `t/model.css` `:root` plus each `:has(#prompt-i)` override and evaluated every expression in float64, implementing `calc/max/exp/sqrt/abs/sign/clamp/--gelu`. The CSS graph yields `c d e`, `e . ␠`, `␠ a b` and `b c d`, which **matches the Python reference for all 4 prompts**, each with exactly one indicator = 1. This validates the generated graph, not Chromium's float precision. Browser behaviour was not tested here.
- MNIST is similar. There is no automated CSS check. The Python prediction and test accuracy are shown as static text (`tools/build.py:237-243,297`).
