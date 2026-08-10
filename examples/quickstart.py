#!/usr/bin/env python3
# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Six things worth seeing, in order of how much they change your mind.

    python3 examples/quickstart.py

Takes about a minute. Every verdict printed comes from a C compiler running
all 4,294,967,296 int32 inputs, not from this script.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proven_reason import (catalog, check, evaluate, find, gate,  # noqa: E402
                           reason, receipt)

print("receipt (bug fifteen — must be 1):", receipt())
print("shelf:", len(catalog()), "proven instructions\n")
print("=" * 72)

# ---------------------------------------------------------------- 1
# The thing a unit test will not tell you.
print("\n1  A CLAMP THAT PASSES EVERY UNIT TEST AND IS WRONG FOUR BILLION TIMES\n")
ref = "return x < 0 ? 0 : (x > 255 ? 255 : x);"
v = check("return x & 255;", ref)
print("   candidate : return x & 255;")
print("   reference :", ref)
print("   verdict   :", v)
print("\n   Note where it first fails: x = %d." % v.first_bad)
print("   Nobody writes that test. That is the entire problem.")

# ---------------------------------------------------------------- 2
# The gate, repairing it.
print("\n" + "=" * 72)
print("\n2  THE GATE REPAIRS IT FROM THE SHELF\n")
t = time.time()
g = gate("return x & 255;", ref)
print("   outcome   :", g.outcome)
print("   note      :", g.note)
print("   ships     :", (g.code or "nothing")[:64], "...")
print("   and that replacement is PROVEN over all 4,294,967,296 inputs.")
print("   (%.1fs)" % (time.time() - t))

# ---------------------------------------------------------------- 3
# Refusal is a safe outcome, and it is not a failure.
print("\n" + "=" * 72)
print("\n3  WHEN NOTHING FITS, IT SHIPS NOTHING\n")
g = gate("return (x >> 1);", "return x / 2;")
print("   candidate : return (x >> 1);      (for x / 2)")
print("   outcome   :", g.outcome)
print("   ships     :", g.code)
print("   note      :", g.note)
print("\n   x >> 1 rounds toward negative infinity; x / 2 rounds toward zero.")
print("   They agree on every non-negative input and differ on odd negatives.")

# ---------------------------------------------------------------- 4
# No human wrote these.
print("\n" + "=" * 72)
print("\n4  THE SHELF — NO HUMAN WROTE ANY OF THESE EXPRESSIONS\n")
for name in ("NEG", "ABS", "LOWBIT", "SATU8"):
    ins = find(name)
    print("   %-7s %-30s %s" % (ins.name, ins.meaning, ins.expr[:70]))
    print("   %-7s %-30s %s" % ("", "proven equal to", ins.ref))
print("\n   ABS is add-then-xor, not the textbook xor-then-subtract.")
print("   It found what was cheapest in the material it had, not what is idiomatic.")

# ---------------------------------------------------------------- 5
# It knows the difference between "nothing fits" and "nothing exists".
print("\n" + "=" * 72)
print("\n5  AN ABSTENTION IS A NARROW CLAIM, AND IT SAYS SO\n")
r = reason([(0, 0), (1, 2), (2, 4), (-3, -6), (100, 200)])
print("   doubling  :", r.expr, "|", r.verdict, "| rule(21) =", r(21))
r = reason([(0, 7), (1, 91), (2, -13), (3, 55)])
print("   nonsense  : found =", r.found, "|", r.verdict)
print("   note      :", r.note)

# ---------------------------------------------------------------- 6
# The fence that will not be moved.
print("\n" + "=" * 72)
print("\n6  64-BIT: THE LANES ARE PROVEN, THE COMPOSITION IS NOT\n")
from proven_reason.wide import LANES, VERDICT, add64, selftest  # noqa: E402
print("   add64(0x7FFFFFFFFFFFFFFF, 1) = 0x%X"
      % add64(0x7FFFFFFFFFFFFFFF, 1))
for k, d in LANES.items():
    print("   %-8s %-7s size %d  %7d evals  (%d bits in)"
          % (k, d["verdict"], d["size"], d["evals"], d["bits_in"]))
s = selftest(n=50000)
print("\n   selftest  : %s pairs, %d mismatches"
      % ("{:,}".format(s["checked"]), s["mismatches"]))
print("   VERDICT   :", VERDICT)
print("\n   Reproduce that number yourself:  python3 verify/wide_verify.py")

print("\n" + "=" * 72)
print("\nIt is not smarter than a frontier model. It is the only participant")
print("that can tell you when it is wrong, and the only one whose silence")
print("means something.\n")
