# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""proven-reason — a bolt-on that can tell you when your code is wrong.

Not by testing a few inputs. By running **every one of the 4,294,967,296
int32 inputs** through your code and a reference, in a compiled sweep, and
reporting what the machine found.

    from proven_reason import check

    v = check("return (x + 15) & ~15;", "return (x + 15) & ~15;")
    v.proven          # True
    print(v)          # PROVEN — agrees on every one of 4,294,967,296 inputs...

Bolt it onto a model and it becomes a gate with three safe outcomes:

    from proven_reason import gate

    g = gate(model_wrote, reference)
    g.outcome         # 'PASS' | 'FIX' | 'REFUSE'
    g.code            # what is safe to ship, or None

Measured on ten tasks with four free local models on one laptop:
**21 wrong answers between them, zero after the gate, no model made worse.**

WHAT THIS PACKAGE IS
--------------------
An artefact, not a factory. The expressions in `catalog/isa.json` were
authored by an engine that is **not included here**, and each was proven over
the whole int32 domain before being written down. This package ships:

    check()      the exhaustive compiled sweep — the part that proves
    gate()       PASS / FIX / REFUSE around any code generator
    catalog()    31 proven instructions, each with its reference
    reason()     the smallest PROVEN rule on the shelf that fits your examples
    wide         64-bit arithmetic from four PROVEN 16-bit lanes

It can verify anything of the shape `int32 -> int32`. It can only *repair*
with rules already on the shelf — it does not search for new ones, and
`reason()` says so rather than pretending.

THE DISTINCTION THIS LIBRARY WILL NOT BLUR
------------------------------------------
    PROVEN  <=>  for all x in [INT_MIN, INT_MAX] : candidate(x) == reference(x)

`PROVEN` needs a reference **you** supply. There is no honest way to invent
one, so without it the strongest thing sayable is `EXACT-ON-EXAMPLES(n)`.
"""
from __future__ import annotations

from typing import NamedTuple, Optional, Sequence, Tuple

from .catalog import Instruction, catalog, find, fits, verify_all
from .evaluator import INT_MAX, INT_MIN, evaluate, receipt, s32
from .sweep import TOTAL_INPUTS, Verdict, check, have_compiler

__version__ = "0.2.0"

__all__ = [
    "check", "gate", "reason", "catalog", "find", "fits", "verify_all",
    "evaluate", "receipt", "s32", "Verdict", "GateResult", "Rule",
    "Instruction", "INT_MIN", "INT_MAX", "TOTAL_INPUTS", "have_compiler",
]


class GateResult(NamedTuple):
    """The outcome of putting generated code through the sweep.

    PASS    the code swept clean; it is passed through unchanged.
    FIX     the sweep found it wrong; a PROVEN shelf rule replaces it.
    REFUSE  the sweep found it wrong and nothing on the shelf fits.
            **Nothing ships. This is a safe outcome, not a failure.**

    There is deliberately no fourth outcome in which something unverified
    reaches the caller.
    """
    outcome: str
    code: Optional[str]
    verdict: Verdict
    note: str

    @property
    def safe(self) -> bool:
        return self.outcome in ("PASS", "FIX")

    def __str__(self) -> str:
        return "%-6s %s" % (self.outcome, self.note)


def gate(candidate: str, reference: str,
         pairs: Optional[Sequence[Tuple[int, int]]] = None) -> GateResult:
    """Put generated C through the sweep and decide what may ship.

        candidate   a C body for `int f(int x)` — what your model wrote
        reference   a C body that defines what you actually wanted
        pairs       optional; if the candidate is wrong these are used to
                    look for a shelf rule. Derived from the reference when
                    omitted.

    The compiler decides, not this function.
    """
    v = check(candidate, reference)
    if v.proven:
        return GateResult("PASS", candidate, v,
                          "the model's own code, swept clean over all %s "
                          "inputs" % "{:,}".format(TOTAL_INPUTS))

    if pairs is None:
        pairs = _pairs_from(reference)

    for ins in fits(pairs or []):
        rv = check("return %s;" % ins.expr, reference)
        if rv.proven:
            return GateResult("FIX", "return %s;" % ins.expr, v,
                              "rejected (%s); replaced with PROVEN shelf rule "
                              "%s" % (_short(v), ins.name))

    return GateResult("REFUSE", None, v,
                      "rejected (%s) and nothing on the shelf fits — nothing "
                      "ships" % _short(v))


def _short(v: Verdict) -> str:
    if v.verdict == "WRONG":
        return "wrong on %s inputs, first at x=%d" % (
            "{:,}".format(v.mismatches), v.first_bad)
    return v.verdict


_PROBES = [INT_MIN, INT_MIN + 1, -1000000, -65536, -4096, -256, -255, -129,
           -128, -127, -100, -17, -16, -15, -8, -3, -2, -1, 0, 1, 2, 3, 7, 8,
           15, 16, 17, 100, 127, 128, 254, 255, 256, 300, 4095, 4096, 65535,
           65536, 1000000, INT_MAX - 1, INT_MAX]


def _pairs_from(reference: str):
    """Ask the compiler what the reference actually does at the boundaries."""
    import os
    import subprocess
    import tempfile
    if not have_compiler():
        return []
    prog = ('#include <stdio.h>\nint P(int x){ %s }\n'
            'int main(void){int xs[]={%s};for(int i=0;i<%d;i++)'
            'printf("%%d %%d\\n",xs[i],P(xs[i]));}'
            % (reference, ",".join(str(v) for v in _PROBES), len(_PROBES)))
    d = tempfile.mkdtemp(prefix="proven-reason-")
    s, e = os.path.join(d, "p.c"), os.path.join(d, "p")
    with open(s, "w") as f:
        f.write(prog)
    if subprocess.run(["cc", "-O2", "-fwrapv", "-w", s, "-o", e],
                      capture_output=True).returncode:
        return []
    out = subprocess.run([e], capture_output=True, text=True).stdout
    return [tuple(int(t) for t in ln.split())
            for ln in out.strip().split("\n") if ln.strip()]


class Rule(NamedTuple):
    """A rule that fits your examples, and how strongly it is backed."""
    found: bool
    expr: Optional[str]
    verdict: str
    note: str
    instruction: Optional[Instruction] = None

    def __call__(self, x: int) -> Optional[int]:
        return evaluate(self.expr, x) if self.expr else None

    def __str__(self) -> str:
        return ("%s  [%s]" % (self.expr, self.verdict) if self.found
                else "no rule  [%s]" % self.verdict)


def reason(pairs: Sequence[Tuple[int, int]],
           reference: Optional[str] = None) -> Rule:
    """The smallest PROVEN rule on the shelf that fits every one of `pairs`.

        reason([(0,0), (1,2), (2,4), (-3,-6)])

    WHAT THIS DOES NOT DO, stated here rather than discovered later: it does
    **not search** for a new expression. The engine that authors rules is not
    part of this package. This looks through 31 proven instructions and
    returns the simplest one consistent with your examples.

    So an abstention here means "nothing on this shelf fits", which is a
    narrower claim than "no such rule exists" — and the note says which.
    """
    if not pairs:
        return Rule(False, None, "NO-EXAMPLES",
                    "give it at least one (input, output) pair")

    hits = fits(pairs)
    if not hits:
        return Rule(False, None, "ABSTAIN",
                    "no rule on the %d-instruction shelf reproduces all %d of "
                    "your examples. This build verifies but does not author, "
                    "so this is not a claim that no such rule exists."
                    % (len(catalog()), len(pairs)))

    best = hits[0]
    if reference is None:
        return Rule(True, best.expr, "EXACT-ON-EXAMPLES(%d)" % len(pairs),
                    "fits all %d examples and is PROVEN equal to `%s` over "
                    "every int32 input. Supply reference= to have it swept "
                    "against YOUR definition." % (len(pairs), best.ref), best)

    v = check("return %s;" % best.expr, reference)
    return Rule(v.proven, best.expr if v.proven else None, v.verdict,
                str(v), best if v.proven else None)
