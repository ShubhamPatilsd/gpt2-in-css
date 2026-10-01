# R6L — load time of `combined8-c32` (≈34 s blank tab) and the distribution question — report

Agent R6L, 2026-09-30. Scratch `R6L/`, log `R6L.log.md`, tools copy `R6L/tools` (= `R5X/tools` + `r6l_boot.py` + 3 hunks, `R6L/tools-vs-R5X.diff`, 100 lines).
Bundle: `bundles/combined8-c32-fast` (BUILD.md there). Nothing under repo `tools/` or `experiments/` touched; no git.
Machine all afternoon: AC, but swap used 4.95 → 5.9 → 8.4 GB (macOS added swapfiles 5–8 between 15:05 and 15:33 while other agents' jobs ran),
disk 7 → 2 GB → **the Chrome gate never opened during my session** (needs disk ≥ 4 GB & swap < 4,000 MB, or ≥ 3 GB & < 3,000 MB). Everything
Chrome-side is armed behind the gate (§4) and self-reports; everything else below is measured from existing artefacts or offline.

## 0. Headline

- **The 34 s is not CSS parsing, not font decoding, not the 51k head rows being styled — it is ONE 30.8 s main-thread task in which Chrome lays out
  the UA-styled (unstyled) model markup while the 50 MB `<head>` stylesheet is still pending**; the stylesheet body itself stalls behind that task
  (its `responseEnd` is 31.8 s). CSS parse + first styled recalc + 283 font fetches/decodes + first paint + load take the last 2.5 s (§1).
- Fix (offline-verified, in `combined8-c32-fast`): move the `<link>` into `<body>` (parser-blocking in Chromium → the model markup is not parsed
  until the sheet is in) and add a 280 B inline boot `<style>` (`html::before` message, `body{display:none}` until the sheet applies). Model bytes
  unchanged: `runtime.css` = reference + 53 B tail, `index.html` = reference ± the head/link bytes, witnesses 283/283 (§3). Expected load
  ≈ 3–5 s to Ready on this machine; first paint (the boot line) ≈ 0.2 s. **R6V independently built the same structure (`R6V_EARLY_PAINT`);
  the merge must take one of the two** (`R6L/split-point.md`).
- Distribution (§5): 296.4 MB to ship (HTML 7.1 + CSS 50.2 + 283 fonts 239.1), ≈243 MB on the wire with brotli text (CSS 50.2 → 3.0 MB, HTML → 0.9 MB;
  the woff2 fonts are already brotli). Largest file 56.9 MB → fits GitHub Pages (100 MB/file, 1 GB site) but its 100 GB/month soft bandwidth ≈ 330–400
  first-time loads/month; Cloudflare Pages (25 MiB/file) cannot host it. Same-origin fonts → no CORS. Chrome ≥ 139 only (`@function`). 50 Mbit/s →
  ≈40–47 s download + the load tail. Renderer 2 GB after load, 4.4–6.2 GB while generating → 16 GB machine, warn. Simplest sharing: `R6L/pack_bundle.py`
  → one folder/zip (launcher + `model/` with `fonts/`), recipient runs `python3 tools/launch_browser_gpt2.py --directory model`. Nothing was published.

## 1. Load-time attribution of `combined8-c32` (from the 32/32 run `R5X/run-combined8-c32/c32-p40.json`: 1 Hz `Performance.getMetrics`, resource/paint timing, RSS)

Headless Chrome 153, `tools/launch_browser_gpt2.py --no-open` server (HTTP/1.0), `--js-flags=--heap-growing-percent=10`, viewport 900×300. Times from navigation start.

| phase | window (s) | Δ (s) | evidence |
|---|---|---:|---|
| HTML fetch (7,125,736 B) | 0.00–0.04 | 0.04 | `responseEnd` 43.5 ms |
| HTML parse → 169,282 nodes / 86,438 elements | 0.04–0.17 | 0.13 | `domInteractive` = `DOMContentLoaded` 169 ms |
| **UA-styled style + layout of the whole model markup** (84,592 `<i>`, 780k text characters in Unicode planes 2–7: every distinct character → a system font-fallback lookup; no author sheet yet) | ≈1.0–31.8 | **30.8** | the metrics request sent at t = 1.0 s is answered at 31.8 s (main thread blocked by one task); at that point RecalcStyleCount 2 / 0.14 s, **LayoutCount 1 / LayoutDuration 31.43 s**, LayoutObjects 169,173, TaskDuration 31.74 s; renderer RSS creeps 430 → 539 MB (no CSS, no fonts in memory) |
| stylesheet body delivery (50,217,724 B) — stalled behind the blocked main thread, not by the network | (0.007–31.78) | 0 (hidden) | `runtime.css` startTime 7 ms, `responseEnd` 31,784 ms; on the same server the 7 MB HTML arrived in 43 ms |
| CSS parse (72k rules, 42k `@property`, 9.2k `@keyframes`) + first styled recalc + 2 layouts | 31.8–32.8 | ≈1.0 | at 32.8 s: RecalcStyleCount 5 / 1.22 s (+1.08 s of style), LayoutCount 3, LayoutObjects 171,788 |
| 283 font fetches (239 MB) + decode + layouts + **first paint 33.10 s** + load 34.29 s | 32.8–34.3 | ≈1.5 | resource entries 250 (buffer cap), `lastResourceEnd` 33.79 s; RSS 685 → 2,066 MB between 33.1 and 34.1 s (decoded fonts land); RecalcStyle 12 → 17, Layout 10 → 12 |
| settle → Ready/idle (`RecalcStyleCount` stable) | 34.3–36.7 | 2.4 | `fontsStatus: loaded`, 283 faces; Run at 37.3 s |

Reading: **90 % of the wait is a layout that should never happen** — Chromium blocks *painting* while a head stylesheet is pending, but it still
builds the DOM (0.17 s) and, when the compositor asks for a frame, styles and lays out the body with UA styles only. In this page that means 780k
characters in planes 2–7 (`.head-row` text is 6 astral code points per row, `𠀀𰀀…`; V leaves U+F5800; witnesses U+F0000…) rendered with the default
serif font, each distinct code point triggering a platform font-fallback search — ≈300k distinct code points × ≈100 µs. With `runtime.css` applied
those elements carry `font-family` of a webfont whose cmap covers them and the head is `content-visibility: hidden` (R2D lock), so the *styled* first
recalc + layout is only ≈1 s. The R5A/R5E worries (CSS parse of 50 MB, 39.5k `@property`, brotli of 239 MB, 51k head rows) together account for ≈2.5 s.
Caveat: one run, harness counters rather than a trace; the traced load (§4, arm `base`) will show the task as a single `Layout` event with its
`dirtyObjects`/root and the `ParseAuthorStyleSheet` and font-decode events for the tail.

## 2. Candidate changes — status and expected effect (measured columns land in `R6L/loads/SUMMARY.md`, §4)

| change | what | status | expected on this machine |
|---|---|---|---|
| **(d) stylesheet split / in-body link** (`R6L_BODY_LINK`) | `<link>` first in `<body>`; parser stops there until the sheet is in → model markup never exists unstyled; the inline `<style>` (`R6L_BOOT`) paints a one-line boot message at ≈0.2 s and hides `body` until the sheet applies | **built + offline-verified** (`combined8-c32-fast`, §3); loads armed (`bodylink` arm) | load 34 → ≈3–5 s; first paint 33 → ≈0.2 s; Ready ≈ same as load + settle |
| (d′) diagnostic: boot style only, link stays in head (`R6L_BOOT=1 R6L_BODY_LINK=0`, `bundles/R6L-hidebody`) | isolates the mechanism: if `body{display:none}` alone removes the 31 s, the culprit is the UA-styled layout (and the belt is worth keeping in R6V's variant) | built; loads armed (`hide` arm) | ≈ same load as (d) but no early paint (head sheet still render-blocking) |
| (c) defer the head's first style/layout | already the case: R2D's lock (`.full-head{content-visibility:hidden}` until `--bridge-ready:1`) holds at load; the styled first recalc of all 86k elements is 1.1 s in total; the head only hurt in the *unstyled* layout, which (d) removes | no change needed | 0 |
| (a) fonts served uncompressed (`.ttf`) | `R6L/make_ttf_twin.py` written (fontTools, 914 MB on disk) | **not measured: disk fell to 2 GB** (needs ≈1 GB + gate). Fonts are fetched only after the sheet applies, decode overlaps the fetch (RSS lands 33.1–34.1 s), and the whole fetch+decode+layout window is 1.5 s | ≤ 1 s at best; run when disk ≥ 5 GB |
| (b) CSS dedupe of the 12 per-layer variants (R5E §5, ≈10 MB / 26 %) | emitter change to the corestate rule generation; exactness would need computed-style identity, not byte identity | **not done**: parse + first styled recalc is ≈1.0 s in total, so −26 % of parse ≈ −0.2 s; not worth the numerics risk this round | ≈ −0.2 s |
| (e) parser-cost items (42k `@property`, `initial` walls) | R5E already trimmed the walls; total parse ≈ ≤ 1 s | no action | ≈ 0 |
| HTTP precompression | irrelevant on localhost (the 50 MB body arrived at wire speed once the main thread was free); decisive for hosting (§5) | `R6L/br/`: css 50.2 → 3.0 MB (br q9) / 6.1 MB (gzip -9); html 7.1 → 0.87 / 1.2 MB | — |

## 3. What shipped in `bundles/combined8-c32-fast` (no READY yet — §4)

`R6L/compile.sh` = `R5X/compile.sh` + `R6L_BODY_LINK`/`R6L_BOOT` passthrough, `VALUE_LAYOUT=widths R4S_SMALL_HOPS=0`, capacity 32, 12 blocks, 19.7 s build.
- `index.html` (7,126,006 B): `<head>` ends with `<style>html::before{content:"Loading the model stylesheet (50 MB)… Chrome parses it, then loads the 283 weight fonts (239 MB). Nothing else is shown until then.";display:block;margin:24px;font:16px/1.5 system-ui;color:#222;background:#f7f5ef}body{display:none}</style>`; `<body>` starts with `<link rel="stylesheet" href="runtime.css">`; every following byte is `combined8-c32`'s.
- `runtime.css` (50,217,769 B) = `combined8-c32/runtime.css` + `html::before{content:none}body{display:block}` (53 B; later author sheet, same specificity → the inline boot rules are overridden; `body`'s computed display is `block` before and after, `html::before` disappears).
- `R6L/check_identity.py … --expect-r6l`: html == transform(reference) ✔, css == reference + tail ✔ (prefix byte-identical), witnesses 283/283 ✔, manifest +`r6lBodyLink`,`r6lBoot`; `launch_browser_gpt2.py --check`: 285 static files, 296,449,715 B, no JavaScript ✔. **Flag-off twin** (`R6L_BODY_LINK=0 R6L_BOOT=0`, built in `R6L/scratch`, deleted): `index.html` byte-identical to `combined8-c32` (6,221,102 B), `runtime.css` identical after `../`-depth normalisation (the scratch dir is one level deeper: +849 B = 283 url() × `../`), witnesses 283/283, manifest +2 keys → the owners' flag-off method PASSes.
- Cascade/semantics: no model rule, declaration, element, font or `:has()` chain changed (R2G/R5E passes see a `<link>` as an extra body child, which is on no ancestor path). The SVG SMIL timelines and `#run` logic start when the sheet applies, exactly as before (they never ran unstyled). `R6L_BOOT_TEXT` changes the message.
- **Merge with R6V**: `R6V_EARLY_PAINT` also moves the link into the body (after the controls + a CSS-phase panel). Take R6V's variant in the merged bundle and set `R6L_BODY_LINK=0 R6L_BOOT=0`; if the `hide` arm shows Chrome laying out UA-styled content *before* a body link, add `body{display:none}` (inline) + `body{display:block}` (sheet tail) to R6V's variant — the two strings are in `r6l_boot.py`.

## 4. Chrome measurements (armed; results self-report)

Gate closed all session (§ header). Armed with `R6L/gate_wait.sh` (polls 60 s, ≤ 4 h) → `R6L/with_lock.sh` (mkdir `CHROME.lock`, owner `R6L <label> <pid> <time>`, touch 30 s, rmdir only mine, watchdog):
1. `R6L/session1.sh` (cap 1,500 s): `load_inner.sh` = the user's server (`launch_browser_gpt2.py --no-open`) + `R6L/load_native.mjs` (headless Chrome 154, Playwright 1.62; load event, first paint, Ready = `#fonts-loaded.done`, idle, metrics every 250 ms, RSS 1 Hz; run 1 of each arm with a light trace: blink, blink.style, blink.resource, devtools.timeline, loading, v8.gc, fonts): **`combined8-c32` ×3, `R6L-hidebody` ×2, `R6L-bodylink` ×3** → `R6L/loads/<arm>/*.json`, `R6L/loads/SUMMARY.md` (mean [min…max] per arm), log line in `R6L.log.md`.
2. `R6L/session2.sh` (after 1, cap 2,500 s): ONE passive prompt-40 32-token run of `combined8-c32-fast` (`R6L/c32_inner.sh`, R4M harness, keyboard trigger) vs `R4P/reference_ids_32_40.json` → `R6L/run-combined8-c32-fast/c32-p40.summary.md`; **creates `bundles/combined8-c32-fast/READY` iff 32/32**.
Not armed: (a) `.ttf` arm (disk), cap-8 twin 8/8 (the change does not touch the core: identical CSS prefix and model markup — the c32 32/32 is the acceptance), 5-load B7 protocol (B7's).
Manual re-run when the machine is quiet: `R6L/with_lock.sh s1 1500 R6L/session1.sh`; headed like the user: `B0_HEADED=1 R6L/load_inner.sh combined8-c32-fast headed 1`.

## 5. Distribution — can this be given to other people?

**Bytes (from `R6L/pack_bundle.py --dry-run` on `combined8-c32-fast`; every referenced file resolved, 283 fonts, no basename collisions):**

| part | files | bytes | on the wire with precompression |
|---|---:|---:|---|
| `index.html` | 1 | 7,126,006 | br q9 873 KB (q11 smaller), gzip -9 1.2 MB |
| `runtime.css` | 1 | 50,207,351 | **br q9 3.0 MB**, gzip -9 6.1 MB (97 % of the sheet is repeated structure) |
| fonts `.woff2` | 283 | 239,105,940 (largest `embedding-lookup.woff2` 56,853,724; head faces 16.4 ×3 + 9.8 ×3 MB; 276 stage faces ≤ 1.0 MB) | as is (woff2 = brotli inside; re-compressing gains nothing; do not gzip them) |
| **total** | 285 | **296,439,297 B (296 MB)** | **≈ 243 MB** (br) / ≈ 246 MB (gzip) |

**Static hosting:** every file < 100 MB and the site is 0.3 GB, so GitHub Pages' hard limits are met (100 MB per file at push, 1 GB published site); its
**100 GB/month soft bandwidth cap ≈ 330–400 first-time visitors/month** (243–296 MB each; repeat visits hit the browser cache if the fonts are served
immutable — they already carry `?v=<digest>`); Pages gzips text on the fly, so `runtime.css` ships as ≈6 MB there. Cloudflare Pages (25 MiB per asset)
**cannot** host it as is (the 57 MB embedding font and the 50 MB CSS exceed it). S3+CloudFront / nginx / any plain static server work; note CloudFront
only compresses on the fly below 10 MB, so upload `runtime.css.br` with `Content-Encoding: br` yourself (or `brotli_static on` in nginx).
`tools/serve_precompressed.py` is the local model of the right behaviour (selects `.br`/`.gz`, sets `Content-Encoding`, `Vary`, immutable cache on `?v=` URLs).
**Headers:** fonts are same-origin → no CORS headers needed (move them to a CDN origin and every `@font-face` fetch needs `Access-Control-Allow-Origin`);
`runtime.css` must be served as `text/css` (Chrome rejects mistyped stylesheets in standards mode); fonts `font/woff2`; the CSP is already a `<meta>` in
the HTML (`script-src 'none'`), so no server CSP is required; cache fonts immutable, `index.html`/`runtime.css` `no-cache` (no digest in their URLs).
**Chrome-only:** the sheet uses `@function` (Chrome 139, Aug 2025 — the README's stated floor), `if()` (137), `calc-size()` (129), anchor positioning
`anchor-name`/`anchor-size()` (125), `round()/mod()/rem()` (125), view timelines + `timeline-scope` (115/116), `@container style()` queries (111),
`:has()` (105), `@property` + `content-visibility` (85), `pow()/exp()/log()` (120), `abs()/sign()` (135), `transition-behavior` (117), SVG SMIL
(`<set>`), `font-variation-settings`. **Minimum: Chrome/Chromium/Edge 139** (tested on 153/154). Firefox and Safari lack `@function`, `if()`,
`calc-size()` and anchor positioning → the page does nothing there.
**Download time:** at 50 Mbit/s (6.25 MB/s) 296 MB ≈ 47 s uncompressed, ≈ 39 s with brotli text; then the load tail (≈ 3–5 s with the fix, 34 s
without). 100 Mbit/s ≈ 20 s; 20 Mbit/s ≈ 100 s. Ready is gated on the last of the 283 fonts (the witness barrier), so the wait is the full download.
**Memory:** renderer ≈ 2 GB after load, 4.4 GB RSS / 6.2 GB footprint during 32-token generation (R5A/R5G) → **16 GB machines only; on 8 GB the tab
will be discarded or swap for minutes**; warn recipients, and tell them to close other browsers.
**Simplest recipe (nothing published):** `python3 work/2026-09-19/R6L/pack_bundle.py bundles/combined8-c32-fast <out> --br` → `<out>/tools/launch_browser_gpt2.py`
(verbatim copy of the repo launcher; stdlib Python 3) + `<out>/model/{index.html,runtime.css,fonts/}` (URLs rewritten to `fonts/<name>?v=…`) + `README.txt`;
zip `<out>` (≈300 MB) → recipient: `unzip; python3 tools/launch_browser_gpt2.py --directory model` (opens a separate Chrome profile with JS disabled,
serves only the allow-listed files). Hosted alternative: upload `<out>/model` to a static host with the headers above and share the URL; the recipient
needs Chrome ≥ 139 and 16 GB. (Not run for real this session: 300 MB of copies with 2 GB of disk free; the dry run resolved every file.)

## 6. Risks / not done

- The whole Chrome-side table (§2 measured columns, §4) is pending the gate; the attribution rests on one recorded run's counters (very sharp: one task, one layout).
- Parser-blocking of a body `<link>` is Chromium behaviour, not a spec guarantee; the `body{display:none}` belt covers a Chrome that lays out already-parsed body content anyway. The `hide` arm measures that case.
- Two implementations of the same page change exist (R6L, R6V) — a merge must pick one (§3).
- `.ttf` arm and the CSS dedupe not measured/done (disk; expected ≤ 1 s and ≈ 0.2 s respectively).
- Disk: `bundles/R6L-bodylink`, `bundles/R6L-hidebody` (57 MB each, timing twins; delete after session 1), `R6L/br` 11 MB, `R6L/tools` copy.
