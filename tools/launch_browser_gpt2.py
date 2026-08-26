#!/usr/bin/env python3
"""Serve the compiled static model and launch a separate stock Chromium profile.

No JavaScript, CDP, inference endpoint, or token scheduler. The user clicks Run
in the document. Only the HTML/CSS and their explicit local assets are served.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "experiments/browser-gpt2/demo-font-vector-twelve"


def chrome_binary():
    candidates = [
        os.environ.get("CHROME_BIN"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        *(
            shutil.which(name)
            for name in ("google-chrome", "chromium", "chromium-browser")
        ),
    ]
    return next(
        (str(Path(p).resolve()) for p in candidates if p and Path(p).is_file()), None
    )


def static_assets(directory, root=ROOT):
    root, directory = root.resolve(), directory.resolve()
    page = directory / "index.html"
    pending, allowed = [page, directory / "runtime.css"], set()
    while pending:
        path = pending.pop().resolve()
        if path in allowed:
            continue
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Missing or out-of-workspace static asset: {path}")
        allowed.add(path)
        if path.suffix not in (".css", ".html"):
            continue
        source = path.read_text()
        if path.suffix == ".html" and (
            re.search(r"<script\b|\bon\w+\s*=|javascript:", source, re.IGNORECASE)
            or "script-src 'none'" not in source
        ):
            raise ValueError("Document does not satisfy the no-JavaScript contract")
        urls = re.findall(r"url\([\s\"\']*([^\"\')]+)", source)
        if path.suffix == ".html":
            urls += re.findall(r'<link\b[^>]*\bhref="([^\"]+)"', source)
        for url in urls:
            parsed = urlparse(url.strip())
            if not parsed.path or parsed.scheme == "data":
                continue
            if parsed.scheme or parsed.netloc:
                raise ValueError(f"Non-local runtime asset: {url}")
            pending.append((path.parent / unquote(parsed.path)).resolve())
    return allowed


class StaticModelHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, root, allowed, **kwargs):
        self.allowed = allowed
        super().__init__(*args, directory=str(root), **kwargs)

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if Path(self.translate_path(self.path)).resolve() not in self.allowed:
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):
        if Path(self.translate_path(self.path)).resolve() not in self.allowed:
            self.send_error(404)
            return
        super().do_HEAD()

    def end_headers(self):
        self.send_header(
            "Content-Security-Policy", "script-src 'none'; object-src 'none'"
        )
        super().end_headers()


@contextmanager
def static_model_server(directory, port=0):
    """The same strict static server is used by the launcher and HTTP smoke test."""
    directory = directory.resolve()
    server = ThreadingHTTPServer(
        ("127.0.0.1", port),
        partial(StaticModelHandler, root=ROOT, allowed=static_assets(directory)),
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield (
            f"http://127.0.0.1:{server.server_port}/"
            + (directory / "index.html").relative_to(ROOT).as_posix()
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument(
        "--heap-growth-percent", type=int, choices=(0, 10, 25, 50, 100), default=10
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Serve only; do not launch Chrome"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check the static bundle without launching or serving",
    )
    args = parser.parse_args()
    directory = args.directory.resolve()
    allowed = static_assets(directory)
    if args.check:
        print(
            json.dumps(
                {
                    "directory": str(directory),
                    "staticFiles": len(allowed),
                    "assetBytes": sum(p.stat().st_size for p in allowed),
                    "runtimeJavaScript": False,
                },
                indent=2,
            )
        )
        return
    chrome = chrome_binary()
    if not args.no_open and not chrome:
        parser.error("Chrome/Chromium was not found; set CHROME_BIN or use --no-open")
    process = None
    with (
        static_model_server(directory, args.port) as url,
        tempfile.TemporaryDirectory(prefix="gpt2-css-browser-") as profile,
    ):
        try:
            print(
                f"Static model: {url}\nChoose a prompt, then click Run. Ctrl-C stops this server/profile.",
                flush=True,
            )
            if not args.no_open:
                preferences = Path(profile) / "Default" / "Preferences"
                preferences.parent.mkdir()
                preferences.write_text(
                    json.dumps(
                        {
                            "profile": {
                                "default_content_setting_values": {"javascript": 2}
                            }
                        }
                    )
                )
                command = [
                    chrome,
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    f"--user-data-dir={profile}",
                    f"--app={url}",
                ]
                if args.heap_growth_percent:
                    command.append(
                        f"--js-flags=--heap-growing-percent={args.heap_growth_percent}"
                    )
                process = subprocess.Popen(
                    command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                process.wait()
            else:
                threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
