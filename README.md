# BishopVerify

Independent verification for *Rotating the board: counting bishop arrangements
by turning them into rook arrangements*.

This repository exists so the paper's claims can be checked **without trusting
the program that produced them**, and without access to that program.

```sh
python verify.py            # structural checks, no network
python verify.py --online   # also check against the live OEIS record
```

No dependencies beyond the Python standard library. The run takes a few seconds
and prints PASS or FAIL for every check, exiting non-zero if any fails.

An unreachable oeis.org is reported as a skip rather than a failure, since an
outage there says nothing about these files — pass `--require-online` when you
need the absence of an answer to count as one.

## What it checks

**File format.** The five staged b-files are LF-only with no byte-order mark,
carry contiguous indices, and hold only positive values — the conditions the
OEIS requires of a submitted b-file.

**Structural identities.** These follow from the problem rather than from any
implementation, so they are evidence independent of the code:

- The bishop graph has exactly two components, so the whole-board count must be
  the sum of the black and white counts. Checked for every n where all three are
  known.
- At even n a reflection carries the black squares onto the white ones, so the
  two counts must be **equal**. Checked at n = 2, 4, 6, 8, 10.
- At odd n no such reflection exists, so they must **differ**. Checked at
  n = 3, 5, 7, 9, 11. This direction matters: if the counts agreed at odd n as
  well, the even-n agreement would be evidence of a bug rather than of symmetry.

**Monotonicity.** Every sequence is strictly increasing. A count that shrank as
the board grew would be an error, not a discovery.

**Independent recomputation.** Every check above is a comparison between
committed files, so a fabricated-but-internally-consistent set of numbers
would satisfy all of them. `a(6)` of A290719 is instead recomputed from
scratch — brute force over every connected induced subgraph of the 6x6
black-square bishop graph — and compared against the committed value. See
`test_tamper.py` for a demonstration: it changes three committed values
together in a way that keeps every self-consistency check above satisfied,
and confirms only this recomputation catches it.

**Against the live record.** With `--online`, the script fetches the currently
published b-file for each sequence directly from oeis.org and separates two
questions that are easy to run together and mean very different things:

- **Do these files agree with terms computed by other people?** Every term that
  predates this work — 41 of them across the five sequences, contributed by Eric
  W. Weisstein and Andrew Howroyd — must match. This is the evidence.
- **Did the ten new terms land, unaltered?** Each must now be present in the live
  b-file and equal to what was submitted.

The first check is the important one. Agreement on 41 independently published
values is far stronger evidence for the method than any statement made about it
in the paper. Agreement on our own ten says only that we can copy, which is why
they are counted separately rather than folded into one total.

The published reach is reported, never asserted. If somebody extends one of these
sequences further, that is not a failure of this repository.

## What it does not do

It does not recompute the ten new values. Doing so requires the counting engine
and, at n = 11, about twenty-seven minutes and several gigabytes; that work lives
in a separate private repository. What is offered here is everything needed to
check the values for internal consistency, for agreement with the published
record, and for conformance to the identities the problem forces.

An independent recomputation remains the strongest possible check, and the
method is described in full in the paper precisely so that someone can attempt
one.

## The ten new values

All ten were approved by the OEIS on 13 August 2026 and are now the published
record. `--online` confirms that on every run.

| Sequence | New terms | Counts |
| --- | --- | --- |
| A290719 | a(10), a(11) | connected induced subgraphs, black squares |
| A290769 | a(10), a(11) | connected induced subgraphs, white squares |
| A291595 | a(10), a(11) | connected induced subgraphs, whole board |
| A289145 | a(9), a(10) | connected dominating sets, black squares |
| A289169 | a(9), a(10) | connected dominating sets, white squares |

The values themselves are in `data/`, in OEIS b-file format.

## Provenance

The sequences were contributed to the OEIS by Eric W. Weisstein in 2017. The
most recent additions before this work were made by Andrew Howroyd in August and
September of that year.
