#!/usr/bin/env python3
"""Precompress the CSS-only TinyStories page for static HTTP hosting."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = [
    ROOT
    / "output-head-benchmark"
    / "generated"
    / "clustered-256-embedding-packed8-shared-runtime.css",
    ROOT / "tinystories" / "recurrent.css",
    ROOT / "tinystories" / "nested-runtime.css",
    ROOT / "tinystories" / "streaming.css",
    ROOT / "tinystories" / "streaming-packed8.html",
]
EXPERIMENT_ASSETS = [
    ROOT
    / "output-head-benchmark"
    / "generated"
    / "clustered-256-embedding-packed8-score-token-shared-runtime.css",
    ROOT
    / "output-head-benchmark"
    / "generated"
    / "clustered-256-embedding-packed8-row-int8-shared-runtime.css",
    ROOT
    / "output-head-benchmark"
    / "generated"
    / "clustered-256-embedding-packed8-row-int10-shared-runtime.css",
    ROOT / "tinystories" / "streaming-packed8-score-token.html",
    ROOT / "tinystories" / "streaming-packed8-row-int8.html",
    ROOT / "tinystories" / "streaming-packed8-row-int10.html",
]


def write_gzip(source: Path) -> Path:
    target = source.with_name(source.name + ".gz")
    with source.open("rb") as input_file, target.open("wb") as output_file:
        with gzip.GzipFile(
            fileobj=output_file,
            mode="wb",
            filename="",
            mtime=0,
            compresslevel=9,
        ) as compressed:
            shutil.copyfileobj(input_file, compressed, length=1024 * 1024)
    return target


def write_brotli(source: Path, executable: str) -> Path:
    target = source.with_name(source.name + ".br")
    subprocess.run(
        [executable, "-q", "9", "-f", "-o", str(target), str(source)],
        check=True,
    )
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiments",
        action="store_true",
        help="also precompress score/token and row-quantized candidates",
    )
    arguments = parser.parse_args()
    assets = ASSETS + EXPERIMENT_ASSETS if arguments.experiments else ASSETS
    missing = [path for path in assets if not path.exists()]
    if missing:
        formatted = "\n".join(f"  {path.relative_to(ROOT)}" for path in missing)
        raise SystemExit(
            f"build TinyStories before precompressing; missing:\n{formatted}"
        )
    brotli = shutil.which("brotli")
    if brotli is None:
        raise SystemExit("brotli executable not found")

    results = []
    for source in assets:
        gzip_path = write_gzip(source)
        brotli_path = write_brotli(source, brotli)
        results.append(
            {
                "path": str(source.relative_to(ROOT)),
                "raw_bytes": source.stat().st_size,
                "gzip_bytes": gzip_path.stat().st_size,
                "brotli_bytes": brotli_path.stat().st_size,
            }
        )
    print(
        json.dumps(
            {
                "files": results,
                "total_raw_bytes": sum(item["raw_bytes"] for item in results),
                "total_gzip_bytes": sum(item["gzip_bytes"] for item in results),
                "total_brotli_bytes": sum(item["brotli_bytes"] for item in results),
                "javascript": False,
                "note": "The HTTP server must select .br/.gz and set Content-Encoding.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
