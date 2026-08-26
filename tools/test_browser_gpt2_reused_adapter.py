"""Cheap controller contracts; real Chromium integration remains mandatory."""

import re
import unittest
from unittest.mock import patch

from browser_gpt2_reused_adapter import compile_reused_runtime_core
from browser_gpt2_reused_core import isolate_metric_state
from probe_native_reused_loop import loop_parts


class ReusedAdapterTests(unittest.TestCase):
    def test_metric_isolation_preserves_font_settings_and_numeric_branch(self):
        source = (
            '@container runtime style(--layer:0){.shared-proj-pack0{font-family:a,b,c;font-variation-settings:"A000" calc(var(--hidden-000) / var(--range-proj))}}'
            ".shared-proj-c0{--out-000:calc(var(--r-000) + 3)}"
        )
        css = isolate_metric_state(source)
        self.assertIn(
            '--proj-settings-0:"A000" calc(var(--hidden-000) / var(--range-proj))', css
        )
        self.assertIn("font-variation-settings:var(--proj-settings-0)", css)
        self.assertIn(".shared-proj-c0{--out-000:calc(var(--r-000) + 3)}", css)
        self.assertIn(".shared-proj>.scroller{--x-000:initial", css)
        self.assertNotIn("--epoch:initial", css)
        self.assertEqual(css.count("{"), css.count("}"))

    def test_head_owns_token_boundaries_and_pass_is_private(self):
        source, output, css = loop_parts(768, 6, centered=True)
        body = source.replace(
            "{child}",
            '<div class="reused-output" id="reused-result">'
            + output.replace("{child}", "")
            + "</div>",
        )
        with patch(
            "browser_gpt2_reused_adapter.compile_reused", return_value=(body, css)
        ):
            html, compiled, metadata = compile_reused_runtime_core(2, 3)
        for step in (2, 4):
            self.assertNotIn(f"body:has(#loop-advanced-{step}.done){{--pass:", compiled)
            self.assertIn(
                f":where(body:has(#token-{step // 2}-advanced.done)) .core-controller{{--pass:{step + 1}}}",
                compiled,
            )
        self.assertIn(
            'syntax:"<number>";inherits:false;initial-value:0',
            re.search(r"@property --pass\{[^}]+", compiled)[0],
        )
        self.assertIn(
            "@container loopcontrol style(--pass:6){.core-block{--native-pass:6}}",
            compiled,
        )
        self.assertIn(".reused-input{--epoch:var(--native-pass)}", compiled)
        self.assertTrue(
            all(
                "--native-pass" not in m[0]
                for m in re.finditer(r"\.core-controller\{[^}]+\}", compiled)
            )
        )
        self.assertEqual(compiled.count("{"), compiled.count("}"))
        self.assertIn('id="core-result"', html)
        self.assertNotIn("<script", html.lower())
        self.assertTrue(metadata["nativeLayerTokenHandshake"])
        self.assertTrue(metadata["localLayerContainer"])
        self.assertIn('class="core-controller"', html)
        self.assertNotIn("@container runtime ", compiled)
        self.assertIn(
            ".core-controller:where(:has(#loop-advanced-3.done)){--pass:4}", compiled
        )


if __name__ == "__main__":
    unittest.main()
