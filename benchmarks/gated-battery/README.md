# The gated battery — four local models + the reasoner, versus two frontier models

Twelve `int32 -> int32` tasks with realistic traps (overflow at `INT_MAX`,
sign-smear in byte swaps, `INT_MIN` boundaries), plus four 64-bit tasks.
Both frontier models' answers were literals frozen before grading. The four
local models ran raw through ollama. Grader: exhaustive compiled sweep, all
4,294,967,296 inputs per verdict (`result.json` holds every row).

## Category A — int32, gate fully active

|                      | raw ok | raw BAD | shipped ok | refused | shipped WRONG |
|----------------------|-------:|--------:|-----------:|--------:|--------------:|
| Claude Fable 5 (raw) |     12 |       0 |         12 |       — |             0 |
| Claude Opus 5 (raw)  |     12 |       0 |         12 |       — |             0 |
| qwen2.5-coder:7b + reasoner |  7 |  5 |          9 |       3 |         **0** |
| deepseek-coder:6.7b + reasoner | 5 | 7 |          8 |       4 |         **0** |
| llama3:8b + reasoner |      2 |      10 |          8 |       4 |         **0** |
| mistral + reasoner   |      3 |       9 |          9 |       3 |         **0** |

The four local models produced **31 wrong answers**; the reasoner repaired
17 into proven code, refused 14, and **shipped zero**. Both frontier models
were perfect raw on this battery — and the only reason that is *known* is
that this package's sweep graded them.

## Category B — 64-bit: every wrong local answer (10) repaired by the
proven-lane composition; all columns shipped 4/4 clean.

## The judge, graded live

On every authored repair, the judge (`G_* / COMBINE` decisions) predicted
HOLD or NO-HOLD before the sweep ran, and the compiler graded the
prediction: **13 of 13 HOLD calls held — zero dangerous errors — four timid
ones.** Advisory only; the sweep always decides.

## Honest limits

Two-operand and array tasks: the gate is inert (nothing fits 32 bits of
input), and the local models' wrong answers there shipped unprotected.
Open-prose tasks: recorded, not scored — no grader exists, and a score
would be the only dishonest number in the file.
