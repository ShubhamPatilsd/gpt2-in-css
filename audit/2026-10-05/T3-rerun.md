# T3: re-running the toy transformer end to end, compared with MNIST

Date: 2026-10-05. Environment: macOS Darwin 25.0.0, Python 3.14.6, NumPy 2.3.5, **Google Chrome 154.0.8037.97** (stock, headless via Playwright 1.62.1 Node; `executablePath` = system Chrome). Scratch: `audit/2026-10-05/T3-scratch/`. Command log: `T3-rerun.log.md`. No tracked file changed.

## How the transformer is "tried out"

1. **Build (Python, build-time only).** Run `make transformer`, which is `python3 tools/build_transformer.py`. The script has no flags and always writes `<script-dir>/../transformer/{model.css,index.html}`. The weights are random from `default_rng(19)`. Only the LM head is fitted, by ridge least squares on the cyclic sequence ` abcde.`. That gives 1 block, 3 heads, d=12, d_ff=24, vocabulary of 7, and 3 generation steps unrolled statically. To rebuild without touching `transformer/`, I copied the script to `T3-scratch/tools/` and ran it there.
2. **Run (browser, no JS).** Open `transformer/index.html` and pick one of 4 radio prompts. The input is selected through `:root:has(#prompt-N:checked)`. The output is 7 `.token-option` spans per step, and `opacity` is set to the one-hot `1 - abs(sign(logit - max))`. The page has no `<script>`, which I verified in the DOM.

## Results

| Check | Result |
|---|---|
| Rebuild time | 0.15 s real |
| Rebuilt `model.css` vs `transformer/model.css` | **byte-identical**, sha256 `5885222c6febdc58adf77d7482019c2cc88485f633a9158920ab37baa73a5b98` (1.3 MB, 6326 lines, 3069 `@property`) |
| Rebuilt `index.html` vs tracked | byte-identical (`be61a628…7d93a181e9cb83f7d`) |
| Second independent rebuild | same hash, so the build is deterministic |

**NumPy reference.** Default prompt `␠ab`, generating `cde`. Step-1 logits over `[␠ a b c d e .]`:
`[-1.103647, -1.167173, -0.888779, 4.948199, -1.034034, -0.846952, -0.907632]`. The minimum top1−top2 margin across all prompts and steps is 5.67, so argmax is never fragile.

**Browser (CSS) vs reference, all 4 prompts:**

| Prompt | CSS output | Reference | One-hot exact (one 1, six 0s) | Max abs error, step-1 logit |
|---|---|---|---|---|
| `␠ab` | cde | cde | yes | 9e-6 |
| `bcd` | e.␠ | e.␠ | yes | 9e-6 |
| `de.` | ␠ab | ␠ab | yes | 9e-6 |
| `.␠a` | bcd | bcd | yes | 2e-5 |

The logit errors are at the limit of the 6-significant-digit precision of `getComputedStyle` serialization. CSS step-1 logits for `␠ab`: `[-1.10364, -1.16717, -0.888781, 4.94819, -1.03403, -0.84695, -0.907628]`. There were no console errors.

**Timing (headless, file://).** Chrome launch 905 ms. Transformer page `load` 39 ms. First computed-style read, which forces the style resolve of about 3k registered properties, 66 ms. Switching prompts took 44–81 ms each. The whole session (both pages plus 14 radio clicks plus 3 screenshots) took 4.6 s, or 4.83 s wall time including Node.

**Rendered text.** `innerText` contains all 7 options per step, because unselected options are hidden only by opacity. The visible output is the opacity-1 option. In the screenshot, `␠` renders as a small "SP" glyph.

## MNIST (`index.html`) flow, for comparison

- **Build:** `make build`, which is `python3 tools/build.py`. It *trains* a 784→32→10 ReLU MLP on `data/mnist.npz` (and downloads it if missing), then writes `model.css`, `samples/*.svg` and `index.html` to the repo root. I did not rebuild it, because it writes to tracked root files and training was out of scope.
- **Run:** pick one of 10 sample radios. The 10 `--score-N` `calc()` dot products drive the bar widths and the "mlogit" counters.
- **Default (sample-0, label 0):** CSS prediction **0**, matching the page's "Python reference prediction 0". CSS scores were `[10.3084, -5.30598, 1.12277, -4.51483, -6.14232, -6.28125, 1.35656, 0.991241, -5.5759, -0.62548]`, against an independent NumPy evaluation of the weights parsed from `model.css` (max abs error 5e-5, which is the reference rounding). **All 10 samples:** CSS argmax equals the reference argmax equals the label.
- **Timing:** page `load` 164 ms (1.9 MB CSS plus SVGs), first style read 3 ms.
- **Discrepancy:** the MNIST lede says "a real 784-input *linear* classifier … ten dot products", but the shipped model is a 784→32→10 MLP. The footer of the same page says so.

**Contrast with MNIST:** the transformer has a single deterministic build with no data and no training beyond a closed-form head fit, 4 inputs, and an autoregressive output fed back through the CSS dependency graph. MNIST needs a dataset plus SGD training, has 10 inputs, and makes one forward pass.

## Artifacts

- Screenshots: `T3-scratch/transformer-default.png`, `T3-scratch/transformer-prompt3.png`, `T3-scratch/mnist-default.png`
- Data: `T3-scratch/reference.json`, `T3-scratch/mnist_reference.json`, `T3-scratch/browser_result.json`
- Scripts: `T3-scratch/reference.py`, `T3-scratch/mnist_ref.py`, `T3-scratch/run_browser.mjs`
- Rebuild outputs: `T3-scratch/transformer/`, `T3-scratch/rebuild2/transformer/`

## Failures (verbatim)

- `python3 -c "import playwright"` gave `ModuleNotFoundError: No module named 'playwright'`
- `npx --no-install playwright --version` gave `npm error A complete log of this run can be found in: /Users/shubhampatil/.npm/_logs/2026-10-05T07_40_45_899Z-debug-0.log`

I worked around both with the Playwright runtime the repo already uses (see `tools/test_svg_internal_precision_probe.mjs`).
