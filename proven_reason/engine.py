# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""engine — the part that AUTHORS.

Examples in, the smallest expression that reproduces every one of them out.
Size-ordered, so the first size that matches is **provably minimal in the
grammar it was given** — every smaller size was exhausted, not sampled.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
This is the authoring engine. It is **not** the core that produced it, which
is not in this distribution and is not described here.

So this is the honest description, and the whole of it: **a size-ordered
exhaustive search over a declared grammar.** It authors, and it proves
minimality within that grammar. It reaches what an exhaustive walk of that
grammar reaches, and nothing beyond it.

THE THREE THINGS THAT DECIDE WHETHER IT ANSWERS
-----------------------------------------------
    the examples   Too few and two different rules both fit; it returns the
                   smaller one, which may not be the one you meant.
    the material   `ops`, `consts`, and anything declared through `material=`.
                   This is the lever that matters most and the one most often
                   left empty. Declaring the proven catalog is measured below.
    the size cap   `max_size`. The space grows steeply per level, so a ceiling
                   set too low measures your ceiling, not the engine's reach.

An abstention names which of the three ran out. It is a defined outcome, not
an error.

MATERIAL IS THE WHOLE GAME
--------------------------
Measured on this codebase, same target, same everything except what was
declared:

    SATB, halves not declared    5,425,498 evaluations   found nothing
    SATB, halves declared              424 evaluations   size 2, 0.4s

**12,796x.** Nothing about the search changed. Six proven expressions became
available to build with. That is why `material=` exists and why
`proven_reason.catalog()` is worth passing to it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .evaluator import evaluate, s32

__all__ = ["Grammar", "Authored", "synthesize", "OPS", "DEFAULT_GRAMMAR"]

# name -> (arity, C template, python implementation)
OPS: Dict[str, Tuple[int, str, Callable]] = {
    "+":    (2, "({a} + {b})", lambda a, b: s32(a + b)),
    "-":    (2, "({a} - {b})", lambda a, b: s32(a - b)),
    "&":    (2, "({a} & {b})", lambda a, b: s32(a & b)),
    "|":    (2, "({a} | {b})", lambda a, b: s32(a | b)),
    "^":    (2, "({a} ^ {b})", lambda a, b: s32(a ^ b)),
    "*":    (2, "({a} * {b})", lambda a, b: s32(a * b)),
    "<<1":  (1, "({a} << 1)",  lambda a, _: s32(a << 1)),
    "<<2":  (1, "({a} << 2)",  lambda a, _: s32(a << 2)),
    "<<3":  (1, "({a} << 3)",  lambda a, _: s32(a << 3)),
    "<<4":  (1, "({a} << 4)",  lambda a, _: s32(a << 4)),
    "<<5":  (1, "({a} << 5)",  lambda a, _: s32(a << 5)),
    "<<8":  (1, "({a} << 8)",  lambda a, _: s32(a << 8)),
    "<<16": (1, "({a} << 16)", lambda a, _: s32(a << 16)),
    ">>1":  (1, "({a} >> 1)",  lambda a, _: a >> 1),
    ">>2":  (1, "({a} >> 2)",  lambda a, _: a >> 2),
    ">>4":  (1, "({a} >> 4)",  lambda a, _: a >> 4),
    ">>8":  (1, "({a} >> 8)",  lambda a, _: a >> 8),
    ">>16": (1, "({a} >> 16)", lambda a, _: a >> 16),
    ">>31": (1, "({a} >> 31)", lambda a, _: a >> 31),
    "~":    (1, "(~{a})",      lambda a, _: s32(~a)),
    "neg":  (1, "(-{a})",      lambda a, _: s32(-a)),
    "+1":   (1, "({a} + 1)",   lambda a, _: s32(a + 1)),
    "-1":   (1, "({a} - 1)",   lambda a, _: s32(a - 1)),
}


@dataclass
class Grammar:
    """THE MATERIAL. What it can build with decides what it can build.

    A handicapped grammar is not a result about the engine. Giving it only
    `<<1` while you write `(x << 4)` yourself makes the same function cost it
    four operators against your one. Keep both sides equal or say you didn't.
    """
    ops: Sequence[str] = tuple(OPS)
    consts: Sequence[int] = (0, 1, 2, -1, 7, 8, 15, 16, 31, 255, 127, -128,
                             2147483647)
    material: Sequence[Tuple[str, str]] = ()   # (name, expression) pairs

    def with_material(self, instructions) -> "Grammar":
        """Declare proven expressions as things to build WITH.

        REGISTERED IS NOT DECLARED. An expression the search cannot reach is
        not material, whatever else you have done with it — that distinction
        was measured at 2,927x on this codebase. This method is the declaring.
        """
        mat = tuple((getattr(i, "name", str(i)), getattr(i, "expr", str(i)))
                    for i in instructions)
        return Grammar(self.ops, self.consts, tuple(self.material) + mat)


DEFAULT_GRAMMAR = Grammar()


@dataclass
class Authored:
    """What the engine came back with.

    `minimal` is True only when the exhaustive ladder closed every smaller
    size. It is a claim about this grammar, never about all expressions.
    """
    found: bool
    expr: Optional[str] = None
    size: Optional[int] = None
    evaluations: int = 0
    minimal: bool = False
    note: str = ""
    levels: Tuple[int, ...] = ()

    def __call__(self, x: int) -> Optional[int]:
        return evaluate(self.expr, x) if self.expr else None

    def __repr__(self):
        if not self.found:
            return "Authored(NOT FOUND after %s evaluations)" % (
                "{:,}".format(self.evaluations))
        return "Authored(%r, size=%d, evals=%s%s)" % (
            self.expr, self.size, "{:,}".format(self.evaluations),
            " MINIMAL" if self.minimal else "")


class _Node:
    __slots__ = ("vals", "expr", "size")

    def __init__(self, vals, expr, size):
        self.vals, self.expr, self.size = vals, expr, size


def synthesize(examples: Sequence[Tuple[int, int]],
               holdout: Sequence[Tuple[int, int]] = (),
               grammar: Grammar = DEFAULT_GRAMMAR,
               max_size: int = 3,
               on_level=None) -> Authored:
    """Author the smallest expression in `x` reproducing every example.

        synthesize([(0,0), (1,2), (2,4), (-3,-6)])
        # Authored('(x << 1)', size=1, evals=39 MINIMAL)

    `holdout` never steers the search — it only decides whether the answer is
    reported at all. An expression that fits the examples and fails the
    hold-out is REJECTED, not returned with a caveat.

    `on_level(size, new_nodes, evaluations)` is called after each rung. That
    stream is the diagnosis when it abstains: the level counts show the space
    and its growth, so you can see whether raising `max_size` is worth it or
    whether the material is what ran out.
    """
    xs = [a for a, _ in examples]
    want = tuple(s32(b) for _, b in examples)
    if not xs:
        return Authored(False, note="no examples given")

    seen = set()
    levels: List[List[_Node]] = [[]]
    counts: List[int] = []

    def add(vals, expr, size, bucket) -> bool:
        if vals in seen:
            return False
        seen.add(vals)
        bucket.append(_Node(vals, expr, size))
        return True

    # level 0: the variable, the constants, and every declared expression
    add(tuple(s32(x) for x in xs), "x", 0, levels[0])
    for c in grammar.consts:
        add(tuple(s32(c) for _ in xs), str(c), 0, levels[0])
    for _name, expr in grammar.material:
        vals = tuple(evaluate(expr, x) for x in xs)
        if all(v is not None for v in vals):
            add(vals, expr, 0, levels[0])

    def ok(n: _Node) -> bool:
        if n.vals != want:
            return False
        for hx, hy in holdout:
            v = evaluate(n.expr, hx)
            if v is None or v != s32(hy):
                return False
        return True

    for n in levels[0]:
        if ok(n):
            return Authored(True, n.expr, 0, 0, True,
                            "already on the shelf, or a constant")

    evals = 0
    for s in range(1, max_size + 1):
        new: List[_Node] = []
        for i in range(s):
            A, B = levels[i], levels[s - 1 - i]
            for na in A:
                for opname in grammar.ops:
                    ar, tmpl, fn = OPS[opname]
                    if ar == 1:
                        if i != s - 1:
                            continue
                        evals += 1
                        vals = tuple(fn(v, 0) for v in na.vals)
                        node = _Node(vals, tmpl.format(a=na.expr), s)
                        if ok(node):
                            return Authored(True, node.expr, s, evals, True,
                                            "minimal in this grammar",
                                            tuple(counts))
                        add(vals, node.expr, s, new)
                    else:
                        for nb in B:
                            evals += 1
                            vals = tuple(fn(u, v)
                                         for u, v in zip(na.vals, nb.vals))
                            node = _Node(vals,
                                         tmpl.format(a=na.expr, b=nb.expr), s)
                            if ok(node):
                                return Authored(True, node.expr, s, evals,
                                                True,
                                                "minimal in this grammar",
                                                tuple(counts))
                            add(vals, node.expr, s, new)
        levels.append(new)
        counts.append(len(new))
        if on_level:
            on_level(s, len(new), evals)
        if not new:
            break

    return Authored(
        False, evaluations=evals, levels=tuple(counts),
        note=("no expression of size <= %d in this grammar. Space searched: "
              "%d operators, %d constants, %d declared. Levels: %s. "
              "Raise max_size, or declare more material — the second is "
              "usually the one that is missing."
              % (max_size, len(grammar.ops), len(grammar.consts),
                 len(grammar.material),
                 " ".join("%d" % c for c in counts) or "none")))
