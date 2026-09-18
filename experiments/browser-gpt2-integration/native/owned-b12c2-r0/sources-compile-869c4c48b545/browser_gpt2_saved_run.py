"""Reject stale or incomplete artifacts before reporting numerical quality."""

import hashlib
import json


def completed_run(directory, prefix=""):
    run = json.loads((directory / (prefix + "pipeline-results.json")).read_text())
    if not run.get("complete"):
        raise ValueError(
            "A partial run cannot reuse previous completed numerical artifacts"
        )
    for name, digest in run.get("artifactSha256", {}).items():
        current = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if current != digest:
            raise ValueError(f"Runtime artifact changed after measurement: {name}")
    return run
