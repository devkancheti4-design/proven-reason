# proven-reason for students

Free, offline, no API key. You need Python 3.10+ and a C compiler
(`xcode-select --install` on macOS, `sudo apt install gcc` on Linux, WSL on
Windows). Every transcript below is from a real run — reproduce any of them.

```bash
git clone https://github.com/devkancheti4-design/proven-reason
cd proven-reason && pip install -e .
```

The one idea: **your answer is checked on every input that exists** — all
4,294,967,296 of them — not the three cases you thought to test. When you're
wrong, it tells you the exact first input that breaks you. When nothing
provable exists, it says so instead of guessing.

---

## Exercise 1 — the lie every textbook tells you

"Shift right is division by two." Check it:

```bash
proven-reason verify "return x >> 1;" --reference "return x / 2;"
```

```
FIX
  rejected (wrong on 1,073,741,824 inputs, first at x=-2147483647);
  engine authored a replacement in 540,642 evaluations and the sweep proved it
  ships: return ((x - (x >> 31)) >> 1);
```

Wrong on **a billion inputs** — every odd negative, because `>>` rounds
toward −∞ and `/` rounds toward zero. The repair it authors is the
branchless idiom professionals use. *Question to answer in your write-up:
why does adding `x >> 31` fix the rounding?*

## Exercise 2 — the modulo trap

"Is x odd?" Most students write `x % 2`. So do most language models:

```bash
proven-reason ask "one if x is odd, else zero" --reference "return x & 1;"
```

```
FIX
  rejected (wrong on 1,073,741,824 inputs, first at x=-2147483647);
  engine authored a replacement in 89 evaluations and the sweep proved it
  ships: return (x & 1);
```

In C, `-7 % 2` is `-1`, not `1`. The fused model made the same mistake you
would — and the gate caught it, because the gate tests `INT_MIN` and you
don't.

## Exercise 3 — the clamp that passes your unit tests

```bash
proven-reason verify "return x & 255;" \
    --reference "return x < 0 ? 0 : (x > 255 ? 255 : x);"
```

```
FIX
  rejected (wrong on 4,278,189,825 inputs, first at x=-2147483647);
  PROVEN shelf rule SATU8 ships instead
```

`x & 255` *wraps* where a clamp *saturates*. It is right on 16,777,471
inputs — including every one you'd think to test — and wrong on the other
4.2 billion. This is the class of bug that survives code review.

## Exercise 4 — 64-bit, and what "proven" may honestly mean

A classic student overflow "guard":

```bash
proven-reason verify64 "if (a > 0 && b > 0 && a + b < 0) return 0; return a + b;" \
    --reference "return (long long)((unsigned long long)a + (unsigned long long)b);"
```

```
FIX
  rejected (WRONG on 499,078 pairs); the add lane composition ships instead
  — four PROVEN 16-bit lanes, composition TESTED on 4,000,169 pairs
```

Note the words: at 32 bits the verdict is **PROVEN** (every input ran). At
64 bits nobody can run 2¹²⁸ inputs, so the strongest honest word is
**TESTED**, built on 16-bit lanes that ARE proven. *Learning to keep those
words apart is the entire discipline of verification.*

## Exercise 5 — beat the engine

Generate sealed secret functions and compete — same pairs to you and the
engine, the compiler grades you both:

```bash
cd benchmarks/sealed-duel
python3 duel_gen.py        # prints pairs; secrets go to a file you don't read
# write your guesses, then grade yourself with duel_grade.py
```

A frontier language model played this exact game against the engine:
**engine 13 proven, 0 wrong; frontier model 8 proven, 5 wrong.** Every one
of the model's five failures broke first at a boundary input. See if you
can do better — the engine will not mind losing to you, and the compiler
will not let either of you lie about it.

---

## The launch test, so you know it handles homework

Seven classic questions through a fused free 7B model, plus two 64-bit —
one command each, every verdict from an exhaustive sweep:

```
absolute value of x                            PASS
one if x is a power of two, else zero          PASS
round x down to a multiple of 8                PASS
the sign of x: -1, 0, or 1                     PASS
x modulo 8, exactly as C computes it           PASS
isolate the lowest set bit of x                PASS
divide x by 4, rounding toward zero            PASS
64-bit add (direct)                            PASS
64-bit add ("guarded" — the classic mistake)   FIX

shipped safe: 9/9 — wrong shipped: 0, by construction
```

When the model is right, its own code ships untouched. When it's wrong,
you get a proven repair or an honest refusal. **You never get a wrong
answer dressed as a right one — which is the one thing neither your
textbook's answer key nor any language model can promise you.**

## What it will not do

It answers questions whose answer is a function of one 32-bit integer
(plus the 64-bit lane path). It will not write your essay, your Python
homework, or anything it cannot prove. Its silence is a real answer:
REFUSE means "nothing provable fits" — argue with the compiler, not with
the tool.
