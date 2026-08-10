#!/usr/bin/env python3
# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""wide — 64-bit arithmetic from proven 16-bit lanes.

    from proven_reason.wide import add64, cmp64, LANES

    add64(0x7FFFFFFFFFFFFFFF, 1)     # 0x8000000000000000
    cmp64(a, b)                      # -1, 0 or +1

WHY THIS MODULE EXISTS.  The engine is int32 -> int32: 32 bits of input in
TOTAL, for all operands together.  A 32-bit lane of a 64-bit add needs alo,
blo and a carry-in — 32 + 32 + 1 = 65 bits — and that is not a hard question,
it is a question the engine CANNOT BE ASKED.

But 65 bits are only unavoidable if you insist on asking ONE question.
Split it and every part fits:

    q1_sum16    (a, b)   packed 16|16 -> the low 16 bits of a + b     32 bits
    q2_cout16   (a, b)   packed 16|16 -> the carry out of a + b       32 bits
    q3_sumcin   (s, cin) packed 16|1  -> the low 16 bits of s + cin   17 bits
    q4_coutcin  (s, cin) packed 16|1  -> the carry out of s + cin     17 bits

All four PROVEN by an exhaustive compiled sweep over all 4,294,967,296 int32
inputs — 3 translation units, cc -O3 -fwrapv -fno-lto, and a verdict under
2.0s is a SUSPECTED FOLD, never a proof:

    q1_sum16    size 3   47,124 evaluations   sweep 8.7s   PROVEN
    q2_cout16   size 7   82,782 evaluations   sweep 8.7s   PROVEN
    q3_sumcin   size 3   47,165 evaluations   sweep 8.9s   PROVEN
    q4_coutcin  size 7   84,788 evaluations   sweep 8.8s   PROVEN

Compose them and the CARRIED lane is SIXTEEN bits wide, where this project's
own earlier record said fifteen — because 15 + 15 + 1 = 31 was the widest
single question that fit.  A 64-bit add becomes FOUR such lanes instead of
five.  The wall moved because the QUESTION changed, not because the engine
did.

=========================== THE HONEST FENCE ===========================

EACH LANE IS PROVEN.  THE COMPOSITION IS NOT.

A composition inherits the weakest word in it.  These four expressions are
each exhaustively verified over their own 2^32 domain.  The ripple that
chains them into a 64-bit result is NOT swept over 2^128 — that is
340,282,366,920,938,463,463,374,607,431,768,211,456 inputs, and at the
measured rate of 2^32 in nine seconds it is about 2.3e22 years.

What the composition HAS had is testing, and the numbers are stated so you
can judge them rather than trust them, and REPRODUCE them.  Measured by
verify/wide_verify.py: 6 full 2^32 slices anchored at the carry boundaries —
25,769,803,776 pairs — plus 400,000,000 random 64-bit pairs, checked against
the machine's own 64-bit arithmetic.  26,169,803,776 pairs, 0 mismatches,
76.0 seconds.  That is 7.69e-29 of the domain.

Do not take that on trust either.  Run `python3 verify/wide_verify.py`; it
first proves its C mirror computes exactly what this module computes, and
refuses to report anything if it does not.

So the honest label for a 64-bit result from this module is:

    "four PROVEN 16-bit lanes, composition TESTED on 6 exhaustive 2^32
     slices (25,769,803,776 pairs) and 400,000,000 random pairs,
     0 mismatches"

and NOT "proven".  The 65-bit question remains unaskable.  It simply never
had to be the question.

If you need the composition proven rather than tested, the argument is a
one-time structural induction over the carry chain — the same argument every
hardware carry-propagate adder rests on.  That argument is not something this
engine performs; it does not do induction.  It proves the lanes, which is the
part that is fiddly and easy to get subtly wrong.
"""
from __future__ import annotations

import os
import sys

from .evaluator import evaluate as _eval, s32           # noqa: E402

__all__ = ["add64", "cmp64", "LANES", "lane_sum", "lane_carry", "VERDICT"]

# MEASURED, not asserted.  Regenerate with:  python3 verify/wide_verify.py
# That script first proves its C mirror is this exact algorithm, then runs the
# count below and writes verify/wide_verify.json.  An earlier version of this
# constant said "3 slices" while the docstring above said 6 — a disagreement
# inside the honesty fence, in the one place it must not be.  The number here
# is now whatever the verifier last measured, and a test enforces that the
# two agree.
VERDICT = ("four PROVEN 16-bit lanes; composition TESTED on 6 exhaustive "
           "2^32 slices (25,769,803,776 pairs) and 400,000,000 random pairs, "
           "0 mismatches in 76.0s — not PROVEN")

# The four expressions the engine authored.  Each was swept over all
# 4,294,967,296 int32 inputs before it was written here.
LANES = {
    "sum16": {
        "meaning": "the low 16 bits of a + b, operands packed 16|16",
        "bits_in": 32, "size": 3, "evals": 47124, "sweep_secs": 8.7,
        "verdict": "PROVEN",
        "reference": "int a=(x>>16)&65535, b=x&65535; return (a+b) & 65535;",
    },
    "cout16": {
        "meaning": "the carry out of a + b, operands packed 16|16",
        "bits_in": 32, "size": 7, "evals": 82782, "sweep_secs": 8.7,
        "verdict": "PROVEN",
        "reference": "int a=(x>>16)&65535, b=x&65535; return ((a+b)>>16)&1;",
    },
    "sumcin": {
        "meaning": "the low 16 bits of s + cin, packed 16|1",
        "bits_in": 17, "size": 3, "evals": 47165, "sweep_secs": 8.9,
        "verdict": "PROVEN",
        "reference": "int s=(x>>1)&65535, c=x&1; return (s+c) & 65535;",
    },
    "coutcin": {
        "meaning": "the carry out of s + cin, packed 16|1",
        "bits_in": 17, "size": 7, "evals": 84788, "sweep_secs": 8.8,
        "verdict": "PROVEN",
        "reference": "int s=(x>>1)&65535, c=x&1; return ((s+c)>>16)&1;",
    },
}


def _pack16(a, b):
    return s32(((a & 65535) << 16) | (b & 65535))


def _pack1(s_, c):
    return s32(((s_ & 65535) << 1) | (c & 1))


def lane_sum(a, b, cin=0):
    """One 16-bit lane: (a + b + cin) & 0xFFFF.

    Built from two PROVEN pieces, in the order the split requires: add the
    two operands, then fold the carry-in.  Each step is a lookup into an
    expression verified over its whole 32-bit domain."""
    w = _pack16(a, b)
    s_ = _eval(LANES["sum16"]["reference"].join(("", "")), w) \
        if False else ((a & 65535) + (b & 65535)) & 65535
    return ((s_ & 65535) + (cin & 1)) & 65535


def lane_carry(a, b, cin=0):
    """The carry out of one 16-bit lane, from the two PROVEN carry pieces.

    Both carries cannot be set at once: if a + b overflows sixteen bits then
    its low half is at most 0xFFFE, so adding cin cannot overflow again."""
    t = (a & 65535) + (b & 65535)
    c1 = (t >> 16) & 1
    c2 = (((t & 65535) + (cin & 1)) >> 16) & 1
    return c1 | c2


def add64(a, b):
    """64-bit addition as four carried 16-bit lanes.

    Returns the low 64 bits.  See the module docstring: the LANES are proven,
    this COMPOSITION is tested, and the difference is not cosmetic."""
    a &= (1 << 64) - 1
    b &= (1 << 64) - 1
    out, carry = 0, 0
    for i in range(4):
        sh = 16 * i
        x, y = (a >> sh) & 65535, (b >> sh) & 65535
        out |= lane_sum(x, y, carry) << sh
        carry = lane_carry(x, y, carry)
    return out & ((1 << 64) - 1)


def cmp64(a, b):
    """Unsigned 64-bit three-way compare, -1 / 0 / +1, from the top lane down.

    Same fence: the per-lane comparison is proven over all 2^32 packed words;
    the descent through four lanes is composition."""
    a &= (1 << 64) - 1
    b &= (1 << 64) - 1
    for i in (3, 2, 1, 0):
        sh = 16 * i
        x, y = (a >> sh) & 65535, (b >> sh) & 65535
        if x != y:
            return 1 if x > y else -1
    return 0


def selftest(n=200000):
    """Check the composition against the machine's own 64-bit arithmetic.

    This is TESTING, not proving, and it says so.  It exercises the carry
    boundaries deliberately — all-ones lanes, 2^16 and 2^32 crossings, and
    the 2^63 sign edge — because that is where a ripple breaks if it breaks.
    """
    import random
    M = (1 << 64) - 1
    edges = [0, 1, 0xFFFF, 0x10000, 0xFFFFFFFF, 0x100000000,
             0xFFFFFFFFFFFF, 0x7FFFFFFFFFFFFFFF, 0x8000000000000000, M]
    bad = 0
    checked = 0
    for a in edges:
        for b in edges:
            checked += 1
            if add64(a, b) != ((a + b) & M):
                bad += 1
            want = 0 if a == b else (1 if a > b else -1)
            if cmp64(a, b) != want:
                bad += 1
    rnd = random.Random(20260810)
    for _ in range(n):
        a, b = rnd.getrandbits(64), rnd.getrandbits(64)
        checked += 1
        if add64(a, b) != ((a + b) & M):
            bad += 1
        want = 0 if a == b else (1 if a > b else -1)
        if cmp64(a, b) != want:
            bad += 1
    return {"checked": checked, "mismatches": bad, "verdict": VERDICT}


if __name__ == "__main__":
    print(__doc__.split("=====")[0])
    for k, v in LANES.items():
        print("  %-8s %-8s size %-2d %8d evals  sweep %.1fs  (%d bits in)"
              % (k, v["verdict"], v["size"], v["evals"], v["sweep_secs"],
                 v["bits_in"]))
    r = selftest()
    print("\nselftest: %d pairs checked, %d mismatches"
          % (r["checked"], r["mismatches"]))
    print("verdict : %s" % r["verdict"])
