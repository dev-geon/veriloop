# Exit Documents Reference

Read this before writing the documents a run leaves beside its confirmed specification
(`IA.md`). `IA.md` is the contract, `REVIEW.md` is the audit, and `PRD.md` is the
description of what now exists.

Write both documents in Korean whatever language the conversation uses. Keep code,
identifiers, file paths, commands, `AC-<n>` identifiers, quoted output, the verdict and
severity tokens (`Pass`, `Fail`, `Failed`, `Warning`), and the JSON block as they are.

## REVIEW.md

Persist the final report as `REVIEW.md` in the same directory as `IA.md` on every exit,
so the outcome lives beside the spec it verified. Keep it readable across runs:

- Start with a current-state section: the latest run, exit reason, gate status and
  snapshot, loop-phase acceptance status, and every open item (deferred criteria,
  warnings with their disposition, unresolved discrepancies). This is the only part a
  later run rewrites.
- Follow it with one section per run, newest last, each describing only what that run
  changed and found. Never rewrite an earlier run's section; correct it with a dated note.
- End with exactly one fenced block whose info string is `json veriloop-report` and
  that conforms to `schemas/review-report.schema.json`. Use the dispositions
  `accept`, `issue`, and `cleanup`, and name runs `<work id>/run-NNN` so that runs of
  different work sharing one archive are never confused.
- `.agent-review/` is usually untracked, so cite each archived `run.json` by path and
  SHA-256 in that block instead of relying on links other readers cannot open.

When a deferred criterion is executed later, update the current-state section, the
summary block, and the product document's verification chapter without reopening the
loop, unless it fails; a failure starts a new repair run.

## PRD.md

Write the product document only on a `goal_met` exit; on any other exit, say in the
report that none was written and why. Overwrite it when the same work runs again.

`PRD.md` is written for someone who was not in the room, and who needs to understand the
delivered product before they can judge a verification table. A checklist of acceptance
criteria is not a product document. Use a `#` title, then exactly these ten `##`
chapters with these exact headings, in this order. `scripts/check_prd.py` rejects a
missing, renamed, reordered, or extra `##` chapter; use `###` and below inside a chapter.

| `##` heading | What the chapter answers |
|---|---|
| `무엇인가` | The thing in one paragraph, in the reader's terms, not the implementation's. |
| `누가 쓰는가` | The roles, and what each one comes to do with it. |
| `어떤 문제를 푸는가` | The situation before, and what changed. |
| `무엇을 하는가` | The feature set, grouped the way a user would group it, complete enough that nothing shipped is missing. |
| `어떻게 쓰는가` | The main flow end to end, plus the secondary flows that matter. |
| `어떻게 동작하는가` | The model, algorithm, or data flow a reader must hold to trust the numbers or the behaviour, with its assumptions and where they are approximations. |
| `비기능 요구` | Determinism, honesty about missing data, accessibility, performance, permissions, language — whatever the work actually commits to. |
| `검증` | Every acceptance criterion from `IA.md` by its identifier, each on a line with `Pass`, `Fail`, or `Deferred` and the evidence that settled it, plus the commands or runs that produced that evidence. This is **one chapter, not the document**. |
| `남은 일` | Accepted warnings, deferred items, known defects and inconsistencies with their disposition, and follow-up work with its owner or ticket. Record a discrepancy you could not resolve as a discrepancy; do not quietly drop it. |
| `이 문서의 한계` | What it did not cover and what its claims rest on. |

Scale the chapters to the work: a single bug fix earns a short paragraph per chapter and
a full verification table; a program-sized deliverable earns the whole document. Never
drop a chapter to save space — write `해당 없음` followed by the reason.

For a follow-up repair, update the existing product document in place and preserve
unchanged grounded sections; do not rewrite the whole feature description. Reference
shared verification evidence rather than copying full logs into both reports.

Ground every factual claim in the code with a `file:line`, and mark inference as
inference (`추정`). Keep the findings themselves in `REVIEW.md` and reference that file
rather than restating them.

## Programs of many pieces

When a program spans many pieces of work, the same pair scales: a program-level `IA.md`
and `PRD.md` sit in the parent directory and describe the whole, while each piece keeps
its own pair in its own directory. The program-level `PRD.md` is the one a stakeholder
reads first.
