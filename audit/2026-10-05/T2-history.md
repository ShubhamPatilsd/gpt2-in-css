# T2 — History of the toy transformer (2026-08-24), from MNIST to tiny-gpt2 to GPT-2

Scope: what was tried, in what order, what broke, how it was checked, what came out, and why the
project moved on. This is read-only research. No repo files were changed.

## Source key

- **F1** = `~/.codex/sessions/2026/08/24/rollout-2026-08-24T11-41-49-01a03514-2c60-7840-b076-723cc2b863a8.jsonl`
  is the Codex Desktop session (GPT-5) that built everything on 08-24. `F1:L<n>` is the 0-based line in
  that jsonl. Times are UTC (`Z`). PDT = UTC − 7, so 19:02Z is 12:02 PDT (the commit time zone).
- **F5** = `…/2026/08/24/rollout-2026-08-24T21-07-35-01a035be…_01a0371a….jsonl`
- **F11** = `…/2026/08/25/rollout-2026-08-25T12-07-20-01a035be…_01a03a51….jsonl`
- **CC-d66** = `~/.claude/projects/-Users-shubhampatil-Documents-programming-gpt2-css/d66b829e-c235-42e5-9746-1569b44e93ca.jsonl`
  (2026-10-05). `84d3debf…jsonl` is a fork of the same conversation, with identical turns up to its #153.
- Commits are cited by short hash. File lines refer to the current `HEAD` unless a commit is given.

Who did the work: every 08-24 commit was made by Codex inside F1, at the user's request "keep committing as you
go" (F1:L377). The git author is the user's identity. The code in commit 8f189b3 was written before the
repo existed: Codex ran `git init` at about 19:02Z (F1:L382).

---

## 0. The trigger (verified)

- **User, 18:42Z (F1:L8):** *"i saw a tweet where someone was able to write gpt2 in cmake / i want to do this
  with html+css / if we were able to get an MLP (on an MNIST task) working first with those two, would that
  then allow us to scale up to gpt2"*
- **Codex answer (F1:L37):** MNIST would prove "neural-network inference can be expressed in CSS," but not
  that GPT-2 scales. It proposed a 7-step ladder: linear MNIST → quantized 784→16→10 MLP → interactive pixels
  → "a microscopic transformer: perhaps vocabulary 16, dimension 8, one head, one block" → one next-token
  inference → "several statically unrolled generation steps" → "only then evaluate whether loading real GPT-2
  weights is survivable."
- **User, 18:44Z (F1:L43):** *"ok wait lets get the first step working then in this project"*

## 1. MNIST (verified), 18:45Z–19:02Z, commit `8f189b3` (12:02:56 PDT)

| Sub-step | Evidence | Result |
|---|---|---|
| 1a. Linear 784→10 classifier, one fixed test image (digit 7) | F1:L104, L220 | 92.17% test accuracy, 7,840 weights. Chromium picked class 7, matching Python, with 0 scripts |
| Verification method | F1:L78, L130, L172 | Codex tried a "terminal-browser" skill first. It could not attach, so Codex switched to the in-app browser (Playwright via `node_repl`). It read the computed bar widths |
| User: *"why do we have a makefile"* | F1:L226 | Codex: convenience only, not part of inference (F1:L229). The Makefile was kept |
| User: *"how many images here?"* → *"on the page can we try a bunch of diff images"* | F1:L235, L246 | 10 test images (one per digit), picked with radio buttons + `:has()`. All 10 classified correctly in Chromium (F1:L302, L316) |
| User: *"does this do training with cmake"* (gpt2.cmake) | F1:L322 | No. gpt2.cmake is inference only, and its toy model uses random weights from `gen_model.py` (F1:L339). This framing later shaped the toy transformer |
| User: *"ok now whats the next step in our plan"* | F1:L345 | Codex proposed a 784→**16**→10 ReLU MLP (F1:L350) |
| User: *"keep going until you reached the end goal"* (F1:L356), then *"keep committing as you go"* (F1:L377) | | This started the autonomous run that produced the next four commits |
| 1b. Nonlinear MLP | F1:L394; `git show 8f189b3:tools/build.py` lines 42–44 (`hidden_size = 32`, "784 -> 32 -> 10 ReLU MLP with mini-batch Adam") | **784→32→10** ReLU, 8 epochs of Adam, **96.14%** (`8f189b3:index.html:251`). Checked in Chromium on all 10 samples before committing |

The linear version was never committed: the repo did not exist yet, so only the MLP is in `8f189b3`. One
leftover of the linear stage stayed in the code: the build script's module docstring (`8f189b3:tools/build.py:2`)
and the page lede (`index.html:15`) still say "linear classifier."

**Correction to prior audits:** `audit/2026-09-18/S1-sessions-aug-sep08.md:18` and
`audit/2026-10-02/N1-tricks-aug24-sep13.md:22` both say "784→16→10". The 16 was only the plan (F1:L350). The
code and F1:L394 ("32 CSS ReLUs") both say 32. CC-d66 #102 reached the same conclusion. `blog/facts.md:20` is correct (32).

What MNIST established: a `calc()` weighted sum of `var()` inputs, ReLU as `max(0, …)`, input swapped by
`:has(#radio:checked)`, and output read from a bar width. The MNIST page puts each weight in its own custom
property (`--hidden-w-00-000`).

## 2. Toy transformer (verified), 19:03Z–19:09Z, commit `8a59db0` (12:09:43 PDT)

### 2.1 Goal and design (Codex, autonomous; no user prompt specific to this step)

- **F1:L417 (19:03:11Z):** "I'm moving to a separate tiny-transformer demo now so the stable MNIST page stays
  intact. The target circuit will include embeddings, positional state, layer normalization, causal attention,
  GELU, residuals, and a tied output head—the essential GPT-2 forward path."
- **F1:L418–420:** the first action was to probe for `jax`, `jaxlib`, `tensorflow`, `autograd` and `scipy`.
  **All were missing.**
- Reasoning summaries (F1:L423–441; the text itself is encrypted, only the titles survive): "Evaluating tiny
  GPT-2 model for use" → "Planning tiny GPT-2 tokenizer integration" → "Exploring CSS numeric comparisons for
  token selection" → "Planning tiny transformer training with numeric gradients" → "Designing
  cycle-predicting tiny transformer architecture" → "Planning multi-step transformer export with CSS decoding".
- **Inferred:** with no autodiff library installed, Codex dropped real training. Instead it froze a random
  block and fitted only the output layer in closed form. This is also why the "tied output head" plan in
  L417 became a separately fitted head in the code. Codex never says this outright. The evidence is the probe
  result plus the summary titles. Note also that the first reasoning title is about tiny-gpt2: the real
  checkpoint was under consideration from the start, and the toy was the cheaper first step.

### 2.2 What was built (`tools/build_transformer.py` in `8a59db0`; same code at HEAD apart from §2.5)

- Vocabulary `" abcde."` (7 tokens), `D_MODEL=12`, `N_HEAD=3` (head dim 4), `D_FF=24`, `MAX_CONTEXT=6`, one
  block, `PROMPTS=[" ab","bcd","de.",". a"]`, `GENERATION_STEPS=3` (HEAD lines 13–23). **1,435 parameters.**
  I re-counted this (log #19).
- `make_model(seed=19)` (HEAD :50): all weights are Gaussian noise, except the token embedding, which gets
  `+ np.eye(7) * 1.4` (:53). The result is near-one-hot embeddings, set by hand.
- `fit_language_head()` (:93): runs the random block on every substring of the cycle (7 starts × lengths 1–5
  = 35 examples). The targets are +5 for the correct next character and −1 for the others (:103). The head is
  then solved by ridge regression with λ=1e-4 (:107). This is the only "training."
- `CssCompiler.forward()` (:169) emits, per position: the embedding sum, LayerNorm (mean, deltas, variance,
  `1/sqrt`), q/k/v dot products with the weights baked in as literals, causal attention (scores are only
  emitted for source ≤ position, then `max()` and `exp()` softmax), the output projection and residual,
  LayerNorm, the FC layer, GELU (tanh built from `exp`, input clamped to ±10), the down projection and
  residual, a final LayerNorm, and 7 logits. The argmax is `1 - abs(sign(logit - max))` (:343). The
  next-token embedding is computed as Σ one-hot × `wte` (:350).
- `compile_css()` (:361) makes three full copies of the model (`generation-0/1/2`). Each copy re-runs the whole
  prefix: there is no KV cache. Copy *n* reads the previous copy's `next-embedding` plus a literal `wpe`
  row. Prompts are set by `:root:has(#prompt-N:checked)` rules that hold embeddings precomputed in Python.
  The winning token is shown via `opacity: var(--generation-S-is-token-T)`.
- Page: `transformer/index.html` ("Experiment 002 · no runtime JavaScript") with 4 radio prompts and a
  `<details>` showing the Python reference outputs. It links back to the MNIST page.
- Differences from MNIST: weights are inlined literals instead of variables, there is a compiler class, and
  the new operations are attention, LayerNorm, GELU, an in-CSS argmax, and token feedback.

### 2.3 Test 1: failed (verified)

- Build at 19:07:24Z (F1:L448–450): the Python reference gave `␠ab→cde`, `bcd→e.␠`, `de.→␠ab`, `.␠a→bcd`.
  `model.css` was 1,215,111 bytes, and a grep for `<script` found nothing.
- Served with `python3 -m http.server 4173` (F1:L456). Playwright clicked each of the 4 prompts and read the
  `getComputedStyle(opacity)` of all 7 options × 3 steps (F1:L461).
- **Result (F1:L463):** every opacity was `1`, so all 7 tokens were visible at every step for every prompt.
  The argmax had produced nothing.

### 2.4 Diagnosis and fix (verified), 19:07:59Z–19:09:08Z

1. F1:L467–469: `CSS.supports` confirmed `calc` multiplication, `sqrt`, `exp`, `abs` and `sign`. So no
   function was missing. But `--generation-0-ln1-0-mean` read back as **unexpanded expression text**, and the
   logit and indicator values read back as empty.
2. F1:L473–475: the `:root` rule had 4,509 declarations, and all of them parsed. So the problem was not
   parsing.
3. F1:L479–481: a walk over all declarations found the first empty one at index 265,
   `--generation-0-attn-prob-0-0-0`, which is the softmax division. Everything after it was empty too.
4. F1:L485–487: `calc(1/2)` and `pow` were supported. The attention denominator, the `exp` and the
   inverse-std were huge nested `calc(exp((calc(((calc(…` strings. Each one was the whole upstream
   expression pasted in as text.
5. **Diagnosis (F1:L494):** "ordinary custom properties recursively substitute their full expression text,
   so the transformer graph expands until later calculations become invalid."
6. **Fix (F1:L495):** the compiler records every name and emits
   `@property --x { syntax: "<number>"; inherits: true; initial-value: 0; }` for each one. This forces each
   scalar to be computed as a number before the next step uses it. The CSS grew to 1,646,406 bytes (F1:L503).
7. **Test 2 (F1:L507–509):** Chromium output exactly one visible token per step. `␠ab` gave tokens 3,4,5
   (`cde`). Codex reported that all four prompts match Python (F1:L514). One more fix was needed: the prompt
   text was invisible because whitespace in the `prompt-stack` markup broke the `white-space: pre` display
   (F1:L520–523). A presentation check then read `{"prompt":"␠ab","tokens":["c","d","e"],"scripts":0}`
   (F1:L535), and the commit followed at F1:L539–541.

The `@property` "materialize" rule found here was reused in every later model (N1 T3). It is also the source
of FULL_GPT2.md's line that "Typed properties are not optional in this design" (`bc741e9:FULL_GPT2.md`).

### 2.5 Later touches (verified)

- `git log --all -- tools/build_transformer.py transformer/` lists only two commits: `8a59db0` and `c328e4c`.
- **`c328e4c` (12:34 PDT; F1:L775 "search up if anyone has figured out hacks… and apply those"):** replaced
  the 6 GELU intermediates per unit with a single `@function --gelu()` (Chromium 139+). The toy CSS went from
  1,646,406 to 1,330,393 bytes (−19.2%) and from 4,509 to 3,069 typed properties (`OPTIMIZATIONS.md` table).
  Chromium re-verified all four sequences (F1:L965).
- The toy was never touched again. It has **no animation and no `@keyframes`**: I grepped `transformer/`
  and found 0 matches. Its autoregression is unrolled in space and computes all at once on load.

### 2.6 Re-verification today

- **Verified by me (Python only):** I imported `tools/build_transformer.py` in memory and re-ran `make_model`,
  `fit_language_head` and `predict`. The outputs are again `cde`, `e.␠`, `␠ab`, `bcd`, with 1,435 parameters.
  `transformer/model.css` at HEAD is 1,330,393 bytes with 3,069 `@property` lines, matching OPTIMIZATIONS.md.
- **Not re-run by me in a browser.** CC-d66 #102 reports a headless Chromium 153 run with the same 4/4 match
  and 0 scripts. I cite it but did not repeat it.

## 3. Why move on: tiny-gpt2 (verified), 19:10Z–19:16Z, commit `1ad8aa4` (12:16 PDT)

- **Stated reason (F1:L551):** "The next scale test will use a real pretrained GPT-2-family checkpoint rather
  than another synthetic model… if its full 50,257-token output head runs in CSS, the exporter architecture is
  sound before attempting the 124M model." The toy had shown the circuit worked. What was still untested was
  real weights, the real tokenizer, and the 50,257-way output.
- Codex looked up `sshleifer/tiny-gpt2` and `openai-community/gpt2` on the Hugging Face API (F1:L552–560).
  The config has `n_embd: 2`, 2 layers and 2 heads (F1:L572). The legacy (non-zip) PyTorch pickle was decoded
  by hand with `pickle` + `struct` + NumPy, without PyTorch (F1:L576–594; `1ad8aa4:tools/build_pretrained_gpt2.py`).
- First build: 28,661,394 bytes. Reference outputs `Hello→" stairs"(16046)`, `The→" factors"(5087)`,
  `CSS→" stairs"` (F1:L616).
- **Problem (F1:L647):** "putting all 154,000 assignments in one `:root` rule caused even the third dependency
  to fall back to its initial value." **Fix:** split the graph across many `:root` rules. After that, Chromium
  matched Python for all 3 prompts (F1:L662–673).
- Page: "Experiment 003", single-token prompts, a tree-reduced max, and a one-hot argmax over all 50,257
  logits (`1ad8aa4:pretrained/index.html`).

## 4. The GPT-2 small wall (verified), 19:16Z–19:19Z, commit `bc741e9` (12:19 PDT)

- Downloaded the 548 MB `openai-community/gpt2` checkpoint and ran it in NumPy: `Hello → ","` (F1:L695–733).
- `tools/analyze_full_gpt2.py` counted 84,953,088 transformer MACs + 38,597,376 head MACs = 123,550,464 CSS
  terms per token. It estimated about 480k typed properties, 3.18 GB of compact CSS (6.14 GB readable), and a
  6.4–30.7 GB browser working set (F1:L726).
- Codex: "Emitting and loading that would risk exhausting… system memory, so this is the honest hard
  boundary" (F1:L733). FULL_GPT2.md concludes that tiny-gpt2 is "the largest verified end-to-end result."
- After `c328e4c`, the estimate fell to 229,365 properties but still 3.16 GB, "because the 123.55 million
  explicit multiplication terms dominate" (F1:L989).
- F1:L758 summary: the four commits `8f189b3` → `8a59db0` → `1ad8aa4` → `bc741e9`, made **in 17 minutes**
  (12:02 to 12:19 PDT).

## 5. What came after, and why it ended at real GPT-2 (verified unless marked)

| When | Prompt / event | Outcome |
|---|---|---|
| 19:22Z | User: *"is size and memory th eonl yconcern here? why is it blown up so largely with css but not something like js"* (F1:L764) | Codex: CSS has no loops, arrays or indexing, so every scalar operation becomes source text. Typed intermediates are needed (F1:L769) |
| 19:36–19:48Z | *"let it keep running off a prompt… to test tok/sec"* (F1:L1027), *"wait we should bench the autoregressiveness"* (F1:L1131) | A JS-timed benchmark (`24ff03b`), then a real 4-token chain: 57.2 MB, about 6.2 tok/s (`cfb2dc1`, F1:L1265). "`tiny-gpt2` itself is degenerate, hence the repeated `stairs`/`factors`" |
| 21:21Z | *"can we find weights online for gpt 2 that dont make it spit out incoherent bullshit?"* + typed prompt (F1:L1453) | Codex: the cause is the width-2 checkpoint, not CSS (F1:L1462). It found `calum/tinystories-gpt2-3M` (F1:L1530). It also found the convex-hull pruning (only 16 of 50,257 tokens can win; F1:L1616) |
| 21:42Z | *"we dont want to use javascript for anything here… tokenizing cannot be done thru js / also it only keeps outputing factors or stairs. wha texactly did you do here?"* (F1:L2022) | JS removed (`de75b61`). `<select>` token pickers. Codex admitted that "the width-2 checkpoint is essentially a pipeline test, not a usable language model" (F1:L2359) |
| 22:12Z | *"the inference should happen thru a css animation perhaps? idk it shouldnt calculate everthing up front"* (F1:L2491) | Codex dropped its own fake reveal animation (F1:L2496) and built an x86CSS-style latch clock: about 1 token per 1.2 s (`8dbecde`, F1:L2861) |
| 23:05Z | *"what has been done and what is left from our original roadmap"* (F1:L2867) | Roadmap table (F1:L2883): toy "Done", tiny-gpt2 "Partially done", coherent generation "Not done", GPT-2 small "Analyzed, not implemented". Next step: port TinyStories-3M |
| 08-24 evening → 08-25 | TinyStories streaming (`756a408`, `81a92ff`) | First coherent output: "Once upon a time, there was a little girl named Lily…" (S1 F5) |
| 08-25 08:23Z | User: *"wait i dont want to finetune anything special because at some point i wanna see if we can get the actual gpt2 running?"* (F5:L2298) | Codex rejected any "specially trained CSS model": optimizations must keep the real checkpoint's math (F5:L2315). **This is the stated reason the project aimed at stock GPT-2 rather than a custom model** |
| 08-26 21:47Z | *"commit and push… then sketch out how feasible it would be to get the actual gpt 2 running in the browser"* (F11:L1888) | Started the GPT-2-small feasibility work and the move to a variable-font (HVAR) matmul backend (S1 F11 → F19). This later became the 12-layer GPT-2 demo |

**Inferred:** the toy transformer was a deliberate plumbing test, not a model anyone meant to keep. It
answered one question ("can CSS do attention, LayerNorm, GELU, an argmax and token feedback?") in about
6 minutes of wall time. It was dropped right away because none of its open questions were about the toy:
real weights, a real vocabulary, scale, time-sequencing and text quality all needed a real checkpoint. The
user never commented on the toy directly. Every user prompt in F1 after L356 is about the pretrained pages.

## 6. Problems log (toy and its neighbours)

| # | Problem | Where found | Fix |
|---|---|---|---|
| P1 | Untyped custom properties substitute expression text, so the graph blows up and goes invalid from the softmax divide onwards, and all opacities fall back to 1 | Toy, F1:L463–494 | Register every intermediate as `@property <number>` |
| P2 | Prompt text invisible (whitespace in the `prompt-stack` markup) | Toy, F1:L520 | Collapse the markup |
| P3 | No autodiff library available | Toy, F1:L418–420 | (inferred) a random block plus a closed-form ridge-regression head |
| P4 | 154k declarations in one `:root` rule: the third dependency falls back to its initial value | tiny-gpt2, F1:L647 | Split into many `:root` rules |
| P5 | Six registered GELU temporaries per unit | Both, F1:L825–863 | `@function --gelu()` |
| P6 | Three copies of the model = three full recomputes, all at load time | Toy design | Not fixed in the toy. Later solved by the KV cache (`7996961`) and the clock/gates |

## 7. What the blog already says vs. this history

- `gpt2-css-blog/content/post.json` (the live post, per memory) has the heading "Creating a dummy
  transformer", one intro paragraph, the `toy-transformer` embed, and these empty sub-headings: Vocabulary &
  Embeddings, Attention, Normalization, GeLU?, Residuals, Argmaxxing, "Autoregression? Sorta", "A fun story on
  @property".
- Its sentence "we can just initialize it with random weights" is **only partly accurate.** The block is
  random, but the embeddings get a hand-set 1.4 diagonal and the LM head is fitted by least squares. CC-d66
  #206–#236 explained this to the user.
- `blog/post.html` (in this repo, superseded) and `blog/old-drafts/draft-outline-markdown.md:45-49` fold the
  toy transformer into "Step 2" together with tiny-gpt2. `blog/facts.md:23-26` has no facts specific to the toy.
- CC-d66 #189 suggested a section outline, including that the `toy-transformer` diagram's "Softmax" box
  should read "Argmax." I did not re-check the diagram.

## 8. Verified vs inferred summary

**Verified** (by git, code, or raw session text): the order MNIST-linear → picker → MLP-32 → toy → tiny-gpt2 →
GPT-2-small analysis; every user quote above; the toy's hyperparameters, its random block with a fitted head,
and the 1.4 diagonal; the first-run failure (all opacities 1) and how it was diagnosed; the `@property` fix;
the 4/4 match in Chromium in 2026-08; the 1.65→1.33 MB `@function` change; no animation in the toy; the toy
unchanged after `c328e4c`; the reasons Codex gave for moving to tiny-gpt2 and the user's reasons for going
to real GPT-2.

**Inferred:** that the missing autodiff libraries are why the head was fitted instead of trained, and why
"tied head" became a separately fitted head; that the toy was always meant as a throwaway plumbing test; that
tiny-gpt2 was planned from the start (the only evidence is one reasoning-summary title). The reasoning text in
F1 is encrypted, so Codex's internal reasons can't be recovered beyond those titles.
