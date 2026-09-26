"""Independent verification of the ten new bishop-graph terms.

This checks the published claims WITHOUT trusting the program that produced
them. It uses only the Python standard library, and it fetches the currently
published OEIS b-files so the agreement is checked against the live record
rather than against a copy.

    python verify.py            # offline structural checks only
    python verify.py --online   # also check against the live OEIS record

Every check prints PASS or FAIL and the script exits non-zero if any fails.
"""

from __future__ import annotations

import argparse
import re
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

# What the OEIS held BEFORE this work, measured from the published b-files at the
# time. All ten new terms were approved on 13 August 2026, so the live b-files now
# reach further than this. The numbers are kept because they are what separates
# the terms this work contributed from the terms it was checked against: agreement
# on somebody else's 41 values is evidence, agreement on our own 10 is not.
REACH_BEFORE_THIS_WORK = {
    "A290719": 9, "A290769": 9, "A291595": 9,
    "A289145": 8, "A289169": 8,
}

# The indices each staged b-file must hold: the OEIS offset up to the last term
# this work contributed. Every other check compares only the terms that are
# present, so without this a line deleted from a b-file would withdraw a claim
# (or one of the 41 terms it is checked against) and still pass.
CLAIMED_INDICES = {
    "A290719": (1, 11), "A290769": (2, 11), "A291595": (1, 11),
    "A289145": (1, 10), "A289169": (2, 10),
}

failures: list[str] = []

# Every term with n <= this is recomputed from first principles rather than
# trusted from data/, in all five sequences. n = 6 is the largest board where
# brute force still finishes in about a second (18 vertices per colour, so
# 2**18 candidate subsets); n = 7 would be 2**25.
RECOMPUTE_MAX_N = 6

# One line of a b-file: an index and a value, each in plain decimal. int()
# alone would also accept "+5", "1_000" and surrounding whitespace.
BFILE_LINE = re.compile(r"(0|-?[1-9][0-9]*) (0|-?[1-9][0-9]*)")


def color_squares(n: int, parity: int) -> list[tuple[int, int]]:
    """The squares of one colour on an n x n board, 0-indexed.

    Matches the convention the b-files were measured under: (0, 0) is black,
    and two squares share a colour iff (row + col) has the same parity.
    """
    return [(r, c) for r in range(n) for c in range(n) if (r + c) % 2 == parity]


def bishop_adjacency(squares: list[tuple[int, int]]) -> list[int]:
    """adj[i] is a bitmask of the squares a bishop on squares[i] attacks.

    Two squares share a diagonal -- and so attack each other, at any range,
    since nothing here models blocking pieces -- iff their coordinates have
    equal sum or equal difference.
    """
    k = len(squares)
    adj = [0] * k
    for i, (ri, ci) in enumerate(squares):
        for j, (rj, cj) in enumerate(squares):
            if i != j and (ri + ci == rj + cj or ri - ci == rj - cj):
                adj[i] |= 1 << j
    return adj


def count_connected_subsets(adj: list[int]) -> tuple[int, int]:
    """(connected induced subgraphs, connected dominating sets) of a graph.

    Both count non-empty vertex subsets that induce a connected subgraph; the
    second counts only those that also dominate, i.e. every vertex is in the
    subset or adjacent to one in it. Brute force over every subset: no
    shortcut that could share a bug with whatever produced the committed
    values. Fine up to about twenty vertices; the 6x6 board has 18 per colour.
    """
    k = len(adj)
    everything = (1 << k) - 1
    closed = [adj[v] | (1 << v) for v in range(k)]
    connected = dominating = 0
    for mask in range(1, 1 << k):
        start = (mask & -mask).bit_length() - 1
        seen = frontier = 1 << start
        while frontier:
            nxt = 0
            f = frontier
            while f:
                v = (f & -f).bit_length() - 1
                f &= f - 1
                nxt |= adj[v] & mask
            nxt &= ~seen
            seen |= nxt
            frontier = nxt
        if seen == mask:
            connected += 1
            covered = 0
            m = mask
            while m:
                v = (m & -m).bit_length() - 1
                m &= m - 1
                covered |= closed[v]
            if covered == everything:
                dominating += 1
    return connected, dominating


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
                    help="fetch the live OEIS b-files and check them against these")
    ap.add_argument("--require-online", action="store_true",
                    help="with --online, treat an unreachable OEIS as a failure "
                         "rather than a skip")
    args = ap.parse_args()
    if args.require_online:
        args.online = True

    staged = {s: read_bfile(DATA / f"b{s[1:]}.txt") for s in SEQS}

    print("\n1. FILE FORMAT  (OEIS requires LF-only, no BOM, 'n value' per line)\n")
    for s in SEQS:
        raw = (DATA / f"b{s[1:]}.txt").read_bytes()
        check(f"{s}: no carriage returns", b"\r" not in raw)
        check(f"{s}: no byte-order mark", not raw.startswith(b"\xef\xbb\xbf"))
        lines = [ln for ln in raw.decode("utf-8").split("\n")[:-1]
                 if not ln.startswith("#")] if raw.endswith(b"\n") else None
        well_formed = lines is not None and all(BFILE_LINE.fullmatch(ln) for ln in lines)
        check(f"{s}: every line is 'n value' in plain decimal, ending in a newline",
              well_formed)
        order = [int(ln.split()[0]) for ln in lines] if well_formed else []
        check(f"{s}: indices strictly increasing, no repeats",
              well_formed and order == sorted(set(order)))
        lo, hi = CLAIMED_INDICES[s]
        ns = sorted(staged[s])
        check(f"{s}: holds exactly the claimed terms", ns == list(range(lo, hi + 1)),
              f"n = {ns[0]}..{ns[-1]}, claimed {lo}..{hi}" if ns else "no terms")
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

    print("\n4. INDEPENDENT RECOMPUTATION  (first principles, nothing in data/ trusted)\n")
    # colour -> n -> (connected, dominating), by brute force on the board itself
    brute = {colour: {n: count_connected_subsets(bishop_adjacency(color_squares(n, parity)))
                      for n in range(1, RECOMPUTE_MAX_N + 1)}
             for colour, parity in (("black", 0), ("white", 1))}
    for s, (colour, what) in SEQS.items():
        which = 1 if what == "connected dominating sets" else 0
        ns = [n for n in range(1, RECOMPUTE_MAX_N + 1) if n in staged[s]]
        wrong = []
        for n in ns:
            colours = ("black", "white") if colour == "both" else (colour,)
            recomputed = sum(brute[c][n][which] for c in colours)
            if recomputed != staged[s][n]:
                wrong.append(f"a({n}) is {recomputed}, data/ says {staged[s][n]}")
        check(f"{s}: every term up to n = {RECOMPUTE_MAX_N} recomputed from the bishop graph",
              bool(ns) and not wrong,
              "; ".join(wrong) if wrong else f"n = {ns[0]}..{ns[-1]}" if ns else "no terms")

    skipped: list[str] = []
    if args.online:
        print("\n5. THE PUBLISHED RECORD  (fetched live from oeis.org)\n")
        independent = 0
        contributed = 0
        for s in SEQS:
            try:
                pub = fetch_published(s)
            except (OSError, ValueError) as e:
                # An OEIS outage is not a failure of these claims. Anything else
                # is a fault in this script, and must not be disguised as one:
                # a bare "except Exception" here once let a NameError print
                # ALL CHECKS PASSED while checking nothing.
                print(f"  [SKIP] {s}: could not reach OEIS ({e})")
                skipped.append(s)
                continue

            # Agreement on terms that predate this work is the evidence. Those
            # were computed by other people, so matching them says the method is
            # right. Agreement on our own terms says only that we can copy.
            before = REACH_BEFORE_THIS_WORK[s]
            # Every one of these was in the published b-file when it was measured,
            # so an absent one is not a term that agrees. Comparing only the ones
            # that happen to still be there would let this check pass having
            # compared nothing at all, which is the same false verdict as an
            # unnoticed exception, reached by a different route.
            expected = [n for n in staged[s] if n <= before]
            prior = [n for n in expected if n in pub]
            prior_gone = [n for n in expected if n not in pub]
            prior_bad = [n for n in prior if staged[s][n] != pub[n]]
            check(f"{s}: agrees with every term that predates this work",
                  not prior_bad and not prior_gone,
                  f"{len(prior)} of {len(expected)} independently published terms match"
                  + (f", {len(prior_gone)} no longer in the live b-file: {prior_gone}"
                     if prior_gone else ""))
            independent += len(prior)

            # The ten new terms were approved on 13 Aug 2026, so each must now be
            # in the live b-file, and must equal what was submitted.
            ours = [n for n in staged[s] if n > before]
            missing = [n for n in ours if n not in pub]
            altered = [n for n in ours if n in pub and staged[s][n] != pub[n]]
            check(f"{s}: the terms this work contributed are published",
                  not missing, f"n = {ours}" + (f", missing {missing}" if missing else ""))
            check(f"{s}: the published values match what was submitted", not altered,
                  "unchanged since approval" if not altered else f"differ at {altered}")
            contributed += len(ours) - len(missing)

            # Reported, never asserted: somebody else extending the sequence
            # further is not a failure of this repository.
            print(f"         live b-file reaches n = {max(pub) if pub else '-'}")

        if independent or contributed:
            print(f"\n  {independent} terms reproduced independently, "
                  f"{contributed} contributed terms confirmed published")
        if skipped:
            print(f"  NOT CHECKED against oeis.org: {', '.join(skipped)}")
            if args.require_online:
                failures.append(f"could not reach OEIS for {', '.join(skipped)}")
    else:
        print("\n5. THE PUBLISHED RECORD  skipped. Re-run with --online to check "
              "against oeis.org\n")

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s) -> {', '.join(failures)}")
        return 1
    # The verdict has to carry the caveat. A log read from the bottom must not
    # show an unqualified pass for a run that never reached the OEIS.
    if skipped:
        print(f"ALL CHECKS PASSED, but {len(skipped)} sequence(s) were never "
              f"checked against oeis.org")
        return 0
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
