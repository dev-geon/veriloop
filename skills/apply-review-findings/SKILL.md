---
name: apply-review-findings
description: >
  Apply the findings of a code review to the working tree: fix every Failed finding,
  Warnings only when safe or requested, and verify each fix resolves the finding's
  evidence — resolved findings are reported as Pass.
  Use this skill whenever a review report exists (from the veriloop skill or
  any structured review) and the user asks to act on it — "apply the review findings",
  "fix what the review found", "리뷰 지적사항 반영해줘", "리뷰에서 나온 문제 고쳐줘" —
  and as the fix step inside the run-review-loop skill.
---

# Apply Review Findings

Turn a review report into the smallest set of edits that makes the next review pass.
You are the repair crew, not a second reviewer and not a refactoring engine: fix what
the review found, verify each fix against the finding's own evidence, and change
nothing else.

## Invocation mode

Inside `run-review-loop`, consume only its issued repair packet and obey its role
boundaries. Return one JSON object matching `../../schemas/worker-result.schema.json`,
with a check for each exact Failed title; do not write REVIEW.md, ledger or run records.
Do not inspect passed gate probes or expand a minimal gate failure packet. The table
and report updates in Step 5 apply only to standalone invocations.

When the packet names an invariant oracle, reproduce each Failed finding as an oracle
divergence (seed plus minimized input) before editing. If the oracle cannot reproduce
it, extend the oracle first and include that extension in the finding's check. In any
mode, never write review history (finding identifiers, run numbers, "after review")
into code comments; state the requirement the code meets.

## Step 1 — Load the findings

Locate the review report (the user points at it, it is the output of a review that
just ran in this conversation, or — by convention — the `REVIEW.md` file beside the
work's `IA.md`). Prefer the machine-readable JSON block at the end of an
`veriloop` report; fall back to parsing the prose findings. For each finding
capture: severity, title, file/line, the evidence (the caller that breaks, the query
that fans out), the suggested fix, and the structured `repair_plan` when present. A
legacy report without a repair plan may be used only after the fixer derives the
missing plan from the specification and code before editing; new Veriloop review
results must contain one.

If there is no review report at all, say so and stop — running a review first is the
`veriloop` skill's job, not this one's.

## Step 2 — Decide what to fix

- **Failed**: always resolve; prioritize the highest-risk causal group first.
- **Warning**: fix only when the user asked for it, or when the fix is a strict
  deletion (dead code, narration comments) that cannot change behavior. Everything
  else stays untouched. This is a convergence rule, not laziness: a loop that chases
  warnings produces new diffs for the next review to comment on and never terminates.
  Remaining warnings stay in the report for a human to accept or batch later.
- **Warnings-only cleanup mode**: when explicitly invoked for it (e.g., the
  run-review-loop warning-debt disposition), fix ONLY warnings — skip any warning the
  ledger marks `accepted`, and still take the minimal-diff path.
- If the repo has `.agent-review/ledger.json`, skip findings marked `accepted` and
  keep finding titles identical to the ledger's so statuses reconcile.
- **Needs-verification findings**: verify first (trace the caller, find the partition
  key). If the finding turns out to be false, record it as `skipped — not reproducible`
  with your evidence instead of "fixing" a non-problem.
- **Risk-focus findings**: when the spec or the review names a Risk focus area, a fix
  touching it gets the strongest verification available — run the covering tests, not
  only the finding's own evidence.

## Step 3 — Repair the causal group

Group findings that violate the same invariant. Trace directly affected callers and
state transitions, including normal behavior that must be preserved. Keep unrelated
refactoring out of scope. Minimal edits mean a coherent root-cause repair, not an
isolated patch for each symptom. For each causal group:

1. Read the full file (not just the cited line) and the finding's evidence.
2. When practical, reproduce failure with a regression check before editing. Read the
   repair plan as an implementation design: verify its invariant and root cause
   against the specification and current code, then follow its affected paths and
   implementation steps. Repair the cause and verify every stated verification case
   plus adjacent affected normal paths. Make the smallest coherent edit that resolves
   the evidence. Prefer the review's `repair_plan` and `fix_hint`; deviate only when
   the plan is disproved by the code or specification, and say so in the worker
   result.
3. Follow the repository's conventions — the review's convention findings tell you the
   local dialect (Result vs exceptions, repository layering, naming). A fix written in
   the wrong dialect just becomes next round's finding.
4. Do not refactor beyond the finding. Every extra changed line is new review surface;
   scope creep is the main reason review-fix loops fail to converge. If you notice an
   unrelated problem, note it in your output — don't touch it.

## Step 4 — Verify each fix against its own evidence

A fix is done when the finding's failure scenario no longer exists, checked concretely:

- Stale caller → the caller now resolves (grep the old name: zero hits outside history).
- Serialized-field break → the wire/storage name is restored or migrated end to end.
- Cross-partition/unbounded query → the query now pins the partition key / has bounds;
  quote the new query text.
- Convention violation → the code now matches the cited precedent.

Run the build and the tests covering the changed files if the repo supports it
cheaply, and report the actual result — "compiles, 14/14 tests pass" or "no build
infrastructure available, verified by grep".

## Step 5 — Report

In loop mode, return the worker JSON contract described above instead of this section.

Output a status table that reuses the review's exact finding titles (the next review
pass and the loop controller correlate by title). A finding whose fix is applied and
verified is reported as **Pass**:

```
| # | Severity | Finding (title from review) | Status | Evidence of resolution |
|---|----------|------------------------------|--------|------------------------|
| 1 | Failed   | ...                          | Pass   | ...                    |
| 2 | Warning  | ...                          | skipped — <reason> | ...        |
```

Then list files changed, and anything you deliberately did not touch (nits, unrelated
observations). Write in the language the user is conversing in; any text you add to a
persisted `REVIEW.md` is written in Korean.

When the findings came from a persisted `REVIEW.md`, update that file's finding
statuses to match this table so the persisted report reflects the repaired state. A
loop report (one that contains a `json veriloop-report` block) is the loop
controller's record: do not edit it; update `REVIEW-standalone.md` when that is where
the findings came from, and otherwise report the table in the conversation only.
