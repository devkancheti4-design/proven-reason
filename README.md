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
from proven_reason import gate

g = gate(model_wrote, reference)
g.outcome         # 'PASS' | 'FIX' | 'REFUSE'
g.code            # what is safe to ship, or None
```

Measured on ten tasks, four free local models, one laptop:
**21 wrong answers between them. Zero after the gate. No model got worse.**

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

This is an **artefact, not a factory.**

The expressions in `catalog/isa.json` were authored by an engine called **the
sphere**, which is **not included here**. The sphere manufactures engines;
those engines wrote this library. It is two steps upstream, it is not what
ships, and it is not what any table below benchmarks.

| ships here | not here |
|---|---|
| `check()` — the exhaustive compiled sweep | the authoring engine |
| `gate()` — PASS / FIX / REFUSE | the search |
| `catalog()` — 31 proven instructions, each with its reference | |
| `reason()` — the smallest proven rule that fits your examples | |
| `wide` — 64-bit from four PROVEN 16-bit lanes | |

**So it verifies anything of the shape `int32 -> int32`, and repairs only with
rules already on the shelf.** `reason()` says so itself rather than pretending:

```python
r = reason([(0, 7), (1, 91), (2, -13)])
r.found     # False
r.note      # 'no rule on the 31-instruction shelf reproduces all 3 of your
            #  examples. This build verifies but does not author, so this is
            #  NOT a claim that no such rule exists.'
```

That is a narrower claim than "no such rule exists", and the difference
matters.

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

## Install

```bash
git clone https://github.com/devkancheti4-design/proven-reason
cd proven-reason && python3 -m pip install -e .
```

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
- **It does not author.** That engine is not in this package.
- **It has no clock.** Bound work by size, not by a timer.

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

## Licence

**Apache License 2.0** — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Chosen over MIT for the explicit patent grant in §3, which terminates for
anyone who brings a patent claim against this work.
