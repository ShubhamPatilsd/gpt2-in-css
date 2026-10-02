GPT-2 (124M) running in pure HTML + CSS — no JavaScript, no server-side compute.
==============================================================================

What this is
  A single web page (index.html + runtime.css + 285 font files) in which a 12-layer GPT-2 forward pass is
  executed by the browser's CSS engine: weights are OpenType variable fonts, arithmetic is font variation /
  anchor positioning / container queries / @function math, control flow is SVG SMIL + CSS animations.
  Greedy decoding (argmax over the full 50,257-token vocabulary), capacity 32 tokens per run.

Requirements
  * Google Chrome or Chromium or Microsoft Edge, version 139 or newer (uses CSS @function, if(), calc-size(),
    anchor positioning, view timelines, @container style() queries). Firefox and Safari show nothing useful.
  * 16 GB of RAM or more. The tab uses about 2 GB after loading and up to about 6 GB while generating.
    On an 8 GB machine the tab will be discarded or swap for minutes. Close other browsers / large apps first.
  * About 300 MB of disk for this folder (fonts 242 MB, stylesheet 50 MB, page 7 MB).
  * Python 3.9+ for the tiny local server (the page must be served over http://, not opened as a file://).

How to run
  1. Unpack the folder and open a terminal in it.
  2. python3 tools/launch_browser_gpt2.py --directory model
        (starts a strict static server on localhost and opens a separate Chrome profile with JavaScript disabled)
     or: python3 tools/launch_browser_gpt2.py --directory model --no-open
        then open the printed http://127.0.0.1:<port>/.../index.html URL in Chrome yourself.
  3. Wait for the status line to say "Ready".

What to expect
  * Loading: within a second you see the controls, the prompt box and a moving bar "Loading the model's
    stylesheet (50 MB of CSS)…"; then "Loading model weights: N of 285 fonts" counts up while the fonts
    decode; "Ready" after about 5 seconds on a laptop (more on a slow disk / first visit from a remote host,
    where the 300 MB download dominates).
  * Prompt: either pick one of the dropdown prompts (their expected outputs are known), or type your own text
    in the prompt box. The box shows a one-line CSS rule,   .tk-root { --draft-prompt: ""; }   — type your prompt
    BETWEEN THE TWO QUOTES and leave the rest of the rule as it is (the rule is the prompt's only way into the
    stylesheet; deleting a quote or a brace invalidates it). ASCII letters/digits/punctuation, single spaces, no
    line breaks.
    The line under the box shows how the text tokenizes; only the FIRST 4 GPT-2 tokens are used (longer text
    is truncated), and each prompt token costs one full step (about 15–20 s) before the first new token appears.
    Leave the box empty to use the dropdown prompt. Wait for "Ready" — the Run checkbox is enabled only then — and
    finish typing before you tick it: the box locks the moment Run is ticked.
  * Tick "Run / continue". A progress line shows "token t of 32 · layer k of 12" with a 12-segment bar (dark =
    layers finished, exact; light = estimated progress inside the current layer); while the output head
    scores the 50,257-word vocabulary a 13th, orange segment fills over an estimated ≈3 s and pulses
    ("vocabulary head: 50,257 rows → next token…"). Generated text appears in the output area as tokens finish;
    the area is at least four lines tall, grows with the window, and scrolls if the text is longer; the
    footer paragraph sits below it (in a very short window it is simply off-screen).
  * Speed: about 15 s per token at the start, growing to about 45 s per token by token 32 (the context grows);
    a full 32-token run takes about 15 minutes. Decoding is greedy, so the same prompt always gives the same
    text. Nothing is uploaded anywhere; the page has no script and a script-src 'none' policy.
  * To start over: press Reset (reloads the page).

Known limits
  * Tokenizer box: no newlines, no runs of two or more spaces, no non-ASCII characters (they are not tokenized
    like GPT-2 would); deleting a quote makes the rule invalid and silently falls back to the dropdown prompt.
  * At most 4 typed prompt tokens; 32 steps per run in total (prompt tokens included).
  * Chrome only; one run per page load.
