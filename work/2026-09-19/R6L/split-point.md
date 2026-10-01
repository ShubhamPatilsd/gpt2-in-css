# R6L ↔ R6V: where the shell ends and the model sheet begins (2026-09-30 15:35, R6L)

Finding (R5X/run-combined8-c32/c32-p40.json metric samples): the 34 s load is ONE 30.8 s main-thread task — Chrome lays out the
UA-styled model markup (84,592 <i>, 780k PUA/unassigned-plane characters → system font-fallback per character) while the 50 MB
<head> stylesheet is still pending; CSS parse + first styled recalc + fonts + first paint take only the last ≈2.5 s.

R6L's split (flags `R6L_BODY_LINK=1 R6L_BOOT=1` in R6L/tools/r6l_boot.py; identical bytes otherwise):
  <head> … <title>…</title><style>html::before{content:"Loading the model stylesheet (50 MB)…";display:block;…}body{display:none}</style></head>
  <body><link rel="stylesheet" href="runtime.css">   ← parser-blocking in Chromium: nothing after it is parsed until the sheet is in
  <div class="controls">… (everything from here on is byte-identical to combined8-c32)
  runtime.css ends with `html::before{content:none}body{display:block}` (later author sheet, same specificity → restores everything).

Consequences for R6V's load indicator: it necessarily lives AFTER the link (inside the model DOM) and appears when the sheet has
applied — i.e. it covers the FONT phase (N/283), which is the whole remaining wait. The boot line (html::before) covers the CSS
phase and disappears the moment runtime.css applies. Please do not add a second pre-sheet message; if you want the boot text
changed, `R6L_BOOT_TEXT` sets it. The two changes compose: R6V's rules go anywhere in the sheet; R6L's two rules are appended last.

## 15:45 update — R6V already ships the same structure (R6V_EARLY_PAINT: inline head <style> for the controls + a CSS-phase panel, then
`<link>` in <body>, then the model). R6L_BODY_LINK/R6L_BOOT are the same change minus the panel plus a `body{display:none}` belt.
For the merge: take ONE — R6V's (it carries the loading UI) — and set `R6L_BODY_LINK=0 R6L_BOOT=0`. R6L's load-time numbers transfer
unchanged because every byte after the link is identical in both variants; the only R6L-specific question the session-1 loads
answer is whether the parser really stops at a body <link> (R6L-bodylink) or whether Chrome lays out UA-styled content past it
(R6L-hidebody isolates that). R6V: if bodylink alone is fast, your variant is fast too; if only hidebody is fast, add `body{display:none}`
+ a `body{display:block}` tail to yours (R6L can hand you the two strings).
