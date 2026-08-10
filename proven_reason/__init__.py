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
    check()       the exhaustive compiled sweep — the part that proves
    gate()        PASS / FIX / REFUSE around any code generator
    synthesize()  the engine — authors, and proves minimality in its grammar
    catalog()     31 proven instructions, each with its reference
    reason()      shelf first, then author
    wide          64-bit arithmetic from four PROVEN 16-bit lanes

The core that produced this engine is **private, not in this distribution,
and not described in it.** What ships is a size-ordered exhaustive search
over a declared grammar: it authors, and it proves minimality within that
grammar — that, and nothing claimed beyond it.

An abstention states the bounds it holds under — size, grammar, material —
and never says "no such rule exists", because it cannot know that.

THE DISTINCTION THIS LIBRARY WILL NOT BLUR
------------------------------------------
    PROVEN  <=>  for all x in [INT_MIN, INT_MAX] : candidate(x) == reference(x)

`PROVEN` needs a reference **you** supply. There is no honest way to invent
one, so without it the strongest thing sayable is `EXACT-ON-EXAMPLES(n)`.
"""
from __future__ import annotations

from typing import NamedTuple, Optional, Sequence, Tuple

from .catalog import Instruction, catalog, find, fits, verify_all
from .engine import Authored, DEFAULT_GRAMMAR, Grammar, synthesize
from .evaluator import INT_MAX, INT_MIN, evaluate, receipt, s32
from .sweep import TOTAL_INPUTS, Verdict, check, have_compiler

__version__ = "0.2.0"

__all__ = [
    "check", "gate", "reason", "catalog", "find", "fits", "verify_all",
    "synthesize", "Grammar", "Authored", "armed",
    "evaluate", "receipt", "s32", "Verdict", "GateResult", "Rule",
    "Instruction", "INT_MIN", "INT_MAX", "TOTAL_INPUTS", "have_compiler",
]


def armed() -> Grammar:
    """The default grammar with the whole proven catalog DECLARED as material.

    Registering is not declaring. This is the declaring, and on this codebase
    that distinction was worth 2,927x on one target and 12,796x on another.
    Use it unless you have a reason not to.
    """
    return DEFAULT_GRAMMAR.with_material(catalog())


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
         pairs: Optional[Sequence[Tuple[int, int]]] = None,
         max_size: int = 3) -> GateResult:
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

    # Nothing shelved fits. AUTHOR one, then make the compiler judge it —
    # the engine's answer gets no more benefit of the doubt than the model's.
    if pairs and max_size > 0:
        ex = list(pairs)
        cut = max(1, len(ex) * 3 // 4)
        for size in range(1, max_size + 1):
            a = synthesize(ex[:cut], holdout=ex[cut:], grammar=armed(),
                           max_size=size)
            if a.found:
                cand = "return %s;" % a.expr
                av = check(cand, reference)
                if av.proven:
                    return GateResult("FIX", cand, v,
                                      "rejected (%s); engine authored a "
                                      "replacement in %s evaluations and the "
                                      "sweep proved it"
                                      % (_short(v),
                                         "{:,}".format(a.evaluations)))
                break

    return GateResult("REFUSE", None, v,
                      "rejected (%s); nothing on the shelf fits and nothing "
                      "of size <= %d was authored — nothing ships"
                      % (_short(v), max_size))


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
           reference: Optional[str] = None,
           max_size: int = 3,
           on_level=None) -> Rule:
    """The smallest rule that reproduces every one of `pairs`.

        reason([(0,0), (1,2), (2,4), (-3,-6)])
        # (x << 1)  [EXACT-ON-EXAMPLES(4)]

    It looks on the proven shelf first — that is free — and if nothing there
    fits it AUTHORS one, size-ordered, with the whole catalog declared as
    material. The first size that matches is minimal in that grammar.

    Give it `reference=` and the verdict gets stronger: the authored
    expression is swept against your definition over all 4,294,967,296 inputs
    and comes back PROVEN or WRONG. The engine's own answer earns no benefit
    of the doubt — the compiler judges it exactly as it judges anyone's.

    `on_level(size, nodes, evaluations)` streams the ladder. When it abstains
    that stream is the diagnosis: it shows the space, its growth, and what was
    declared, so you can tell whether size or material is what ran out.

    ON max_size. The default is 3 because that is what the measurement
    supports. With the whole catalog declared, the ladder costs:

        level 1        859 nodes         3,864 evaluations     0.0s
        level 2     37,044 nodes       265,859 evaluations     0.4s
        level 3  1,806,713 nodes    15,991,565 evaluations    25.1s

    Level 4 is about a billion evaluations and several gigabytes. Raise it
    deliberately, on a target you believe needs it, not by default.
    """
    if not pairs:
        return Rule(False, None, "NO-EXAMPLES",
                    "give it at least one (input, output) pair")

    # 1. the shelf — already proven, and instant
    for ins in fits(pairs):
        if reference is None:
            return Rule(True, ins.expr, "EXACT-ON-EXAMPLES(%d)" % len(pairs),
                        "fits all %d examples, and is PROVEN equal to `%s` "
                        "over every int32 input" % (len(pairs), ins.ref), ins)
        v = check("return %s;" % ins.expr, reference)
        if v.proven:
            return Rule(True, ins.expr, v.verdict, str(v), ins)
        break

    # 2. author it
    ex = list(pairs)
    cut = max(1, len(ex) * 3 // 4)
    a = None
    for size in range(1, max_size + 1):
        a = synthesize(ex[:cut], holdout=ex[cut:], grammar=armed(),
                       max_size=size, on_level=on_level)
        if a.found:
            break

    if a is None or not a.found:
        return Rule(False, None, "ABSTAIN", a.note if a else "no examples")

    if reference is None:
        return Rule(True, a.expr, "EXACT-ON-EXAMPLES(%d)" % len(pairs),
                    "authored in %s evaluations, minimal at size %d in the "
                    "declared grammar. Supply reference= to have it swept "
                    "over all %s inputs."
                    % ("{:,}".format(a.evaluations), a.size,
                       "{:,}".format(TOTAL_INPUTS)))

    v = check("return %s;" % a.expr, reference)
    return Rule(v.proven, a.expr if v.proven else None, v.verdict, str(v))
