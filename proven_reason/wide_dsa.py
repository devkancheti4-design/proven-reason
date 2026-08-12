# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""wide_dsa — 64-bit DSA functions, authored INDIRECTLY.

Nothing here was written as 64-bit code. Each function splits its operand
into two 32-bit lanes and runs the catalog's authored expressions —
verbatim, via the evaluator — on each lane, then joins the lane results by
the mechanical identity of the operation:

    popcount64(x) = POPCNT(lo) + POPCNT(hi)        bits are disjoint
    parity64(x)   = PARITY(lo ^ hi)                xor folds parity
    bswap64(x)    = BSWAP(hi) | BSWAP(lo) << 32    byte order swaps lanes
    revbits64(x)  = REVBITS(hi) | REVBITS(lo) << 32

THE FENCE, same as wide.py and never blurred: each 32-bit lane expression is
PROVEN over its own 2^32 by the exhaustive compiled sweep that admitted it
to the catalog. The lane JOIN is a one-line identity, TESTED by suite —
2^64 cannot be swept, and no verdict here claims otherwise. `verdict64()`
returns the exact sentence.
"""
from __future__ import annotations

from .catalog import find
from .evaluator import s32

__all__ = ["popcount64", "parity64", "bswap64", "revbits64", "verdict64"]

_M64 = (1 << 64) - 1


def verdict64() -> str:
    return ("32-bit lane expressions PROVEN over their own 2^32 each; the "
            "one-line lane joins TESTED by suite — 2^64 cannot be swept, "
            "and this sentence is the strongest honest claim.")


def _lanes(x: int):
    x &= _M64
    return s32(x & 0xFFFFFFFF), s32((x >> 32) & 0xFFFFFFFF)


def _ins(name):
    i = find(name)
    if i is None:
        raise RuntimeError("catalog instruction %s missing" % name)
    return i


def popcount64(x: int) -> int:
    """Bits set in a 64-bit value: the two lane counts, summed — exact
    because no bit lives in both lanes. Lane counts: the authored POPCNT."""
    lo, hi = _lanes(x)
    p = _ins("POPCNT")
    return p(lo) + p(hi)


def parity64(x: int) -> int:
    """1 if an odd number of bits set: parity of the xor-folded lanes."""
    lo, hi = _lanes(x)
    return _ins("PARITY")(s32(lo ^ hi))


def bswap64(x: int) -> int:
    """The eight bytes reversed: byte-swap each lane, swap the lanes."""
    lo, hi = _lanes(x)
    b = _ins("BSWAP")
    return (((b(lo) & 0xFFFFFFFF) << 32) | (b(hi) & 0xFFFFFFFF)) & _M64


def revbits64(x: int) -> int:
    """All 64 bits reversed: bit-reverse each lane, swap the lanes."""
    lo, hi = _lanes(x)
    r = _ins("REVBITS")
    return (((r(lo) & 0xFFFFFFFF) << 32) | (r(hi) & 0xFFFFFFFF)) & _M64


def selftest(n: int = 200000) -> dict:
    """TESTING, and it says so: edge values plus deterministic random,
    checked against Python's own big-int arithmetic."""
    import random
    rng = random.Random(20260812)
    edges = [0, 1, 2, 0xFF, 0xFFFF, 0xFFFFFFFF, 0x100000000,
             0x5555555555555555, 0xAAAAAAAAAAAAAAAA,
             0x7FFFFFFFFFFFFFFF, 0x8000000000000000, _M64]
    bad = checked = 0
    xs = edges + [rng.getrandbits(64) for _ in range(n)]
    for x in xs:
        checked += 1
        if popcount64(x) != bin(x & _M64).count("1"):
            bad += 1
        if parity64(x) != bin(x & _M64).count("1") % 2:
            bad += 1
        if bswap64(x) != int.from_bytes(
                (x & _M64).to_bytes(8, "big"), "little"):
            bad += 1
        if revbits64(x) != int(bin(x & _M64)[2:].zfill(64)[::-1], 2):
            bad += 1
    return {"checked": checked, "mismatches": bad, "verdict": verdict64()}
