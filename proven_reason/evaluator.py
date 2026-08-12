# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""evaluator — integer expressions with C's int32 semantics AT EVERY STEP.

This is the whole of the evaluation surface. It is deliberately small enough
to read in one sitting, because everything else in this library rests on it
agreeing with the machine.

THE ONE THING THIS FILE EXISTS TO GET RIGHT
-------------------------------------------
C wraps every intermediate to 32 bits. Python does not — it computes the whole
tree in unbounded integers. An evaluator that wraps only the RESULT will agree
with C almost everywhere and disagree at the boundaries, which is exactly where
the bugs live.

That defect was real in this project's history. For

    ((2 & ((-x) >> 31)) + ((x | (-x)) >> 31))     at x = INT_MIN

wrapping only the result gives -1; the machine gives 1. That single line let a
gate accept an expression that is wrong on real hardware, and it cost eleven
boundary faults before it was found.

`receipt()` returns 1 if the fix is live. If it ever returns anything else,
nothing this library says should be believed.
"""
from __future__ import annotations

import ast
from typing import Dict, Optional

__all__ = ["s32", "evaluate", "compile_expr", "receipt",
           "INT_MIN", "INT_MAX"]

INT_MIN = -2147483648
INT_MAX = 2147483647
_MASK = 0xFFFFFFFF


def s32(v: int) -> int:
    """Wrap to a signed 32-bit integer, the way C does with -fwrapv."""
    v &= _MASK
    return v - (1 << 32) if v >= (1 << 31) else v


_CACHE: Dict[str, ast.expr] = {}


def _parse(expr: str) -> Optional[ast.expr]:
    """Parse once and keep it. Parsing dominates evaluation cost otherwise —
    measured at 79.7% of total time, 0.3782 microseconds per character."""
    t = _CACHE.get(expr)
    if t is None:
        try:
            t = ast.parse(expr, mode="eval").body
        except SyntaxError:
            return None
        _CACHE[expr] = t
    return t


def evaluate(expr: str, x: int) -> Optional[int]:
    """Evaluate `expr` at `x` with C int32 semantics, wrapping after EVERY
    operation. Returns None if the expression is malformed or uses anything
    outside the supported set.

    The only free variable is `x`. Supported: + - * & | ^ << >> ~ unary-minus.
    Shifts take their right operand modulo 32, as the hardware does.
    """
    tree = _parse(expr)
    if tree is None:
        return None

    def ev(n):
        if isinstance(n, ast.Name):
            if n.id != "x":
                raise ValueError("unknown name %r" % n.id)
            return s32(x)
        if isinstance(n, ast.Constant):
            if not isinstance(n.value, int) or isinstance(n.value, bool):
                raise ValueError("non-integer constant")
            return s32(n.value)
        if isinstance(n, ast.UnaryOp):
            v = ev(n.operand)
            if isinstance(n.op, ast.USub):
                return s32(-v)
            if isinstance(n.op, ast.Invert):
                return s32(~v)
            if isinstance(n.op, ast.UAdd):
                return v
            raise ValueError("unsupported unary operator")
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            o = n.op
            if isinstance(o, ast.Add):
                return s32(a + b)
            if isinstance(o, ast.Sub):
                return s32(a - b)
            if isinstance(o, ast.Mult):
                return s32(a * b)
            if isinstance(o, ast.BitAnd):
                return s32(a & b)
            if isinstance(o, ast.BitOr):
                return s32(a | b)
            if isinstance(o, ast.BitXor):
                return s32(a ^ b)
            if isinstance(o, ast.LShift):
                return s32(a << (b & 31))
            if isinstance(o, ast.RShift):
                return s32(a >> (b & 31))
            raise ValueError("unsupported binary operator")
        raise ValueError("unsupported node %s" % type(n).__name__)

    try:
        return ev(tree)
    except Exception:                                    # noqa: BLE001
        return None


def receipt() -> int:
    """1 if the every-step wrapping fix is live. Anything else means stop.

    This is the exact expression and input from the original divergence, so a
    regression cannot slip past by being merely plausible.
    """
    v = evaluate("((2 & ((-x) >> 31)) + ((x | (-x)) >> 31))", INT_MIN)
    return 1 if v == 1 else 0


# ---------------------------------------------------------------------
# compile_expr — the same semantics, as a native closure.
#
# `evaluate` walks the AST per call. That is fine for a few thousand calls
# and ruinous for millions: promoting an instruction to an operator applies
# it to every node of every level, and the walk then dominates everything.
# Measured in a live run: a promoted search spent its time in the
# interpreter's own arithmetic dispatch rather than in the search.
#
# This compiles an expression ONCE into Python bytecode with s32 wrapped
# around every operation — the identical wrapping `evaluate` applies, so
# the results are equal by construction and checked by
# `test_compile_matches_evaluate`.
# ---------------------------------------------------------------------

_COMPILED: Dict[str, object] = {}


def _emit(n) -> str:
    if isinstance(n, ast.Name):
        if n.id != "x":
            raise ValueError("unknown name")
        return "s(x)"
    if isinstance(n, ast.Constant):
        if not isinstance(n.value, int) or isinstance(n.value, bool):
            raise ValueError("non-integer constant")
        return "s(%d)" % n.value
    if isinstance(n, ast.UnaryOp):
        v = _emit(n.operand)
        if isinstance(n.op, ast.USub):
            return "s(-(%s))" % v
        if isinstance(n.op, ast.Invert):
            return "s(~(%s))" % v
        if isinstance(n.op, ast.UAdd):
            return v
        raise ValueError("op")
    if isinstance(n, ast.BinOp):
        a, b = _emit(n.left), _emit(n.right)
        o = n.op
        for T, sym in ((ast.Add, "+"), (ast.Sub, "-"), (ast.Mult, "*"),
                       (ast.BitAnd, "&"), (ast.BitOr, "|"),
                       (ast.BitXor, "^")):
            if isinstance(o, T):
                return "s((%s) %s (%s))" % (a, sym, b)
        if isinstance(o, ast.LShift):
            return "s((%s) << ((%s) & 31))" % (a, b)
        if isinstance(o, ast.RShift):
            return "s((%s) >> ((%s) & 31))" % (a, b)
        raise ValueError("op")
    raise ValueError("node")


def compile_expr(expr: str):
    """Return a fast callable f(x) with identical semantics to
    `evaluate(expr, x)`, or None if the expression is unsupported."""
    fn = _COMPILED.get(expr)
    if fn is not None:
        return fn
    tree = _parse(expr)
    if tree is None:
        return None
    try:
        src = "lambda x, s=s32: " + _emit(tree)
        fn = eval(src, {"s32": s32})            # noqa: S307 - our own source
    except Exception:                            # noqa: BLE001
        return None
    _COMPILED[expr] = fn
    return fn
