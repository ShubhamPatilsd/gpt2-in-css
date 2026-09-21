# R4P — a better single-token prompt for the 32-token greedy demo (offline, NumPy only)

Agent R4P, 2026-09-21. Work dir `work/2026-09-19/R4P/`, log `work/2026-09-19/R4P.log.md`. No Chrome launched, CHROME.lock untouched, repo `tools/` / `experiments/` untouched. All compute ran `nice -n 19` with 2 BLAS threads behind the `CPU-BUSY-R4P` marker (start/end stamps in the log).

## 1. How the prompt token is specified (R3M/tools emitter)

There is **no `--prompt` CLI flag**. `browser_gpt2_runtime.py` (`work/2026-09-19/R3M/tools/browser_gpt2_runtime.py`, identical to R4C/tools and the base of R4D/tools) hard-codes the prompt in `feedback()`:

- line 55: `"body{--epoch:1;--prompt-token:15496;container-name:runtime}"` — the default prompt id (compiled into `runtime.css`).
- line 498–500: `options = [15496, 464, 40, 32, 1212, 2061]` (Hello, The, I, A, This, What) → a `<select>` in `index.html` and one rule per option `body:has(option[value="T"]:checked){--prompt-token:T}`. The first option is the default-selected one, so `--prompt-token` is 15496 unless the user picks another option before checking "Run".
- line 64: `.feedback-reader{--frozen-prompt:var(--prompt-token)}` freezes the choice on run; line 97–102: `.feedback-select{--token:if(style(--epoch:1):var(--frozen-prompt); style(--epoch:i):var(--feedback-(i-1)) ...)}` feeds epoch 1 the prompt and later epochs the fed-back argmax. Line 492 prints the prompt via `counter(prompt,gpt2-vocabulary)`.
- `browser_gpt2_embedding.py` line 58: `@property --token{... initial-value:15496}` is only a fallback initial value; the embedding lookup is a **full-vocabulary (50257) font lookup** (`TOKEN_GROUP = round(down, --token/256)`, `TOKEN_LOCAL = mod(--token,256)`), so any id 0..50256 works without rebuilding fonts. The head is full-vocabulary too (`head="full-vocabulary-q16-two-pass"`), which is what already lets arbitrary fed-back ids flow.
- `--teacher-forced-tokens <json>` (line 637) is diagnostic only (fixes all inputs; disables free-running), not a prompt mechanism.
- Manifest `promptTokens=1` is a literal (line 591). The runtime structurally supports exactly **one prompt token**: epoch 1 consumes `--frozen-prompt`, epoch i>1 consumes `--feedback-(i-1)`. A multi-token prompt would need a prefill path (per-epoch teacher inputs for the first k epochs, like the `--teacher-forced-tokens` `if()` chain, then switching to feedback) — an emitter change, not just a constant.

In the compiled `bundles/combined4-c32/runtime.css` the literal `15496` occurs 19 times but only 3 are the prompt (the `body{--prompt-token}` rule, the `@property --token` initial value, the option rule); the other 16 are digit coincidences inside weight constants.

**So: any single token id can be used with no other change**, by either (a) picking one of the six existing dropdown options at run time (ids 15496/464/40/32/1212/2061 — includes recommendation #3, `I` = 40 — zero recompile), or (b) editing the constant on line 55 and/or the `options` list (put the desired id first, or add `selected`) and recompiling with the unchanged R4C/R4D recipe. Nothing else in the emitter reads the prompt id.

## 2. Screening method

`R4P/screen_prompts.py` (from a copy of `R4C/reference_ids_32.py`, `PYTHONPATH=R3M/tools`): for each candidate id, free-running greedy for 32 tokens through `browser_gpt2_core.reference_sequence(quantized=True)` (q9 weights) + the q16 head exactly as R4C (`rint(hidden/R*16384)/16384*R`, `rint(hidden @ q.T * SCORE_GAIN * 256).argmax`), then a teacher-forced pass over the produced ids (equal to free-running for all 60 candidates), then the float greedy (`quantized=False`, float `hidden @ wte.T` argmax). Only deviation from R4C's script: the checkpoint load / layer quantization is memoized across the 33 passes (pure functions; the 15496 row reproduces R4C's `reference_ids_32.json` bit-for-bit). Tokenizer = `build_pretrained_gpt2.Gpt2Tokenizer` on `data/gpt2/vocab.json`; each word tried with and without leading space (`Ġ`), 30 words → 60 single-token ids. `R4P/margins.py` adds, for shortlisted prompts, the per-step top1−top2 gap of the q16 head in integer score units (same rounding as the head).

Scores: distinct = number of distinct ids among the 32 generated; longest repeat = largest n such that some n-gram occurs twice in the 32; coherence judged by reading the decoded text. Raw data: `R4P/screen_results.json`, `R4P/screen_prompts.out`, `R4P/margins.json`.

## 3. Results (sorted by distinct desc, longest repeat asc; `⏎` = newline)

| id | prompt | distinct/32 | longest repeat | q==float? (first mismatch) | decoded quantized 32 tokens (prompt + continuation) |
|---|---|---|---|---|---|
| 18435 | ` Hello` | 29 | 1 | NO (@14) | ` Hello, I'm not sure if you're aware of the fact that the U.S. government has been using the word "terrorism" in its official name for` |
| 1649 | ` When` | 27 | 1 | NO (@24) | ` When the time comes, you'll be able to use the same tools you used to create your own custom templates.⏎⏎The following is a list of the most` |
| 29449 | `Breaking` | 27 | 1 | yes | `Breaking, and the other two are still in the process of being released.⏎⏎The first is a new album, which will be released on October 7. The` |
| 3347 | `She` | 27 | 1 | yes | `She, who is also a former president of the United States, said she was "very disappointed" by the decision.⏎⏎"I think it's a very` |
| 1858 | `There` | 26 | 1 | yes | `There is no evidence that the government has been able to prevent the spread of the virus.⏎⏎"The virus is not spread by people who are infected with it` |
| 40 | `I` | 25 | 1 | yes | `I.⏎⏎The first thing I did was to go to the local grocery store and buy a bag of frozen yogurt. I was so excited to try it.` |
| 314 | ` I` | 25 | 1 | yes | ` I.⏎⏎The first thing I did was to go to the local grocery store and buy a bag of frozen yogurt. I was so excited to try it.` |
| 3260 | `After` | 25 | 1 | yes | `After the first round of the playoffs, the Celtics were in a tough spot. They had a lot of young talent, but they were also a team that was struggling` |
| 28065 | `Yesterday` | 25 | 1 | yes | `Yesterday, the U.S. Supreme Court ruled that the government can't force a person to pay for a drug that's not legal.⏎⏎The ruling,` |
| 5195 | `Why` | 25 | 2 | yes | `Why, then, is it possible that the world's most powerful nation, the United States, is now in the midst of a civil war?⏎⏎The answer` |
| 23782 | ` Scientists` | 24 | 1 | yes | ` Scientists, and the Science of the Universe.⏎⏎The study, published in the journal Nature Communications, is the first to show that the universe is expanding at a` |
| 34668 | ` Yesterday` | 24 | 2 | yes | ` Yesterday, the U.S. Supreme Court ruled that the government can't force a person to pay for a drug that's not legal.⏎⏎The Supreme Court` |
| 19184 | `Water` | 24 | 2 | NO (@16) | `Water, and the other two are the same.⏎⏎The first is the "water" that is the main source of water in the world. The second is` |
| 14617 | `Long` | 24 | 2 | NO (@5) | `Long, the first time I saw a new character, I was like, 'Oh my God, this is so cool.' And then I saw the first episode of` |
| 2293 | ` After` | 24 | 4 | NO (@1) | ` After the first day of the new year, the city's population was expected to grow by about 1.5 percent.⏎⏎But the city's population has been` |
| 632 | ` It` | 23 | 2 | NO (@3) | ` It is a very important step in the development of the new technology.⏎⏎The new technology is called "smart meters" and it is a new way of measuring` |
| 26685 | ` Researchers` | 23 | 2 | NO (@2) | ` Researchers, who are also the lead authors of the study, said that the study was the first to show that the brain's ability to process information is affected by the` |
| 29193 | `Scientists` | 23 | 3 | NO (@31) | `Scientists, who have been studying the effects of the sun's radiation on the body, have found that the sun's rays are able to penetrate the skin and cause skin` |
| 1881 | ` One` | 23 | 3 | yes | ` One of the most important things to do is to get your hands on a copy of the book.⏎⏎The book is available in paperback and Kindle.⏎⏎` |
| 25606 | `Researchers` | 23 | 5 | NO (@5) | `Researchers, who are also working with the University of California, Berkeley, and the University of California, San Diego, have found that the brain's ability to process information` |
| 3198 | `One` | 23 | 7 | yes | `One of the most important things to remember is that you can't just say "I'm going to do this." You have to say "I'm going to do` |
| 1318 | ` There` | 22 | 3 | NO (@2) | ` There is no way to know if the person who is responsible for the death of the victim is the person who killed the victim.⏎⏎The court also said that` |
| 1867 | ` What` | 21 | 2 | yes | ` What is the difference between a "good" and a "bad" person?⏎⏎A good person is someone who is willing to listen to others and to listen` |
| 7454 | `Once` | 21 | 4 | NO (@6) | `Once the game is over, you can return to the main menu and select the "Return to the main menu" option.⏎⏎You can also return to the` |
| 4874 | ` Once` | 21 | 4 | yes | ` Once the game is over, you can return to the main menu and select the "Return to the main menu" option.⏎⏎You can also return to the` |
| 23421 | `London` | 21 | 4 | yes | `London, England.⏎⏎The first of the three to be released in the UK, the second is a new album, and the third is a new album.` |
| 6288 | ` Today` | 21 | 5 | yes | ` Today, the U.S. government has been trying to get the U.S. to stop using the term "radical Islamic terrorism" to describe the group.` |
| 679 | ` He` | 21 | 7 | NO (@22) | ` He is a member of the National Rifle Association, and he has been a member of the National Rifle Association since the day he was elected to the U.S.` |
| 770 | ` This` | 21 | 8 | yes | ` This is a very good example of how to use the "I'm not a fan of this" rule.⏎⏎The "I'm not a fan of this` |
| 5638 | ` Water` | 20 | 2 | yes | ` Water, and the other two are the same.⏎⏎The first is the "B" in the middle of the name. This is the name of the "` |
| 1532 | `If` | 20 | 3 | yes | `If the user is not logged in, the user will be redirected to the login page.⏎⏎The user can also use the login page to login to the site` |
| 1002 | ` If` | 20 | 3 | yes | ` If the user is not logged in, the user will be redirected to the login page.⏎⏎The user can also use the login page to login to the site` |
| 554 | ` In` | 19 | 3 | NO (@14) | ` In the past, the government has been able to use the power of the courts to block the implementation of the law.⏎⏎The government has also been able to` |
| 8888 | `Today` | 19 | 5 | yes | `Today, the U.S. government has been trying to get the U.S. to stop using its military to fight terrorism.⏎⏎The U.S` |
| 1135 | `We` | 19 | 13 | yes | `We have a lot of people who are very passionate about the game and want to play it. We have a lot of people who are very passionate about the game and` |
| 775 | ` We` | 19 | 13 | yes | ` We have a lot of people who are very passionate about the game and want to play it. We have a lot of people who are very passionate about the game and` |
| 317 | ` A` | 18 | 4 | yes | ` A.J. and J.A. were both in the same room.⏎⏎The two men were sitting in the same room, and the two women were` |
| 24942 | ` Breaking` | 18 | 6 | NO (@5) | ` Breaking the Throne, and the final chapter of the series.⏎⏎The series is set in the year 2032, and is set in the year 2033.` |
| 2215 | `When` | 18 | 7 | NO (@8) | `When the first of the two games, the Colts were able to get a win, but the Colts were able to get a loss.⏎⏎The Colts were able` |
| 383 | ` The` | 17 | 9 | yes | ` The⏎⏎"I'm not sure if I'm going to be able to do it, but I'm going to be able to do it. I'm going` |
| 1026 | `It` | 17 | 10 | yes | `It is not possible to determine the exact cause of the accident.⏎⏎The driver of the car was not injured.⏎⏎The driver of the car was not` |
| 1212 | `This` | 17 | 10 | yes | `This is a very good example of how to use the "I'm not a fan of the idea of a 'I'm not a fan of the idea of a` |
| 818 | `In` | 16 | 12 | yes | `In the past, the government has been accused of using the power of the purse to enrich itself. But the government has been accused of using the power of the purse` |
| 1375 | ` She` | 15 | 8 | NO (@18) | ` She, who was born in the United States, was born in the United States. She was born in the United States. She is the mother of three.⏎` |
| 5882 | ` Long` | 15 | 14 | yes | ` Long, the first time I've ever seen a movie with a female lead. I've never seen a movie with a female lead. I've never seen a movie` |
| 15496 | `Hello` | 14 | 15 | yes | `Hello, I'm sorry, but I'm not sure if you're aware of this. I'm not sure if you're aware of this. I'm not sure` |
| 6109 | `Every` | 13 | 12 | yes | `Every, I think, is the most important thing. I think it's the most important thing to do. I think it's the most important thing to do.` |
| 3887 | ` Every` | 13 | 16 | yes | ` Every, I'm not sure if I'm going to be able to do it. I'm not sure if I'm going to be able to do it. I` |
| 2061 | `What` | 12 | 8 | yes | `What is the best way to get a job?⏎⏎The best way to get a job is to get a job.⏎⏎The best way to get a` |
| 3576 | ` London` | 12 | 11 | yes | ` London, and the UK's largest city, London.⏎⏎The UK's largest city, London. The UK's largest city, London. The UK's largest` |
| 1544 | `He` | 12 | 17 | yes | `He is a very good player, but he is not a great player. He is not a great player. He is not a great player. He is not a` |
| 20266 | `Dear` | 11 | 17 | yes | `Dear, I'm sorry, but I'm not sure I can do this. I'm not sure I can do this. I'm not sure I can do this` |
| 23420 | ` Dear` | 11 | 17 | yes | ` Dear, I'm sorry, but I'm not sure I can do this. I'm not sure I can do this. I'm not sure I can do this` |
| 14126 | `Chapter` | 10 | 3 | NO (@0) | `Chapter⏎⏎Chapter 1⏎⏎Chapter 2⏎⏎Chapter 3⏎⏎Chapter 4⏎⏎Chapter 5⏎⏎Chapter 6⏎⏎Chapter 7⏎⏎Chapter 8` |
| 7006 | ` Chapter` | 10 | 7 | yes | ` Chapter⏎⏎Chapter 1: The Great War⏎⏎Chapter 2: The Great War⏎⏎Chapter 3: The Great War⏎⏎Chapter 4: The Great War` |
| 32 | `A` | 10 | 21 | yes | `A.⏎⏎The first thing I noticed was that the first thing I noticed was that the first thing I noticed was that the first thing I noticed was that the` |
| 4162 | ` Why` | 9 | 20 | NO (@0) | ` Why the hell is this?⏎⏎The answer is that the answer is that the answer is that the answer is that the answer is that the answer is that the` |
| 3666 | `My` | 9 | 22 | yes | `My⏎⏎I'm a big fan of the "I'm a big fan of the "I'm a big fan of the "I'm a big fan of` |
| 2011 | ` My` | 6 | 25 | yes | ` My⏎⏎A. I'm a⏎⏎A. I'm a⏎⏎A. I'm a⏎⏎A. I'm a⏎⏎A.` |
| 464 | `The` | 2 | 29 | yes | `The⏎⏎The⏎⏎The⏎⏎The⏎⏎The⏎⏎The⏎⏎The⏎⏎The⏎⏎The⏎⏎The⏎⏎The⏎⏎` |

q16 head margins (top1−top2, integer score units, per generated step) for the shortlist — `R4P/margins.json`:

| id | prompt | min margin (step) | note |
|---|---|---|---|
| 15496 | Hello (current) | 4 (step 3) | verified in Chrome by R4C (ids agree); baseline for "how small is still safe" |
| 1858 | There | 9 (step 10) | no step below 9 |
| 3260 | After | 7 (step 16) | one step at 7, one at 9 |
| 40 | I | 9 (steps 19, 25) | |
| 28065 | Yesterday | **1 (step 31)** | fragile at the last token |
| 3347 | She | **0 (step 5)** | exact tie broken by argmax order — do not use |

## 4. Recommendations (top 3)

1. **1858 `There`** — `There is no evidence that the government has been able to prevent the spread of the virus.⏎⏎"The virus is not spread by people who are infected with it` — 26 distinct, no repeated bigram, fully grammatical from token 1, quantized == float, min margin 9 (> Hello's 4). Needs recompile (not in the dropdown). Ids: `R4P/reference_ids_32_1858.json`.
2. **3260 `After`** — `After the first round of the playoffs, the Celtics were in a tough spot. They had a lot of young talent, but they were also a team that was struggling` — 25 distinct, no repeat, coherent narrative, quantized == float, min margin 7. Needs recompile. Ids: `R4P/reference_ids_32_3260.json`.
3. **40 `I`** — `I.⏎⏎The first thing I did was to go to the local grocery store and buy a bag of frozen yogurt. I was so excited to try it.` — 25 distinct, no repeat, quantized == float, min margin 9; **already the third `<option>` in every compiled bundle, so it needs no recompile** (select "I" before Run). Slightly awkward start (`I.`), then a clean little story ending on a full stop at token 32. (`Ġ I` = 314 gives the identical continuation.) Ids: `R4P/reference_ids_32_40.json`.

Honourable mentions: 28065 `Yesterday` (Supreme-Court sentence, 25 distinct, but margin 1 at the last step) and 5195 `Why` (25 distinct, longest repeat 2). Avoid: 464 `The` (degenerates to `The⏎⏎The⏎⏎…`, 2 distinct), 3666/2011 `My`, 32 `A`, 20266 `Dear`, 1544 `He` — all loop within ~10 tokens; 15496 `Hello` (current) loops after 14 distinct tokens.

Each `reference_ids_32_<id>.json` has `promptToken`, `promptText`, `teacherForcedReference`, `freeRunningReference` (equal), plus `floatReference`, `quantizedEqualsFloat`, `agree` (R4C's `savedCodex32` omitted, as allowed).

## 5. Risk: does changing the prompt change anything else in the bundle?

- **Quantization ranges are dynamic, not calibrated on the prompt.** `manifest.json` has `dynamicActivationRange: true`; the core emits `dynamic_range=True` blocks (`browser_gpt2_core.py` line 327) whose `--range-qkv/--range-fc/--range-proj` are computed at run time from the live activations (`bundles/combined4-c32/runtime.css` is full of `* var(--range-qkv)` etc.). Weight quantization (q9 rows, `WEIGHT_SCALE`, `SCORE_GAIN`, `R`, `AXIS_STEPS`) is prompt-independent. I found nothing in `browser_gpt2_runtime.py`, `browser_gpt2_core.py`, `browser_gpt2_embedding.py` that derives a constant from the prompt id (`TOKENS = [15496, 995, …]` in core.py is only the default `--tokens-file` fixture of core's own `main()`, unused by the runtime emitter). The per-epoch constants in the CSS (`style(--epoch:24):0.0486…`) are position embeddings, not prompt-dependent.
- Therefore a recompile with a different `--prompt-token` should produce a bundle identical except for the three prompt literals (and the dropdown), and selecting `I` in the existing bundle changes nothing at all on disk.
- **What still needs Chrome re-verification:** the browser's fixed-point activation path (q16 axes, HVAR rounding, packed caches) is not modelled by the NumPy reference beyond quantized weights + q16 head; R4C only proved agreement for the Hello trajectory. A different trajectory exercises different rounding events, so the 32 ids for the new prompt must be checked in Chrome once (compare against `reference_ids_32_<id>.json`). The margin data says the top 3 are at least as robust as Hello (min gap 7–9 vs 4), but that is a heuristic, not a proof.
- Prompt id is also displayed via `counter(prompt,gpt2-vocabulary)` — any id 0..50256 has a symbol, so display is fine.

## 6. Not verified / caveats

- No Chrome run (by instruction); none of the new-prompt ids have been observed in the browser.
- I did not diff a recompiled bundle; the "identical except prompt literals" claim is from reading the emitter, not from a build.
- Float greedy here = float weights + float head; the fed-back trajectory diverges from quantized for 22/60 prompts, marked in the table as fragile. All three recommendations agree between quantized and float over all 32 steps.
- "Coherence" is my reading of the text; distinct/repeat numbers are mechanical.
