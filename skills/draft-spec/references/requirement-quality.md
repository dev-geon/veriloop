# Requirement Quality Reference

Goal: make the statements a worker, reviewer, and gate will all read mean one thing to
each of them. A spec can be grounded in the code and the user and still fail here: two
sections can contradict each other, one criterion can hide two requirements, or a word
like "quickly" can leave the threshold to whoever reads it. Each of these lets the roles
converge on different targets while every one of them follows the spec.

These rules apply to the statements the spec commits to: Scope, Target behavior,
Constraints, Acceptance criteria, and Invariant oracles. Current behavior describes the
code as it is and is judged by its `file:line` grounding, not by these rules.

The rules are adapted from the requirement characteristics in ISO/IEC/IEEE 29148. Only
the parts that change what the loop does are kept here; this file, not the standard, is
the reference every role and platform uses.

## Criterion identifiers

- Give every acceptance criterion an identifier `AC-<n>` (`AC-1`, `AC-2`, ...), in the
  order the criteria first appear.
- An identifier is permanent. A revision that removes a criterion retires its number; it
  is never reused, and the remaining criteria are not renumbered.
- The identifier names the requirement, not the history that produced it. It is not a
  review finding identifier, a run number, or a ledger key, and those never appear in the
  spec.

## One requirement per criterion

A criterion states one observable outcome, verified by its own check.

- Split a criterion that joins outcomes ("returns the total **and** logs the request")
  into one criterion per outcome. A failure must point at one requirement, so the fixer's
  repair plan stays bounded.
- A single outcome with a compound condition ("when the fleet is empty and the year is
  closed, returns zero") is still one criterion.
- Several criteria may share a test command when each passes a filter, name, or
  assertion that isolates its own outcome.

## Words that leave the threshold open

Replace each of these with a measurable bound, an enumerated set, or a named reference
behavior. When the replacement needs a value or a choice the dialogue has not settled, it
is an open decision: EXTRACT or PRESENT it, never pick one.

The spec is written in the user's language; the examples below cover English and Korean
and are not exhaustive.

| Kind | Examples | Sharpen to |
|---|---|---|
| Unmeasured quality | fast, efficient, robust, user-friendly, appropriately, sufficiently; 빠르게, 효율적으로, 적절히, 충분히, 안정적으로 | a bound with a unit and the check that measures it |
| Open-ended list | etc., and so on, including but not limited to; 등, 등등, ~ 같은 | the complete set, or the rule that decides membership |
| Escape clause | if possible, where needed, as appropriate, when feasible; 가능하면, 필요한 경우, 상황에 따라 | the condition that decides it, or a separate decision |
| Comparison without a baseline | better, improved, reduced, more accurate; 개선된, 더 나은, 줄어든 | the baseline value and the target value, or the reference to compare against |
| Superlative | best, optimal, minimal, all possible; 최적의, 최소한의, 모든 가능한 | a bound, or the reference behavior it must equal |
| Unclear referent | it, this, that, the data, the value; 이것, 그것, 해당, 이 값 | the symbol, field, or entity named explicitly |
| Requirement stated only as a prohibition | must not be slow, must not break; 느리지 않아야, 깨지지 않아야 | the positive property and its check (a scope bound that names what must not change is fine) |

## Contradictions across the spec

Read the committed sections against each other. Each of these is a contradiction:

- Scope excludes something that Target behavior or a criterion requires.
- Target behavior changes something that Constraints says must not change.
- Two criteria cannot both pass on the same revision.
- One term is used with two meanings, or two terms name the same thing.
- A criterion's check exercises behavior that is out of scope.
- Risk focus names an area the scope excludes.

A contradiction is resolved by asking the user which statement holds, never by quietly
editing the one that looks wrong.

## Non-functional lens

During decision-surface enumeration, check whether the work commits to any of these.
Enumerate them only where the work touches them:

- **Performance and cost**: latency or throughput bounds, query or round-trip counts,
  paging limits, request units, billed calls that grow with data or traffic.
- **Security and permissions**: who may call or see what, secrets handling, input that
  crosses a trust boundary.
- **Reliability**: behavior under partial failure, retries and idempotency, timeouts,
  data integrity across a failed write.

A committed property becomes a decision and then a loop-phase criterion with a check (or
a `post_deploy` criterion when only the real environment can measure it). A spec does not
get a non-functional section for work that commits to none; an uncommitted property is
judged by the review lenses, not by the spec.
