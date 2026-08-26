import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from launch_browser_gpt2 import StaticModelHandler, static_assets


class StaticLauncherTests(unittest.TestCase):
    def test_only_explicit_assets_are_served_with_script_blocking(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "index.html").write_text(
                '<meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><link rel="stylesheet" href="runtime.css">'
            )
            (root / "runtime.css").write_text(
                '@font-face{font-family:a;src:url("weights.woff2?version=1")}'
            )
            (root / "weights.woff2").write_bytes(b"fixture font")
            (root / "private.txt").write_text("not a runtime asset")
            allowed = static_assets(root, root)
            self.assertEqual(len(allowed), 3)
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                partial(StaticModelHandler, root=root, allowed=allowed),
            )
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urllib.request.urlopen(
                    base + "/weights.woff2?version=1"
                ) as response:
                    self.assertEqual(response.read(), b"fixture font")
                    self.assertIn(
                        "script-src 'none'", response.headers["Content-Security-Policy"]
                    )
                with self.assertRaises(urllib.error.HTTPError) as missing:
                    urllib.request.urlopen(base + "/private.txt")
                self.assertEqual(missing.exception.code, 404)
                missing.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join()
            (root / "runtime.css").write_text(
                '@font-face{src:url("https://example.com/font.woff2")}'
            )
            with self.assertRaises(ValueError):
                static_assets(root, root)


if __name__ == "__main__":
    unittest.main()
