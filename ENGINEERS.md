# proven-reason for AI/ML engineers

Free, Apache-2.0, offline-capable. The pitch in one sentence: **wrap any
code-generating model — local, frontier, or API — in a gate that makes
shipping a wrong `int32 -> int32` answer impossible**, with 64-bit handled
through proven lanes.

```bash
git clone https://github.com/devkancheti4-design/proven-reason
cd proven-reason && pip install -e .
```

## Connect anything

```python
from proven_reason.models import Ollama, Anthropic, OpenAICompat, Callable_, fuse

fz = fuse(Ollama("qwen2.5-coder:7b"))                # local, $0, no key
fz = fuse(Anthropic("claude-opus-5"))                # your ANTHROPIC_API_KEY
fz = fuse(Anthropic("claude-fable-5"))               # frontier-most Claude
fz = fuse(OpenAICompat("gpt-4o"))                    # your OPENAI_API_KEY
fz = fuse(OpenAICompat("m", base_url="http://localhost:8000"))  # vLLM/LM Studio
fz = fuse(Callable_(lambda p: your_stack(p)))        # anything that talks

out = fz.ask("divide x by two the way C does", "return x / 2;")
out.outcome    # PASS | FIX | REFUSE  — there is no fourth outcome
out.code       # proven code, or None
```

The adapter is the only thing that changes. The judgment (authored decision
expressions in `catalog/decisions.json`) and the truth (an exhaustive
compiled sweep over all 4,294,967,296 inputs) are identical for a 7B and a
frontier model — which is the design claim: **the guarantee does not depend
on the model.**

## The live three-way test

Six trap-heavy tasks. The frontier columns are Claude Fable 5's and Claude
Opus 5's recorded answers, frozen before grading; the local column is
qwen2.5-coder:7b running **live through the fuse**. One grader for all
three: this package's sweep.

```
task                                         fable5    opus5     qwen+fuse
round x up to the next multiple of 16        PROVEN    PROVEN    PASS
swap the four bytes of x                     PROVEN    PROVEN    PASS
saturating increment (stop at INT_MAX)       PROVEN    PROVEN    REFUSE
sign-extend the low 12 bits of x             PROVEN    PROVEN    PASS
divide x by 8, rounding toward -inf          PROVEN    PROVEN    PASS
one if x is a multiple of 16                 PROVEN    PROVEN    PASS

fable5  raw: 6 proven, 0 wrong-shipped
opus5   raw: 6 proven, 0 wrong-shipped
qwen+fuse : 5 PASS, 0 FIX, 1 REFUSE — wrong shipped: 0 by construction
```

Read the REFUSE row carefully — it is the product. qwen's live answer for
saturating increment was wrong; the gate shipped **silence** instead. The
frontier models earned their 6/6, but note who graded them: this package.
Ungated, their zero is unattested; gated, everyone's zero is structural.

**Postscript — whose fault was the REFUSE, and how it died.** Three-way
split: the model wrote the wrong answer (always the first fault); the shelf
lacked `SATINC` (stock); and the engine declares material as leaves, not
composable operators (a deliberate simplicity trade, documented here).
The fix took one authoring session: `SATINC` was authored in 147,673
evaluations, PROVEN by the sweep in 10.5s, and shipped as catalog
instruction 32. The same task now ends:

```
rejected (wrong on 1 inputs, first at x=2147483647);
PROVEN shelf rule SATINC ships instead      -> FIX
```

Wrong on ONE input in 4,294,967,296 — caught, named, repaired. REFUSE
rates are a stock level, not a ceiling.

And when frontier models face questions their training has no idiom for,
the picture inverts — see [benchmarks/sealed-duel](benchmarks/sealed-duel):
on twenty sealed grammar-sampled functions, **the engine went 13 PROVEN /
0 wrong while a frontier model shipped 5 wrong of 13 graded.**

## Integration patterns

**CI gate** — refuse to merge unverified integer utilities:

```python
g = Reasoner().gate(candidate_body, reference_body)
sys.exit(0 if g.safe else 1)          # REFUSE fails the build, honestly
```

**Retry loop with counterexample feedback** — the first failing input is
the most informative token you can add to a prompt:

```python
for _ in range(3):
    g = fz.ask(ticket, reference)
    if g.safe: break
    ticket += f"\n(previous attempt failed first at x={g.verdict.first_bad})"
```

**Distillation filter** — only proven pairs enter your training set:
generate with any model, keep `g.outcome in ("PASS", "FIX")`, and every
sample in the dataset carries a machine-checked label.

**64-bit**: `gate64(candidate, reference)` — suite-TESTED (4,000,169
edge-heavy pairs; 2¹²⁸ cannot be swept and the verdict never claims it),
repaired with lane compositions whose 16-bit lanes are each PROVEN over
their own 2³².

## Cost

| | this package | frontier API |
|---|---|---|
| per answer | ~11s CPU, $0 | $ per token |
| verification | included, exhaustive | none offered |
| wrong answers shipped | 0 by construction | unknowable |

Measured: four different free local models produced 41 wrong answers raw
across two batteries; fused, they shipped zero, with 27 proven repairs.

## Honest limits, so your design doc is right

- The proof domain is `int32 -> int32` (32 bits of input **total**) plus the
  64-bit lane path. Two-operand int32, arrays, floats, strings: the gate is
  inert and says so.
- `REFUSE` rates depend on the catalog. Deep targets whose building blocks
  are not shelved refuse rather than guess; extending the catalog converts
  refusals to repairs (measured: 12,796× cost drop on one target from
  declaring two pieces of material).
- The engine is exhaustive, not clever: `synthesize` proves minimality
  within its declared grammar, bounded by `max_size` and `max_nodes`, and
  its abstentions name which bound ran out.
- Verification requires a `reference` — a C body defining correct. Nothing
  honest can be proven against vibes.
