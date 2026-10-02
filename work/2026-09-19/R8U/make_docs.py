"""R8U: README.txt / BUILD.md for the R8U bundles (from the live bundles' files; every anchor asserted).
usage: make_docs.py <live-bundle> <new-bundle> <variant c32|8>"""
import sys, pathlib
live, new, variant = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
r = (live / "README.txt").read_text()
def rep(a, b):
    global r
    assert r.count(a) == 1, a; r = r.replace(a, b)
rep('''  * Loading: within a second you see the controls, the prompt box and a moving bar "Loading the model's''',
    '''  * Page: title at the top (status "Ready" etc. small at the top right), then ONE row — "Prompt [dropdown] or type:
    [prompt box] [Run / continue] [Reset]" — the token chips under the box, a quiet "Options ▸" line (seed and
    temperature), the progress line and then the generated text in large type; practical notes in the footer.
  * Loading: within a second you see the title, the prompt row and a moving bar "Loading the model's''')
rep('''  * Sampling (optional): two selects next to the status line. "Seed": auto''', '''  * Sampling (optional): click "Options ▸" (closed by default) to show two selects. "Seed": auto''')
rep('''    After Run the status line shows the seed and temperature actually used,''', '''    After Run the Options line shows the seed and temperature actually used,''')
rep('''a 13th, orange segment fills''', '''a 13th, amber segment fills''')
rep('''("vocabulary head: 50,257 rows → next token…")''', '''("vocabulary head (choosing the next token)"; on prompt steps "absorbed")''')
rep('''read it off the status line if you want to replay the run.''', '''read it off the Options line if you want to replay the run.''')
(new / "README.txt").write_text(r)
b = (live / "BUILD.md").read_text()
head = f"""# bundles/demo-{variant} — round 8 (R8U): production page layout on the round-7 bundle (model, controls and handshakes unchanged)

Built by R8U on 2026-10-02 with `work/2026-09-19/R8U/compile.sh` (= `R7X/compile.sh` + the `R8U_LAYOUT` passthrough, default 1; tools copy
`work/2026-09-19/R8U/tools` = `R7X/tools` + `r8u_layout.py` + module constants `PANEL_TOP`/`TOKENS_TOP` (r6p_prompt.py) and `WARN_TOP`
(r7h_id_guard.py) whose defaults are the old literals + the R8U block in `browser_gpt2_runtime.py`). `R8U_LAYOUT=0` rebuilds the round-7 bundle
byte for byte (index.html + runtime.css; R8U.md §2).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U
export R7B_PREFILL_HEAD_SKIP=1 R7B_CAPACITY_36=1 R7B_SAMPLING=1 R7B_NEW_TOKENS=32 R7H_ID_GUARD=1 R6X_SCROLLBAR_FIX=1 R8U_LAYOUT=1
{"VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 ./compile.sh <out> 36 12" if variant == "c32" else "./compile.sh <out> 8 12"}
```

Layout (R8U.md §1): title "GPT-2 in CSS" + one muted line (status small at the top right); one row "Prompt [dropdown] or type: [the
unchanged `.tk-root {{ --draft-prompt: "…"; }}` editor] [Run / continue] [Reset]"; token chips under the editor; a quiet native
`<details>` "Options ▸" line with Seed / Sampling / readout; small progress line + 4 px bar; generated text 22 px; footer = practical notes.
DOM of .controls unchanged except one `<details class="r8u-opt">` after Reset; new body child `<header class="r8u-head">` (exempt from the
early-paint lock, styled inline). Offline: model core rules identical in multiset and order (R8U/check_layout_diff.py), witnesses identical,
static no-JS rc 0, pack dry-run resolves every url(). Previous BUILD.md (round 7) follows.

---

"""
(new / "BUILD.md").write_text(head + b)
print("ok", new)
