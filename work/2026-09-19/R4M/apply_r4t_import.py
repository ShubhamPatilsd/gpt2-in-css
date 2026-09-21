"""R4M: R4T's `import r4t_consumer_chunk as r4t` in browser_gpt2_reused_adapter.py is adjacent to R4S's/R4D's import lines (the only
textual conflict of R4T's diff on the merged tree); insert it after R4D's import. usage: apply_r4t_import.py <tools-dir>"""
import sys, pathlib
p = pathlib.Path(sys.argv[1]) / "browser_gpt2_reused_adapter.py"; s = p.read_text()
old = "import r4d_flags as r4d\n"; new = old + "import r4t_consumer_chunk as r4t\n"
assert s.count(old) == 1 and "import r4t_consumer_chunk" not in s, "unexpected adapter import block"
p.write_text(s.replace(old, new)); print("R4T import inserted")
