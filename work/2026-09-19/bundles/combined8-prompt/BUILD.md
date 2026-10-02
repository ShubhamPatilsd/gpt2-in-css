# bundles/combined8-prompt — `combined8` (cap 8, `--value-layout runs`) + R6P echo fix + typed prompt (same flags/tools as `bundles/combined8-c32-prompt/BUILD.md`)

Built by R6P on 2026-09-30 15:50: `cd work/2026-09-19/R6P && R6P_ECHO_FIX=1 R6P_TYPED_PROMPT=1 R6P_PROMPT_SLOTS=4 VALUE_LAYOUT=runs R4S_SMALL_HOPS=1 ./compile.sh …/bundles/combined8-prompt 8 12`
(combined8's recipe: `bundles/combined8/BUILD.md`; R5H forces R4S off at import). Purpose: the capacity-8 "ids unchanged" check (dropdown Hello, nothing typed → must give
`[11, 314, 1101, 7926, 11, 475, 314, 1101]`, verify rc 0) and a cheaper page for trying the typed prompt (N ≤ 4 prompt tokens + 9−N generated).

- Flags-off twin (`R6P_ECHO_FIX=0 R6P_TYPED_PROMPT=0`) == `bundles/combined8` byte-identical (index.html 6,460,006 B identical; runtime.css identical URL-normalised; manifest +8 keys) — `R6P/logs/compare-c8-off-vs-combined8.log`.
- vs `combined8`: elements 67,524 → 67,557, max depth 182, runtime.css 38,269,982 → 39,213,271 B, index.html 6,460,006 → 6,462,123 B, witnesses 283/285 (+2 tokenizer faces), `--check` 287 static files / 288,058,278 B / `runtimeJavaScript:false`.
- Chrome: `R6P/run_chain.sh` step (2) (gated; READY only on 8/8 + verify rc 0). Tools diff: see `bundles/combined8-c32-prompt/BUILD.md`.
