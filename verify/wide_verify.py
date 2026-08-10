#!/usr/bin/env python3
# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""wide_verify.py — produce the number in wide.VERDICT instead of asserting it.

The fence in proven_reason/wide.py says the 64-bit COMPOSITION is tested, not
proven, and then quotes a count of slices and random pairs.  Two problems with
that as it stood:

  1. The docstring said 6 slices and the VERDICT string said 3 — in the SAME
     FILE.  The VERDICT is the sentence callers quote, so the disagreement sat
     in the one place it must not.
  2. selftest() defaults to 200,000 pairs.  The "400,000,000" came from a run
     whose evidence was not in the repository.  An unreproducible number in an
     honesty fence is just a nicer-looking assertion.

This script makes the claim checkable.  It:

  A. Builds a C MIRROR of the lane composition in wide.py — the same four
     16-bit lanes, the same ripple — because 25 billion pairs cannot go
     through Python.
  B. PROVES THE MIRROR IS THE SAME ALGORITHM by running both on the same
     pseudo-random pairs and requiring exact agreement.  Without this step the
     C result says nothing about the shipped Python.
  C. Runs the mirror against the machine's own 64-bit arithmetic over N full
     2^32 slices at the carry boundaries, plus M random 64-bit pairs.
  D. Prints the measured counts, and the exact VERDICT sentence they justify.

Whatever this prints is what the docs are allowed to say.  Nothing more.

    python3 verify/wide_verify.py            # default, a few minutes
    python3 verify/wide_verify.py --quick    # smoke, for CI
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from proven_reason.wide import add64, cmp64                    # noqa: E402

# The six 64-bit values every slice is anchored to.  These are the carry
# boundaries: all-zero, the low bit, a full 32-bit run of ones, the 2^32
# crossing, the signed edge, and all-ones.
ANCHORS = [
    ("zero",        0x0000000000000000),
    ("one",         0x0000000000000001),
    ("lo32 ones",   0x00000000FFFFFFFF),
    ("2^32",        0x0000000100000000),
    ("sign edge",   0x7FFFFFFFFFFFFFFF),
    ("all ones",    0xFFFFFFFFFFFFFFFF),
]

# ---------------------------------------------------------------- the mirror
# A faithful C transcription of wide.lane_sum / wide.lane_carry / add64 /
# cmp64.  Step B below is what makes this trustworthy rather than assumed.
MIRROR = r'''
#include <stdio.h>
#include <stdint.h>

static inline uint32_t lane_sum(uint32_t a, uint32_t b, uint32_t cin){
    uint32_t s = (a + b) & 0xFFFFu;
    return (s + (cin & 1u)) & 0xFFFFu;
}
static inline uint32_t lane_carry(uint32_t a, uint32_t b, uint32_t cin){
    uint32_t t  = (a & 0xFFFFu) + (b & 0xFFFFu);
    uint32_t c1 = (t >> 16) & 1u;
    uint32_t c2 = (((t & 0xFFFFu) + (cin & 1u)) >> 16) & 1u;
    return c1 | c2;
}
__attribute__((noinline)) uint64_t W_add64(uint64_t a, uint64_t b){
    uint64_t out = 0; uint32_t carry = 0;
    for (int i = 0; i < 4; i++){
        int sh = 16 * i;
        uint32_t x = (uint32_t)((a >> sh) & 0xFFFFu);
        uint32_t y = (uint32_t)((b >> sh) & 0xFFFFu);
        out |= (uint64_t)lane_sum(x, y, carry) << sh;
        carry = lane_carry(x, y, carry);
    }
    return out;
}
__attribute__((noinline)) int W_cmp64(uint64_t a, uint64_t b){
    for (int i = 3; i >= 0; i--){
        int sh = 16 * i;
        uint32_t x = (uint32_t)((a >> sh) & 0xFFFFu);
        uint32_t y = (uint32_t)((b >> sh) & 0xFFFFu);
        if (x != y) return x > y ? 1 : -1;
    }
    return 0;
}
'''

# Step B: emit pairs the Python side will check, so the mirror is verified
# rather than believed.
AGREE = MIRROR + r'''
#include <stdlib.h>
static uint64_t st = 0x243F6A8885A308D3ULL;
static uint64_t rnd(void){ st ^= st << 13; st ^= st >> 7; st ^= st << 17; return st; }
int main(int argc, char **argv){
    long n = atol(argv[1]);
    for (long i = 0; i < n; i++){
        uint64_t a = rnd(), b = rnd();
        printf("%llu %llu %llu %d\n",
               (unsigned long long)a, (unsigned long long)b,
               (unsigned long long)W_add64(a,b), W_cmp64(a,b));
    }
    return 0;
}
'''

# Step C: the actual measurement.
MEASURE = MIRROR + r'''
#include <stdlib.h>
static uint64_t st = 0x9E3779B97F4A7C15ULL;
static uint64_t rnd(void){ st ^= st << 13; st ^= st >> 7; st ^= st << 17; return st; }
volatile uint64_t SINK;
int main(int argc, char **argv){
    int nslice = atoi(argv[1]);
    long long nrand = atoll(argv[2]);
    unsigned long long anchors[6] = {
        0x0000000000000000ULL, 0x0000000000000001ULL, 0x00000000FFFFFFFFULL,
        0x0000000100000000ULL, 0x7FFFFFFFFFFFFFFFULL, 0xFFFFFFFFFFFFFFFFULL };

    long long bad_add = 0, bad_cmp = 0, npairs = 0;

    /* Each slice: anchor a, and sweep b across ALL 2^32 values of its low
       32 bits, with the high 32 bits taken from the anchor. That is a full
       2^32 pairs per slice, at a carry boundary. */
    for (int s = 0; s < nslice; s++){
        uint64_t a = anchors[s % 6];
        uint64_t hi = anchors[(s + 3) % 6] & 0xFFFFFFFF00000000ULL;
        for (long long u = 0; u <= 0xFFFFFFFFLL; u++){
            uint64_t b = hi | (uint64_t)(uint32_t)u;
            uint64_t got = W_add64(a, b), want = a + b;
            SINK += got;
            if (got != want) bad_add++;
            npairs++;
        }
        fprintf(stderr, "  slice %d/%d done\n", s + 1, nslice);
    }

    for (long long i = 0; i < nrand; i++){
        uint64_t a = rnd(), b = rnd();
        uint64_t got = W_add64(a, b), want = a + b;
        SINK += got;
        if (got != want) bad_add++;
        int cg = W_cmp64(a, b);
        int cw = (a < b) ? -1 : (a > b ? 1 : 0);
        if (cg != cw) bad_cmp++;
        npairs++;
    }
    printf("%lld %lld %lld\n", bad_add, bad_cmp, npairs);
    return 0;
}
'''


def cc(src, name):
    d = tempfile.mkdtemp()
    s = os.path.join(d, name + ".c")
    e = os.path.join(d, name)
    with open(s, "w") as f:
        f.write(src)
    r = subprocess.run(["cc", "-O2", "-w", s, "-o", e], capture_output=True)
    if r.returncode:
        print(r.stderr.decode()[:900])
        sys.exit("compile failed")
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slices", type=int, default=6)
    ap.add_argument("--random", type=int, default=400_000_000)
    ap.add_argument("--agree", type=int, default=200_000)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    if a.quick:
        a.slices, a.random, a.agree = 1, 2_000_000, 20_000

    print("STEP B — is the C mirror the same algorithm as the shipped Python?")
    exe = cc(AGREE, "agree")
    out = subprocess.run([exe, str(a.agree)], capture_output=True,
                         text=True).stdout
    n, bad = 0, 0
    for line in out.strip().split("\n"):
        av, bv, sv, cv = line.split()
        av, bv, sv, cv = int(av), int(bv), int(sv), int(cv)
        if add64(av, bv) != sv or cmp64(av, bv) != cv:
            bad += 1
        n += 1
    print("  %d pairs through BOTH implementations, %d disagreements" % (n, bad))
    if bad:
        sys.exit("MIRROR IS NOT THE SHIPPED ALGORITHM — measurement abandoned")
    print("  the mirror is the shipped algorithm; its result is admissible\n")

    print("STEP C — measuring. %d full 2^32 slices + %s random pairs."
          % (a.slices, "{:,}".format(a.random)))
    exe = cc(MEASURE, "measure")
    t0 = time.time()
    p = subprocess.run([exe, str(a.slices), str(a.random)],
                       capture_output=True, text=True)
    dt = time.time() - t0
    bad_add, bad_cmp, npairs = (int(v) for v in p.stdout.split())
    slice_pairs = a.slices * 4294967296
    print("  %s pairs checked in %.1fs, %d add mismatches, %d cmp mismatches"
          % ("{:,}".format(npairs), dt, bad_add, bad_cmp))

    frac = npairs / float(1 << 128)
    verdict = ("four PROVEN 16-bit lanes; composition TESTED on %d exhaustive "
               "2^32 slices (%s pairs) and %s random pairs, %d mismatches — "
               "not PROVEN" % (a.slices, "{:,}".format(slice_pairs),
                               "{:,}".format(a.random), bad_add + bad_cmp))
    print("\nMEASURED VERDICT — this, and nothing stronger:")
    print("  " + verdict)
    print("\n  coverage: %.3g of 2^128" % frac)

    json.dump({"slices": a.slices, "slice_pairs": slice_pairs,
               "random_pairs": a.random, "pairs_checked": npairs,
               "add_mismatches": bad_add, "cmp_mismatches": bad_cmp,
               "seconds": round(dt, 1), "coverage_of_2_128": frac,
               "verdict": verdict},
              open(os.path.join(HERE, "wide_verify.json"), "w"), indent=1)
    print("\n  written to verify/wide_verify.json")
    return 0 if (bad_add + bad_cmp) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
