#!/usr/bin/env python3
"""Serialize the unconventional probes without leaving stale directory locks.

Usage: python3 tools/run_unconventional_isolated.py --label NAME -- COMMAND ...
The advisory lock is released by the OS even if this process exits unexpectedly.
Only cooperating experiments are isolated; ordinary machine activity still exists.
"""

import argparse
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    lock_path = Path("/tmp/gpt2-css-unconventional-experiments.lock")
    with lock_path.open("a+") as lock:
        started = time.monotonic()
        print(f"[{args.label}] waiting for experiment lock", file=sys.stderr, flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        lock.seek(0)
        lock.truncate()
        lock.write(f"{os.getpid()} {args.label}\n")
        lock.flush()
        print(f"[{args.label}] acquired after {time.monotonic() - started:.3f}s", file=sys.stderr, flush=True)
        child = subprocess.Popen(command, start_new_session=True)

        def forward(sig, _frame):
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                pass

        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, forward)
        status = child.wait()
        return status if status >= 0 else 128 - status


if __name__ == "__main__":
    raise SystemExit(main())
