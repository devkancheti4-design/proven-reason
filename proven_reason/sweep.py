# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""sweep — the part that proves.

This library never claims a proof of its own. It hands two functions to a C
compiler and has the machine run **every one of the 4,294,967,296 int32
inputs** through both. `PROVEN` is the compiler's word, not this code's.

THE DISCIPLINE, and why each piece is there
-------------------------------------------
`-fwrapv`          signed overflow must wrap, not be undefined, or the
                   compiler is entitled to assume it never happens and delete
                   the very case being tested.
`-fno-lto`         no cross-unit optimisation that could merge the two
                   functions into one and compare it against itself.
`noinline`         each side stays a real call the optimiser cannot fuse.
`volatile` sink    both results are consumed, so neither loop can be
                   eliminated as dead.
under 2.0 seconds  is NOT a proof. 4.29 billion iterations do not finish that
                   fast; it means the compiler folded both sides to a constant.
                   Reported as SUSPECTED-FOLD after a second run at -O1.

A verdict that comes back too fast is treated as a failure to verify, never
as a success.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from typing import NamedTuple

__all__ = ["Verdict", "check", "have_compiler", "TOTAL_INPUTS"]

TOTAL_INPUTS = 4294967296

_HARNESS = r'''
#include <stdio.h>
__attribute__((noinline)) int F(int x){ %s }
__attribute__((noinline)) int G(int x){ %s }
volatile long long SINK;
int main(void){
    long long bad = 0; int first = 0, seen = 0;
    for (long long u = -2147483648LL; u <= 2147483647LL; u++){
        int x = (int)u;
        int a = F(x), b = G(x);
        SINK += a; SINK += b;
        if (a != b){ bad++; if (!seen){ seen = 1; first = x; } }
    }
    printf("%%lld %%d\n", bad, first);
    return 0;
}
'''


class Verdict(NamedTuple):
    """What the compiler found.

    verdict     PROVEN | WRONG | SUSPECTED-FOLD | NO-COMPILE | NON-TERMINATING
    mismatches  how many of the 4,294,967,296 inputs disagree
    first_bad   the first input where they disagree — this is the fix
    seconds     how long the sweep took
    """
    verdict: str
    mismatches: int
    first_bad: int
    seconds: float

    @property
    def proven(self) -> bool:
        return self.verdict == "PROVEN"

    def __str__(self) -> str:
        if self.verdict == "PROVEN":
            return ("PROVEN — agrees on every one of %s int32 inputs, "
                    "checked in %.1fs by a compiled sweep."
                    % ("{:,}".format(TOTAL_INPUTS), self.seconds))
        if self.verdict == "WRONG":
            return ("WRONG — disagrees on %s of %s inputs, first at x=%d. "
                    "Add that input to your examples and ask again."
                    % ("{:,}".format(self.mismatches),
                       "{:,}".format(TOTAL_INPUTS), self.first_bad))
        if self.verdict == "NON-TERMINATING":
            return ("NON-TERMINATING — the compiled run was still going at "
                    "the %.0fs timeout. A healthy sweep takes ~11s; the "
                    "candidate almost certainly contains a loop that never "
                    "exits on some input. NOT a proof, NOT a pass."
                    % self.seconds)
        if self.verdict == "SUSPECTED-FOLD":
            return ("SUSPECTED-FOLD — the sweep returned in %.2fs, which is "
                    "too fast to be real. The compiler almost certainly "
                    "folded both sides to a constant. NOT a proof."
                    % self.seconds)
        return "NO-COMPILE — the candidate or the reference did not compile."


def have_compiler() -> bool:
    return shutil.which("cc") is not None


def _run(candidate: str, reference: str, opt: str, timeout: float):
    d = tempfile.mkdtemp(prefix="proven-reason-")
    src, exe = os.path.join(d, "sweep.c"), os.path.join(d, "sweep")
    with open(src, "w") as f:
        f.write(_HARNESS % (candidate, reference))
    cc = subprocess.run(["cc", opt, "-fwrapv", "-fno-lto", "-w", src,
                         "-o", exe], capture_output=True)
    if cc.returncode:
        return None, 0.0
    t0 = time.time()
    try:
        out = subprocess.run([exe], capture_output=True, text=True,
                             timeout=timeout).stdout
    except subprocess.TimeoutExpired:
        return "TIMEOUT", time.time() - t0
    return out, time.time() - t0


def check(candidate: str, reference: str,
          timeout: float = 900.0) -> Verdict:
    """Sweep two C function bodies against each other over the whole int32
    domain. Both are bodies of `int f(int x)` — statements, including return.

        check("return (x + x);", "return x * 2;")

    There is no sampling and no shortcut: every input is run.

    `timeout` (seconds) bounds each compiled run. A candidate containing a
    loop that never terminates — `while (x) x >>= 1;` on a negative input is
    the classic — would otherwise hang the caller FOREVER. That defect was
    real here: found in live use, when a model's non-terminating popcount
    spun a sweep for 57 minutes. A healthy sweep takes ~11s; anything still
    running at the timeout is reported NON-TERMINATING, which is never a
    proof and never a pass.
    """
    if not have_compiler():
        raise RuntimeError(
            "no C compiler on PATH. The compiler is what proves; without it "
            "this library can only report EXACT-ON-EXAMPLES.")

    out, dt = _run(candidate, reference, "-O3", timeout)
    if out == "TIMEOUT":
        return Verdict("NON-TERMINATING", -1, 0, dt)
    if out is None or not out.strip():
        return Verdict("NO-COMPILE", -1, 0, dt)
    bad, first = (int(v) for v in out.split())
    if bad:
        return Verdict("WRONG", bad, first, dt)
    if dt >= 2.0:
        return Verdict("PROVEN", 0, 0, dt)

    # Too fast to be real. Try again with less optimisation before believing
    # anything; if it is still instant, it folded and this is not a proof.
    out, dt2 = _run(candidate, reference, "-O1", timeout)
    if out == "TIMEOUT":
        return Verdict("NON-TERMINATING", -1, 0, dt2)
    if out is None or not out.strip():
        return Verdict("NO-COMPILE", -1, 0, dt2)
    bad, first = (int(v) for v in out.split())
    if bad:
        return Verdict("WRONG", bad, first, dt2)
    if dt2 >= 2.0:
        return Verdict("PROVEN", 0, 0, dt2)
    return Verdict("SUSPECTED-FOLD", 0, 0, dt2)
