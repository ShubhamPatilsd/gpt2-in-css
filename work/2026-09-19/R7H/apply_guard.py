"""R7H: patch the tools copy (R7H/tools = R6X/tools v6) with the id-guard hook. Idempotent; usage: python3 R7H/apply_guard.py"""
import pathlib, sys
import shutil
HERE = pathlib.Path(__file__).resolve().parent
shutil.copy(HERE / "r7h_id_guard.py", HERE / "tools" / "r7h_id_guard.py")  # the module lives outside tools/ so a rebase (rm -rf tools; cp -R R6X/tools) cannot lose it
T = HERE / "tools" / "browser_gpt2_runtime.py"
s = T.read_text()
def edit(old, new):
    global s
    if new in s: return
    if s.count(old) != 1: sys.exit(f"anchor not unique/found: {old[:60]!r} ({s.count(old)})")
    s = s.replace(old, new, 1)
edit("import r6v_progress_ui as r6v  # R6V: display-only progress UI\n",
     "import r6v_progress_ui as r6v  # R6V: display-only progress UI\nimport r7h_id_guard as r7h  # R7H: self-checking winner->token-id hop (calibration + agreement gates)\n")
edit("    front, output, control_css, timeline_names = feedback(capacity)\n",
     "    front, output, control_css, timeline_names = feedback(capacity)\n"
     "    front, output, control_css, timeline_names = r7h.apply(front, output, control_css, timeline_names, capacity)  # R7H (flag R7H_ID_GUARD)\n")
T.write_text(s); print("R7H hook applied")
