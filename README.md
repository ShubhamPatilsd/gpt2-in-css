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

This is the compiler source (Python) that writes the page, the scripts that pack it, the Cloudflare deploy config,
and two documents that explain how the page works. The built page (fonts, `runtime.css`, `index.html`) is **not** in
git, because it is about 300 MB.

```
compile.sh                  Final page compiler entry point (wraps tools/browser_gpt2_runtime.py with the shipped flags)
tools/                      Compiler and font builders (Python), plus research benchmarks and profilers (Playwright .mjs)
  browser_gpt2_runtime.py     Main compiler: writes index.html + runtime.css + fonts for the full 12-layer model
  browser_gpt2_*.py           Model parts: embedding, attention/KV cache, MLP font vectors, vocabulary head
  f4_* r2*_ ... r8u_*.py      Optimization passes and UI features, switched by the env flags in compile.sh
  build_*.py                  Font and CSS builders for the experiment stages that the final compile reuses
  launch_browser_gpt2.py      Local static server + launcher (separate Chrome profile, JavaScript off, strict CSP)
  serve_precompressed.py      Static server that serves .br/.gz files
pack/                       Pack a built bundle into a self-contained upload folder and zip
  prepare_upload.sh           bundles/<name>  ->  <out>/model (upload tree) + <out>-zip/gpt2-in-css.zip
deploy/cloudflare-worker/   Cloudflare Worker config for the hosted demo (see DEPLOY.md)
docs/                       How it works: I1 = the data path of one token, I2 = control path, clocking, sampling, UI
```

The documents in `docs/` were written against the original research tree. Paths in them such as
`work/2026-09-19/R7X/tools/x.py` correspond to `tools/x.py` here.

Tests and browser test harnesses were removed from this public copy. The research benchmark and profiler scripts in
`tools/` (`benchmark_*`, `profile_*`, `compare_*`, `diagnose_*`, ...) are kept for reference. Many of them expect
experiment pages that are not in this repository, so treat them as notes, not as working tools.

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
