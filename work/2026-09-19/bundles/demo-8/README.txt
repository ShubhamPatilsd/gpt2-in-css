GPT-2 (124M) running in pure HTML + CSS — no JavaScript, no server-side compute.
==============================================================================

What this is
  A single web page (index.html + runtime.css + 286 font files) in which a 12-layer GPT-2 forward pass is
  executed by the browser's CSS engine: weights are OpenType variable fonts, arithmetic is font variation /
  anchor positioning / container queries / @function math, control flow is SVG SMIL + CSS animations.
  This is the SHORT variant: 8 steps per run in total (prompt tokens included — a 4-token prompt leaves 4 new tokens). Decoding is
  greedy (argmax over the full 50,257-token vocabulary) by default, or Gumbel-max sampling with a chosen seed
  and temperature (the noise is one more variable font).

Requirements
  * Google Chrome or Chromium or Microsoft Edge, version 139 or newer (uses CSS @function, if(), calc-size(),
    anchor positioning, view timelines, @container style() queries). Firefox and Safari show nothing useful.
  * 16 GB of RAM or more. The tab uses about 2 GB after loading and up to about 6 GB while generating.
    On an 8 GB machine the tab will be discarded or swap for minutes. Close other browsers / large apps first.
  * About 320 MB of disk for this folder (fonts 251 MB, stylesheet 40 MB, page 7 MB).
  * Python 3.9+ for the tiny local server (the page must be served over http://, not opened as a file://).

How to run
  1. Unpack the folder and open a terminal in it.
  2. python3 tools/launch_browser_gpt2.py --directory model
        (starts a strict static server on localhost and opens a separate Chrome profile with JavaScript disabled)
     or: python3 tools/launch_browser_gpt2.py --directory model --no-open
        then open the printed http://127.0.0.1:<port>/.../index.html URL in Chrome yourself.
  3. Wait for the status line to say "Ready".

What to expect
  * Page: title at the top (status "Ready" etc. small at the top right), then ONE row — "Prompt [dropdown] or type:
    [prompt box] [Run / continue] [Reset]" — the token chips under the box, a quiet "Options ▸" line (seed and
    temperature), the progress line and then the generated text in large type; practical notes in the footer.
  * Loading: within a second you see the title, the prompt row and a moving bar "Loading the model's
    stylesheet (40 MB of CSS)…"; then "Loading model weights: N of 286 fonts" counts up while the fonts
    decode; "Ready" after about 5 seconds on a laptop (more on a slow disk / first visit from a remote host,
    where the 320 MB download dominates).
  * Prompt: either pick one of the dropdown prompts (their expected outputs are known), or type your own text
    in the prompt box. The box shows a one-line CSS rule,   .tk-root { --draft-prompt: ""; }   — type your prompt
    BETWEEN THE TWO QUOTES and leave the rest of the rule as it is (the rule is the prompt's only way into the
    stylesheet; deleting a quote or a brace invalidates it). ASCII letters/digits/punctuation, single spaces, no
    line breaks.
    The line under the box shows how the text tokenizes; only the FIRST 4 GPT-2 tokens are used (longer text
    is truncated). Each prompt token beyond the first is absorbed in its own step of about 10–13 s (the progress
    line says "absorbing prompt token k of N"; the vocabulary head is skipped on those steps), then the remaining new
    tokens follow (8 steps in total in this short variant). Leave the box empty to use the dropdown prompt.
    Wait for "Ready" — the Run checkbox is enabled only then — and finish typing before you tick it: the box
    locks the moment Run is ticked.
  * Sampling (optional): click "Options ▸" (closed by default) to show two selects. "Seed": auto (the seed is taken from a clock the
    moment you tick Run) or 1…64 to pick one; "Sampling": greedy (T = 0, the default), T = 0.7 or T = 1.0.
    After Run the Options line shows the seed and temperature actually used, e.g. "T = 1.0 · seed 17", so any
    sampled run can be replayed exactly by selecting that seed and temperature. With greedy decoding the seed is
    irrelevant and the same prompt always gives the same text.
  * Tick "Run / continue". A progress line shows "new token t of 8 · layer k of 12" with a 12-segment bar
    (dark = layers finished, exact; light = estimated progress inside the current layer); while the output head
    scores the 50,257-word vocabulary a 13th, amber segment fills over an estimated ≈3 s and pulses
    ("vocabulary head (choosing the next token)"; on prompt steps "absorbed"). Generated text appears in the output area as tokens finish;
    the area is at least four lines tall, grows with the window, and scrolls if the text is longer; the
    footer paragraph sits below it. The status line ends with "Complete • 8 new tokens" (fewer with a typed prompt).
  * Speed: about 15 s per token at the start, growing to about 50 s per token by the last tokens (the context
    grows); a full 8-step run takes about 2–3 minutes on mains power with free memory —
    considerably longer on battery or when the machine swaps. Nothing is uploaded anywhere; the page has no
    script and a script-src 'none' policy.
  * To start over: press Reset (reloads the page and clears the controls). Do NOT use the browser's Reload
    for a replay: Chrome restores the ticked Run box and restarts the seed clock from 0, so an "auto" seed
    would become seed 1 — press Reset, then pick the shown seed explicitly.

If something looks wrong
  Scrollbars, headed vs headless Chrome, and the geometry self-check
  The page does its arithmetic with layout geometry: hidden measuring elements whose widths encode numbers are read back
  through CSS scroll-driven animations, and one such element was decoded with the assumption that its scrolling box is
  exactly 524,288 px wide. A classic, space-taking scrollbar (macOS with "Show scroll bars: Always" or with a mouse
  attached, Windows, most Linux desktops) makes that box 15–17 px narrower, which shifted every read-back token id
  above ≈9,300 by +1 — the model then continued from the wrong word ("House ofEARTH" instead of "House of
  Representatives"). Headless Chrome, and Chrome started with --hide-scrollbars, never showed it; overlay scrollbars
  (macOS default with a trackpad only) take no space and are also unaffected. Since v6 the measuring box declares
  scrollbar-width:none (Chrome 121+), so the scrollbar policy of the OS no longer matters, and the page now
  self-checks the mechanism: a constant of known value is read back the same way before every token and each fed-back
  id is compared with the exact winner; if either check fails the run is HELD (no token appears) and a red panel
  "Geometry self-check failed" is shown instead of wrong text. If you see that panel: use Chrome/Edge 121 or newer
  (139+ is required anyway), do not run with a browser "minimum font size" set, keep the window at 100 % zoom
  if in doubt, then press Reset.

Known limits
  * Tokenizer box: no newlines, no runs of two or more spaces, no non-ASCII characters (they are not tokenized
    like GPT-2 would); deleting a quote makes the rule invalid and silently falls back to the dropdown prompt.
  * At most 4 typed prompt tokens; 8 steps per run in total, prompt tokens included (the run stops by itself).
  * Sampling: 64 seeds and two temperatures only (the noise table is a font with 64 columns); "auto" seed means
    the seed depends on when you click — read it off the Options line if you want to replay the run.
  * Chrome only; one run per page load.
