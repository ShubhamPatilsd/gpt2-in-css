"""R3M: apply the R3H block-flow hook to a merged tools tree (deterministic exact-string edits; usage: apply_r3h_hook.py <tools-dir>).

Same three hunks as r3h-hook.diff. The import hunk is placed after R3F's `import r2g_has_scope as r2g` when that
line exists (R3F's import hunk and this one are adjacent lines -> the only textual overlap of the merge), else
after `import r2c_hoist as r2c`."""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / "browser_gpt2_runtime.py"
s = p.read_text()
assert "r3h_blockflow_max" not in s, "hook already applied"
anchor = "import r2g_has_scope as r2g\n" if "import r2g_has_scope as r2g\n" in s else "import r2c_hoist as r2c\n"
assert s.count(anchor) == 1, anchor
s = s.replace(anchor, anchor + "import r3h_blockflow_max as r3h\n")
old_hook = "        head_css, head_bank_regs, head_bank_decls = f4.pack_head_input(head_css)\n"
assert s.count(old_hook) == 1
s = s.replace(old_hook, old_hook + (
    "    if r3h.BLOCKFLOW_MAX:\n"
    "        # R3H #1 (#176): coarse groups become block containers of in-flow\n"
    "        # zero-height rows; a block's max-content width is the max child width,\n"
    "        # i.e. the same quantity the single max-content grid track computed.\n"
    "        head_css = r3h.blockflow_max(head_css)\n"))
old_meta = "        **r2d.manifest(),\n"
assert s.count(old_meta) == 1
s = s.replace(old_meta, old_meta + "        r3hBlockflowMax=r3h.BLOCKFLOW_MAX,\n")
p.write_text(s)
print(f"R3H hook applied to {p} (import anchored after {anchor.strip()!r})")
