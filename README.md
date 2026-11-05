# GPT-2 in CSS

GPT-2 small (124M parameters, 12 layers) running entirely in HTML + CSS. The page has no JavaScript: it ships with
`Content-Security-Policy: script-src 'none'`. The weights are stored in fonts (variable-font axes, HVAR/GSUB tables), and
the browser's layout and font-shaping engines do the matrix math. CSS animations, view timelines and container style
queries clock the model through the 12 layers and feed each new token back in.

- Live demo: https://gpt2-css.shubhampatilsd.workers.dev/
- Blog post: https://shubhampatil.dev/blog/gpt2-css

The page takes up to 4 prompt tokens and generates 32 new tokens (context 36). It decodes greedily by default, and has
seed and temperature options (Gumbel-max sampling). In greedy mode it gives the same token ids as the float reference
GPT-2.

## Requirements to run the demo

- Desktop Google Chrome or Edge **139 or newer**. The page uses CSS `@function`, `if()`, `calc-size()`, anchor
  positioning, view timelines and `@container style()` queries. Other browsers show a broken page.
- About **16 GB of RAM**. The tab uses about 2 GB after it loads, and up to about 6 GB while it generates.
- About 300 MB download (240 MB of fonts). Each token takes about 15 to 45 s, so 32 tokens take about 15 minutes.

## What is in this repository

The compiler source of the shipped page, and the full research history that led to it: about 450 experiments, eight
speed rounds and the audits, with the git history from the first commit (2026-08-24) on. The built page (fonts,
`runtime.css`, `index.html`) is **not** in git, because it is about 300 MB.

```
compile.sh                  Final page compiler entry point (wraps tools/browser_gpt2_runtime.py with the shipped flags)
tools/                      Compiler, font builders, tests, research benchmarks and profilers (Python, Playwright .mjs)
  browser_gpt2_runtime.py     Main compiler: writes index.html + runtime.css + fonts for the full 12-layer model
  browser_gpt2_*.py           Model parts: embedding, attention/KV cache, MLP font vectors, vocabulary head
  f4_* r2*_ ... r8u_*.py      Optimization passes and UI features, switched by the env flags in compile.sh
  build_*.py                  Font and CSS builders for the experiment stages that the final compile reuses
  launch_browser_gpt2.py      Local static server + launcher (separate Chrome profile, JavaScript off, strict CSP)
pack/                       Pack a built bundle into a self-contained upload folder and zip
deploy/cloudflare-worker/   Cloudflare Worker config for the hosted demo (see DEPLOY.md)
docs/                       How it works: I1 = the data path of one token, I2 = control path, clocking, sampling, UI
experiments/                ~450 probes and studies: font axes (HVAR/avar2/gvar), GSUB, SVG filters, anchors,
                            timelines, counters, output-head search, quantisation, scaling to 12 layers
work/2026-09-19/            The speed rounds for the shipped page (baseline 40.2 s/token -> about 16 s/token)
audit/                      Profiling audits, cost models, and reviews of every experiment (E1-E6)
EXPERIMENTS.md              Index of every experiment, round and audit, in date order
transformer/, pretrained/,  The first prototypes (2026-08-24/25): MNIST MLP, toy transformer, tiny GPT-2,
tinystories/, index.html    TinyStories streaming demo
OPTIMIZATIONS.md, FULL_GPT2.md, MODEL_CANDIDATES.md   Early design notes
```

Generated files are not in git: fonts, built CSS/HTML bundles, Chrome traces, run logs, and any file over 1 MB.
The scripts next to each experiment, or in `tools/`, build them again. Many research scripts expect those generated
files, so treat them as notes, not as working tools.

The documents in `docs/` were written against the research tree. A path such as `work/2026-09-19/R7X/tools/x.py`
means `tools/x.py` as it was in round R7X. The history of `tools/` follows the rounds, so `git log -- tools/x.py`
shows each version.

## Research history

Experiments from the same day and topic share one commit, dated when their files last changed. [EXPERIMENTS.md](EXPERIMENTS.md) lists them
all. The main steps:

1. **2026-08-24 – 08-26: first prototypes.** A CSS-only MNIST MLP, then a toy transformer, then a tiny GPT-2 and a
   TinyStories model compiled to CSS (`transformer/`, `pretrained/`, `tinystories/`). JavaScript was removed from the
   runtime, and a recurrent CSS clock streams tokens. [FULL_GPT2.md](FULL_GPT2.md) records the first wall: GPT-2
   small did not fit as plain CSS.
2. **2026-09-08 – 09-17: how to compute in a browser engine.** Hundreds of probes on where the matrix math can live:
   variable-font axes and HVAR metrics, GSUB, avar2, SVG filters (RGB/HDR carriers, dithering), anchor positioning,
   scroll/view timelines, counters. Then the output head (HNSW, IVF, LSH, certified group search) and precision
   (W8A8, q15/q16 groupwise). See `audit/2026-09-18/E1-experiments-001-075.md` to `E6-…` for a review of each one.
3. **2026-09-17 – 09-21: the full 12-layer model.** Chained blocks, a hybrid 12-block profile, browser integration
   and scaling runs (`experiments/browser-gpt2*`, `experiments/gpt2-flat-12block-chain`).
4. **2026-09-18 – 10-02: eight speed rounds.** From a 40.2 s/token baseline to about 16 s/token (round 4), then the
   shareable demo: typed prompts, a pure-CSS progress UI, a 2 s load, sampling with seed and temperature, and a
   32-token context (rounds 6–8). Results: `work/2026-09-19/RESULTS-round*.md`. Profiles: `audit/2026-09-18/P1-*`, `P2-*`.
5. **2026-10-05 – 11-01: write-up and deploy.** `audit/2026-10-05/T1–T3` re-run and explain the early prototypes;
   `deploy/` holds the Cloudflare Worker.

## Run locally

The easiest way is the prebuilt bundle. Download `gpt2-in-css.zip` from the GitHub release (if one is published) and
run:

```sh
unzip gpt2-in-css.zip -d gpt2-in-css && cd gpt2-in-css
python3 tools/launch_browser_gpt2.py --directory model          # Python 3.9+, opens Chrome with JavaScript disabled
python3 tools/launch_browser_gpt2.py --directory model --no-open  # or open the printed URL yourself
```

Any static file server works too, but the launcher also sends the same strict CSP as the hosted page.

## Build from source

Status: this is the exact compiler source of the shipped page, but a from-scratch rebuild from a fresh clone has not
been verified yet. Treat it as "compiler source + prebuilt bundle", not as a one-command build.

1. Tools: Python 3.11+ and [uv](https://docs.astral.sh/uv/). The compiler runs with
   `uv run --with numpy --with fonttools --with pillow --with brotli`. Some analysis scripts also need `torch`,
   `safetensors` or `hnswlib`.
2. Get the GPT-2 weights from Hugging Face (MIT license) into `data/gpt2/`:

   ```sh
   pip install -U "huggingface_hub[cli]"
   hf download openai-community/gpt2 model.safetensors config.json vocab.json merges.txt --local-dir data/gpt2
   # or: mkdir -p data/gpt2 && curl -L -o data/gpt2/model.safetensors \
   #       https://huggingface.co/openai-community/gpt2/resolve/main/model.safetensors
   ```

3. Build the font stages that the final compile reuses (`--reuse-core`). All scripts resolve paths from the repo root
   (`Path(__file__).resolve().parents[1]`), and write into `experiments/`:
   - `tools/build_gpt2_block_css.py` -> `experiments/gpt2-block-css/`
   - `tools/build_flat_twelve_block_chain.py` -> `experiments/gpt2-flat-12block-chain/layer01..11/`
   - `tools/build_hybrid_twelve_block.py` -> `experiments/hybrid-12block-profile/`
   - `tools/browser_gpt2_embedding.py` -> `experiments/browser-gpt2/embedding/`
   - `tools/build_gpt2_global_q16_layernorm_integer_full.py` -> `experiments/gpt2-global-q16-layernorm-integer-full/`
   - `tools/build_gpt2_groupwise_production_q16_sixfont.py` -> the `score-high-*` / `score-residual-*` head fonts
   - `tools/build_noise_font_r7b.py` -> `assets-r7b/` (Gumbel noise font for sampling)

   Example: `uv run --with numpy --with fonttools --with pillow --with brotli python tools/build_gpt2_block_css.py`.
   The packed operator fonts in `assets/`, `assets-r5h/` and `global-projection-assets/` are built on demand by the
   compiler. The tokenizer fonts in `assets-r6p/` (`gpt2-token-id-{0,1}-full.ttf`) must exist before the compile
   (see `tools/r6p_prompt.py`).
4. Compile the shipped page (12 layers, context 36, 32 new tokens):

   ```sh
   R7B_PREFILL_HEAD_SKIP=1 R7B_CAPACITY_36=1 R7B_SAMPLING=1 R7B_NEW_TOKENS=32 \
   R7H_ID_GUARD=1 R6X_SCROLLBAR_FIX=1 R8U_LAYOUT=1 \
   VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 ./compile.sh bundles/demo-c32 36 12
   ```

5. Pack it into a self-contained folder (fonts copied into `model/fonts/`, url()s rewritten):

   ```sh
   pack/prepare_upload.sh out    # -> out/model (upload tree) and out-zip/gpt2-in-css.zip
   python3 tools/launch_browser_gpt2.py --directory out/model
   ```

## Deploy

The hosted demo is a Cloudflare Worker on `workers.dev`. 286 small files are Workers static assets. The two files over
the 25 MiB static-asset limit (`runtime.css` and `fonts/embedding-lookup.woff2`) come from an R2 bucket through a small
server-side Worker. The Worker runs on Cloudflare, not in the browser, so the page still has no client JavaScript.
See [deploy/cloudflare-worker/DEPLOY.md](deploy/cloudflare-worker/DEPLOY.md).

Do not host the demo on a host that bills bandwidth: one cold visit downloads about 243 MB.

## Credits and license

- GPT-2 weights: OpenAI, released under the MIT license, from
  [openai-community/gpt2](https://huggingface.co/openai-community/gpt2). The fonts in the built page are derived from
  these weights.
- License for the code in this repository: **TBD**.
