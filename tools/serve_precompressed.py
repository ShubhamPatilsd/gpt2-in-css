#!/usr/bin/env python3
"""Serve precompressed static HTML/CSS without adding client-side code."""

from __future__ import annotations

import argparse
import mimetypes
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def accepts_encoding(header: str, encoding: str) -> bool:
    wildcard_quality = None
    for item in header.split(","):
        parts = [part.strip() for part in item.split(";")]
        name = parts[0].lower()
        quality = 1.0
        for parameter in parts[1:]:
            if parameter.lower().startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        if name == encoding:
            return quality > 0
        if name == "*":
            wildcard_quality = quality
    return wildcard_quality is not None and wildcard_quality > 0


class PrecompressedHandler(SimpleHTTPRequestHandler):
    def send_head(self):  # type: ignore[no-untyped-def]
        original = Path(self.translate_path(self.path))
        if original.is_file():
            accepted = self.headers.get("Accept-Encoding", "")
            choices = []
            if accepts_encoding(accepted, "br"):
                choices.append(("br", original.with_name(original.name + ".br")))
            if accepts_encoding(accepted, "gzip"):
                choices.append(("gzip", original.with_name(original.name + ".gz")))
            for encoding, compressed in choices:
                if compressed.is_file():
                    return self._send_encoded(original, compressed, encoding)
        return super().send_head()

    def _send_encoded(  # type: ignore[no-untyped-def]
        self, original: Path, compressed: Path, encoding: str
    ):
        content = compressed.open("rb")
        try:
            self.send_response(200)
            content_type = mimetypes.guess_type(original.name)[0]
            self.send_header(
                "Content-Type", content_type or "application/octet-stream"
            )
            self.send_header("Content-Encoding", encoding)
            self.send_header("Content-Length", str(compressed.stat().st_size))
            self.send_header("Vary", "Accept-Encoding")
            cache_control = (
                "public, max-age=31536000, immutable"
                if original.suffix == ".css" and "?v=" in self.path
                else "no-cache"
            )
            self.send_header("Cache-Control", cache_control)
            self.end_headers()
            return content
        except Exception:
            content.close()
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4173)
    arguments = parser.parse_args()
    handler = partial(PrecompressedHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", arguments.port), handler)
    print(f"serving {ROOT} at http://127.0.0.1:{arguments.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
