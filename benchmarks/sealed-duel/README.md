# The sealed duel — the shipped engine versus a frontier model

Twenty secret functions, sampled from the engine's own grammar by a fixed
seed (20260811) — compositions with no name and no idiom, so neither side
gets a linguistic handle. Both sides received the **same 20 input/output
pairs** per task and nothing else. The frontier model (Claude Fable 5) wrote
its answers from the pairs alone, frozen in `answers_fable5.json` **before**
any grading ran, with `secrets.json` unread. The grader swept both columns
against the secret over **all 4,294,967,296 int32 inputs** per task.

## Result

|                            | PROVEN | WRONG | ABSTAIN | NOT-GRADED |
|----------------------------|-------:|------:|--------:|-----------:|
| Fable 5 (ships everything) |      8 |     5 |       — |          7 |
| the engine (this package)  |     13 |     0 |       7 |          — |

On the **13 tasks the machine fully graded**: the engine went 13-for-13,
proven on every input, zero wrong. The frontier model shipped **5 wrong
answers** — every first failing input at a boundary (`INT_MIN`,
`INT_MIN+1`, …), every one indistinguishable *to the model* from its
correct answers. Head-to-head: engine 5 wins, 8 ties, 0 losses.

The 7 remaining secrets were too deep for the engine's authored rung bound
(≤ 3) inside a 4 GB memory envelope: it **abstained and shipped nothing**,
which is its discipline working. The frontier model's answers for those 7
were never swept and are recorded as **unknown, not victories** — nobody
gets credit for an unverified answer here.

## Why this is fair

- identical information: both sides saw exactly the same pairs
- no names: the secrets are grammar samples, so training-set idioms and
  linguistic priors are useless to both sides
- frozen first: the model's answers were committed before grading
- one judge: a C compiler, `-fwrapv -fno-lto`, `noinline`, volatile sink,
  SUSPECTED-FOLD discipline, every input run — for both columns

## Reproduce

```bash
python3 duel_gen.py          # regenerates secrets + pairs from the seed
python3 duel_grade.py        # regrades both columns (hours of sweeps)
```

## What running this benchmark found

Adversarial use of the package surfaced two real defects, both fixed in
v0.3.0 and both worth knowing about in any harness like this:

1. `check()` had **no timeout** — a candidate with a non-terminating loop
   hung the caller forever (measured: 57 minutes before intervention).
   Now: `NON-TERMINATING`, never a proof, never a pass.
2. `synthesize()` had **no memory bound** — a collision-free level can
   outgrow RAM *while being built* and the OS kills the process before any
   between-levels check can act (measured: six searches OOM-killed).
   Now: `max_nodes`, and crossing it is a reported abstention.
