import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from browser_gpt2_saved_run import completed_run


class SavedRunTests(unittest.TestCase):
    def test_incomplete_and_rebuilt_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source = directory / "runtime.css"
            source.write_text("body{color:red}")
            report = directory / "pipeline-results.json"
            record = {
                "complete": False,
                "artifactSha256": {
                    "runtime.css": hashlib.sha256(source.read_bytes()).hexdigest()
                },
            }
            report.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                completed_run(directory)
            record["complete"] = True
            report.write_text(json.dumps(record))
            self.assertTrue(completed_run(directory)["complete"])
            source.write_text("body{color:blue}")
            with self.assertRaises(ValueError):
                completed_run(directory)


if __name__ == "__main__":
    unittest.main()
