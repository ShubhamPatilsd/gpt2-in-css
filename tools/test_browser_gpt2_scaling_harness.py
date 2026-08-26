"""Protect experimental evidence from lost failures or mismatched reruns.

No browser is launched. These tests cover actual review findings that could
otherwise turn a failed or different experiment into an apparent success.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import investigate_browser_gpt2_scaling as driver


class EvidenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.result = self.root / "runs/baseline-c2-l1-p1-r0/results.json"

    def invoke(self, *extra):
        args = [
            "probe",
            "--variants",
            "baseline",
            "--capacity",
            "2",
            "--positions",
            "1",
            "--query-updates",
            "1",
            *extra,
        ]
        with (
            patch.object(driver, "OUT", self.root),
            patch("sys.argv", args),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return driver.main()

    def save(self, **values):
        data = {
            "variant": "baseline",
            "capacity": 2,
            "layers": 1,
            "positions": 1,
            "repeat": 0,
            "queryUpdates": 1,
            "traceRequested": False,
            "passed": True,
            "samples": [],
            **values,
        }
        self.result.parent.mkdir(parents=True)
        self.result.write_text(json.dumps(data))
        return self.result.read_bytes()

    def test_compile_failure_is_saved_and_returns_failure(self):
        with (
            patch.object(
                driver,
                "run_case",
                side_effect=ValueError("missing native base compensation"),
            ),
            self.assertRaises(SystemExit),
        ):
            self.invoke()
        data = json.loads(self.result.read_text())
        self.assertFalse(data["passed"])
        self.assertIn("compilation", data["failurePhase"])
        self.assertIn("missing native base compensation", data["exception"])

    def test_failed_trace_cannot_be_hidden_by_successful_timing_on_rerun(self):
        original = self.save(traceRequested=True, tracePassed=False)
        with patch.object(driver, "run_case") as run:
            with self.assertRaises(SystemExit):
                self.invoke("--trace")
            run.assert_not_called()
        self.assertEqual(self.result.read_bytes(), original)

    def test_rerun_with_changed_query_count_is_rejected_without_overwrite(self):
        original = self.save(queryUpdates=4)
        with patch.object(driver, "run_case") as run:
            with self.assertRaises(SystemExit) as exc:
                self.invoke()
            self.assertEqual(exc.exception.code, 2)
            run.assert_not_called()
        self.assertEqual(self.result.read_bytes(), original)

    def test_existing_matching_success_is_preserved(self):
        original = self.save()
        with patch.object(driver, "run_case") as run:
            self.invoke()
            run.assert_not_called()
        self.assertEqual(self.result.read_bytes(), original)

    def test_zero_positions_and_invalid_counts_do_not_become_valid_runs(self):
        for extra in (
            ("--positions", "0"),
            ("--repeats", "0"),
            ("--query-updates", "-1"),
        ):
            with self.subTest(extra=extra), patch.object(driver, "run_case") as run:
                with self.assertRaises(SystemExit) as exc:
                    self.invoke(*extra)
                self.assertEqual(exc.exception.code, 2)
                run.assert_not_called()
        self.assertFalse(self.result.exists())


if __name__ == "__main__":
    unittest.main()
