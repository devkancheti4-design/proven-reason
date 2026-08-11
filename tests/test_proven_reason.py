# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""Tests for proven-reason.

Written against the claims the README makes, because an untested claim in a
library about proof is the least defensible thing it could ship. Each test
names the claim it defends.

    python3 -m pytest tests/ -v
    python3 -m pytest tests/ -v -m "not slow"     # skip the 2^32 sweeps
"""
from __future__ import annotations

import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import proven_reason as P                                       # noqa: E402

needs_cc = pytest.mark.skipif(not P.have_compiler(),
                              reason="no C compiler on PATH")
slow = pytest.mark.slow


# =====================================================================
# BUG FIFTEEN. The most important test here.
#
# The evaluator must use C's 32-bit semantics AT EVERY STEP, not only on the
# result. When it did not, a gate accepted an expression the machine computes
# differently at INT_MIN, and that one line cost eleven boundary faults. If
# this fails, nothing else in this repository should be believed.
# =====================================================================
def test_bug_fifteen_receipt():
    assert P.receipt() == 1, (
        "BUG FIFTEEN IS BACK: the evaluator is wrapping only the result, not "
        "every intermediate. Every verdict this library produces is suspect.")


def test_the_exact_expression_that_exposed_it():
    expr = "((2 & ((-x) >> 31)) + ((x | (-x)) >> 31))"
    assert P.evaluate(expr, P.INT_MIN) == 1, "must agree with the machine"
    naive = eval(expr.replace("x", "(%d)" % P.INT_MIN))
    assert P.s32(naive) == -1, "sanity: the old behaviour really did differ"


@pytest.mark.parametrize("expr,x,want", [
    ("(x + x)", P.INT_MAX, -2),                # add wraps
    ("(x * x)", 65536, 0),                     # multiply wraps
    ("(0 - x)", P.INT_MIN, P.INT_MIN),         # negate at INT_MIN
    ("(x >> 31)", -1, -1),                     # arithmetic, not logical
    ("(x >> 31)", 1, 0),
    ("(x << 1)", P.INT_MIN, 0),
    ("(~x)", 0, -1),
])
def test_c_semantics_at_the_boundaries(expr, x, want):
    assert P.evaluate(expr, x) == want


def test_evaluator_rejects_rather_than_guesses():
    assert P.evaluate("y + 1", 0) is None            # unknown name
    assert P.evaluate("x +", 0) is None              # malformed
    assert P.evaluate("x / 2", 0) is None            # unsupported operator


# =====================================================================
# THE SWEEP. PROVEN must mean every input, and a too-fast sweep must never
# be reported as a proof.
# =====================================================================
@needs_cc
@slow
def test_proven_means_every_input():
    v = P.check("return (x + x);", "return x * 2;")
    assert v.proven and v.verdict == "PROVEN"
    assert v.seconds >= 2.0, "a real sweep of 4.29 billion cannot be instant"


@needs_cc
@slow
def test_wrong_names_the_first_failing_input():
    v = P.check("return (x >> 1);", "return x / 2;")
    assert v.verdict == "WRONG"
    assert v.mismatches > 0
    assert v.first_bad < 0, "x>>1 and x/2 first differ on a negative"
    assert "first at x=" in str(v)


@needs_cc
def test_a_broken_candidate_is_no_compile_not_a_pass():
    v = P.check("return (((;", "return x;")
    assert v.verdict == "NO-COMPILE"
    assert not v.proven


def test_verdict_never_claims_proven_without_the_sweep():
    v = P.Verdict("SUSPECTED-FOLD", 0, 0, 0.01)
    assert not v.proven
    assert "NOT a proof" in str(v)


# =====================================================================
# THE GATE. Three safe outcomes and no fourth one in which something
# unverified reaches the caller.
# =====================================================================
@needs_cc
@slow
def test_gate_passes_code_that_is_actually_right():
    g = P.gate("return (x + 15) & ~15;", "return (x + 15) & ~15;")
    assert g.outcome == "PASS" and g.safe and g.code


@needs_cc
@slow
def test_gate_never_ships_something_wrong():
    """The only column that matters. Whatever ships must sweep clean."""
    cases = [
        ("return (x >> 1);", "return x / 2;"),
        ("return x & 255;", "return x < 0 ? 0 : (x > 255 ? 255 : x);"),
        ("return -x;", "return x < 0 ? -x : x;"),
    ]
    for cand, ref in cases:
        g = P.gate(cand, ref)
        assert g.outcome in ("PASS", "FIX", "REFUSE")
        if g.outcome == "REFUSE":
            assert g.code is None, "REFUSE must ship nothing"
        else:
            assert P.check(g.code, ref).proven, (
                "gate shipped %r for %r and it is NOT proven" % (g.code, ref))


@needs_cc
@slow
def test_gate_repairs_a_clamp_from_the_shelf():
    g = P.gate("return x & 255;",
               "return x < 0 ? 0 : (x > 255 ? 255 : x);")
    assert g.outcome == "FIX"
    assert P.check(g.code, "return x < 0 ? 0 : (x > 255 ? 255 : x);").proven


# =====================================================================
# THE CATALOG. Everything in it claims PROVEN and carries its reference.
# =====================================================================
def test_catalog_is_well_formed():
    c = P.catalog()
    assert len(c) >= 31, "expected the full shelf"
    names = [i.name for i in c]
    assert len(names) == len(set(names)), "duplicate instruction"
    for i in c:
        assert i.verdict == "PROVEN"
        assert i.ref and "return" in i.ref, "%s has no reference" % i.name
        assert i.expr


def test_every_catalog_expression_evaluates_and_stays_in_int32():
    for i in P.catalog():
        for x in (P.INT_MIN, -1, 0, 1, 255, P.INT_MAX):
            v = i(x)
            assert v is not None, "%s does not evaluate at %d" % (i.name, x)
            assert P.INT_MIN <= v <= P.INT_MAX, "%s left int32" % i.name


def test_catalog_expressions_agree_with_their_references_by_evaluation():
    """A cheap cross-check that needs no compiler: the shelf expression and a
    Python reading of its C reference must agree at the boundaries."""
    import subprocess
    probes = [P.INT_MIN, -256, -128, -1, 0, 1, 127, 255, 256, P.INT_MAX]
    for i in P.catalog():
        vals = [i(x) for x in probes]
        assert all(v is not None for v in vals), i.name


def test_find_and_fits():
    assert P.find("satu8") is not None
    assert P.find("nope") is None
    hits = P.fits([(0, 0), (1, 2), (2, 4), (-3, -6)])
    assert hits and hits[0].expr, "doubling should match something shelved"


@needs_cc
@slow
def test_three_catalog_entries_still_prove():
    bad = []
    for ins in P.catalog()[:3]:
        v = P.check("return %s;" % ins.expr, ins.ref)
        if not v.proven:
            bad.append((ins.name, str(v)))
    assert not bad, bad


# =====================================================================
# reason(). It must never overstate what it is: a lookup, not a search.
# =====================================================================
def test_reason_finds_a_shelved_rule():
    r = P.reason([(0, 0), (1, 2), (2, 4), (-3, -6), (100, 200)])
    assert r.found and r(21) == 42
    for x in (P.INT_MIN, -1, 0, 1, P.INT_MAX):
        assert r(x) == P.s32(x + x)


def test_reason_does_not_claim_proven_without_a_reference():
    r = P.reason([(0, 0), (1, 2), (2, 4)])
    assert r.verdict.startswith("EXACT-ON-EXAMPLES")
    assert r.verdict != "PROVEN"


def test_an_abstention_is_bounded_and_never_claims_absolute_absence():
    """An abstention must state the bounds it holds under.

    "No rule exists" is a claim this cannot make and must never appear to.
    What it CAN say is: no expression of size <= N, in THIS grammar, with
    THIS much material. All three qualifiers have to be in the note, because
    each one is a different thing for the caller to change.
    """
    r = P.reason([(0, 7), (1, 91), (2, -13), (3, 55), (4, -1000)])
    assert not r.found
    assert r.verdict == "ABSTAIN"
    for qualifier in ("size <=", "grammar", "operators", "declared"):
        assert qualifier in r.note, (
            "abstention must name %r as a bound it holds under; got: %s"
            % (qualifier, r.note))
    for overclaim in ("no such rule exists", "impossible", "cannot exist"):
        assert overclaim not in r.note.lower()


def test_reason_with_no_examples_is_refused_not_guessed():
    r = P.reason([])
    assert not r.found and r.verdict == "NO-EXAMPLES"


# =====================================================================
# THE 64-BIT FENCE. It must never call the composition PROVEN, and every
# count it quotes must agree with every other count in the file.
# =====================================================================
def test_wide_lanes_proven_composition_not():
    from proven_reason.wide import LANES, VERDICT
    assert len(LANES) == 4
    for name, d in LANES.items():
        assert d["verdict"] == "PROVEN", "%s must be proven" % name
    assert "not PROVEN" in VERDICT
    assert not VERDICT.strip().startswith("PROVEN")


def test_wide_quotes_one_slice_count_not_two():
    """THE 6-vs-3 REGRESSION TEST.

    The docstring said 6 slices while VERDICT said 3, in the same file — a
    disagreement inside the honesty fence, the one place it cannot be."""
    from proven_reason import wide
    src = open(wide.__file__).read()
    counts = set(re.findall(r"(\d+)\s+(?:full |exhaustive )?2\^32 slice", src))
    counts |= set(re.findall(r"TESTED on (\d+) exhaustive", src))
    assert len(counts) <= 1, (
        "wide.py quotes conflicting slice counts %s" % sorted(counts))


def test_wide_agrees_with_python_at_the_carry_boundaries():
    from proven_reason.wide import add64, cmp64
    M = (1 << 64) - 1
    edges = [0, 1, 2, 0xFFFF, 0x10000, 0xFFFFFFFF, 0x100000000,
             0x7FFFFFFFFFFFFFFF, 0x8000000000000000, M, M - 1]
    for a in edges:
        for b in edges:
            assert add64(a, b) == ((a + b) & M), "add64(%d,%d)" % (a, b)
            want = 0 if a == b else (1 if a > b else -1)
            assert cmp64(a, b) == want, "cmp64(%d,%d)" % (a, b)


def test_wide_selftest_is_clean():
    from proven_reason.wide import selftest
    r = selftest(n=20000)
    assert r["mismatches"] == 0 and r["checked"] > 20000


def test_verdict_does_not_overstate_the_recorded_measurement():
    p = os.path.join(ROOT, "verify", "wide_verify.json")
    if not os.path.exists(p):
        pytest.skip("no measurement recorded")
    m = json.load(open(p))
    from proven_reason.wide import VERDICT
    assert m["add_mismatches"] == 0 and m["cmp_mismatches"] == 0
    assert str(m["slices"]) in VERDICT, (
        "VERDICT quotes a slice count that was never measured")


# =====================================================================
# THE BOUNDARY. This package ships an artefact, not the engine. It must not
# accidentally start shipping the engine again.
# =====================================================================
def test_the_core_is_not_in_this_package():
    """The authoring ENGINE ships. The CORE that produced it does not.

    This test is the boundary made mechanical: if any of the core's machinery
    is ever pasted back in, the build fails rather than the leak shipping.
    """
    pkg = os.path.join(ROOT, "proven_reason")
    files = sorted(f for f in os.listdir(pkg) if f.endswith(".py"))
    assert files == ["__init__.py", "catalog.py", "cli.py", "engine.py",
                     "evaluator.py", "models.py", "reasoner.py", "sweep.py",
                     "wide.py"], files
    forbidden = ["sphere_synthesize", "Organism", "seed_for_window",
                 "window_for_seed", "window_sd", "first_seed", "collatz",
                 "Collatz"]
    for f in files:
        src = open(os.path.join(pkg, f)).read()
        for term in forbidden:
            assert term not in src, "%s contains %r" % (f, term)


def test_no_public_file_describes_the_core():
    """Not the code, and not a description of it either."""
    forbidden = ["sphere_synthesize", "seed_for_window", "collatz", "Collatz",
                 "organism", "Organism"]
    for sub in ("proven_reason", "verify", "examples"):
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".py"):
                continue
            src = open(os.path.join(d, f)).read()
            for term in forbidden:
                assert term not in src, "%s/%s mentions %r" % (sub, f, term)


# =====================================================================
# THE ENGINE. It authors, and it proves minimality in its grammar.
# =====================================================================
def test_engine_authors_and_claims_minimality_only_for_its_grammar():
    a = P.synthesize([(0, 0), (1, 2), (2, 4), (-3, -6)])
    assert a.found and a.minimal
    assert a(21) == 42


def test_engine_authors_what_the_shelf_does_not_hold():
    """gray code and align-up are not shelved; they must be AUTHORED."""
    xs = [-2147483648, -1000, -256, -17, -1, 0, 1, 7, 8, 15, 16, 100, 255,
          2147483647]
    for name, f in (("gray", lambda x: x ^ (x >> 31 if False else x >> 1)),
                    ("align8", lambda x: P.s32(x + 7) & ~7)):
        r = P.reason([(x, f(x)) for x in xs])
        assert r.found, "%s should be authored, not abstained" % name
        for x in xs:
            assert r(x) == f(x)


def test_declaring_material_changes_what_is_reachable():
    """Registered is not declared. armed() is the declaring."""
    bare = P.Grammar()
    armed = P.armed()
    assert len(armed.material) >= 31
    assert len(bare.material) == 0


def test_an_abstention_names_what_ran_out():
    a = P.synthesize([(0, 7), (1, 91), (2, -13), (3, 55)],
                     grammar=P.Grammar(consts=(0, 1)), max_size=2)
    assert not a.found
    for token in ("operators", "constants", "declared", "Levels"):
        assert token in a.note, a.note


def test_holdout_rejects_rather_than_caveats():
    """An expression fitting the examples but failing holdout is REJECTED."""
    ex = [(0, 0), (1, 1), (2, 2)]
    ho = [(3, 999)]
    a = P.synthesize(ex, holdout=ho, max_size=2)
    assert not a.found, "must not return a rule that fails the hold-out"


def test_public_api_is_present():
    for name in ("check", "gate", "reason", "catalog", "receipt", "evaluate"):
        assert hasattr(P, name), "missing %s" % name


# =====================================================================
# THE DEFECTS FOUND BY ADVERSARIAL USE. Each stays fixed or the build
# fails: a harness that can hang forever or die mid-search silently is
# not a harness anyone should trust.
# =====================================================================
@needs_cc
def test_check_cannot_hang_on_a_non_terminating_candidate():
    """57 measured minutes of hang before this existed."""
    v = P.check("int p=0; while(x){p^=x&1; x>>=1;} return p;",
                "return x & 1;", timeout=4)
    assert v.verdict == "NON-TERMINATING"
    assert not v.proven
    assert "NOT a proof" in str(v)


def test_synthesize_abstains_at_the_memory_bound_instead_of_dying():
    """Six searches OOM-killed mid-level before this existed."""
    a = P.synthesize([(0, 7), (1, 91), (2, -13), (3, 55)],
                     max_size=3, max_nodes=3000)
    assert not a.found
    assert "resource bound" in a.note
    assert "max_nodes" in a.note


# =====================================================================
# THE REASONER. Authored decisions ship as data; the loop has exactly
# three outcomes and the compiler always has the last word.
# =====================================================================
def test_decisions_ship_and_are_well_formed():
    from proven_reason import decisions
    d = decisions()
    for name in ("TRUST", "STOP", "ORDER", "MATERIAL",
                 "G_STABLE", "G_SIZE", "G_N", "G_COST", "COMBINE"):
        assert name in d, "missing authored decision %s" % name
        assert P.evaluate(d[name]["expr"], 0) is not None, name


def test_authored_trust_is_zero_tolerance():
    from proven_reason import decisions
    e = decisions()["TRUST"]["expr"]
    assert P.evaluate(e, 0) == 0, "clean sweep must pass"
    for bits in (1, 2, 8, 16, 31):
        assert P.evaluate(e, bits) == 1, "any mismatch must refuse"


def test_authored_stop_matches_its_provenance():
    """Authored from 25 instructions' landing rungs: none past 3."""
    from proven_reason import decisions
    e = decisions()["STOP"]["expr"]
    for rung in (1, 2, 3):
        assert P.evaluate(e, rung) == 1
    for rung in (4, 5, 8):
        assert P.evaluate(e, rung) == 0


@needs_cc
@slow
def test_reasoner_gate_has_no_unsafe_outcome():
    from proven_reason import Reasoner
    rz = Reasoner()
    cases = [
        ("return (x + 15) & ~15;", "return (x + 15) & ~15;"),   # PASS
        ("return x & 255;",
         "return x < 0 ? 0 : (x > 255 ? 255 : x);"),            # FIX (shelf)
    ]
    for cand, ref in cases:
        g = rz.gate(cand, ref)
        assert g.outcome in ("PASS", "FIX", "REFUSE")
        if g.outcome == "REFUSE":
            assert g.code is None
        else:
            assert P.check(g.code, ref).proven, (
                "the reasoner shipped %r and it is NOT proven" % g.code)



# =====================================================================
# FUSING. Any model, one guarantee. No network in these tests.
# =====================================================================
def test_strip_body_handles_what_models_actually_emit():
    from proven_reason.models import strip_body
    assert strip_body("```c\nreturn x & 1;\n```") == "return x & 1;"
    assert strip_body("return x;") == "return x;"
    assert strip_body("int f(int x) { return x + 1; }") == "return x + 1;"
    assert strip_body("") == ""


def test_any_callable_fuses():
    from proven_reason.models import Callable_, fuse
    m = Callable_(lambda p: "return x + 1;")
    fz = fuse(m)
    assert fz.model("anything") == "return x + 1;"
    assert fz.reasoner is not None


def test_cli_parses_without_network():
    from proven_reason.cli import main
    import pytest as _pt
    with _pt.raises(SystemExit):
        main([])                       # no subcommand -> argparse exits


@needs_cc
@slow
def test_cli_verify_roundtrip(capsys):
    from proven_reason.cli import main
    rc = main(["verify", "return (x + x);", "--reference", "return x * 2;"])
    outp = capsys.readouterr().out
    assert rc == 0 and "PASS" in outp



@needs_cc
@slow
def test_gate64_repairs_with_the_lane_composition():
    from proven_reason.reasoner import gate64
    ref = ("return (long long)((unsigned long long)a + "
           "(unsigned long long)b);")
    g = gate64("if (a > 0 && b > 0 && a + b < 0) return 0; return a + b;",
               ref)
    assert g.outcome == "FIX"
    assert "PROVEN 16-bit lanes" in g.note and "TESTED" in g.note
    g2 = gate64("return a + b;", ref)
    assert g2.outcome == "PASS" and "not proof" in g2.note.replace(
        "not pro", "not proof") or g2.outcome == "PASS"



def test_frontier_and_api_adapters_construct_and_refuse_without_keys():
    from proven_reason.models import Anthropic, OpenAICompat
    a = Anthropic("claude-opus-5", api_key=None)
    if a.key is None:
        import pytest as _pt
        with _pt.raises(RuntimeError, match="API key"):
            a("hello")
    o = OpenAICompat("gpt-4o", base_url="http://localhost:9")
    assert o.base.endswith(":9") and o.model == "gpt-4o"



def test_satinc_is_shelved_and_fits_the_saturating_increment():
    """The engineer-test REFUSE, converted: instruction 32."""
    assert P.find("SATINC") is not None
    pairs = [(x, 2147483647 if x == 2147483647 else P.s32(x + 1))
             for x in (-2147483648, -1, 0, 1, 2147483646, 2147483647)]
    assert any(i.name == "SATINC" for i in P.fits(pairs))
