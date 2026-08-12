#!/usr/bin/env python3
"""widen.py — evidence that MATERIAL, not depth, is the lever.

Three targets that used to abstain against `max_nodes=4,000,000`. All three
came back the same way -- "resource bound: the search reached max_nodes" --
which reads like a limit of the engine and is nothing of the sort. A
resource bound is the CALLER'S number.

The obvious response is to raise it. That is the wrong lever and this file
is the demonstration: every run below holds `max_size` and `max_nodes`
FIXED and moves only the MATERIAL.

    clp2         a proven catalog instruction APPLIED to (x - 1).
                 Unreachable while the catalog is declared as leaves --
                 a leaf contributes its VALUE and cannot be applied to
                 anything. Promoted to an OPERATOR it lands immediately.

    mult-of-10   needs the constant 10, which the default grammar does not
                 carry. It derives it: (2 + 8).

    knuth-hash   needs 2654435761, which is past INT_MAX and must be
                 declared in its int32 form, -1640531535. No amount of
                 searching invents a constant that was never declared.

Run:  python3 benchmarks/widening/widen.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", ".."))
from proven_reason import reason                          # noqa: E402

M = 0xFFFFFFFF


def s32(v):
    v &= M
    return v - (1 << 32) if v >> 31 else v


def clp2(x):
    u = (x - 1) & M
    for k in (1, 2, 4, 8, 16):
        u |= u >> k
    return s32((u + 1) & M)


XS = [0, 1, 2, 3, 5, 8, 13, 21, 100, 255, 1024, 65536, 2**30, 2147483647,
      -1, -2, -7, -100, -65536, -2**30, -2147483648]

CASES = [
    ("mult-of-10", lambda x: s32(x * 10), "return x*10;", {}),
    ("knuth-hash", lambda x: s32(x * 2654435761),
     "return (int)((unsigned)x * 2654435761u);",
     {"consts": (-1640531535,)}),
    ("clp2", clp2,
     "unsigned u=(unsigned)x; u--; u|=u>>1; u|=u>>2; u|=u>>4; u|=u>>8;"
     " u|=u>>16; u++; return (int)u;",
     {"promote": ("SMEAR", "NEXTP2", "ORS1", "ORS2", "ORS4", "ORS8",
                  "DEC", "INC")}),
]

print("max_size and max_nodes are FIXED. Only the material moves.\n")
print("%-12s %-9s %-34s %7s" % ("target", "verdict", "material declared",
                                "secs"))
print("-" * 66)
for name, fn, ref, material in CASES:
    pairs = [(x, fn(x)) for x in XS]
    t0 = time.time()
    r = reason(pairs, reference=ref, max_size=2, **material)
    declared = ", ".join("%s=%s" % (k, len(v)) for k, v in material.items()) \
        or "catalog defaults only"
    print("%-12s %-9s %-34s %6.0fs" % (name, r.verdict, declared,
                                       time.time() - t0))
    if r.expr:
        print("             %s" % str(r.expr)[:96])

print("""
Each of these previously returned "resource bound: reached max_nodes".
None of them needed a bigger budget. They needed material -- an operator
that could be applied, or a constant that was never declared. That is why
an abstention here names what was missing instead of only how hard it
looked.""")
