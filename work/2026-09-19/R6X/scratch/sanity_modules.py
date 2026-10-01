import sys, importlib.util
sys.path.insert(0, "tools")
import r6p_prompt as mine
spec = importlib.util.spec_from_file_location("r6p_owner", "../R6P/tools/r6p_prompt.py"); owner = importlib.util.module_from_spec(spec); spec.loader.exec_module(owner)
assert mine.panel_css(32) == owner.panel_css(32), "panel_css differs at default"
print("panel_css(32) byte-identical to R6P's at default:", len(mine.panel_css(32)), "chars")
import r6v_progress_ui as r6v
a = r6v.inline_style(1000); r6v.TOP_PX = 146; r6v.HIDE_SELECTOR = "body>:not(.controls):not(.ld):not(.tk-panel)"; b = r6v.inline_style(1000)
print("r6v honours module overrides:", "top:146px" in b and "top:52px" in a and ":not(.tk-panel){content-visibility:hidden}" in b and r6v.early_paint_runtime_css() == "body>:not(.controls):not(.ld):not(.tk-panel){content-visibility:visible}")
print("load_panel_css uses TOP_PX:", "top:146px" in r6v.load_panel_css("--x", 285) and "top:168px" in r6v.load_panel_css("--x", 285))
