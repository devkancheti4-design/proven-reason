#!/usr/bin/env python3
"""duel_gen.py — PHASE 1 of the sealed duel: Fable 5 versus the reasoner
shipped in proven-reason. The authoring system that produced it is not
included here and does not compete.

Twenty secret functions, sampled from the engine's own grammar by a fixed
seed, sizes 2..6 — compositions with no name and no idiom, so neither side
gets a linguistic handle. Both sides receive the SAME pairs and nothing else.

The secrets go to secrets.json. THE OPPONENT (Fable 5) MUST NOT READ
THAT FILE — its answers are written from pairs.json alone, before the
grader runs. The grader (phase 3) sweeps both columns over all 4,294,967,296
inputs. PROVEN counts; nothing else does.
"""
import json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from proven_reason import evaluate, s32
from proven_reason.engine import OPS

rng = random.Random(20260811)

CONSTS = [0, 1, 2, 3, 7, 8, 15, 16, 31, 255, 127, -128]
UN = [k for k, v in OPS.items() if v[0] == 1]
BIN = [k for k, v in OPS.items() if v[0] == 2]

def tree(size):
    if size <= 0:
        return "x" if rng.random() < 0.72 else str(rng.choice(CONSTS))
    if rng.random() < 0.45:
        op = rng.choice(UN)
        return OPS[op][1].format(a=tree(size - 1))
    op = rng.choice(BIN)
    ls = rng.randint(0, size - 1)
    return OPS[op][1].format(a=tree(ls), b=tree(size - 1 - ls))

XS = [-2147483648, -2147483647, -1000000, -65536, -4096, -300, -256, -255,
      -129, -128, -127, -100, -33, -17, -16, -15, -8, -5, -3, -2, -1, 0, 1,
      2, 3, 5, 7, 8, 9, 15, 16, 17, 31, 33, 100, 127, 128, 200, 254, 255,
      256, 300, 1000, 4095, 4096, 65535, 65536, 1000000, 2147483646,
      2147483647]

secrets, pairs_out, seen = [], [], set()
while len(secrets) < 20:
    e = tree(rng.randint(2, 6))
    if e in seen:
        continue
    seen.add(e)
    vals = [evaluate(e, x) for x in XS]
    if any(v is None for v in vals):
        continue
    if len(set(vals)) < 4:                    # near-constant: no question
        continue
    if vals == [s32(x) for x in XS]:          # identity: no question
        continue
    secrets.append(e)
    pairs_out.append({"task": len(secrets), "pairs": list(zip(XS, vals))})

json.dump({"seed": 20260811,
           "secrets": [{"task": i + 1, "expr": e}
                       for i, e in enumerate(secrets)]},
          open(os.path.join(HERE, "secrets.json"), "w"), indent=1)
json.dump(pairs_out, open(os.path.join(HERE, "pairs.json"), "w"))

print("SEALED. 20 secrets written to secrets.json — the opponent must")
print("not read it. The pairs, the ONLY thing either side sees:")
print()
for t in pairs_out:
    interesting = [p for p in t["pairs"]
                   if p[0] in (-2147483648, -256, -17, -3, -1, 0, 1, 2, 3,
                               5, 8, 15, 16, 17, 33, 100, 255, 256, 65536,
                               2147483647)]
    print("TASK %2d: %s" % (t["task"],
                            "  ".join("f(%d)=%d" % (a, b)
                                      for a, b in interesting)))
