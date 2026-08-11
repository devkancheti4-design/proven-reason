# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""cli — proven-reason from the command line.

    # fuse any local model and ask for proven code
    proven-reason ask "divide x by two the way C does" \\
        --reference "return x / 2;" --model qwen2.5-coder:7b

    # gate code you already have (no model needed)
    proven-reason verify "return x >> 1;" --reference "return x / 2;"

    # author directly from the reference (no model needed)
    proven-reason author --reference "return x < 0 ? -x : x;"

Every answer that ships was swept over all 4,294,967,296 int32 inputs.
REFUSE means nothing safe exists within the envelope — nothing ships.
"""
from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="proven-reason",
        description="Proven int32 code from any model: PASS / FIX / REFUSE, "
                    "judged by an exhaustive compiled sweep.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ask", help="fuse a model; ticket -> proven code")
    a.add_argument("ticket", help="what the function should do, in words")
    a.add_argument("--reference", required=True,
                   help="C body defining correct, e.g. 'return x / 2;'")
    a.add_argument("--model", default="qwen2.5-coder:7b",
                   help="any ollama model name (default: qwen2.5-coder:7b)")
    a.add_argument("--host", default="http://localhost:11434")

    v = sub.add_parser("verify", help="gate existing code, no model")
    v.add_argument("candidate", help="C body to check")
    v.add_argument("--reference", required=True)

    au = sub.add_parser("author", help="author from the reference, no model")
    au.add_argument("--reference", required=True)
    au.add_argument("--max-size", type=int, default=3)

    v64 = sub.add_parser("verify64",
                         help="gate a 64-bit `long long f(long long a, long "
                              "long b)` body — suite-TESTED, lane-repaired")
    v64.add_argument("candidate")
    v64.add_argument("--reference", required=True)

    ns = ap.parse_args(argv)

    from .reasoner import Reasoner
    rz = Reasoner()

    if ns.cmd == "verify64":
        from .reasoner import gate64
        out = gate64(ns.candidate, ns.reference)
        print(out.outcome)
        print("  " + out.note)
        if out.code:
            print("  ships: %s" % (out.code[:120] + ("..." if
                                                     len(out.code) > 120
                                                     else "")))
        return 0 if out.safe else 1

    if ns.cmd == "ask":
        from .models import Ollama, fuse
        out = fuse(Ollama(ns.model, host=ns.host)).ask(ns.ticket,
                                                       ns.reference)
    elif ns.cmd == "verify":
        out = rz.gate(ns.candidate, ns.reference)
    else:
        from .reasoner import _pairs_from
        from .engine import synthesize
        from . import armed, check
        pairs = _pairs_from(ns.reference)
        if not pairs:
            print("could not compile the reference")
            return 2
        cut = max(1, len(pairs) * 3 // 4)
        r = None
        for rung in range(1, ns.max_size + 1):
            r = synthesize(pairs[:cut], holdout=pairs[cut:], grammar=armed(),
                           max_size=rung)
            if r.found:
                break
        if r is None or not r.found:
            print("ABSTAIN — %s" % (r.note if r else "no attempt"))
            return 1
        vv = check("return %s;" % r.expr, ns.reference)
        print("%s  %s" % (vv.verdict, r.expr))
        return 0 if vv.proven else 1

    print(out.outcome)
    print("  " + out.note)
    if out.code:
        print("  ships: %s" % out.code)
    return 0 if out.safe else 1


if __name__ == "__main__":
    sys.exit(main())
