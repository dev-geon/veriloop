# Invariant Oracle Reference

An invariant oracle is an executable check that decides an invariant for generated or
exhaustively enumerated inputs by comparing the implementation with a reference that is
correct by construction: a simpler model, the unoptimized or full-scope path, the
original implementation, or a metamorphic relation between two runs. Hand-written
expected values do not qualify.

Specify one when the work must hold an invariant over a space too large to enumerate by
hand (a cache or index that must answer exactly like its source, an optimized path that
must equal the plain one, a port that must preserve another system's semantics), or when
`run-review-loop` escalates an invariant that kept failing.

The specification states:

- the reference, and why it is trustworthy for this invariant;
- the input generator: seeded and reproducible, covering at least every dimension along
  which earlier failures varied, and minimizing a failing input before reporting it;
- the comparison: what is normalized, and that silent wrong answers and unexpected
  failures both count as divergences unless the specification explicitly allows one;
- the budget: seeds or time for in-loop runs and for an extended run;
- strength: every earlier failure of the invariant becomes an executable case in the
  target, a test-only switch that disables its repair plus the seed or minimized input
  that exposed it, named by the behavior it protects and never by a finding identifier.
  With a switch on, the oracle must fail for that case. The oracle is not accepted until
  it rediscovers all of them.

The oracle's checks are loop-phase acceptance criteria. Hand-enumerated cases remain as
fast regressions, not as the completeness argument.
