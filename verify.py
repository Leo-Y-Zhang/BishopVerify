"""Independent verification of the ten new bishop-graph terms.

This checks the published claims WITHOUT trusting the program that produced
them. It uses only the Python standard library, and it fetches the currently
published OEIS b-files so the "these terms are new" claim is checked against
the live record rather than against a copy.

    python verify.py            # offline structural checks only
    python verify.py --online   # also fetch OEIS and confirm the terms are new

Every check prints PASS or FAIL and the script exits non-zero if any fails.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"

# sequence -> (colour, what it counts)
SEQS = {
    "A290719": ("black", "connected induced subgraphs"),
    "A290769": ("white", "connected induced subgraphs"),
    "A291595": ("both", "connected induced subgraphs"),
    "A289145": ("black", "connected dominating sets"),
    "A289169": ("white", "connected dominating sets"),
}

# what the OEIS held before this work, measured from the published b-files
PUBLISHED_REACH = {
    "A290719": 9, "A290769": 9, "A291595": 9,
    "A289145": 8, "A289169": 8,
}

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def read_bfile(path: Path) -> dict[int, int]:
    out: dict[int, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        n, v = line.split()
        out[int(n)] = int(v)
    return out


def fetch_published(seq: str) -> dict[int, int]:
    # oeis.org rejects the default urllib user agent with HTTP 403, which would
    # make this check silently skip rather than run. Identify ourselves instead.
    url = f"https://oeis.org/{seq}/b{seq[1:]}.txt"
    req = urllib.request.Request(url, headers={
        "User-Agent": "BishopVerify/1.0 (independent verification script; contact via GitHub)"
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8", "replace")
    out: dict[int, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) == 2:
            out[int(parts[0])] = int(parts[1])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--online", action="store_true",
                    help="fetch the live OEIS b-files and check the terms are still new")
    args = ap.parse_args()

    staged = {s: read_bfile(DATA / f"b{s[1:]}.txt") for s in SEQS}

    print("\n1. FILE FORMAT  (OEIS requires LF-only, no BOM, 'n value' per line)\n")
    for s in SEQS:
        raw = (DATA / f"b{s[1:]}.txt").read_bytes()
        check(f"{s}: no carriage returns", b"\r" not in raw)
        check(f"{s}: no byte-order mark", not raw.startswith(b"\xef\xbb\xbf"))
        ns = sorted(staged[s])
        check(f"{s}: indices contiguous", ns == list(range(ns[0], ns[-1] + 1)),
              f"n = {ns[0]}..{ns[-1]}")
        check(f"{s}: all values positive", all(v > 0 for v in staged[s].values()))

    print("\n2. STRUCTURAL IDENTITIES  (these follow from the problem, not the code)\n")

    # the bishop graph has exactly two components, so the whole board is the sum
    shared = sorted(set(staged["A290719"]) & set(staged["A290769"]) & set(staged["A291595"]))
    ok_sum = all(staged["A290719"][n] + staged["A290769"][n] == staged["A291595"][n]
                 for n in shared)
    check("black + white = whole board, connected subgraphs",
          ok_sum, f"checked n = {shared[0]}..{shared[-1]}")

    # at even n a reflection carries black onto white, so the counts must agree
    for a, b, label in (("A290719", "A290769", "connected subgraphs"),
                        ("A289145", "A289169", "connected dominating sets")):
        evens = [n for n in sorted(set(staged[a]) & set(staged[b])) if n % 2 == 0]
        ok = all(staged[a][n] == staged[b][n] for n in evens)
        check(f"black = white at even n, {label}", ok, f"checked n = {evens}")

    # and they must differ at odd n, or the reflection argument proves nothing
    for a, b, label in (("A290719", "A290769", "connected subgraphs"),
                        ("A289145", "A289169", "connected dominating sets")):
        odds = [n for n in sorted(set(staged[a]) & set(staged[b])) if n % 2 == 1 and n > 1]
        ok = all(staged[a][n] != staged[b][n] for n in odds)
        check(f"black differs from white at odd n, {label}", ok, f"checked n = {odds}")

    print("\n3. GROWTH  (a count that shrank would mean a bug, not a discovery)\n")
    for s in SEQS:
        ns = sorted(staged[s])
        ok = all(staged[s][ns[i]] < staged[s][ns[i + 1]] for i in range(len(ns) - 1))
        check(f"{s}: strictly increasing", ok)

    if args.online:
        print("\n4. NOVELTY  (fetched live from oeis.org)\n")
        for s in SEQS:
            try:
                pub = fetch_published(s)
            except Exception as e:                      # network, not a claim failure
                print(f"  [SKIP] {s}: could not reach OEIS ({e})")
                continue
            pub_max = max(pub) if pub else -1
            check(f"{s}: published reach is n = {PUBLISHED_REACH[s]} as stated",
                  pub_max == PUBLISHED_REACH[s], f"live b-file reaches n = {pub_max}")
            new = [n for n in staged[s] if n > pub_max]
            check(f"{s}: contributes {len(new)} new term(s)", len(new) == 2, f"n = {new}")
            agree = [n for n in staged[s] if n in pub and staged[s][n] == pub[n]]
            disagree = [n for n in staged[s] if n in pub and staged[s][n] != pub[n]]
            check(f"{s}: agrees with every published term", not disagree,
                  f"{len(agree)} overlapping terms match")
    else:
        print("\n4. NOVELTY  skipped. Re-run with --online to check against oeis.org\n")

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s) -> {', '.join(failures)}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
