# C1 — Per-token cost model of the recommended CSS-only TinyStories pipeline

Scope: `tinystories/streaming-packed8.html` (the README's "recommended compressed experiment", README.md:182-193). Model: `calum/tinystories-gpt2-3M`, d=64, H=16 (head width 4), L=8, V=50,257, rolling KV window W=8 (7 cached slots + current), 16 predeclared stages. All numbers below are either (a) read from the emitter source, (b) counted in the emitted CSS with `grep -c`/byte offsets, or (c) quoted from the repo's measurement files. Inferences about Chromium internals are labelled **[inference]**.

Read-only audit. Log: `audit/2026-09-18/C1-cost-model.log.md`.

---

## 0. What the page is, physically

`streaming-packed8.html` (4,317 B) links four stylesheets (`tools/build_tinystories_nested.py:300-303`, selection of head file at :238-240):

| File | Bytes on disk | Built by | Role |
|---|---:|---|---|
| `output-head-benchmark/generated/clustered-256-embedding-packed8-shared-runtime.css` | 125,344,932 | `tools/build_clustered_output_head_benchmark.py` (`build_packed_feedback(3, True)`, :731-807) | output head: 50,257 `--dN()` token-dot functions, 256 `--dcN()` cluster maxima, 256 `--dtN()` winner recovery, 5,632 `--peCxP()` packed embedding lookups, 2,415 registered props, 3 `.model{}` rules |
| `tinystories/recurrent.css` | 21,049,908 | `tools/build_tinystories_recurrent.py` (`compile_recurrent_graph`, :137-546) | one-position transformer + KV shift; 28,323 `@property`, 40 `.model{}` rules, dead animation clock |
| `tinystories/nested-runtime.css` | 2,534,887 | `tools/build_tinystories_nested.py:103-126` | 7,238 re-registrations (`inherits:true`), 9 `.handoff{}` copy rules (7,235 decls), 197 decoder functions |
| `tinystories/streaming.css` | 1,547 | `tools/build_tinystories_nested.py:129-173` | gate: `--gate-open`, 1 ms keyframe, `content-visibility:if(style(--gate-open:1)…)`, pause control |
| HTML | 4,317 | `:176-188, 295-320` | 16 nested `<div class="model nested-model">` each containing `<span class="token-output">` + `<div class="handoff">` (next model inside) |

Sum on disk = 148,935,591 B. OPTIMIZATIONS.md:184-192 documents 148,926,533 B (difference +9,058 B explained in §6).

DOM per stage k: `M_k (.model)` → `T_k (.token-output)` + `H_k (.handoff)` → `M_{k+1}` … (`build_tinystories_nested.py:176-188`). All 16 `M_k` match the same `.model` rules from both big stylesheets; nothing is duplicated per stage in CSS.

---

## 1. How each construct is emitted (the emitter IS the cost model)

### 1.1 Transformer (`recurrent.css`)

`CssCompiler` (`tools/build_tinystories_step.py:140-209`):
- `dot(name, vector, weights, bias)` → **one** `--name:calc(b + (var(--x0))*w0 + … + (var(--x63))*w63)` (:163-175). One registered `<number>` property per output neuron; 64 (or 256) products inside one `calc()`. Emitted sample: `--ts-l0-qkv-0:calc(-.184246331 + (var(--ts-l0-ln1-out-0))*-.007960155 + …`.
- `normalize()` → mean (1 calc, 64 adds), 64 `center` calcs, variance (1 calc, 64 squares), inverse `calc(1/sqrt(v + 1e-05))`, 64 `out` calcs = **131 registered props per LayerNorm** (:182-209).
- `maximum()` → one `max(a,b,…)` (:177-180).
- Every name passed through `raw/calc/dot/input` is appended to `compiler.names` and **registered** as `@property … syntax:"<number>"` (`build_tinystories_recurrent.py:453-458`) — `inherits:true` only for `input()` names (the `--ts-k/v-*` cache inputs), `inherits:false` for everything else. So every intermediate in the transformer is an eager, typed, registered custom property on `.model`.
- Attention per head (`:192-258`): 7 cached scores each `calc((active)*((4 products)/2.0) + (1-(active))*-999999)` (masking of unfilled slots via `--ts-source-active-s:if(style(--ts-length:…):1;else:0)`, :125-134), 1 current score, `max()` of 8, 8 `exp()`, 1 denominator, 8 probabilities, 4 attended outputs each an 8-term weighted sum. No `@function` here.
- GELU: `--ts-lL-gelu-u:--gelu(var(--ts-lL-fc-u))` (:290-292) → the single shared `@function --gelu` (`tools/build_pretrained_gpt2.py:37-45`: 5 locals, 1 `clamp`, 1 `exp`). 2,048 invocations per stage.
- KV cache shift (`:332-355`): for each of 2 kinds × 8 layers × 7 slots × 64 dims = **7,168** registered props `--ts-next-k-L-s-d:if(style(--ts-length:s):<new k>; style(--ts-length:7):var(--__1k-L-(s+1)-d); else:var(--__1k-L-s-d))` — 2 `style()` self-queries each.
- Positional embedding: 64 props `--ts-position-value-d:if(style(--ts-position:0):…;… 20 cases)` (:149-156); input `--ts-input-d:calc(var(--__1embedding-d) + (pos))` (:157-163).
- State bank (`:367-446`): unregistered `--__1X:var(--__2X, <prompt fallback>)` (7,251 decls) and registered interface `--ts-X:var(--__1X)` (7,188 decls). The execute/store `@keyframes` (:507-533) exist in the file but are disabled by `.nested-model{animation:none!important}` (`build_tinystories_nested.py:118`).

### 1.2 Output head (`clustered-256-embedding-packed8-shared-runtime.css`)

Emitted order (byte offsets measured): `--dN()` 0–80,638,875 → `--dcN()` –82,190,951 → `--dtN()` –87,752,885 → `--peCxP()` –124,407,078 → 2,415 `@property` –124,570,878 → 3 `.model{}` rules (774,054 B) to EOF. Matches `clustered-256.json.packed8_component_bytes` exactly.

| Construct | Emitter | Emitted shape (verified) | Count | Bytes |
|---|---|---|---|---:|
| token dot `--dN()` | `shared_token_function` :238-249 | `@function --d0() returns <number>{result:calc(var(--h0)*-.15104419 + … 64 terms);}` | 50,257 | 80,638,875 (avg 1,604 B) |
| cluster max `--dcN()` | `shared_cluster_function` :281-311 | `--l0:--d187(); … ; --m0x0:max(var(--l0),…32); … result:var(--m1x0)` | 256 (sizes min 43 / median 197 / max 520, mean 196.3 — counted from emitted bodies) | 1,552,076 |
| winner recovery `--dtN(--target)` | `shared_cluster_token_function` :390-426 | per row `--lI:--dT(); --tI:calc((1 - max(0,sign(abs(var(--lI) - var(--target)) - 1e-4)))*T);` then 32-ary `calc(+)` sum tree | 256 | 5,561,934 |
| packed embedding `--peCxP()` | `packed_embedding_function` :194-212 | `result:if(style(--winner-id:187):4935792; … one case per member token; else:0)` | 22 packs × 256 = 5,632 | 36,654,193 |
| `.model` eager graph | :474-604, :755-779 | see §2.2 | 2,415 decls, all registered `inherits:false` (`registration()` :57-60) | 774,054 |

Head `.model` dataflow (all confirmed in the emitted rules):
1. `--hnorm:sqrt(calc(Σ var(--hd)*var(--hd)))` (:474-482).
2. 256 bounds `--uN:calc(Σ_d var(--hd)*center_d + var(--hnorm)*radius)` (:483-492) → 32-ary registered `max()` tree `--um0x0..7`, `--um1x0` (`reduce_registered` :63-83).
3. Seed pick: per cluster `--sdN:calc(abs(var(--uN) - var(--um1x0)))`, `--siN:calc(1 - max(0,sign(var(--sdN) - .000001)))`, `--stN:calc(var(--siN)*N)`; `--seed:calc(Σ --stN)` (:498-515).
4. `--seed-best:if(style(--seed:0):--dc0();style(--seed:1):--dc1();… 256 cases; else:-999999)` (:517-522, `--cN(...)` rewritten to `--dcN()` at :780-790) — **lazy**: one cluster function evaluated.
5. `--aN:calc(1 - max(0,sign((var(--seed-best) - var(--uN)) - .000001)))`; `--zN:if(style(--aN:1):--dcN();else:-999999)` (:525-538) — **lazy**: only clusters whose bound beats the seed score are invoked.
6. `--fm*` 32-ary max tree → `--maximum`; `--active-count` (:539-550).
7. Winner cluster: `--wcdN/--wciN/--wctN` (768 props) → `--winner-cluster:calc(Σ)` (:576-597); `--winner-id:if(style(--winner-cluster:N):--dtN(var(--maximum)); …256 cases; else:-1)` (:598-604) — one `--dt` invoked, which re-invokes every `--dN()` of the winning cluster.
8. `--feedback-pack-P:if(style(--winner-cluster:N):--peNxP(); …256 cases; else:0)` ×22 (:755-764); `--nextd:calc((mod(round(down,calc(var(--feedback-pack-P)/256^o),1),256) - 127)*scale_d)` ×64 (:767-779). Registered typed `<number>` throughout (24-bit integers survive; 48-bit did not — compression-analysis.json `css_number_precision_probe`).

### 1.3 State handoff + decoder (`nested-runtime.css`, `streaming.css`)

- `state_pairs()` = 3 scalars + 64 embedding + 2·8·7·64 KV = **7,235** pairs (`build_tinystories_nested.py:40-60`).
- Re-registration: `@property --ts-next-*|--nextd {syntax:"<number>";inherits:true}` for all 7,235 outputs (:108-111) — overrides the `inherits:false` registrations in `recurrent.css`/head so the child can see them.
- `.handoff{--__2X:var(--ts-next-X); …}` in 8×1000+1 chunks (:112-116) — **unregistered → inherited by default**.
- Child `.model` then runs `--__1X:var(--__2X,fallback)` → `--ts-X:var(--__1X)` (from `recurrent.css`). So one KV coordinate crosses a stage boundary through **4 declarations**: parent `--ts-next-k…` (registered if()) → handoff `--__2k…` → child `--__1k…` → child `--ts-k…` (registered).
- Decoder (:63-100): `.token-output{--token-id:var(--winner-id); --token-bucket:round(down,calc(var(--token-id)/256),1); --token-piece:if(style(--token-bucket:0):--decode-token-0(); … 197 cases; else:"")}`; each `--decode-token-B() returns <string>` is an `if()` with 256 `style(--token-id:T):"text"` cases; `::after{content:var(--token-piece)}`.
- Gate (`streaming_css` :129-173): `.streaming-page .handoff{--gate-open:0; display:inline-block; content-visibility:if(style(--gate-open:1):visible;else:hidden); contain-intrinsic-size:auto 1lh}`; `@container style(--winner-id){.streaming-page .handoff{animation:ts-open-gate 1ms steps(1,end) both}}`; `@keyframes ts-open-gate{to{--gate-open:1;display:inline}}`; pause via `#pause-generation:checked ~ .story .handoff{animation-play-state:paused}`. **See §6.1: the on-disk `streaming.css` is missing the `@container` rule.**

---

## 2. Per-stage component table (one generated token = one `.model` element M_k plus its `.handoff` and `.token-output`)

Symbols: d=64, L=8, H=16, C=7 cached slots (W=C+1=8), F=4d=256, K=256 clusters, V=50,257, m̄=V/K≈196, P=⌈d/3⌉=22 packs, r = fraction of token rows the ball bounds fail to prune (offline mean 9,962/50,257 = 0.198 over 72 states; fixed-prompt `expected_active` = 50/53/62 clusters, `clustered-256.json:18`).

### 2.1 Transformer block (per layer; measured layer-0 byte spans from `recurrent.css` offsets)

| Component | Registered props | `calc()` | Arithmetic terms (per layer) | `@function` calls | Bytes/layer | Scaling |
|---|---:|---:|---|---:|---:|---|
| LN1 | 131 | 131 | 64 add (mean), 64 sub, 64 mul+63 add (var), 1 sqrt/div, 64×(2 mul+1 add) | 0 | 16,845 | 2d+3 props, ~6d ops |
| QKV matvec | 192 | 192 | 12,288 mul + 12,288 add (+192 bias) | 0 | 487,968 | 3d props, 3d² MAC |
| Attention (16 heads × 8 slots) | 480 (+7 shared `--ts-source-active`) | 336 | 512 mul (scores) + ~224 mask ops, 16 `max(8)`, 128 `exp`, 128 div, 512 mul + 448 add (attended); 14,336 KV inputs read via `var()` | 0 | 91,819 | 30·H props, 2·d·W MAC, H·W exp |
| out-proj + residual1 | 64 + 64 | 128 | 4,096 MAC + 64 add | 0 | 173,420 | 2d props, d² MAC |
| LN2 | 131 | 131 | as LN1 | 0 | 17,742 | |
| MLP up d→4d | 256 | 256 | 16,384 MAC | 0 | 650,796 | 4d props, 4d² MAC |
| GELU | 256 | 0 (5 locals+1 clamp+1 exp inside each call) | 256 × (~10 ops + 1 exp) | **256** | 11,300 | 4d calls |
| MLP down 4d→d + residual2 | 64 + 64 | 128 | 16,384 MAC + 64 add | 0 | 613,385 | 2d props, 4d² MAC |
| **Per layer** | **1,702** | **~1,302** | **~50.2k mul, ~50k add, 384 exp** | **256** | **2,064,600** (avg over 8) | 26.6·d props, 12d²+2dW MAC |
| **×8 layers** | 13,616 | 10,416 | ~401k mul (MODEL_CANDIDATES.md says 393,216 — excludes attention) | 2,048 | 16,516,796 | |
| Embedding input + 64 positional `if()` (20 cases) + 7 `active` | 135 | 64 | 64 add; 1,280+28 `style()` tests | 0 | ~52,000 | d·positions cases |
| Final LN + `--h0..63` | 195 | 131 | | 0 | ~20,700 | |
| KV shift `--ts-next-k/v-*` | **7,168** `if()` | 0 | 14,336 `style()` tests | 0 | 921,279 | 2·L·C·d |
| KV interface `--ts-k/v-*:var(--__1…)` (+20 misc) | **7,188** | 0 | 7,188 `var()` | 0 | 235,111 | 2·L·C·d |
| Bank `--__1*:var(--__2*,fallback)` | 0 (7,251 **unregistered, inherited**) | 0 | 7,251 `var()` | 0 | 282,697 | 2·L·C·d + d |
| next-length/position/step + 16 `--ts-next-output` | 19 | 3 | 16 `style()` | 0 | ~1,500 | |
| **Transformer total evaluated per stage** | **28,301 registered** (`recurrent.json.properties`) + 7,251 unregistered = 35,572 decls | **10,619** | **~407k mul, ~465k `var()` substitutions, 1,024 exp (+2,048 in gelu), 22,911 `style()` tests** | **2,048** | **≈18.0 MB** re-evaluated | |
| Parse-once only | 28,323 `@property` (2,191,441 B) + dead clock/`@keyframes ts-store/execute` (828,049 B) | | | | 3.02 MB | |

Note: **51% of the transformer's registered properties are KV plumbing** (7,168 inputs + 7,168 shifts), not arithmetic; the KV path scales as 4·L·C·d declarations per stage across parent/handoff/child.

### 2.2 Output head (per stage)

| Component | Registered props | `calc()`/`max()`/`if()` | Arithmetic | `@function` invocations | Bytes touched | Scaling |
|---|---:|---|---|---:|---:|---|
| `--hnorm` | 1 | 1 calc + sqrt | 64 mul, 63 add | 0 | ~1.6 KB | d |
| Cluster bounds `--uN` | 256 | 256 calc | 16,640 MAC (K·(d+1)) | 0 | ~410 KB | K·d |
| Bound max tree `--um*` | 9 | 9 `max()` | 264 var | 0 | ~2 KB | K/32 |
| Seed select `--sd/--si/--st/--seed` | 769 | 769 calc | 256×(abs,sub,sign,max,mul) + 256 add | 0 | ~40 KB | 3K |
| `--seed-best` | 1 | 1 `if()` 256 cases | | **1 `--dc`** → m̄ `--d` + ~7 `max()` | ~11 KB + 196×1.6 KB | m̄·d |
| Active flags `--aN` | 256 | 256 calc | 256×(sub,sign,max) | 0 | ~20 KB | K |
| Cluster results `--zN` | 256 | 256 `if(style(--aN:1))` | | **~52 `--dc`** → **~9,962 `--d`** (r·V) + ~400 `max()` | 256×~45 B + 9,962×1,604 B ≈ **16.0 MB** | r·V·d |
| Max tree `--fm*`, `--maximum`, `--active-count` | 11 | 9 max + 2 | 256 add | 0 | ~4 KB | K/32 |
| Winner cluster `--wcd/--wci/--wct/--winner-cluster` | 769 | 769 calc | as seed | 0 | ~40 KB | 3K |
| `--winner-id` | 1 | 1 `if()` 256 cases | | **1 `--dt`** → m̄ `--d` again + m̄ tolerance calcs (abs, sub, sign, max, mul) + sum tree | ~11 KB + ~22 KB body + 196×1.6 KB | m̄·d |
| Feedback packs `--feedback-pack-P` | 22 | 22 `if()` × 256 cases | 5,632 `style()` tests | **22 `--pe`** each an `if()` with m̄ cases (~4,312 `style()` tests) | 22×11.5 KB + 22×~6.5 KB | P·(K+m̄) |
| Unpack `--nextd` | 64 | 128 calc + 64 round + 64 mod | 64×5 ops | 0 | ~7 KB | d |
| **Head total per stage** | **2,415 registered, all eager** | 2,180 calc, 18 max, 280 `if()` | eager ≈ 17.5k MAC + ~3.6k misc; **lazy ≈ (r·V + 2m̄)·d ≈ 662k MAC** | **≈ 10,354 `--d` + ~53 `--dc` + 1 `--dt` + 22 `--pe` ≈ 10,430** | **≈ 17.8 MB** re-evaluated of 125.3 MB | |

Row-evaluation multiplicity: the seed cluster's rows are evaluated twice (in `--seed-best` and again in `--z_seed`, since `--a_seed` is trivially 1), and the winning cluster's rows a third time inside `--dtW`. That is ≈2m̄ ≈ 392 extra `--d()` invocations (~4% of head work). Chromium does not memoize `@function` results across call sites **[inference from Blink design; consistent with docs never claiming memoization]**.

### 2.3 State handoff (per stage boundary M_k → M_{k+1})

| Step | Element | Declarations | Registered? | `var()` | Bytes |
|---|---|---:|---|---:|---:|
| Parent computes `--ts-next-*` (7,168 KV `if()`s + 3 scalars) and `--next0..63` (head unpack) | M_k | 7,235 | yes (`inherits:true` via re-registration) | 21.5k | 921 KB (counted in §2.1) |
| Copy into handoff `--__2X:var(--ts-next-X)` | H_k | **7,235** | **no (unregistered → inherited)** | 7,235 | 272,362 |
| Child bank `--__1X:var(--__2X,fallback)` | M_{k+1} | 7,251 | no (unregistered → inherited) | 7,251 | 282,697 |
| Child interface `--ts-X:var(--__1X)` | M_{k+1} | 7,188 | yes | 7,188 | 235,111 |
| **Per boundary** | | **≈28.9k declarations, 7,235 values × 4 hops** | 7,238 `@property` in nested-runtime (562,629 B parse-once) | ~43k | ~1.7 MB |

Scaling: 2·L·C·d + d + 3 properties per hop. Doubling the window or layers doubles handoff cost linearly; doubling d doubles it too.

### 2.4 Decoder + gate (per stage)

| Item | Declarations | Work | Bytes touched |
|---|---:|---|---:|
| `.token-output` | 3 (`--token-id` reg, `--token-bucket` reg, `--token-piece` unreg) + `::after content` | 1 `round`, 1 `if()` with 197 `style()` tests → 1 `--decode-token-B()` with 256 `style()` tests → string | ~9 KB rule + ~8.5 KB function (of 1.68 MB decoder) |
| `.handoff` gate | `--gate-open`, `content-visibility:if(style(...))`, `display`, `contain-intrinsic-size`, animation | 1 container style query against M_k; 1 custom-property animation (1 ms) | ~0.5 KB |
| Layout/paint | | reattach H_k layout tree (`inline-block`→`inline`), lay out one more inline text run in `.story`, paint | — |

### 2.5 Per-stage totals

| Metric | Transformer | Head | Handoff/bank | Decoder+gate | **Total per token** |
|---|---:|---:|---:|---:|---:|
| Declarations evaluated | 35,572 | 2,415 | 14,486 (H_k 7,235 + M_{k+1} bank 7,251; interface counted in transformer) | ~8 | **≈52.5k** |
| `@function` invocations | 2,048 (`--gelu`) | ≈10,430 | 0 | 2 | **≈12.5k** |
| Function-local properties materialised | 2,048×6 = 12,288 | ~53×~203 + ~600 + 0 ≈ 11.4k | 0 | 0 | **≈23.7k** |
| `var()` substitutions | ≈465k | ≈700k | ≈14.5k | 4 | **≈1.18M** |
| Multiplications | ≈407k | ≈680k | 0 | 0 | **≈1.09M** |
| `style()` tests | 22,911 | ~10.7k (256+256+256+5,632+4,312) | 0 | ~453 | **≈34k** |
| `exp()` | 3,072 | 0 | 0 | 0 | 3,072 |
| CSS source bytes re-tokenised/re-parsed | ≈18.0 MB | ≈17.8 MB | ≈0.79 MB | ≈0.02 MB | **≈36.6 MB (24.6% of page)** |

---

## 3. Where the 148.9 MB goes, and which bytes are re-evaluated per stage

Reconciliation with OPTIMIZATIONS.md:184-192 (all component figures reproduced exactly from `clustered-256.json.packed8_component_bytes` and byte offsets):

| OPTIMIZATIONS.md component | Bytes | Verified location | Parse-once | Re-evaluated per stage |
|---|---:|---|---:|---:|
| Full-vocabulary token dot functions | 80,638,875 | head 0–80,638,875 (50,257 × ~1,604 B) | 64.0 MB (≈40k unpruned rows) | **≈16.6 MB** (≈10.35k invocations incl. seed/winner repeats) |
| Packed winning-embedding lookup | 36,654,193 | head 87,752,885–124,407,078 (5,632 fns) | 36.5 MB | ≈0.14 MB (22 fns) |
| Incremental transformer and KV cache | 21,049,908 | `recurrent.css` | 3.0 MB (2.19 MB `@property` + 0.83 MB dead keyframes) | **≈18.0 MB** |
| Per-token winner recovery | 5,561,934 | head 82,190,951–87,752,885 | 5.54 MB | ≈0.02 MB (1 fn) |
| Nested state handoff and decoder | 2,525,724 (on disk 2,534,887) | `nested-runtime.css`: 562,629 B registrations, 272,362 B `.handoff`, 1,681,046 B decoder, ~19 KB rules | 2.25 MB | ≈0.29 MB |
| Cluster maxima | 1,552,076 | head 80,638,875–82,190,951 | 1.24 MB | ≈0.31 MB (~53 fns) |
| Registrations, runtime rules, streaming CSS, HTML | 943,823 | head `@property` 163,800 + head `.model` 774,054 + streaming.css 1,547 + HTML 4,317 (= 943,718; +105 B gate rule missing on disk) | 0.17 MB | **0.77 MB (all 2,415 head decls are eager)** |
| **Total** | **148,926,533** | | **≈112.6 MB (75.6%)** | **≈36.3 MB (24.4%)** |

So three-quarters of the page is parsed once and then sits in the CSSOM (this is where the 1.66 GB RSS comes from: Blink keeps declaration text/tokens plus `StyleRuleFunction` objects for 56,401 functions and 37,976 `@property` registrations — ~11 B of heap per source byte **[inference]**). One quarter — split almost evenly between the transformer circuit and the surviving token-dot bodies — is re-processed on every stage.

---

## 4. What Chromium has to do per stage **[inference unless marked measured]**

**4.1 Style-recalc passes.** Stage k+1 begins when H_k's 1 ms animation reaches its `to` keyframe: `--gate-open:1` → `content-visibility` resolves to `visible` → the display-lock on H_k's subtree is released → M_{k+1}, T_{k+1}, H_{k+1} are styled for the first time, in the **same** recalc pass as H_k's animation update. That pass is the heavy one (~52k declarations, ~12.5k function invocations, §2.5). In the same pass H_{k+1} matches `@container style(--winner-id)` against its container M_{k+1} and receives the gate animation. The animation then needs ≥1 frame to start and ≥1 ms to finish, so the next heavy pass happens ≥1–2 vsync intervals later. Net: **one heavy style pass + one or two trivial animation-tick passes + one layout/paint per token**. The docs' "keeps stages in separate style passes" (README.md:175) matches this.

**4.2 Why a gate at all, and why 1 ms.** Without `content-visibility:hidden`, Blink styles the whole nested chain in one synchronous recalc (that is `nested.html`; README.md:169 "may batch several stages into one paint") — nothing paints until all 16 stages finish. A style-query-driven `content-visibility` with no animation would flip inside the same pass as the parent's computation, so there would still be no pass boundary. The animation is the only CSS-only device that defers a computed-value change to a later frame. The 1 ms (vs 0 ms) duration guarantees the `to` state is applied on a subsequent animation tick rather than being treated as already-finished on creation; its cost is ≤2 frames (~17–33 ms, 2–4% of a stage). The gate is not a throughput bottleneck; it is what makes per-token painting possible.

**4.3 What is invalidated when the parent's winning embedding "changes".** In the streaming page nothing on M_k changes after it is computed. The only mutations per stage are on H_k: `--gate-open` (registered, `inherits:false`) and `display` (`inline-block`→`inline`). Changing `display` type forces Blink to re-attach H_k's layout subtree (LayoutBlockFlow→LayoutInline), which includes the just-unlocked M_{k+1} boxes — cheap because only a handful of boxes exist below the lock. Ancestors (M_1..M_k) are not restyled. Because all state flows parent→child by inheritance and `var()`, there is no cascade back up.

Inheritance cost that *is* incurred: M_k declares ≈21.7k inherited custom properties (7,168 `--ts-k/v` `inherits:true`, 7,235 `--ts-next-*`/`--next*` `inherits:true`, 7,251 unregistered `--__1*`); H_k adds 7,235 unregistered `--__2*`; T_k adds `--token-piece`. Each element that declares an inherited custom property copies its parent's inherited-variables map (copy-on-write) — three copies of a ~29k-entry map per stage, plus AtomicString hashing. Estimate 5–20 ms per stage. Map size does not grow with depth because every stage overwrites the same names.

**4.4 Whole head or pruned clusters?** Pruned. Emitted `--zN:if(style(--aN:1):--dcN();else:-999999)` (head `.model` rule; emitter :535-538) means only clusters with `--aN=1` invoke their `--dc`. Eager portion = 2,415 registered declarations (all of §2.2's non-function rows), ≈17.5k MACs, negligible. Lazy portion ≈ 19.8% of rows on average (measured offline, output-head-benchmark/RESULTS.md:73; fixed-prompt active clusters 50–62 of 256, `clustered-256.json:18`). The docs' statement "Registered custom properties are eager… custom functions are lazy" (output-head-benchmark/RESULTS.md:93-95) is consistent with the emitted structure. Adversarial worst case (no pruning) is 256 `--dc` → all 50,257 `--d` → ≈80.6 MB re-tokenised per stage; the dense eager variant measured 1.70–1.73 s (RESULTS.md table row "Registered-property graph"), so worst case ≈ 2 s/token.

**4.5 Re-parsed or re-evaluated?** `@function` bodies are parsed into `StyleRuleFunction` once at sheet load; per invocation Blink substitutes arguments/locals and `var()` references into the body's token stream, then **parses the substituted tokens into a fresh `calc()` expression tree and evaluates it** — there is no cached compiled arithmetic. Registered `.model` declarations behave the same: substitution → typed parse → evaluate → the result is serialised back to text/tokens when another `var()` consumes it. So per stage, ≈36 MB of source-equivalent tokens flow through tokenizer → substitution → math-expression parser → evaluator. Sanity check against measurements: 857 ms/token over ≈36.6 MB ≈ 42 MB/s, or ≈0.73 µs per `var()` substitution, or ≈0.8 µs per multiply term — the right order of magnitude for a token-stream calc() evaluator, and it explains why byte-shortening the literals (`0.5`→`.5`) gave ~1% (README.md:203-206): tokenisation is only part of the pipeline; node allocation and substitution dominate.

**4.6 `--d` bodies under `--dc` vs `--dt`.** `--dt` (5.56 MB) is invoked once per stage but re-invokes every `--d` of the winning cluster and adds five ops per row; it exists only because Chromium needs a 1e-4 tolerance remap from max value back to ID. The score-token packed variant that removes it was measured ~4% *slower* (RESULTS.md:155-163), which indicates the max-tree over large packed integers costs more than the 196 extra rows.

**4.7 Anomaly worth flagging.** The untyped 48-bit feedback variant differs from the recommended page only in 11 (vs 22) `--feedback-pack` declarations being unregistered and 2,816 `--pe` functions returning untyped values, yet it painted 27% slower (17.4–17.9 s vs 12.8–12.9 s, RESULTS.md:105-109). Nothing in the emitted arithmetic explains ~300 ms/stage; the most plausible mechanism is that unregistered `--feedback-pack-P` values are *inherited* and are re-substituted/re-evaluated in descendants, or that untyped `if()` results are stored as unevaluated token streams and re-evaluated by each of the 64 `--nextd` consumers. Either way it is evidence that **substitution/inheritance mechanics, not arithmetic, can dominate** — and that the same mechanics may be silently taxing the 7,235 unregistered `--__1*/--__2*` handoff properties.

---

## 5. Fixed vs variable cost

| Class | What | Size / count |
|---|---|---|
| **O(1) per page — parse once** | 148.9 MB CSS → CSSOM: 56,401 `@function` rules (50,257 `--d`, 256 `--dc`, 256 `--dt`, 5,632 `--pe`; +197 decoder +1 gelu), 37,976 `@property` (28,323 + 2,415 + 7,238, of which 7,235 are duplicate re-registrations), ≈86k rule declarations, dead animation clock (0.83 MB), 1.68 MB decoder. Renderer RSS after load ≈1.66 GB (measured, browser-results.json `packed8_streaming_generation`). | 112.6 MB of source is never evaluated more than its 20% share |
| **O(stages)** | Per token: ≈52.5k declarations, ≈12.5k function invocations, ≈1.18M `var()`, ≈1.09M multiplies, ≈34k `style()` tests, 3 inherited-map copies, 1 layout-tree reattach, ≥1–2 frames of gate animation, 1 layout+paint. Memory: one retained `ComputedStyle` per stage element with ≈30.7k typed values + inherited map (~a few MB per stage). HTML grows by ~200 B per predeclared stage. | ≈36.6 MB source-equivalent re-evaluated per token |
| **O(stages × V)** | **None at runtime as long as the ball bounds prune.** Runtime is O(stages × r·V·d) with r≈0.2 (≈10.4k `--d` calls), O(stages × P·(K+m̄)) for the packed lookup, O(stages × (K/256 + 256)) for the decoder. The O(V) terms are memory only: V·(≈1,604 + 22×≈30 + ≈110 + ≈31) B ≈ 2.5 KB per vocabulary entry. Worst case (adversarial h, no pruning) degrades to O(stages × V·d) ≈ 5× head cost. | |
| **O(stages²)?** | No: stage depth does not enlarge inherited maps (same names overwritten), and locked subtrees are not styled. Layout of the `.story` inline run grows linearly with visible text. | |

---

## 6. Doc vs emitted-CSS disagreements

1. **The on-disk recommended page cannot open its gates.** `tinystories/streaming.css` (1,547 B, mtime Aug 26 14:49:02) contains **no** `@container style(--winner-id){…}` rule (`grep -c '@container'` = 0). `tools/build_tinystories_nested.py:129-137` emits that rule by default, but `tools/build_tinystories_dynamic.py:441` writes `OUT / "streaming.css"` with `streaming_css(include_winner_gate=False)` — and `Makefile:751` runs `tinystories-nested` *then* `tinystories-dynamic`, so the dynamic build overwrites the shared file (same mtime as `dynamic-prompt.css`/`nested-runtime.css`). `dynamic.html` supplies its own `@container style(--stage-ready:1)` gate in `dynamic-prompt.css`, but `streaming-packed8.html` (mtime Aug 25 02:50) links only `streaming.css`. As built now, `.handoff` never receives the animation, `--gate-open` stays 0, `content-visibility` stays `hidden`, and only token 1 can ever render. The 1.17 tok/s figure came from the Aug 25 build. Fix is trivial (write a separate `dynamic-streaming.css` or keep the gate), but any re-measurement must rebuild `tinystories-nested` last.
2. **Byte totals drift.** OPTIMIZATIONS.md:190 lists "Nested state handoff and decoder 2,525,724"; on disk `nested-runtime.css` is 2,534,887 (+9,163 B: the dynamic build's `.candidate-token` rule, `build_tinystories_nested.py:93-96`). With the −105 B missing gate rule, the on-disk bundle is 148,935,591 B vs the documented 148,926,533 (+9,058 B). Cosmetic, but the documented figure no longer describes the files on disk.
3. **"Only the small state-handoff rule and HTML nodes grow per token" (OPTIMIZATIONS.md:118)** is true of *source bytes* but misleading for *runtime*: each token re-evaluates ≈36 MB of source-equivalent CSS (§3). The docs never quantify the per-stage re-evaluation share.
4. **Seed/winner double counting is undocumented.** RESULTS.md:66-73 describes "one seed cluster, then… only cluster functions whose upper bound can still beat the seed" but the emitted `--z_seed` re-invokes `--dc_seed` (its `--a` is always 1) and `--dtW` re-invokes every `--d` of the winning cluster: ≈2m̄ ≈ 392 redundant rows (~4% of head arithmetic) per stage.
5. **"Cheap bounds"** (output-head-benchmark/RESULTS.md:66): the 256 bounds are 16,640 MACs plus 2×768 sign/abs props for seed and winner selection — ≈2.6% of head MACs; cheap indeed, but the 2,415 eager registered declarations are not free: they are the same class of work as the transformer's 28k.
6. **MODEL_CANDIDATES.md:19-22** quotes 393,216 transformer MACs; the emitted circuit has ≈407k multiplies (adds attention's 2·d·W·L ≈ 8k, masking, and LN), and the three-times-larger figure of ≈1.09M multiplies per stage once the head is included.
7. **Dead weight in `recurrent.css`.** 828 KB of execute/store `@keyframes`, `--clock/--generation` registrations and 16 `--visible-output-*` properties (`build_tinystories_recurrent.py:478-533`) are emitted into the streaming bundle and disabled by `.nested-model{animation:none!important}`; the 16 `--ts-next-output-N` `if()`s are still evaluated per stage (trivial). Not mentioned in the size breakdown.
8. **OPTIMIZATIONS.md:36-38** says deep autoregressive graphs "materialize" GELU intermediates because Chromium invalidated the reused function; the TinyStories path nonetheless relies on `--gelu()` for all 2,048 activations per stage (`--ts-lL-gelu-u:--gelu(var(--ts-lL-fc-u))`), and the results are correct — so the earlier caveat does not apply here (or applies only to the animation-clock design).

---

## 7. Where 1.17 tok/s probably goes

**Measured (cite):**
- 12,828 / 12,891 ms for 15 post-Play tokens → **857 ms per visible token** (tinystories/RESULTS.md:65-67, browser-results.json `streaming_generation.visible_benchmark`; external screenshot observer, stylesheet load excluded).
- Static transformer core alone: **281.5 ms median** (RESULTS.md:15; step.css, 15,411 props, CONTEXT=4 graph) — measured as `model.style.setProperty('--ts-in-0', …); getComputedStyle(model)` on one `.model` element (`tools/build_tinystories_step.py:464-469`), i.e. one forced synchronous recalc of one element, no handoff, no paint.
- Static core + shared exact head: **670.4–702.2 ms median** (RESULTS.md:16; same method, 64 per-dimension `--e` lookups instead of 22 `--pe`).
- Head alone on 35 hard seed-miss states: **743–755 ms median**, 771–782 ms batch mean (output-head-benchmark/RESULTS.md:9-32).
- Static core 18 MB ↔ 281.5 ms and core+head ↔ 686 ms gives ≈ 40–45 MB/s of source-equivalent evaluation in both cases — the same throughput the streaming page shows (36.6 MB / 857 ms ≈ 43 MB/s). This near-constant bytes-per-second is the strongest evidence that per-stage time is proportional to *re-evaluated CSS text*, not to DOM size or depth.

**Inferred split of the 857 ms stage (additivity assumed; ±15%):**

| Bucket | Estimate | Basis |
|---|---:|---|
| Transformer style recalc (28,301 registered + 7,251 bank decls, 2,048 gelu calls, ≈407k MAC, 18 MB) | **≈300–340 ms (37%)** | 281.5 ms measured for the 15.4k-prop static graph; +8 slots vs 4 in attention (+~5%), +7,168 KV `if()` shifts and +7,188 interface copies not present in step.css (+~25–40 ms at 0.7 µs/decl-var) |
| Output head style recalc (2,415 eager decls + ≈10.4k lazy `--d`/`--dc`/`--dt`/`--pe`, ≈680k MAC, 17.8 MB) | **≈380–420 ms (47%)** | 670–702 − 281.5 ≈ 390–420 ms measured by subtraction with the 213 MB shared head; packed head replaces 64 `--e` calls (each a 196-case `if()`) with 22 `--pe` + 64 tiny calcs, so ≤ the shared figure; hard-state head-only median 743–755 ms shows the head alone can exceed the whole average when pruning is weak |
| Handoff / invalidation cascade (H_k 7,235 unregistered copies, 3 inherited-map copies of ~29k entries, display-lock release, container-query match, animation start/finish bookkeeping) | **≈40–80 ms (5–9%)** | 7,235 var() at ~0.7 µs ≈ 5 ms; map copies 3 × ~29k entries ≈ 5–20 ms; remainder is the unexplained residual between (transformer + head) ≈ 700–760 ms and 857 ms. The 27%-slower untyped variant (§4.7) suggests inheritance/substitution mechanics can be far larger than their byte share |
| Gate frames + layout tree reattach (`display` change on H_k) + layout of the growing inline story + paint | **≈20–50 ms (3–5%)** | ≥1–2 vsync intervals (17–33 ms) forced by the 1 ms animation; reattaching a ~4-box subtree and laying out one more text run is single-digit ms; paint of a paragraph is ~1–3 ms |
| Decoder (`--token-piece`, 197+256 style tests, 1 string) | **<1 ms** | ~450 `style()` tests |

**Confidence:** the transformer/head split is anchored on two direct measurements and is robust; the handoff and gate buckets are inferred from the residual and from Blink's known behaviour. Nothing in the repo profiles Chromium's style recalc directly (no traces; grep of docs found only the "separate style passes" statement at README.md:175). A single `chrome://tracing` capture of one stage would settle §4.3–4.7.

---

## 8. Bottom line

Per generated token the browser evaluates ≈52.5k custom-property declarations and ≈12.5k custom-function invocations, substituting ≈1.18M `var()` references and performing ≈1.09M multiplications, by re-tokenising and re-parsing ≈36.6 MB of CSS source-equivalent text — about 24% of the page — at a roughly constant ≈43 MB/s. Two components carry ~85% of that: the ≈10.4k surviving `--dN()` token-dot bodies (≈16.6 MB, ≈662k MAC, the largest single per-stage re-evaluation) and the 8-layer transformer circuit (≈18 MB, ≈407k MAC, 28k registered properties of which half are KV plumbing). The 7,235-value state handoff crosses four declaration hops per coordinate and is small in arithmetic but is the most likely home of the ~100 ms unexplained residual. The 1 ms gate is a correctness/paintability device costing ≤4%, not a throughput bottleneck. Everything scales linearly: transformer ∝ L·(12d² + 2dW), head ∝ r·V·d + K·d, handoff ∝ L·W·d, memory ∝ V·d (parse-once). The one immediate defect: the on-disk `streaming.css` has lost its gate rule to the dynamic build, so the recommended page as currently built cannot progress past token 1.
