# proven-reason

**A bolt-on that tells you when your code is wrong.** Not by testing a few
inputs — by running **every one of the 4,294,967,296 int32 inputs** through
your code and a reference, in a compiled sweep, and reporting what the machine
found.

```python
from proven_reason import check

v = check("return (x + 15) & ~15;", "return (x + 15) & ~15;")
v.proven          # True
print(v)          # PROVEN — agrees on every one of 4,294,967,296 int32 inputs...
```

Bolt it onto any code generator and it becomes a gate:

```python
from proven_reason import Reasoner

rz = Reasoner()
g = rz.gate(model_wrote, reference)
g.outcome         # 'PASS' | 'FIX' | 'REFUSE'
g.code            # what is safe to ship, or None
```

**Every branch point in that loop evaluates an authored expression** shipped
in `catalog/decisions.json` — TRUST (measured rule: zero tolerance), STOP
(no real target ever landed past rung 3), MATERIAL (the fix is material,
never depth — the authored expression is literally `1`), and a judge that
predicts whether a repair will hold. None of the thresholds are hand-picked
constants; each was authored from measured data, and the provenance ships
beside the expression.

Measured across two batteries, four free local models, one laptop: **41
wrong answers between them raw. Zero shipped after the gate.** 27 repaired
with proofs, the rest refused. The judge's live record on repairs: 13 of 13
HOLD calls held, zero dangerous errors.

### The sealed duel

Twenty secret functions sampled from the engine's own grammar, no names, no
idioms — the same 20 pairs to this package and to a frontier model (Claude
Fable 5), whose answers were frozen before grading. Every answer swept over
all 4,294,967,296 inputs ([benchmarks/sealed-duel](benchmarks/sealed-duel)):

|  | PROVEN | WRONG | ABSTAIN |
|---|---:|---:|---:|
| frontier model (ships everything) | 8 | **5** | — |
| **this package's engine** | **13** | **0** | 7 |

On the 13 fully-graded tasks the engine went 13-for-13 and the frontier
model shipped five boundary-broken answers it could not tell from its
correct ones. Head-to-head: 5 wins, 8 ties, 0 losses. The seven abstentions
shipped nothing — and the frontier model's answers there remain unknown,
not victories.

---

## The gate has three safe outcomes and no fourth

| outcome | what happened |
|---|---|
| **PASS** | the model's own code swept clean; it goes through unchanged |
| **FIX** | the sweep found it wrong; a **PROVEN** shelf rule ships instead |
| **REFUSE** | wrong, and nothing on the shelf fits. **Nothing ships.** |

`REFUSE` is a safe outcome, not a failure. There is deliberately no fourth
outcome in which something unverified reaches the caller.

A real repair, run just now:

```
model wrote:  return x & 255;        for a clamp to [0, 255]
sweep: WRONG — 4,278,189,825 of 4,294,967,296 inputs, first at x=-2147483647
  → FIX: shipped SATU8 instead, PROVEN over the whole domain
```

`x & 255` wraps where a clamp saturates. It is right on 16,777,471 inputs and
wrong on the other four and a quarter billion, and it passes every unit test
anyone writes for it, because nobody tests `x = -2147483647`.

---

## The one distinction this library will not blur

```
PROVEN  <=>  for all x in [INT_MIN, INT_MAX] : candidate(x) == reference(x)
```

**`PROVEN` needs a reference you supply.** There is no honest way to invent one
for you, so without it the strongest thing sayable is `EXACT-ON-EXAMPLES(n)`.

A `WRONG` verdict is more useful than it looks — it hands you the exact input
that breaks it, and that input *is* the fix:

```
WRONG — disagrees on 47 of 4,294,967,296 inputs, first at x=1024.
Add that input to your examples and ask again.
```

**Under 2.0 seconds is not a proof.** 4.29 billion iterations do not finish
that fast; it means the compiler folded both sides to a constant. That is
reported as `SUSPECTED-FOLD` after a second run at `-O1`, never as success.

---

## What is in this package, and what is not

**The authoring engine ships. The core that produced it does not.**

There are three layers, and only the middle one is here:

| | |
|---|---|
| **the core** | manufactures engines. **Private. Not in this repository, and not described in it.** |
| **the engine** | `engine.py` — a size-ordered exhaustive search over a declared grammar. **Ships.** |
| **proven-reason** | the bolt-on: verify, gate, catalog, 64-bit. **Ships.** |

So this package can **verify** anything of the shape `int32 -> int32`, and it
can **author** — size-ordered, proving minimality within the grammar it was
given. What it cannot do is whatever the private core does on top of that,
which is not described here and is not needed to use any of this.

| ships | |
|---|---|
| `check()` | the exhaustive compiled sweep — the part that proves |
| `gate()` | PASS / FIX / REFUSE around any code generator |
| `synthesize()` | the engine — authors, and proves minimality in its grammar |
| `catalog()` | 31 proven instructions, each with its reference |
| `reason()` | shelf first, then author |
| `wide` | 64-bit from four PROVEN 16-bit lanes |

**An abstention states the bounds it holds under and never claims more:**

```python
r = reason([(0, 7), (1, 91), (2, -13)])
r.found   # False
r.note    # 'no expression of size <= 3 in this grammar. Space searched:
          #  23 operators, 13 constants, 31 declared. Levels: 655 23249
          #  912504. Raise max_size, or declare more material — the second
          #  is usually the one that is missing.'
```

It cannot say "no such rule exists" and it never appears to. It says: not at
this size, not in this grammar, not with this material — and each of those is
a different thing for you to change. A test enforces it.

### Material is the lever

```python
from proven_reason import reason, synthesize, Grammar, armed

synthesize(pairs)                      # base grammar
synthesize(pairs, grammar=armed())     # the whole proven catalog DECLARED
```

Registering is not declaring. Measured on the engine repository, same target,
same everything except what was declared:

| | evaluations | result |
|---|---:|---|
| halves not declared | **5,425,498** | found nothing |
| halves declared | **424** | size 2, 0.4s |

**12,796×.** Nothing about the search changed.

### What the ladder costs

With the whole catalog declared, measured:

| level | nodes | evaluations | time |
|---:|---:|---:|---:|
| 1 | 859 | 3,864 | 0.0s |
| 2 | 37,044 | 265,859 | 0.4s |
| 3 | 1,806,713 | 15,991,565 | 25.1s |

`max_size` defaults to **3** for that reason. Level 4 is about a billion
evaluations and several gigabytes — raise it deliberately, on a target you
believe needs it.

---

## The shelf

Thirty-one integer instructions. **No human wrote any of these expressions.**
Each was authored from pairs a compiled program printed, and each was swept
over all 4,294,967,296 inputs before the next was attempted.

```
NOT NEG INC DEC  SHL1 SHR1 SHR2 SHR4 SHR8 SHR16 SHR31
ZF SF SIGN ABS   SXB SXH ZXB ZXH   BYTE1 BYTE2 BYTE3
LOWBIT CLRLOW ROL1   MAX0 MIN127 MIN255 MAX128 SATB SATU8
```

**1,733,015 evaluations to author. 238.4 seconds of compiler time to verify.**
That ratio is the point: proving is the wall, not searching.

Nothing here has to be taken on trust — every entry carries the reference it
was proven against:

```python
from proven_reason import verify_all
verify_all()        # re-proves all 31 over 2^32 each, ~4 minutes
```

The cost of an instruction fell as the shelf grew, which is the whole design.
`SATB` with its two halves missing burned **5,425,498 evaluations and found
nothing**; with them on the shelf it landed at **424 evaluations in 0.4
seconds** — the same target, **12,796×**.

---

## Install — three commands to a fused model

```bash
git clone https://github.com/devkancheti4-design/proven-reason
cd proven-reason && python3 -m pip install -e .
```

```bash
ollama pull qwen2.5-coder:7b     # or any model — the guarantee doesn't care
```

```bash
proven-reason ask "one if x is odd, else zero" --reference "return x & 1;"
```

A real first run of exactly that command: the model answered `x % 2` —
wrong on **1,073,741,824 inputs** (every odd negative) — and what shipped
was the proven repair:

```
FIX
  rejected (wrong on 1,073,741,824 inputs, first at x=-2147483647);
  engine authored a replacement in 89 evaluations and the sweep proved it
  (judge said HOLD)
  ships: return (x & 1);
```

### 64-bit too

```bash
proven-reason verify64 "return a + b;" \
    --reference "return (long long)((unsigned long long)a + (unsigned long long)b);"
```

At 64 bits the strongest honest word is **TESTED** (4,000,169 edge-heavy
pairs — 2¹²⁸ cannot be swept), and a wrong candidate is repaired with the
lane composition whose four 16-bit lanes are each **PROVEN** over their own
2³². The verdict string always says which word it earned.

### Fuse ANY model — three lines

```python
from proven_reason.models import Ollama, Callable_, fuse

rz = fuse(Ollama("llama3:8b"))                 # any local model
rz = fuse(Callable_(lambda p: my_api(p)))      # any API, any framework
out = rz.ask("divide x by two the way C does", "return x / 2;")
```

The model supplies language; the authored decisions supply judgment; the
compiler supplies truth. **Swap the model freely — the guarantee never
changes**, and that is the measured point: four different local models, 41
wrong answers raw, zero shipped once fused.

Python 3.10+, and a **C compiler on `PATH`** (`cc`). No model, no API key, no
network. The compiler is not optional — it is the thing that proves.

Check it works:

```bash
python3 -c "from proven_reason import receipt; print(receipt())"
```

It must print `1`. Anything else means the evaluator disagrees with the machine
at `INT_MIN` and nothing this library says can be trusted. See
[MANUAL.md](MANUAL.md) for everything else.

---

## Bolted to a local model

Ten tasks whose answers are functions of one int32, so every answer is
checkable over its whole domain. Four free local models, each run twice — raw,
and gated. Same prompts, same temperature, same grader.

| body | raw proven | raw **WRONG** | +gate proven | +gate **WRONG** |
|---|---:|---:|---:|---:|
| qwen2.5-coder:7b | 7 | 3 | **10** | **0** |
| mistral:latest | 5 | 5 | 9 | **0** |
| llama3:8b | 5 | 5 | 8 | **0** |
| deepseek-coder:6.7b | **2** | **8** | 7 | **0** |

`deepseek-coder:6.7b` was right twice in ten and **shipped nothing false**.

**It is slower, and it is cheaper.** The sweep adds ~11 seconds per function
where a model answers in one. What it costs in API tokens is zero, and a free
7B on your own laptop reaches nothing-wrong — which is the actual saving.

---

## 64-bit

```python
from proven_reason.wide import add64, cmp64, VERDICT
add64(0x7FFFFFFFFFFFFFFF, 1)      # 0x8000000000000000
```

The engine takes **32 bits of input in total**. A 32-bit lane of a 64-bit add
needs `alo`, `blo` and a carry-in — 65 bits — which is not a hard question but
an *unaskable* one. Split it and every part fits:

| lane piece | bits in | size | evaluations | verdict |
|---|---:|---:|---:|---|
| `sum16` | 32 | 3 | 47,124 | **PROVEN** |
| `cout16` | 32 | 7 | 82,782 | **PROVEN** |
| `sumcin` | 17 | 3 | 47,165 | **PROVEN** |
| `coutcin` | 17 | 7 | 84,788 | **PROVEN** |

**The lanes are proven. The composition is not, and the module says so
itself.** Don't trust that number either — reproduce it:

```bash
python3 verify/wide_verify.py
```

It first proves its C mirror computes exactly what the shipped Python computes,
**and refuses to report anything if it does not.** Last run:
**26,169,803,776 pairs, 0 mismatches, 76.0 seconds** — 7.69e-29 of 2¹²⁸.
A composition inherits the weakest word in it.

---

## What it will not do

- **`int32 -> int32`, 32 bits of input in TOTAL.** Not per operand. Two `int`
  arguments is 64 bits and does not fit. The famous `(lo+hi)/2` binary-search
  overflow is exactly the kind of bug it **cannot** catch. Worth knowing before
  you promise anything.
- **It is not a language model.** No opinion on prose, API design, or anything
  whose answer is not an integer.
- **It has no clock.** It walks the whole ladder it is given, however long
  that takes. Bound work by `max_size`, never by a timer.
- **Minimal means minimal in the grammar you gave it**, never over all
  expressions. Hand it fewer operators and it will honestly report a larger
  answer as minimal.

## Where it earns its keep

Saturating arithmetic in codecs and DSP · sign extension in instruction
decoders · colour clamping in graphics · byte swapping in serialization · hash
mixers · alignment rounding in allocators · fixed-point in game engines.

For a typical web engineer this is close to none of their code. For an
embedded, codec, graphics, database, or compiler engineer it is a real slice —
and it is the slice where the bugs are invisible until they are expensive.

---

## The honest summary

**It is not smarter than a frontier model.** On tasks outside integers it is
not in the category at all, and on arrays and prose a frontier model and a 7B
model earn the identical verdict here, because neither can be checked.

It is the only participant that can tell you **when it is wrong**, and the only
one whose **silence means something**.

See [ATTRIBUTION.md](ATTRIBUTION.md) for who did what, every measurement, and
all 34 faults — which belong to the supplier, not the engine.

## Found by adversarial use, fixed in 0.3.0

Running these benchmarks surfaced two real defects — the kind only use finds:

1. **`check()` had no timeout.** A candidate with a non-terminating loop
   hung the caller forever (measured: 57 minutes). Now `NON-TERMINATING` —
   never a proof, never a pass.
2. **`synthesize()` had no memory bound.** A collision-free level can
   outgrow RAM while being built; the OS killed six searches mid-level.
   Now `max_nodes` — crossing it is a reported abstention, not a crash.

## For students

Free, offline, no key — see [STUDENTS.md](STUDENTS.md): five guided
exercises built from real transcripts, and the launch test — nine homework
questions through a fused free 7B, **9/9 shipped safe, 0 wrong shipped, by
construction**.

## Licence

**Apache License 2.0** — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Chosen over MIT for the explicit patent grant in §3, which terminates for
anyone who brings a patent claim against this work.
