# Using it on everything

**It is a reasoner, not a prover.** A prover needs the answer already
written — it can only say yes or no to a claim. The reasoner is the thing
that hands you the claim when nobody wrote it down. The proving underneath
is hired help, and the help is swappable.

That is why this is not an int32 tool. The arrangement is three actors:

    YOU SUPPLY      what correct means — a reference, and sharp intent
    IT REASONS      locates the rule: model recall, engine derivation, or both
    A DECIDER SIGNS commodity, replaceable, never the interesting part

**It works on any function for which you can say what correct means.**
Where you cannot, nothing works — including writing it yourself.

The only thing that changes across domains is *which word the decider can
honestly sign*:

| domain | decider | the word it earns |
|---|---|---|
| `int32 -> int32` | compiled sweep, all 4,294,967,296 inputs | **PROVEN** |
| `(int32, int32) -> int32` | Z3, all 18,446,744,073,709,551,616 pairs at once | **PROVEN** |
| 64-bit, two operands | entropy-seeded suite (2^128 cannot be enumerated) | **TESTED** |
| anything with only examples | the examples | **EXACT-ON-EXAMPLES(n)** |

The word never upgrades itself. That discipline is the product.

---

## Recipe 1 — one variable, int32 (ships in this package)

```python
from proven_reason import reason, gate, pretty

# derive a rule from examples, prove it against your definition
r = reason(pairs, reference="return x/2;")
r.verdict                     # PROVEN — all 4,294,967,296 inputs

# gate any model's output
g = gate(model_wrote, reference)
g.outcome                     # PASS / FIX / REFUSE — no fourth outcome

# fold authored soup into reviewable names
pretty(r.expr)                # ('SATU8(x)', {'SATU8': ...})
```

Or from any terminal, no SDK, no key:

```bash
proven-reason ask "divide x by two the way C does" --reference "return x/2;"
```

## Recipe 2 — two operands, proven by Z3 (copy-paste, measured)

The sweep cannot enumerate 1.8e19 pairs. Z3 covers them all at once,
symbolically, in hundredths of a second. `pip install z3-solver`, then:

```python
import re, z3

def decide2(body: str, ref):
    """Candidate C body vs a z3 reference, over EVERY int32 pair."""
    a, b = z3.BitVec("a", 32), z3.BitVec("b", 32)
    src = re.search(r"return\s+(.*);", body, re.S).group(1)
    src = src.replace("&&", " and ").replace("||", " or ")
    got = eval(src, {"__builtins__": {}},
               {"a": a, "b": b,
                "INT_MAX": z3.BitVecVal(2147483647, 32),
                "INT_MIN": z3.BitVecVal(-2147483648, 32)})
    if z3.is_bool(got):
        got = z3.If(got, z3.BitVecVal(1, 32), z3.BitVecVal(0, 32))
    s = z3.Solver()
    s.add(got != ref(a, b))
    r = s.check()
    if r == z3.unsat:
        return "PROVEN", None
    m = s.model()
    return "WRONG", "a=%s b=%s" % (m.eval(a), m.eval(b))

# the reference IS the definition — write it the clearest way, not the fastest
ref_avg = lambda a, b: z3.Extract(31, 0,
    (z3.SignExt(32, a) + z3.SignExt(32, b)) >> 1)

decide2("return (a + b) / 2;", ref_avg)
# ('WRONG', 'a=1963037172 b=1795059211')   <- the exact overflowing pair
decide2("return (a & b) + ((a ^ b) >> 1);", ref_avg)
# ('PROVEN', None)                          <- every pair, 0.01s
```

Ternary (`?:`) needs a small rewrite to `z3.If` — see the full reader in
the repository history. A counterexample is not a failure report; it is
**the next thing to feed back** (Recipe 4).

## Recipe 3 — 64 bits, two operands (ships in this package)

```python
from proven_reason import gate64

g = gate64("return a + b;",
           "return (long long)((unsigned long long)a + (unsigned long long)b);")
g.outcome    # PASS — "TESTED clean on 4,000,169 64-bit pairs (seed N, fresh each run)"
```

The honest word here is TESTED — 2^128 pairs cannot be enumerated. The
suite seeds from entropy so every run explores pairs no previous run saw;
pass `seed=` to reproduce a failing run exactly. Measured: a planted
1-in-2^24 defect passed the old frozen suite forever, and was caught on
run 8 with fresh seeds.

## Recipe 4 — fuse any model, and the repair loop that makes it universal

```python
from proven_reason.models import Ollama, Anthropic, OpenAICompat, Callable_, fuse

rz = fuse(Ollama("qwen2.5-coder:7b"))     # or Claude, GPT, Gemini, anything
g = rz.ask("clamp x into 0..255", "return x<0 ? 0 : (x>255 ? 255 : x);")
```

Inside the engine's authoring reach (one-var int32, 64-bit lanes), a wrong
model answer gets an **engine-authored** replacement — that is FIX, and it
fired 7 times in one 27-function build.

Outside that reach, **the model is the author and the counterexample is
the teacher**:

```
ask -> decide -> WRONG at (a*, b*) -> feed the pair back -> ask again -> decide
```

Nothing ships until the decider signs. Measured: asked loosely for a floor
average, a 7B wrote `(a+b)/2` — wrong on overflow, exact pair returned.
Asked with **sharp intent** — operators constrained, the overflow condition
named — the same 7B located `(a & b) + ((a ^ b) >> 1)` in one step, and Z3
signed it over every pair that exists. The sharpness of the supply decides
whether the reasoner lands in one step or a thousand.

## Recipe 5 — a whole library, end to end

27 primitives were built this way in 641 seconds on one laptop: supplier
wrote ~450 tokens of *specs* (a name, a line of English, a reference each),
a free local 7B wrote candidates, the engine repaired 7 of them, two
deciders signed everything, 4 were refused, and **nothing unverified
shipped**. A frontier model writing the same library by hand spent 2.7x
the tokens and shipped a bug the sweep caught in its own output
(README → "What it saves").

---

## The fence, stated once

- **Supply the reference, never the implementation.** If you supply the
  implementation you have answered your own question.
- **The word never upgrades.** TESTED does not become PROVEN because the
  suite is large; EXACT-ON-EXAMPLES does not become TESTED because the
  examples are many. Every verdict says which word it earned.
- **REFUSE is a safe outcome.** It means nothing verified exists at the
  current supply — the fix is sharper intent or more material, and the
  abstention names which.
- **No decider, no claim.** For correctness you cannot define, this tool
  is honest about being the wrong one — and so is every other.
