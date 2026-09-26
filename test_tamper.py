"""Tamper tests for verify.py.

This is deliberately not a unit test of a function; it runs the actual gate,
against a copy of the repository with the committed data corrupted, and
requires the gate to fail. The first corruption changes one triple of values
together so that every self-consistency check (file format, the black+white
sum identity, black=white at even n, strict growth) still passes -- only the
first-principles recomputation in verify.py can tell the numbers are wrong.
Before the recomputation check existed, an internally-consistent-but-false
set of numbers like this one would have made the gate print ALL CHECKS
PASSED. So did most of the corruptions in CORRUPTIONS below.

The checks against oeis.org are exercised the same way, with the live b-file
replaced by a fixture built from the committed data, so they run offline.

    python3 test_tamper.py

Prints PASS/FAIL and exits non-zero on failure, matching verify.py's own
convention. No third-party dependencies.
"""

from __future__ import annotations

import contextlib
import os
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


# (description, edits), where an edit is (file, old, new); new=None deletes
# the line and old=None appends new. All but the cut-off line once passed the
# offline gate; that one was caught only because the stump broke strict growth.
CORRUPTIONS = [
    ("the last claimed term of three sequences deleted together", [
        ("b290719.txt", "11 2265142469367980614\n", None),
        ("b290769.txt", "11 1134335726831043925\n", None),
        ("b291595.txt", "11 3399478196199024539\n", None),
    ]),
    ("the first term of a sequence deleted", [
        ("b289145.txt", "1 1\n", None),
    ]),
    ("a b-file cut off part-way through its last line", [
        ("b289169.txt", "10 1073633875253120\n", "10 10736"),
    ]),
    ("a line repeated at the end of a b-file", [
        ("b289145.txt", None, "5 4528\n"),
    ]),
    ("a value written with a digit separator", [
        ("b289145.txt", "9 2014079802496\n", "9 2_014079802496\n"),
    ]),
    ("a(6) of both connected-dominating-set sequences lowered together", [
        ("b289145.txt", "6 176192\n", "6 176191\n"),
        ("b289169.txt", "6 176192\n", "6 176191\n"),
    ]),
    ("a(3) of the black and whole-board sequences lowered together", [
        ("b290719.txt", "3 22\n", "3 21\n"),
        ("b291595.txt", "3 35\n", "3 34\n"),
    ]),
]


def edit(data: Path, filename: str, old: str | None, new: str | None) -> None:
    path = data / filename
    text = path.read_text()
    if old is None:
        path.write_text(text + (new or ""))
        return
    if old not in text:
        raise SystemExit(f"FAIL: expected line {old!r} not found in {filename}; "
                         f"update the corruption to match the committed data")
    path.write_text(text.replace(old, new or "", 1))


def run_online(copy: Path, published: dict[str, str | None]) -> int:
    """Run verify.py --online in-process against fixture b-files.

    published maps a sequence to the text the live b-file would return, or to
    None for one oeis.org cannot be reached for.
    """
    sys.path.insert(0, str(copy))
    try:
        import verify
    finally:
        sys.path.pop(0)
    verify.failures.clear()

    def fake_fetch(seq: str) -> dict[int, int]:
        text = published[seq]
        if text is None:
            raise OSError("fixture: unreachable")
        out = {}
        for line in text.splitlines():
            n, v = line.split()
            out[int(n)] = int(v)
        return out

    verify.fetch_published = fake_fetch
    verify.DATA = copy / "data"
    argv = sys.argv
    sys.argv = ["verify.py", "--online"]
    try:
        with open(os.devnull, "w") as quiet, contextlib.redirect_stdout(quiet):
            return verify.main()
    finally:
        sys.argv = argv


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

    failed = 0
    for description, edits in CORRUPTIONS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "repo"
            shutil.copytree(REPO, copy, ignore=shutil.ignore_patterns(".git"))
            for filename, old, new in edits:
                edit(copy / "data", filename, old, new)
            ok = run_verify(copy) != 0
            print(f"{'PASS' if ok else 'FAIL'}: {description} "
                  f"{'makes the gate fail' if ok else 'still passes the gate'}")
            failed += not ok

    # --online, against fixtures. The honest record is the committed data.
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "repo"
        shutil.copytree(REPO, copy, ignore=shutil.ignore_patterns(".git"))
        record = {s: (copy / "data" / f"b{s[1:]}.txt").read_text()
                  for s in ("A290719", "A290769", "A291595", "A289145", "A289169")}
        altered = dict(record, A289145=record["A289145"].replace(
            "10 1073633875253120", "10 1073633875253121"))
        withdrawn = dict(record, A290769=record["A290769"].replace("3 13\n", ""))
        unreachable = dict(record, A291595=None)
        cases = [
            ("the committed data against an identical live record", record, 0),
            ("a contributed term that differs from the live record", altered, 1),
            ("a term that predates this work missing from the live record", withdrawn, 1),
            ("oeis.org unreachable for one sequence, without --require-online",
             unreachable, 0),
        ]
        for description, published, expected in cases:
            rc = run_online(copy, published)
            ok = rc == expected
            print(f"{'PASS' if ok else 'FAIL'}: --online, {description}: "
                  f"exit {rc}, expected {expected}")
            failed += not ok

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
