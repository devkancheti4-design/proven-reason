#!/usr/bin/env python3
# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Regrade the sealed duel with the public package only. Hours of sweeps."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from proven_reason import synthesize, armed, check

SEC = {s["task"]: s["expr"] for s in json.load(open(os.path.join(HERE,"secrets.json")))["secrets"]}
PAIRS = {t["task"]: [tuple(p) for p in t["pairs"]] for t in json.load(open(os.path.join(HERE,"pairs.json")))}
MINE = json.load(open(os.path.join(HERE,"answers_fable5.json")))["answers"]
SHOWN = {-2147483648,-256,-17,-3,-1,0,1,2,3,5,8,15,16,17,33,100,255,256,65536,2147483647}
G = armed()
rows=[]
for t in sorted(SEC):
    sec, ps = SEC[t], PAIRS[t]
    mv = check(MINE[str(t)], "return %s;" % sec, timeout=300)
    train = [p for p in ps if p[0] in SHOWN]
    ho    = [p for p in ps if p[0] not in SHOWN]
    a=None
    for rung in (1,2,3):
        r = synthesize(train, holdout=ho, grammar=G, max_size=rung,
                       max_nodes=2_000_000)
        if r.found: a=r; break
        if "resource bound" in r.note: break
    if a is None:
        rv = "ABSTAIN(mem)" if "resource bound" in r.note else "ABSTAIN"
    else:
        rv = check("return %s;" % a.expr, "return %s;" % sec, timeout=300).verdict
    print("%2d  fable5 %-16s engine %s" % (t, mv.verdict, rv), flush=True)
    rows.append({"task":t,"fable5":mv.verdict,"engine":rv,
                 "engine_expr":a.expr if a else None})
    json.dump(rows, open(os.path.join(HERE,"regrade.json"),"w"), indent=1)
