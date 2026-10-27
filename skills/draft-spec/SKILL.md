---
name: draft-spec
description: >
  Use this skill to produce the written specification for a concrete piece of upcoming
  development work when none exists yet. The spec gates in the veriloop and
  run-review-loop skills route here whenever
  they find no referenced spec; and users can invoke it directly in any language:
  "write a spec for this first",
  "draft the spec before we start", "명세서 작성해줘", "명세부터 만들자", "이 작업
  명세로 정리해줘". It analyzes the target codebase first — house rules, conventions,
  workflow, and the code the goal touches — then interprets the user's goal against
  that reality and drafts a spec with executable acceptance criteria for the user to
  correct and confirm. Do NOT use for full project documentation suites (project
  plans, ERDs, API reference manuals) or for reviewing an existing spec — only for
  producing the missing specification of one concrete piece of work.
---

# Draft Spec

A specification written from a generic template is fiction; a specification written
from the code is a contract. The review and loop skills in this plugin refuse to
work spec-less, and the fastest honest way to produce the missing spec is to read the
codebase first and interpret the user's goal against what is actually there — not to
hand the user a blank form.

The deliverable is a spec document **the user has confirmed**. Until the user corrects
and accepts the draft, there is no spec — do not let the caller (the review, the loop,
or the user) proceed on an unconfirmed draft.

## Step 1 — Analyze the codebase before interpreting the goal

The spec must describe work that fits *this* repository, so establish the repository's
reality first. Existing code is a reality check and a HOW reference — never the
authority for what the work *should* do; that authority is built in Step 2 with the
user.

- **House rules**: read `CLAUDE.md` / `AGENTS.md` / `CONTRIBUTING.md` if present, and
  linter/formatter/analyzer configs — these are written constraints the spec must not
  contradict.
- **Conventions**: open siblings of the code the goal touches (same directory or same
  layer) and note the established patterns — naming, layering, error handling, DI,
  how queries are built, where tests live. This is the same baseline method as the
  review skill's Step 2 (`skills/veriloop/references/conventions.md`); if
  `.agent-review/baseline.md` exists, start from it and spot-check.
- **Workflow**: how changes land here — branch and PR conventions from recent history
  (`git log`), CI configuration, the commands that build and test this project. The
  spec's acceptance checks must be commands that actually run in this repo.
- **Target code**: read, in full, the files the goal names or implies. Record current
  behavior, callers and consumers, and the data contracts (stored fields, API shapes)
  that must not break. These become the spec's "current behavior" and "constraints"
  sections — grounded in `file:line`, not in memory.

## Step 2 — Analyze the user's goal against that reality

Everything you were given — the goal statement, notes, tickets, a review report — is
**material, not ground truth**. Its content flows into the spec, but its authority
does not: a decision enters the spec only when it is grounded in the user — they said
it, it follows from the model you have built of their goal and constraints, or they
chose from options you presented. The existence of a document is not evidence it
settled anything.

- Restate the goal in terms of the actual files, symbols, and behaviors found in
  Step 1 — a goal that talks about real code is already half a spec.
- **Enumerate the decision surface** — the load-bearing decisions this work is
  obligated to answer. Walk five lenses over each entity the work touches and each
  colliding pair: **structural** (cardinality, composition, identity), **behavioral**
  (lifecycle, concurrency, failure policy, edge cases), **technical** (persistence,
  interfaces, consistency), **contract** (status/enum sets, uniqueness, output
  shapes), **non-functional** (performance and cost bounds, permissions, reliability
  under failure — only where the work touches them; see
  `references/requirement-quality.md`). Enumerate exhaustively; you will ask minimally.
- Resolve each enumerated decision by where the knowledge lives — never by silent
  default:
  - the code answers it → look it up (Step 1), don't ask;
  - the user's own words, or your grounded model of their intent, answers it →
    realize it, don't ask;
  - **domain or preference knowledge only the user holds → EXTRACT**: draw it out
    with questions; never invent it;
  - **a technical shape the user hasn't settled → PRESENT**: options with trade-offs
    and a recommendation, and the user decides — never decide silently.

  There is no "pick a reasonable default and move on" for a load-bearing decision —
  that is a stranger's guess, and it is exactly what detonates later as rework.
- Ask in batched rounds: at most four questions at a time, leading with your
  recommendation.

### Bring in the design partner while decisions are still open

Do not wait until the draft is written to look for omissions. After the decision
surface is enumerated and before the contract is drafted, dispatch a fresh `designer`
subagent resolved from the `design_review_gate` model group. Give it only the grounded
repository facts, the user's goal, the decision surface with each decision's current
disposition, and explicit constraints. Do not give it a previous draft, review report,
ledger, worker result, or gate material.

The design partner is an active thinking partner, not a prose generator or an approval
authority. Because it has the `design_review_gate` model, it must use the repository
facts it inspected to produce a **verifiable implementation design**, not only a list
of questions. Its response must:

1. state the current code and contract boundary it relied on, with `file:line` evidence;
2. propose improvements and alternatives for load-bearing decisions, including the
   problem, recommendation, trade-offs, and a concrete acceptance sentence;
3. provide an implementation design for the proposed target behavior: affected
   symbols and data/API boundaries, state or validation rules, ordered implementation
   seams, verification cases, and explicit non-goals;
4. identify questions that require the user's domain or product judgment, each with a
   recommended choice and the consequence of each option.

Relay every proposal and question to the user. The controller must not silently adopt a
design partner suggestion; the user confirms every product decision, and the designer
never edits target files. Use the user's answers to close decisions, and continue the
interview rounds until the decision surface is closed; if a decision remains
unresolved, stop and ask the user instead of writing a guessed contract. Dispatch a new
fresh design partner only when an answer changed the scope or the state model enough to
invalidate the implementation design; missing decisions and contradictions are the
guess-hunt's job (Step 4). Once confirmed, carry the accepted implementation design into
`IA.md` as target behavior, constraints, acceptance criteria, and risk focus.

## Step 3 — Draft the spec

Draft only after Step 2's load-bearing decisions are closed. A spec written around
open questions either bakes in guesses or ships placeholder sections — both put the
question round after the document, which is backwards. If the user needs to see
structure before answering, show them the decision table from Step 2, not a half-spec.

Use this structure:

```
# <작업 제목>

## 목적과 배경      ← Purpose & background: why this work exists, in one paragraph
## 범위             ← Scope: in / out, explicitly
## 현재 동작        ← Current behavior: what the code does today, file:line grounded
## 목표 동작        ← Target behavior: what it must do when this work is done
## 제약             ← Constraints: repo conventions and workflow that apply; what must NOT change
## 수용 기준        ← Acceptance criteria: each an AC-<n> ID, one outcome, an executable check, a phase
## 불변식 오라클    ← Invariant oracles: only when correctness spans a large input space (see below)
## 위험과 경계 사례 ← Risks & edge cases
## 위험 초점        ← Risk focus: the ONE area where this change fails worst
## 참고             ← References: files, tickets, related docs
```

The English names after each arrow are how this plugin's instructions refer to the
sections; the headings in `IA.md` are the Korean ones.

Acceptance criteria follow the same rule as the loop's goal contract: every criterion
is paired with the exact check that verifies it (a test command, a grep assertion, a
build, an HTTP call). A criterion with no runnable check is a taste judgment — sharpen
it or move it out.

Hold the committed statements to `references/requirement-quality.md`. Give every
criterion a permanent `AC-<n>` identifier that is never renumbered or reused. State one
observable outcome per criterion, so a failure points at one requirement. Replace words
that leave a threshold open with a bound, a complete set, or a named reference behavior;
a replacement that needs a value the dialogue has not settled is an open decision, not a
wording fix.

Give every criterion a phase: `loop` (default; verified before the change lands),
`post_deploy` (needs the deployed or real environment), or `manual` (a human
observation). Only loop-phase criteria decide whether the loop succeeds; the others are
reported as deferred until someone runs them. Phrase a criterion against measured
baseline facts (an existing warning count, already-failing tests, known flaky tests)
rather than an ideal the baseline cannot meet, and make a search-based check exclude
the specification and other documents that quote its own pattern.

**Invariant oracles.** When the work must hold an invariant over a space too large to
enumerate by hand, or when `run-review-loop` routes here because an invariant kept
failing, specify an oracle instead of more hand-written cases, with every element
`references/invariant-oracle.md` requires. The oracle's checks are loop-phase acceptance
criteria.

### Preflight every acceptance check

Before presenting the draft, run each loop-phase check once against the current
baseline, without mutating anything. A red result is fine and expected; a check that
cannot run is a defect of the draft: a missing command or test filter, a syntax error, a
multi-project invocation the tool rejects, an unreachable environment, a missing
permission or credential, or a read-only guard that trips. Record what each check
returned on the baseline. Do not execute post-deploy or destructive checks; confirm only
that their entry point exists. Raise every failure as a question before confirmation,
so that no worker discovers it halfway through a batch.

### Keep the contract separate from its history

`IA.md` holds the current contract only. Put decision records, revision history,
rejected alternatives, and the reasons behind each change in a sibling `DECISIONS.md`.
Workers and reviewers read the contract; reviewers do not read `DECISIONS.md`. Never
cite review finding identifiers, run numbers, reviewer or gate details in `IA.md` or in
product code comments; state the requirement itself, so later reviewers judge the code
rather than the history that produced it. If the contract grows beyond what one reader
can hold in a single pass (as a rule of thumb, about 60 KB), split it by component into
linked parts and give each role only the parts it needs.

**Risk focus** is one short paragraph naming where this change fails worst (which
lens, which file or contract) — `run-review-loop` aims its final-gate reviewer there and the
fixer verifies hardest there. Name one area; a risk focus that lists everything aims
nothing.

Save the draft where this repository keeps documents (an existing docs directory, or
propose a sensible path and let the user decide). Name the file `IA.md`, inside a
directory dedicated to this piece of work — the directory carries the work's identity
(repository or local guidance may pin the exact layout); the filename stays constant
so tooling and later reviews can always find the spec. Check the chosen path is actually
tracked by git — some repos gitignore their docs directories, and a spec teammates
cannot see is not a team contract; if it is ignored, say so and agree on a tracked
location with the user.

## Step 4 — Independent guess-hunt before confirmation

The drafter cannot audit their own guesses — that is self-judgment. Before presenting
the draft, dispatch **one fresh subagent** that did not author the spec (use the
`gate` role's effective model from the `design_review_gate` group in
`.agent-review/config.json` when present; session model otherwise). This guess-hunt
agent must be distinct from every design partner used during the interview. Give it the
draft, the enumerated decision surface with each decision's
disposition and grounding, `references/requirement-quality.md`, and read access to the
code. Its brief is three questions:

1. Is each decision's grounding real — did the user actually say or choose it, or
   was it rubber-stamped as "grounded" without evidence in the dialogue?
2. Walking the five lenses independently over the code the spec touches, is there a
   load-bearing decision the drafter never enumerated at all?
3. Do the committed sections contradict each other, or does a criterion join several
   outcomes or leave its threshold open, in a way that would let two readers build or
   judge different behavior? Report only what changes a decision or a check, not
   wording taste.

Every finding is relayed to the user as a question (EXTRACT or PRESENT — never
silently patched into the draft). Close the findings, re-check once; a surviving
dispute escalates to the user. This costs one subagent and protects everything
downstream: a wrong spec makes the developer, reviewer, and gate all faithfully
converge on the wrong target.

## Step 5 — Confirm and hand back

Present the draft and ask the user to correct and confirm it. Apply their corrections.
Only a confirmed spec counts.

A later change to a confirmed spec, including an oracle delta requested by
`run-review-loop`, follows the same path in small form: read the code it touches,
close its decisions with the user, rerun the preflight for the criteria it adds or
changes, and get confirmation. Edit the contract in place, add a version line at the
top of `IA.md`, and append the rationale to `DECISIONS.md`.

Then state the confirmed spec's path plainly, so the caller can use it.

Write `IA.md` and `DECISIONS.md` in Korean whatever language the conversation uses, and
converse in the user's language. Keep code, identifiers, file paths, commands, `AC-<n>`
identifiers, and quoted output as they are.
