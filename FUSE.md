# Fusing this to any model

One call. The model you already have goes in; a model that cannot ship a
wrong `int32` function comes out.

```python
from proven_reason.models import Ollama, fuse

rz = fuse(Ollama("qwen2.5-coder:7b"))

g = rz.ask("round x down to a multiple of 16", "return x & ~15;")
g.outcome     # 'PASS'
g.code        # 'return (x & ~0xF);'
```

That is a 7-billion-parameter model on a laptop, and the answer was checked
against all 4,294,967,296 `int32` inputs before it was allowed out. 16
seconds, no API key, no network.

---

## The four adapters

Every adapter is the same shape: something that turns a prompt into C. Pick
whichever matches what you already run.

```python
from proven_reason.models import Ollama, Anthropic, OpenAICompat, Callable_

# local — free, offline, no key
Ollama("qwen2.5-coder:7b")
Ollama("llama3:8b", host="http://box:11434")

# Claude
Anthropic("claude-opus-5")                    # reads ANTHROPIC_API_KEY

# GPT
OpenAICompat("gpt-4o")                        # reads OPENAI_API_KEY

# Gemini — via its OpenAI-compatible endpoint
OpenAICompat("gemini-2.5-pro",
             base_url="https://generativelanguage.googleapis.com/v1beta/openai")

# anything else OpenAI-shaped: vLLM, TGI, Groq, Together, OpenRouter, LM Studio
OpenAICompat("mixtral", base_url="http://vllm:8000")

Callable_(my_function)                        # ANYTHING. see below.
```

**The same gate goes around all of them.** Claude, GPT, Gemini, a 7B on your
laptop — the model is an argument, not an assumption. Nothing above knows or
cares which one it wrapped:

```python
for label, m in (("local", Ollama("qwen2.5-coder:7b")),
                 ("claude", Anthropic("claude-opus-5")),
                 ("gpt", OpenAICompat("gpt-4o")),
                 ("gemini", OpenAICompat("gemini-2.5-pro",
                                         base_url=GEMINI_OPENAI_URL))):
    g = fuse(m).ask(ticket, reference)
    print(label, g.outcome)       # PASS / FIX / REFUSE, judged identically
```

That is also how you compare them honestly: same tickets, same reference,
same sweep over all 4,294,967,296 inputs, and a verdict that owes nothing to
anyone's self-report.

### `Callable_` is the escape hatch, and it is the important one

If your model is not any of the above — an internal endpoint, a queue, a
fine-tune behind three layers of company middleware, a coworker in a chat
window — you do not need an adapter. You need a function from `str` to
`str`.

```python
def my_model(prompt: str) -> str:
    return whatever_you_already_have(prompt)      # returns C source

rz = fuse(Callable_(my_model))
```

That is the whole integration surface. **There is nothing this cannot bolt
onto**, because "takes text, returns text" is the only assumption made.

---

## The two methods

```python
g = rz.ask(ticket, reference)        # model writes it, then it is judged
g = rz.verify(candidate, reference)  # you already have code; just judge it
```

Both return the same thing:

| field | meaning |
|---|---|
| `g.outcome` | `'PASS'` \| `'FIX'` \| `'REFUSE'` |
| `g.code` | what is safe to ship, or `None` |
| `g.verdict` | what the decider actually found |

**There is no fourth outcome.** `PASS` means the sweep agreed on every
input. `FIX` means the model was wrong and a **proven** rule shipped in its
place. `REFUSE` means nothing safe was available and you are being told so
rather than handed a guess.

`reference` is the one thing you must supply, and it is not optional
theatre: it is your definition of correct. Nothing can check code against
an intention that was never written down.

---

## Why bother, when the model is already good

Measured, this session and before:

| | raw | after fusing |
|---|---|---|
| 4 local models, 12 tasks | **31 wrong** | **0 shipped wrong** (17 FIX, 14 REFUSE) |
| Fable 5, 20 sealed tasks | 8 proven, **5 wrong** | — |
| the engine, same 20 | 13 proven, **0 wrong** | — |

The point is not that the small model became clever. It did not. The point
is that **wrong answers stopped reaching your codebase**, and the ones that
were salvageable got replaced by rules that had been proven over the entire
input domain rather than spot-checked.

A free 7B behind this gate ships less broken code than a frontier model
without one. That is the entire pitch, and it is measured, not argued.

---

## Deriving a rule instead of asking for one

When you have examples and no idea what the rule is, skip the model:

```python
from proven_reason import reason

r = reason([(0, 0), (1, 2), (2, 4), (-3, -6)])
r.expr        # (x << 1)
```

This is the part a model cannot do for you. A model recalls what has been
written down. `reason()` **derives what has not** — and when it cannot, it
abstains and names what was missing, which is the one thing a confident
wrong answer never does.

Three knobs, and they are all **material**, never depth:

```python
reason(pairs, reference="return x*10;")                    # derive + prove
reason(pairs, consts=(-1640531535,))                       # give it a constant
reason(pairs, promote=("SMEAR", "DEC"))                    # give it an operator
```

`consts` matters more often than it looks: the catalog cannot hold every
constant a target needs, and constants are material like anything else.
Note the **int32 form** — Knuth's hash multiplier `2654435761` is past
`INT_MAX` and must be given as `-1640531535`.

`promote` is the difference between a value and a function. A declared
instruction used as a *leaf* contributes its value, and can only ever be the
whole answer or a direct operand. **Promoted**, it contributes its
*function*, so the search can apply it to something it just computed.
Measured on `clp2`, whose answer is a catalog instruction applied to
`(x - 1)`:

```
leaves only, deeper search : max_nodes exhausted, ~10 GB, abstained
same material, promoted    : PROVEN, 29,636 evaluations
```

Same catalog, same depth, same node cap. Only the material grew. You will
rarely need to set this by hand — `widen=True` is the default and escalates
material automatically — but when you know the shape of your target, saying
so is faster than letting it search.

---

## What this is not

It is **not a prover**. Z3 is a prover, CBMC is a prover, and on a straight
equivalence check Z3 is roughly a hundred times faster than the sweep here.
That is fine, and it is not a competition: proving is commodity, and the
decider slot is deliberately swappable. Point it at Z3 if you like — the
verdict gets cheaper and nothing else changes.

What is *not* commodity is deriving a rule nobody wrote down, from examples,
with an abstention you can trust when it fails.

**Scope, stated plainly:** `int32 -> int32` pure functions, plus a 64-bit
layer built on proven 32-bit lanes. It will not review your web app. Within
that domain the guarantee is total — every input, not a sample — and outside
it the honest answer is that this is the wrong tool.

---

## Attach it to anything with one shell command

The whole API is a subprocess. No SDK, no key, no library — which means
Claude, GPT, Gemini and a 7B on your laptop all drive it identically.

```bash
proven-reason ask "round x up to a multiple of 32" \
              --reference "return (x+31) & ~31;" \
              --model qwen2.5-coder:7b
```

```
PASS
  the model's own code, swept clean over all 4,294,967,296 inputs
  ships: return (x + 31) & ~31;
```

Three outcomes, and deliberately no fourth: **PASS** (the model's own code
survived), **FIX** (it did not; the engine authored a replacement that did),
**REFUSE** (nothing survived — nothing ships, which is a safe answer, not a
failure).

### Driving it from a frontier model

An agent supplies two things per call — what it wants, and what correct
means — and gets back code that a decider has already checked, or a refusal:

```python
import subprocess, json

def proven(english: str, reference: str) -> str | None:
    """Ask for code. Get back something proven, or None. Never a guess."""
    r = subprocess.run(
        ["proven-reason", "ask", english, "--reference", reference],
        capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None
```

**The caller supplies the reference, never the implementation.** A reference
is a definition of correct — write it the clearest way you can, not the
fastest. If you supply an implementation you have answered your own question
and this has nothing to add.

### Why route through it at all

Because the expensive tokens are the *derivation*, and they are the ones that
get displaced. Measured on 27 primitives against a frontier model writing
the same library by hand: **2.7x fewer supplier tokens, and one fewer
shipped bug** — see the head-to-head in [README.md](README.md).
