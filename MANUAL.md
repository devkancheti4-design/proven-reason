# MANUAL

Everything proven-reason does, what it refuses to do, and how to read what it
tells you when it refuses.

---

## 1. Install and check

```bash
git clone https://github.com/devkancheti4-design/proven-reason
cd proven-reason
python3 -m pip install -e .
```

**Python 3.10+** and a **C compiler on `PATH`** (`cc`). No model, no API key,
no network. The compiler is not optional — it is the thing that proves.

```bash
python3 -c "from proven_reason import receipt; print(receipt())"
```

**It must print `1`.** If it prints anything else, stop. The evaluator is
disagreeing with the machine at `INT_MIN`, and nothing this library says can
be trusted until that is fixed. This is not a formality — that exact defect
was real here once, and it cost eleven boundary faults before it was found.

---

## 2. `check` — the part that proves

```python
from proven_reason import check

v = check("return (x + x);", "return x * 2;")

v.proven        # True
v.verdict       # 'PROVEN'
v.mismatches    # 0
v.first_bad     # 0
v.seconds       # 10.7
print(v)        # PROVEN — agrees on every one of 4,294,967,296 int32 inputs...
```

Both arguments are **C function bodies** for `int f(int x)` — statements,
including `return`. There is no sampling: every input is run.

### The verdicts

| verdict | meaning |
|---|---|
| `PROVEN` | agrees on **every** int32 input |
| `WRONG` | disagrees; `first_bad` is the input that breaks it |
| `SUSPECTED-FOLD` | the sweep was too fast to be real. **Not a proof.** |
| `NO-COMPILE` | one side did not compile |

### Why a fast sweep is a failure, not a success

4.29 billion iterations cannot finish in under two seconds. When they appear
to, the compiler has folded both sides to a constant and compared nothing. So
a sub-2s result is re-run at `-O1`, and if it is still instant it comes back
`SUSPECTED-FOLD`. Treat that as unverified.

The harness uses `-fwrapv` (signed overflow must wrap, or the compiler may
delete the very case you are testing), `-fno-lto` (no merging the two
functions into one), `noinline` on both sides, and a `volatile` sink so
neither loop can be optimised away.

### A `WRONG` verdict is the most useful one

```
WRONG — disagrees on 47 of 4,294,967,296 inputs, first at x=1024.
Add that input to your examples and ask again.
```

That input **is** the fix. One missing input out of 4.29 billion was measured
to leave an answer ambiguous; adding it made the answer unique.

---

## 3. `gate` — bolting it onto a code generator

This is the product.

```python
from proven_reason import gate

g = gate(candidate_c, reference_c)

g.outcome   # 'PASS' | 'FIX' | 'REFUSE'
g.code      # what is safe to ship, or None
g.safe      # True for PASS and FIX
g.verdict   # the underlying Verdict
g.note      # why
```

| outcome | what happened | what ships |
|---|---|---|
| **PASS** | swept clean | the model's own code |
| **FIX** | wrong; a proven shelf rule fits | the shelf rule |
| **REFUSE** | wrong, nothing fits | **nothing** |

`REFUSE` is **safe**. The caller gets nothing rather than something wrong.
There is deliberately no fourth outcome.

### A worked repair

```python
g = gate("return x & 255;", "return x < 0 ? 0 : (x > 255 ? 255 : x);")

g.outcome   # 'FIX'
g.verdict   # WRONG — 4,278,189,825 of 4,294,967,296, first at x=-2147483647
g.code      # 'return (((((((255 + ...' — SATU8, proven over the whole domain
```

`x & 255` wraps where a clamp saturates. It is right on 16,777,471 inputs and
wrong on the other four and a quarter billion — **and it passes every unit
test anyone writes for it**, because nobody tests `x = -2147483647`.

### In a loop

```python
def safe_generate(ask_model, ticket, reference):
    for attempt in range(3):
        g = gate(ask_model(ticket), reference)
        if g.safe:
            return g.code
        ticket += "\n(previous attempt failed at x=%d)" % g.verdict.first_bad
    return None      # refused three times; ship nothing
```

Feeding `first_bad` back into the prompt is free and it works — the failing
input is the most informative sentence you can add.

---

## 4. `catalog` — the shelf

Thirty-one proven instructions. **No human wrote any of these expressions.**

```python
from proven_reason import catalog, find, fits, verify_all

for ins in catalog():
    print(ins)                  # SATU8   saturate into an unsigned byte  (((...

find("satu8")                   # one instruction, or None
find("satu8").ref               # 'return x < 0 ? 0 : (x > 255 ? 255 : x);'
find("satu8")(300)              # 255  — evaluate it directly

fits([(0,0), (1,2), (2,4)])     # every shelf rule matching those pairs,
                                # smallest first
```

Nothing here has to be taken on trust. Every entry carries the C reference it
was proven against:

```python
verify_all()      # re-proves all 31 over 2^32 each, ~4 minutes
```

```
   1/31  NOT     PROVEN
   2/31  NEG     PROVEN
   ...
  31/31  SATB    PROVEN

31 of 31 re-proven over all 4,294,967,296 inputs.
```

**1,733,015 evaluations to author the shelf. 238.4 seconds to verify it.**
Proving is the wall, not searching.

---

## 5. `synthesize` and `reason` — the part that authors

```python
from proven_reason import synthesize, reason, armed, Grammar

a = synthesize([(0, 0), (1, 2), (2, 4), (-3, -6)])
a.found         # True
a.expr          # '(x << 1)'
a.size          # 1
a.minimal       # True — every smaller size was exhausted, not sampled
a.evaluations   # 39
```

`reason()` is the convenience wrapper: it checks the proven shelf first, which
is free, then authors if nothing there fits.

```python
r = reason([(x, x ^ (x >> 1)) for x in probes])
r.expr          # '(x ^ (x >> 1))'      authored
r = reason(pairs, reference="return x ^ (x >> 1);")
r.verdict       # 'PROVEN'              swept over all 4,294,967,296 inputs
```

**The engine's own answer earns no benefit of the doubt.** When you give a
reference, the authored expression goes through exactly the same sweep a
model's code goes through, and comes back PROVEN or WRONG on the same terms.

### Material is the lever, and declaring is the act

```python
synthesize(pairs)                      # base grammar only
synthesize(pairs, grammar=armed())     # the whole proven catalog DECLARED
```

**Registered is not declared.** An expression the search cannot reach is not
material, whatever else you have done with it. Measured, same target, same
everything except what was declared:

| | evaluations | result |
|---|---:|---|
| halves not declared | **5,425,498** | found nothing |
| halves declared | **424** | size 2, in 0.4s |

**12,796×.** Nothing about the search changed; six proven expressions became
available to build with.

Declare your own:

```python
g = Grammar().with_material([("MY_ROUND", "((x + 7) & -8)")])
synthesize(pairs, grammar=g)
```

### What the ladder costs, measured

With the whole catalog declared:

| level | nodes | evaluations | time |
|---:|---:|---:|---:|
| 1 | 859 | 3,864 | 0.0s |
| 2 | 37,044 | 265,859 | 0.4s |
| 3 | 1,806,713 | 15,991,565 | 25.1s |

`max_size` defaults to **3** for exactly that reason. Level 4 is roughly a
billion evaluations and several gigabytes. Raise it deliberately.

### Reading an abstention

```python
r = reason(pairs, on_level=lambda s, n, e: print(s, n, e))
```

```
no expression of size <= 3 in this grammar. Space searched: 23 operators,
13 constants, 31 declared. Levels: 655 23249 912504. Raise max_size, or
declare more material — the second is usually the one that is missing.
```

Three bounds, and each is a different thing for you to change:

| what it says | what to do about it |
|---|---|
| `size <= 3` | raise `max_size` — but read the cost table first |
| `23 operators, 13 constants` | the grammar; widen it if your answer needs an operator it lacks |
| `31 declared` | **usually this one.** Pass `grammar=armed()`, or declare your own proven pieces |

It will not say "no such rule exists", because it cannot know that. It says
"not at this size, in this grammar, with this material" — and a test in the
repository fails the build if that ever changes.

### `minimal` means minimal *in that grammar*

Never over all expressions. Hand it fewer operators and it will honestly
report a larger answer as minimal — which is correct, and is why the grammar
is reported alongside the answer.

## 6. 64-bit

```python
from proven_reason.wide import add64, cmp64, LANES, VERDICT

add64(0x7FFFFFFFFFFFFFFF, 1)      # 0x8000000000000000
cmp64(a, b)                       # -1, 0 or 1, unsigned
print(VERDICT)
```

32 bits of input **in total** is the limit, so a 64-bit add lane — `alo`,
`blo`, carry-in, 65 bits — is not a hard question but an unaskable one. Asked
as four smaller questions, every part fits, and all four lanes are `PROVEN`
over their own 2³².

**The lanes are proven. The composition is not, and the module says so.**

```bash
python3 verify/wide_verify.py            # ~2 minutes
python3 verify/wide_verify.py --quick    # ~15 seconds
```

It first proves its C mirror computes exactly what the shipped Python computes
— and **refuses to report anything if it does not** — then measures. Last run:
**26,169,803,776 pairs, 0 mismatches, 76.0 seconds**, which is 7.69e-29 of
2¹²⁸. A composition inherits the weakest word in it.

---

## 7. What it will not do

- **`int32 -> int32`, 32 bits of input in TOTAL.** Not per operand. Two `int`
  arguments is 64 bits and does not fit. Pack two 16-bit values into one word
  and it works — and the proof is then over the 2³² packed words.
  The famous `(lo+hi)/2` binary-search overflow is exactly the kind of bug it
  **cannot** catch.
- **It is not a language model.** No opinion on prose or API design.
- **It has no clock.** It walks the whole ladder it is given, however long
  that takes. Bound work by `max_size`, never by a timer.
- **The core that produced this engine is not here** and is not described
  here. What ships is a size-ordered exhaustive search — that, and nothing
  claimed beyond it.

---

## 8. Where it earns its keep

Saturating arithmetic in codecs and DSP · sign extension in instruction
decoders · colour clamping in graphics · byte swapping in serialization · hash
mixers · alignment rounding in allocators · fixed-point in game engines.

These are the functions where a wrong answer is invisible in review, passes
every unit test, and surfaces months later on one input in a billion.

---

## 9. Troubleshooting

| symptom | first thing to check |
|---|---|
| `receipt()` is not `1` | **stop.** The evaluator disagrees with the machine. |
| `RuntimeError: no C compiler` | install one; without it nothing can be proven |
| verdict is `SUSPECTED-FOLD` | the sweep was too fast to be real — treat as unproven |
| `NO-COMPILE` | your body is not valid C for `int f(int x)`; no signature, no braces |
| `gate` returns `REFUSE` a lot | expected — the shelf is 31 rules, not infinite. `check()` still verifies anything. |
| `reason` abstains | nothing on the shelf fits. It is not saying no rule exists. |
| a sweep takes ~11s | that is correct. 4.29 billion inputs is not free. |

---

## 10. The honest summary

Give it your code and a definition of what you meant; a compiler checks them
against every input that exists. So you are either right everywhere, or you
are told the exact input where you are not.

**It is not smarter than a frontier model.** It is the only participant that
can tell you *when it is wrong*, and the only one whose silence means
something.


---

# Appendix — measured history

Moved out of README.md, which had grown past the point where anyone
reads to the end. Nothing here is edited; it is the record as it stood.

### Two kinds of problem, two different winners (v1.0.0)

The same task, LC231 "is x a power of two", run both ways — and the answer
is that recall and derivation are complementary, not rivals:

```
a free 7B + the sweep      PROVEN on the first attempt
                           return (x > 0) && ((x & (x - 1)) == 0);

the engine, deriving       needed material promoted, depth past its usual
                           bound, and one counterexample the sweep named
                           (x = -2147483647) before it proved at size 3
```

LC231 has a name and an idiom, so a small model's recall is exactly right
and the sweep only has to confirm it. Invert that: on twelve **sealed**
functions that existed nowhere before their seed, a frontier model shipped
**eleven wrong answers** while the engine proved three and was wrong zero
times ([benchmarks/sealed-inverse](benchmarks/sealed-inverse)).

**A model knows what has been written. The engine derives what has not.
The compiler decides between them.** That is the whole architecture, and
both halves are measured.

`ISPOW2` is now shelved — but note what it took, because it is the honest
version of "hard": three things blocked it and all three were the caller's
— a node cap set too low, material stored as leaves instead of applicable
operators, and a probe set missing one input. The engine named the first
two in its own words (`resource bound…`, `no expression of size <= 3…`)
and the compiler named the third (`first bad x=-2147483647`). Adding that
single input made it provable in 27,702 evaluations.

### The inversion rungs (v0.9.0)

Five more, each re-proved over all 4,294,967,296 inputs before landing:
`XS4`, `XS8`, `XL8`, `XL16`, `UNFL8` — the xor-shift folds and their
unfolds, the material an inverse is built from. Catalog: **63**.

**Three were authored and PROVEN but are NOT shipped, and the reason is a
defect in this package, not in the answers.** `catalog/oversized.json`
records them with their measurements. The engine returned them as size-2
and size-3 expressions — two or three operations over declared material —
but material is stored as **flattened text**, so each rung inlines the full
text of everything beneath it and the size compounds down a ladder:

```
UNFL8   size 2          123 characters
UNF4    size 2      112,085 characters
UNF8    size 2    3,764,710 characters
```

All three are the same size to the engine. The difference is entirely what
their leaves happened to be. Promoting a 3.8 MB expression to an operator —
wrapping that text around every node of every level — exhausted memory in a
live run before any search happened.

**The fix is to store material by reference and expand once at proof time.**
Until then the catalog holds only expressions small enough to be honest
about, and the oversized three are recorded as measurements rather than
shipped as blobs.

### The DSA shelf (v0.7.0)

Twenty-six further instructions — the fold ladders hard DSA answers are made
of: the or-shift cascade to `NEXTP2`, the xor folds to `PARITY`, the
masked-add reduction to `POPCNT`, the swap ladders to `BSWAP` and `REVBITS`,
plus `SMEAR`, `CTZ_M`, `ILOG2P`. Each authored from compiled pairs, each
swept over all 4,294,967,296 inputs, each becoming material for the next.
The measured lesson repeated at scale: `POPCNT` abstained for a combined
**96 minutes** across two rounds while a rung was missing, then landed in
**41 seconds** once `PC8` existed. Depth was never the lever; the ladder's
26 landings all sat within the authored STOP bound (rung ≤ 3).

The exam: the three tasks the gated battery REFUSED — popcount, byte swap,
next-power-of-two — re-gated against the stocked catalog, using the models'
original wrong answers (one of them non-terminating):

```
count how many bits of x are set        FIX — PROVEN shelf rule POPCNT
swap the four bytes of x                FIX — PROVEN shelf rule BSWAP
smallest power of two >= x              FIX — PROVEN shelf rule NEXTP2

converted: 3 of 3 former REFUSEs now ship proven code
```

---

## Found by adversarial use, fixed in 0.3.0

Running these benchmarks surfaced two real defects — the kind only use finds:

1. **`check()` had no timeout.** A candidate with a non-terminating loop
   hung the caller forever (measured: 57 minutes). Now `NON-TERMINATING` —
   never a proof, never a pass.
2. **`synthesize()` had no memory bound.** A collision-free level can
   outgrow RAM while being built; the OS killed six searches mid-level.
   Now `max_nodes` — crossing it is a reported abstention, not a crash.

