# proven-reason

**It is not a prover. It is a reasoner.**

Say that first, because the other framing is both weaker and wrong. Z3 is a
prover. CBMC is a prover. A twelve-line `for` loop over every `int32` is a
prover, and on a straight equivalence check Z3 beats this package by more
than a hundred times. Proving is commodity, and this package does not
pretend to own it.

**What it does is derive the rule.** Give it examples and it authors the
smallest expression that reproduces every one of them, out of material that
grows as you use it — and when nothing in that material can reach the
answer, it says so and names what was missing, instead of inventing
something plausible.

```python
from proven_reason import reason

r = reason([(0, 0), (1, 2), (2, 4), (-3, -6)])
r.expr            # (x << 1)
r.verdict         # EXACT-ON-EXAMPLES(4)
```

Then a decider judges it — and the decider is *not* this package's claim to
fame, it is this package's referee:

```python
r = reason(pairs, reference="return x*10;")
r.verdict         # PROVEN — agrees on every one of 4,294,967,296 int32 inputs
```

**Three actors, no overlap.** The reasoner *authors*. A trusted decider —
the compiled sweep here, and Z3 or CBMC just as legitimately — *proves*.
You *supply*: the examples, the reference, and the material. If you say
"it proves it", someone will correctly say it does not. Say **it derives
what has not been written, and a decider checks every input that exists.**
That is the stronger claim anyway: the checker is not the thing being
checked.

A model recalls what is in its training data. A prover checks a claim you
already have. Neither one hands you the rule when the rule was never
written down — that is the gap this fills.

---

## Start here

| you are | go to |
|---|---|
| **bolting this onto a model** — Claude, GPT, Gemini, or a 7B on your laptop | **[FUSE.md](FUSE.md)** — one call, four adapters, works with anything that takes text and returns text |
| **using it beyond one-variable int32** — two operands, 64-bit, any model, any decider | **[EVERYWHERE.md](EVERYWHERE.md)** — the recipes, with the honest word each domain earns |
| **a student** — free, offline, no key, no card | **[STUDENTS.md](STUDENTS.md)** — five guided exercises |
| **an AI/ML engineer** — putting a gate in front of generated code | **[ENGINEERS.md](ENGINEERS.md)** — the live record and the integration |
| **looking for everything else** | **[MANUAL.md](MANUAL.md)** |

```bash
git clone https://github.com/devkancheti4-design/proven-reason
cd proven-reason && python3 -m pip install -e .
proven-reason ask "one if x is odd, else zero" --reference "return x & 1;"
```

Python 3.10+ and a C compiler on `PATH`. No API key, no network, no model
required.

---

## Verifying code you already have

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

## What it saves

### Measured head-to-head: a frontier model wrote the same library by hand

27 integer primitives — clamps, popcounts, sign-extends, byte swap, saturating
add, next-power-of-two. Built twice. Once by this package driving a free local
7B, once by Claude Opus 5 writing every line itself. **The same decider judged
both**: a compiled sweep over all 4,294,967,296 inputs.

| | supplier tokens | wrong |
|---|---:|---:|
| frontier model, by hand | 634 code + 597 test harness = **1,231** | **1 of 23** |
| **this package** + a free local 7B | **450** (specs only) | **0** |

**2.7x fewer supplier tokens, and one fewer bug.** Two honest caveats: 634 is
only the *emitted code* — the reasoning that produced it is not counted, so
2.7x is a floor rather than the true ratio; and the local model's 604 tokens
are free, because it runs on the same laptop.

The bug matters more than the ratio. Asked for `x/2` rounding toward zero, the
frontier model wrote:

```c
return (x + ((unsigned)x >> 31)) >> 1;     /* wrong on 2,147,483,647 inputs */
```

C integer promotion makes the whole expression unsigned, so the final shift is
logical instead of arithmetic and every negative input is wrong. It is the
standard idiom, it reads as correct, and it passes any test that does not probe
negatives. The local 7B made the same class of error on the same function; the
engine authored `((x >> 1) + (x & (0 - (x >> 31))))` instead, and the sweep
proved it.

Seven of the 27 needed that repair. Four were refused outright — nothing
unverified shipped.

---

Three more numbers, measured, with the qualifiers attached rather than omitted.

**Per answer, where it can answer.** A frontier call on a task of this shape
runs roughly 1.5K in / 2K out including reasoning tokens. The engine's
authoring is milliseconds to seconds, and one exhaustive proof is about
eleven CPU-seconds on one core:

| | per answer |
|---|---|
| frontier model, $5/$25 per Mtok | ~$0.058 |
| frontier model, $10/$50 per Mtok | ~$0.115 |
| **this package** | **~$0.0001**, or exactly $0 on hardware you own |

That is roughly **500x** cheaper per answer, and it runs offline with no key.

**As a router, over a whole workload.** The honest number is smaller,
because abstentions still cost you a frontier call. On the sealed duel it
answered 13 of 20, so:

```
all-frontier, 20 tasks    20 x $0.058 = $1.16
this package first         7 x $0.058 = $0.41      ~65% fewer tokens
```

**65%, not 500x** — that is the figure to plan with.

**And the saving that actually matters is neither of those.** It is the
wrong answers that never reached the codebase:

| | wrong answers raw | wrong answers shipped |
|---|---:|---:|
| four free local models, two batteries | **41** | **0** |
| frontier model, 32 sealed tasks | **16** | — (no gate) |
| **this package**, same 32 | **0** | **0** |

A free 7B behind this gate ships less broken code than a frontier model
without one. What a shipped `int32` boundary bug costs to find later is not
a number this repository can honestly put a dollar on — so it does not.

**Where it does *not* save.** On a named, idiomatic problem a model is
faster and cheaper than a search: asked for `isPowerOfTwo`, a free 7B
answered `(x > 0) && ((x & (x-1)) == 0)` correctly on the first attempt,
while the engine needed promoted material and a counterexample to derive it.
Recall beats derivation whenever the answer was already written down
somewhere. This is for when it was not.

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
| `catalog()` | 64 proven instructions, each with its reference |
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

## Fuse ANY model — three lines

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


### From the command line

```bash
proven-reason verify64 "return a + b;" \
    --reference "return (long long)((unsigned long long)a + (unsigned long long)b);"
```

At 64 bits the strongest honest word is **TESTED** (4,000,169 edge-heavy
pairs — 2¹²⁸ cannot be swept), and a wrong candidate is repaired with the
lane composition whose four 16-bit lanes are each **PROVEN** over their own
2³². The verdict string always says which word it earned.

## For AI/ML engineers

Connect anything — `Ollama` (local, $0), `Anthropic("claude-opus-5")`,
`OpenAICompat` (OpenAI/Groq/vLLM/LM Studio), or any callable — and the
guarantee never changes. See [ENGINEERS.md](ENGINEERS.md) for the live
three-way test (Fable 5 vs Opus 5 vs a fused free 7B: zero wrong shipped in
every column, and only the fused column's zero is structural), plus CI-gate,
retry-with-counterexample, and distillation-filter patterns.

## For students

Free, offline, no key — see [STUDENTS.md](STUDENTS.md): five guided
exercises built from real transcripts, and the launch test — nine homework
questions through a fused free 7B, **9/9 shipped safe, 0 wrong shipped, by
construction**.

## Licence

**Apache License 2.0** — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Chosen over MIT for the explicit patent grant in §3, which terminates for
anyone who brings a patent claim against this work.
