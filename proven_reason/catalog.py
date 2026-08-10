# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""catalog — the proven shelf.

Thirty-one integer instructions. **No human wrote any of these expressions.**
Each was authored from example pairs that a compiled program printed, and each
was swept over all 4,294,967,296 int32 inputs against the C reference stored
beside it before the next was attempted.

The whole shelf cost **1,733,015 evaluations** to author and **238.4 seconds**
of compiler time to verify — which is the ratio worth noticing: proving is the
wall, not searching.

Every entry carries its own `ref`, so nothing here has to be taken on trust:

    from proven_reason import catalog, check
    for ins in catalog():
        assert check("return %s;" % ins.expr, ins.ref).proven

That loop takes about four minutes and re-establishes the entire shelf from
scratch. `verify_all()` runs it for you.

WHAT IS NOT HERE. The engine that authored these is not in this package. This
is the artefact, not the factory. It can tell you whether a rule is right, and
it can find a proven rule that fits your examples when one is on the shelf —
it cannot invent a new one. That boundary is stated plainly in `reason()`.
"""
from __future__ import annotations

import json
import os
from typing import List, NamedTuple, Optional, Sequence, Tuple

from .evaluator import evaluate

__all__ = ["Instruction", "catalog", "find", "fits", "verify_all"]

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "catalog", "isa.json")


class Instruction(NamedTuple):
    name: str
    meaning: str
    expr: str          # what the engine authored
    ref: str           # the C body it was proven equal to
    verdict: str       # always PROVEN — nothing else is admitted here
    size: Optional[int]
    evals: Optional[int]
    sweep_secs: Optional[float]

    def __call__(self, x: int) -> Optional[int]:
        return evaluate(self.expr, x)

    def __str__(self) -> str:
        return "%-7s %-32s %s" % (self.name, self.meaning, self.expr)


_LOADED: Optional[List[Instruction]] = None


def catalog() -> List[Instruction]:
    """Every proven instruction, in the order it was authored — which is also
    the order in which each became material for the next."""
    global _LOADED
    if _LOADED is None:
        with open(_PATH) as f:
            rows = json.load(f)
        _LOADED = [Instruction(r["name"], r.get("meaning", ""), r["expr"],
                               r["ref"], r.get("verdict", "PROVEN"),
                               r.get("size"), r.get("evals"),
                               r.get("sweep_secs")) for r in rows
                   if r.get("verdict") == "PROVEN"]
    return list(_LOADED)


def find(name: str) -> Optional[Instruction]:
    """Look one up by name, case-insensitively."""
    n = name.strip().upper()
    for i in catalog():
        if i.name.upper() == n:
            return i
    return None


def fits(pairs: Sequence[Tuple[int, int]]) -> List[Instruction]:
    """Every shelved instruction that reproduces all of `pairs` exactly.

    Returned smallest-first, so `fits(pairs)[0]` is the simplest proven rule
    consistent with what you showed it. An empty list means nothing on the
    shelf fits — which is a real answer, not a failure.
    """
    out = []
    for ins in catalog():
        for x, y in pairs:
            if evaluate(ins.expr, x) != y:
                break
        else:
            out.append(ins)
    return sorted(out, key=lambda i: (i.size or 99, len(i.expr)))


def verify_all(verbose: bool = True):
    """Re-prove the entire shelf from scratch. About four minutes.

    This is the claim of this package made checkable: every expression here is
    swept against its reference over all 4,294,967,296 inputs, now, on your
    machine, rather than because a file says PROVEN.
    """
    from .sweep import check
    bad = []
    for i, ins in enumerate(catalog(), 1):
        v = check("return %s;" % ins.expr, ins.ref)
        if verbose:
            print("  %2d/%d  %-7s %-9s %s"
                  % (i, len(catalog()), ins.name, v.verdict,
                     "" if v.proven else str(v)))
        if not v.proven:
            bad.append((ins.name, v))
    if verbose:
        print("\n%d of %d re-proven over all %s inputs."
              % (len(catalog()) - len(bad), len(catalog()), "4,294,967,296"))
    return bad
