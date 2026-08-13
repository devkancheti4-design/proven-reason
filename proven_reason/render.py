# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""render — fold authored soup back into the names it was built from.

THE DEFECT THIS EXISTS FOR. Material INLINES when an expression is emitted:
a size-2 tree built from a declared instruction flattens into hundreds of
characters, and at its measured worst on this codebase, 3,764,710 of them.
The result is correct, proven, and unreadable — `(x & ~7)` came out
beautiful while a saturating clamp came out as soup no reviewer would sign.

An adversarial review put it precisely: until the emitter prints shelf
instructions BY NAME instead of inlining them, half the outputs are not
code-review-able. This module is that emitter, run as a fold: it parses an
authored expression, finds every subtree that IS a catalog instruction
applied to some operand, and prints it as `NAME(operand)` instead.

    pretty("(... 300 chars of soup ...)")
    # 'MIN255(MAX0(x))', {'MIN255': ..., 'MAX0': ...}

    pretty_c("(... the same soup ...)")
    # '#define MAX0(x) (...)\\n#define MIN255(x) (...)\\n
    #  int f(int x) { return MIN255(MAX0(x)); }'

The fold is STRUCTURAL, not textual: expressions are parsed to syntax
trees and matched by unification, with `x` in the instruction's definition
as the one wildcard — bound once, required identical everywhere it
appears. A fold therefore cannot change meaning: `NAME(T)` expands by
definition to exactly the subtree it replaced. `pretty_c` output compiles
to the same function.

Small instructions do not fold. Renaming `(x + 1)` to `INC(x)` makes
nothing more readable; the threshold keeps single-operator idioms inline
and folds only definitions long enough that a reader would otherwise
drown. Callers can tune it.
"""
from __future__ import annotations

import ast
from typing import Dict, List, Optional, Tuple

from .catalog import catalog

__all__ = ["pretty", "pretty_c"]

_MIN_FOLD_LEN = 20          # definitions shorter than this stay inline


def _parse(expr: str) -> Optional[ast.expr]:
    try:
        return ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None


def _same(a: ast.expr, b: ast.expr) -> bool:
    return ast.dump(a) == ast.dump(b)


def _match(pat: ast.expr, node: ast.expr,
           bind: Dict[str, ast.expr]) -> Optional[Dict[str, ast.expr]]:
    """Unify `pat` (an instruction body, `x` as the wildcard) with `node`.

    `x` binds once and must match identically at every occurrence — that is
    what makes the fold semantics-preserving by construction."""
    if isinstance(pat, ast.Name) and pat.id == "x":
        if "x" in bind:
            return bind if _same(bind["x"], node) else None
        out = dict(bind)
        out["x"] = node
        return out
    if type(pat) is not type(node):
        return None
    if isinstance(pat, ast.Constant):
        return bind if pat.value == node.value else None
    if isinstance(pat, ast.Name):
        return bind if pat.id == node.id else None
    if isinstance(pat, ast.UnaryOp):
        if type(pat.op) is not type(node.op):
            return None
        return _match(pat.operand, node.operand, bind)
    if isinstance(pat, ast.BinOp):
        if type(pat.op) is not type(node.op):
            return None
        b = _match(pat.left, node.left, bind)
        if b is None:
            return None
        return _match(pat.right, node.right, b)
    return None


_OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.BitAnd: "&",
        ast.BitOr: "|", ast.BitXor: "^", ast.LShift: "<<", ast.RShift: ">>",
        ast.Div: "/", ast.Mod: "%"}


def _src(n: ast.expr) -> str:
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Constant):
        return str(n.value)
    if isinstance(n, ast.UnaryOp):
        op = {ast.USub: "-", ast.Invert: "~", ast.UAdd: "+"}[type(n.op)]
        return "(%s%s)" % (op, _src(n.operand))
    if isinstance(n, ast.BinOp):
        return "(%s %s %s)" % (_src(n.left), _OPS[type(n.op)], _src(n.right))
    if isinstance(n, ast.Call):
        return "%s(%s)" % (n.func.id, ", ".join(_src(a) for a in n.args))
    raise ValueError("unrenderable node %r" % n)


def _patterns(min_len: int) -> List[Tuple[str, ast.expr, str]]:
    """Catalog instructions as fold patterns, longest definition first, so
    a compound folds before the pieces it was built from."""
    out = []
    for ins in catalog():
        if len(ins.expr) < min_len:
            continue
        t = _parse(ins.expr)
        if t is not None:
            out.append((ins.name, t, ins.expr))
    out.sort(key=lambda p: -len(p[2]))
    return out


def _fold(node: ast.expr, pats) -> ast.expr:
    for name, pat, _e in pats:
        b = _match(pat, node, {})
        if b is not None and "x" in b:
            return ast.Call(func=ast.Name(id=name, ctx=ast.Load()),
                            args=[_fold(b["x"], pats)], keywords=[])
    if isinstance(node, ast.UnaryOp):
        return ast.UnaryOp(op=node.op, operand=_fold(node.operand, pats))
    if isinstance(node, ast.BinOp):
        return ast.BinOp(left=_fold(node.left, pats), op=node.op,
                         right=_fold(node.right, pats))
    return node


def _used(node: ast.expr, acc: Dict[str, str], defs: Dict[str, str]) -> None:
    if isinstance(node, ast.Call):
        acc[node.func.id] = defs[node.func.id]
        for a in node.args:
            _used(a, acc, defs)
    elif isinstance(node, ast.UnaryOp):
        _used(node.operand, acc, defs)
    elif isinstance(node, ast.BinOp):
        _used(node.left, acc, defs)
        _used(node.right, acc, defs)


def pretty(expr: str, min_len: int = _MIN_FOLD_LEN
           ) -> Tuple[str, Dict[str, str]]:
    """Fold an authored expression into catalog names.

    Returns `(folded_text, used)` where `used` maps each folded name to the
    definition it stands for. If nothing folds — or the expression does not
    parse — the original text comes back unchanged with an empty dict, so
    this is always safe to call on anything the engine emits."""
    tree = _parse(expr)
    if tree is None:
        return expr, {}
    pats = _patterns(min_len)
    defs = {name: e for name, _t, e in pats}
    folded = _fold(tree, pats)
    used: Dict[str, str] = {}
    _used(folded, used, defs)
    if not used:
        return expr, {}
    return _src(folded), used


def pretty_c(expr: str, fn_name: str = "f",
             min_len: int = _MIN_FOLD_LEN) -> str:
    """The review-able AND compilable form: `#define` lines for every folded
    instruction, then the short body. Expands to exactly the original."""
    body, used = pretty(expr, min_len)
    lines = ["#define %s(x) %s" % (n, used[n]) for n in sorted(used)]
    lines.append("int %s(int x) { return %s; }" % (fn_name, body))
    return "\n".join(lines)
