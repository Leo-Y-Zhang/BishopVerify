"""Tamper test for the independent-recomputation check in verify.py.

This is deliberately not a unit test of a function; it runs the actual gate,
against a copy of the repository with one triple of committed values changed
together so that every self-consistency check (file format, the black+white
sum identity, black=white at even n, strict growth) still passes -- only the
first-principles recomputation in verify.py can tell the numbers are wrong.
That is the gap this file exists to close: before the recomputation check
existed, an internally-consistent-but-false set of numbers like this one
would have made the gate print ALL CHECKS PASSED.

    python3 test_tamper.py

Prints PASS/FAIL and exits non-zero on failure, matching verify.py's own
convention. No third-party dependencies.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent

# A290719(6) = A290769(6) = 194751 and A291595(6) = 389502 in the real data.
# Lowering all three by the same shape (194751 -> 194750, doubled -> 389500)
# keeps every existing structural check satisfied: the sum still matches, the
# black/white pair is still equal at this even n, and every sequence is still
# strictly increasing. Only recomputing a(6) from the bishop graph itself
# reveals it is wrong.
TAMPERS = {
    "b290719.txt": ("6 194751\n", "6 194750\n"),
    "b290769.txt": ("6 194751\n", "6 194750\n"),
    "b291595.txt": ("6 389502\n", "6 389500\n"),
}


def run_verify(cwd: Path) -> int:
    return subprocess.run(
        [sys.executable, "verify.py"], cwd=cwd,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "repo"
        shutil.copytree(REPO, copy, ignore=shutil.ignore_patterns(".git"))

        rc = run_verify(copy)
        if rc != 0:
            print(f"FAIL: gate did not pass on an untampered copy first (exit {rc})")
            return 1

        for filename, (old, new) in TAMPERS.items():
            path = copy / "data" / filename
            text = path.read_text()
            if old not in text:
                print(f"FAIL: expected line {old!r} not found in {filename}; "
                      f"update TAMPERS to match the current committed data")
                return 1
            path.write_text(text.replace(old, new, 1))

        rc = run_verify(copy)
        if rc == 0:
            print("FAIL: gate still passed after a self-consistent but wrong "
                  "value replaced the real one -- the recomputation check did "
                  "not catch it")
            return 1

        print("PASS: a self-consistent but wrong committed value makes the "
              "gate fail")
        return 0


if __name__ == "__main__":
    sys.exit(main())
