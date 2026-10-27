---
name: run-review-loop
description: Run a bounded, specification-grounded develop-review-fix loop on a repository until executable acceptance checks pass and independent code review has no failed findings. Use when the user asks to implement or repair work in a review loop, iterate until clean, run the Veriloop workflow, or invokes $run-review-loop. Requires an explicit goal, a confirmed written specification, executable acceptance checks, and scope bounds. Do not use for a one-off review or for open-ended make-it-better requests.
---

# Run Review Loop

Control a develop → review → fix cycle with a maximum of three iterations. The
confirmed specification owns required behavior. Existing code is evidence of current
behavior and local conventions, not authority for product intent.

## 1. Establish the goal contract

Before changing code, record:

1. Specification: a confirmed requirements/design document, ADR, detailed ticket, or
   API contract. Pass its path to every worker and reviewer.
2. Goal: one or two sentences describing the finished state.
3. Executable acceptance criteria: pair every criterion with an exact command or
   observable assertion. Capture exit codes and relevant output. When the specification
   numbers its criteria (`AC-<n>`), start every recorded `criterion` with that
   identifier.
4. Scope bounds: behavior, interfaces, storage formats, and modules that must not
   change.

If the specification is missing, invoke the bundled draft-spec skill and pause the
loop until the user confirms the document. If the goal, checks, or scope bounds are
too vague, ask the smallest blocking question. Never start from a guessed contract.
Record the verification environment for each check (mock repository, local service/DB,
or real-account end-to-end); evidence from one does not establish another.
An unevaluable acceptance check fails; diagnose and rerun it instead of inferring
success.

Each criterion also carries a phase: `loop` (the default; it must pass on the final
candidate before the gate), `post_deploy` (it needs a deployed or real environment after
merge), or `manual` (a human observation). Only loop-phase criteria decide `goal_met`.
Record post-deploy and manual criteria as `deferred` in `run.json` and list them as open
items in the report. Never relabel a loop-phase check as deferred to get past it.

Before the first worker starts, rerun the specification's acceptance preflight (see
draft-spec) when the baseline or environment changed since confirmation. Every
loop-phase command must execute against the current baseline: a red result is
expected, an unrunnable one is not. Stop and ask before delegation when a check cannot
run, a permission or credential guard fails, or a baseline fact a criterion depends on
has moved. Do not let a worker discover it in the middle of a batch.

Add a runtime smoke check when the specification covers a runnable service and the
repository has a safe, inexpensive local start path.

## 2. Load optional model-group configuration

Read `.agent-review/config.json` when present. The canonical groups are
`design_review_gate` and `worker`, assigned to roles in the effective model table below.
`inherit`, a missing group or role, or a missing file means the current session model.
Apply the configured reasoning effort exactly as well; fail preflight if either the
model or effort cannot be honored.

Existing repositories may still provide the legacy `models` and `reasoning_efforts`
maps keyed by `developer`, `fixer`, `reviewer`, and `gate`. Accept that shape without
migration. When both shapes are present, an explicit legacy role entry overrides its
group, and every role without that entry resolves from its group. A group fallback is
resolved for all roles in that group; a role-specific fallback overrides it. In a
legacy-only configuration, resolve `designer` from the legacy `reviewer` role, then
the legacy `gate` role, before using the current session model so design, review, and
gate remain one effective group by default.

The effective model table must be recorded before delegation:

| Role | Group | Use |
|---|---|---|
| designer | `design_review_gate` | design brainstorming and decision interview in `draft-spec` |
| developer | `worker` | implementation |
| fixer | `worker` | verified repair |
| reviewer | `design_review_gate` | five-pass independent review |
| gate | `design_review_gate` | holdout verification |

When delegating, apply an exact configured model only if the host supports model
overrides. If the configured model cannot be used, stop and ask rather than silently
substituting another model. The user's configuration is authoritative.

The configuration may declare `fallback_models` per group or role. A declared fallback
is a substitution the user authorized in advance: when the resolved model is unavailable
or rate-limited, switch that role to its fallback and record the substitution (role,
group, from, to, reason, authorization) in `run.json` `model_substitutions`. Without a
declared fallback, stop and ask. A substitution does not change the independence label;
independence comes from context isolation, not from the model.

Treat a missing `blind_mode` as `strict`. Strict is the only persistent mode; never
save relaxed mode as a repository default.

## 3. Define role contracts and least privilege

Keep each role to one responsibility and request only the capabilities it needs:

| Role | Allowlisted input | Required output | Capability boundary |
|---|---|---|---|
| controller | full run state | run record and user report | orchestrate, run acceptance checks, write `.agent-review/`; never implement, review, or fix |
| designer | repository facts, user goal, decision surface, explicit constraints | proposals, trade-offs, verifiable implementation design, and interview questions | brainstorm and clarify the contract; never silently decide or edit target files |
| developer | spec, goal, current batch, scope, checks | schema-valid worker result | read/write target and run required checks; no review history or gate material |
| fixer | Failed findings or minimal gate failure packet | schema-valid worker result | read/write target and run required checks; no passed probes |
| reviewer | strict-blind allowlist below | review result with a repair plan for every finding | read/search target and run safe checks; never write target or cause external side effects |
| gate | reviewer allowlist plus snapshot | gate result with a repair plan for every Failed finding | read/search frozen target and use isolated temporary tests; never write target or fix |

Use host-enforced read/write or tool allowlists when available. Otherwise state the
same boundary in the role brief; strict blind mode still describes context isolation,
not a filesystem security claim.

Keep worker responses compact. Return changed files, check command or assertion,
result, short evidence, and blockers; omit reasoning traces and full tool transcripts.
The controller must never paste raw worker output into another role's brief.

Before the original worker submission, use
`python3 ../../scripts/check_worker_result.py RESULT.json --role fixer --staging-root DIR`
(paths here are relative to this skill) to validate the complete payload and artifacts.
Use `--role developer` for development. The helper validates; it never truncates evidence,
rewrites verdicts, runs acceptance checks or replaces controller/host-status validation.
Perform this before returning the original result, not during the tool-free format retry.
The controller reruns validation on the exact received payload; supply repeated
`--criterion TITLE` arguments for the assigned checks or exact Failed titles.

Issue every worker, reviewer, and gate its own temporary workspace path outside the
target worktree, derived from the run number, role, iteration, and attempt (for example
`<tmp>/veriloop-<run>-<role>-<iteration>-<attempt>`; every batch, restart, or new
instance is a new attempt). Roles never choose their own paths. If the issued path
already exists or the temporary worktree cannot be created there, a worker is blocked,
and a reviewer or gate reports the checks or probes that needed it as `blocked`; never
fall back to another path. Remove the path when the role exits, and reclaim it yourself
when you stop a role.

Before delegation, create a unique artifact staging directory outside the target
worktree and grant the worker access only to its target plus that directory. Keep the
entire UTF-8 worker result at or below 16 KiB. Keep each evidence excerpt, tool error,
and blocker message at or below 512 characters. The schema also caps checks at 32,
tool failures at 16, and artifacts at 8.

When essential output does not fit, write it to the issued staging directory and
return only the short excerpt plus `artifact_path`. Declare every referenced artifact
with its byte count and SHA-256 digest; one artifact may be at most 10 MiB. Reject a
missing, oversized, digest-mismatched, undeclared, unreferenced, duplicate, symlinked,
or staging-escaping path. Do not create another agent or split one result to handle
large output.

Redact credentials, personal data, and unrelated environment details before writing
an artifact. Never preserve secret-bearing output merely because it is outside the
conversation context.

Do not read artifacts into controller context on a successful path. Inspect the
smallest relevant slice only when a check failed, the compact fields contradict each
other, or the user requests the detail. Never send artifact contents or paths to a
reviewer or gate.

### Handle worker termination and results fail-closed

Inspect the host delegation/tool status before reading the worker body. A reported
timeout, cancellation, context limit, or tool failure is authoritative; never infer
completion from a partial message or changed worktree. Record a compact synthetic
worker result with the matching termination and blocker, then exit as `worker_blocked`
or `worker_failed`.

Require every developer and fixer response to conform to
`../../schemas/worker-result.schema.json`. Use native structured output when the host
supports it. Otherwise require the entire final response to be one raw JSON object
without prose or fences, parse the whole response with a JSON parser, and validate the
schema. Never extract JSON from mixed prose with a regular expression.

For a normally returned but invalid object, allow one format-only retry in the same
worker context. Give only the schema and validation error; do not rerun tools, edit
code, or start another implementation attempt. If the retry is invalid, record a
synthetic `blocked` result with `termination: invalid_result` and exit as
`worker_result_invalid`.

Treat an oversized result as contract-invalid. The format-only retry may shorten
fields and reference an artifact already written during the original work, but it must
not run a tool, write a new artifact, repeat implementation, or delegate to another
agent. If essential evidence exists only in the oversized response, stop as
`worker_result_invalid` rather than discard it and claim completion.

If the host cannot parse and validate the whole object reliably, do not use a
best-effort textual fallback; record `invalid_result` and stop.

Apply these semantic checks after schema validation:

- `completed` requires `termination: completed`, `blocker: null`, no tool failures,
  and every required check at `pass`. A command check records its real exit code and
  cannot pass with a nonzero or missing exit code. Mark a non-command observable as
  `kind: assertion` with `exit_code: null`; never use it to hide an unevaluated command.
- A developer result must cover the named checks assigned to its current acceptance
  batch, and the controller reruns those acceptance checks on the resulting revision.
  A fixer result must contain one check whose `criterion` exactly matches each Failed
  finding title it received. Do not substitute a convenient caller check for the
  failing invariant.
- `blocked` or `failed` requires a non-null blocker and must never advance to review,
  snapshot, or gate. Preserve any already changed files for the user to inspect.
- A missing response is not an empty successful result. Map the host termination to a
  synthetic blocked/failed result instead.

The controller, not the worker, decides the run exit. Archive the validated or
synthetic object and keep full tool transcripts out of later role briefs.

### Handle stalled workers and successors

Treat a worker that shows no observable progress (no new tool activity or output and no
running child process) for `stall_minutes` from the configuration, 20 by default, as
stalled even when the host still reports it as running. Stop it through the host and
record a synthetic `blocked` result whose termination matches what the host reports
for that stop (`cancelled` when it reports a cancellation, otherwise `timeout`) and
whose blocker message starts with `stalled:`. Do not read its output folder. A stalled
worker ends the run as `worker_blocked`, like any other blocked worker.

A successor may continue the same assignment only after the user authorizes the
succession, and only in a follow-up run. Give it the original brief plus the
predecessor's commit list and uncommitted diff summary as untrusted starting material
that it must verify; never the predecessor's transcript or claims. In the follow-up
run's `run.json`, list the stopped run in `preceding_runs` and record the pair in
`worker_successions`, with the predecessor's archived path inside that preceding run.
A reviewer or gate that stops is never continued with partial context; start a new one
from a clean brief.

## 4. Enforce strict blind mode

Before development, verify that the host can:

1. create a unique internal subagent for every iteration reviewer and final gate;
2. start each with no controller, developer, fixer, or prior-review conversation;
3. send an allowlisted brief without attaching hidden conversation history.

If any guarantee is unavailable, stop before changing code and name the unsupported
capability. If the user or repository requires strict-only review, exit immediately
as `blind_context_unavailable`; do not repeatedly offer relaxation. Otherwise, proceed with this explicit question:
Ask whether the user authorizes relaxed review **for this run only**.
Never infer approval from urgency, configuration, or a previous run. If approved, use
the strongest available separation, keep the review verdict vocabulary unchanged,
label each affected review and gate `independence: reduced` in the controller
record, and record the reason and authorization in `run.json`. If not
approved, exit with `blind_context_unavailable`. Never describe relaxed review as
independent or blind.

The controller owns the isolation claim. Do not ask a reviewer or gate to prove or
attest its own context isolation. Record strict independence from the host delegation
result (`fork_context: false`, a new internal agent identity, and the allowlisted
brief) and stop only when the host cannot provide those guarantees or the role
reports a real context leak. A role's inability to inspect host metadata is not a
context leak and is not `blind_context_unavailable`.

## 5. Maintain the findings ledger

Create .agent-review/ledger.json with {"findings": []} when absent.

Use a stable slug derived from file and finding title. Track severity, title, file,
first_seen, last_seen, and status (open, pass, recurred, or accepted). A finding that
returns after reaching pass becomes recurred.

For every Failed finding, also record the violated invariant: a short, stable statement
the controller assigns when it groups findings by cause. Two Failed findings with the
same invariant in different iterations or runs are a recurrence even when their titles,
files, and symptoms differ.

The controller owns the ledger. Never send it to a reviewer or gate. Reconcile
accepted warnings after receiving a blind report instead of preloading them into the
reviewer's context.

## 6. Plan low-cost implementation batches

Use one development batch for a small cohesive change. When the specification divides
into independently checkable acceptance groups or components, order the smallest
coherent batches before development. Give a fresh worker only the current batch, the
necessary spec slice, global scope bounds, and that batch's checks. Complete its checks
before starting the next batch.

Do not run a blind review after every development batch; that multiplies reviewer cost
and exposes partial integration states. After all batches pass their local checks,
freeze and review the cumulative target. Keep cross-component and full-suite checks in
the final acceptance set. If no safe independent boundary exists, keep one batch rather
than inventing a split.

For repair work, group findings by the violated invariant and directly affected
callers before editing. Give the fixer a bounded causal repair packet, not a mandate
to fix unrelated debt. Preserve finding identities while checking all affected paths.
Where practical, reproduce the failure before repair and check both the failure and
normal behavior that must remain valid. “Minimal” means the smallest coherent repair,
not the fewest lines or one symptom at a time.

Workers run their assigned local checks; the controller independently reruns those
checks. Run the full required acceptance set on the final candidate, including required
device checks before gate. Do not repeat full builds or device flows after each edit.
After a pass, repeat checks only for a new relevant change, failure or unresolved risk;
record why. Do not reuse results from an older target as final-candidate evidence.
Record a command's evidence once and map all covered criteria to it without dropping
any criterion. Keep reviewer scope at cumulative target plus directly affected behavior.

Use completion notifications or bounded waits instead of unchanged polling. Parallelize
independent reads/checks, but serialize mutations to shared DBs, devices and worktrees.
Never promise token savings without measurements; track review/fix counts and reasons
for repeated checks instead. Do not lower configured role models to save cost.

## 7. Iterate at most three times

### Develop

If the target diff already exists, skip development. Otherwise delegate the
implementation to a worker with the repository path, confirmed specification, goal
contract, scope bounds, and required verification. The worker must inspect and obey
the applicable AGENTS.md, CLAUDE.md, contributor guidance, and repository checks.

Use the host's internal subagent or delegation mechanism when available. Do not
create a user-owned task or external thread merely to simulate an internal worker.
Give the worker the specification and acceptance checks, but do not give it review
reports, the review checklist, gate plans, holdout probes, or reviewer reasoning.

Inspect the transport status and validate the worker result before reading completion
claims. Advance to cumulative acceptance and blind review only for a semantically valid
`completed` result. A blocked, failed, missing, or twice-invalid result exits through
the worker termination protocol above.

### Review in a unique blind context

Create a new reviewer subagent for this iteration. Never reuse a reviewer from an
earlier iteration or gate. Run the bundled `veriloop` skill with only:

- strict-blind invocation marker;
- repository path;
- frozen review target;
- confirmed specification;
- scope bounds;
- risk focus.

Do not send developer or fixer reasoning, prior reports, ledger contents, accepted
warnings, acceptance results, or gate probes. Exclude `.agent-review/`, `REVIEW.md`,
`PRD.md`, `DECISIONS.md`, worker artifacts and other outcome/history documents from
reviewer and gate reads, searches and displayed diffs. Use explicit allowed paths; a broad search followed
by filtering already-displayed history is not isolation. If forbidden context leaks into the brief, discard that review and
start a clean reviewer; if that cannot be done, return to the strict-mode preflight.

Require the prose report and final machine-readable JSON block. For every finding, the
reviewer must provide a compact, code-grounded `repair_plan` containing the violated
invariant, root cause, affected paths, ordered implementation steps, verification
cases, and non-goals. The plan is a design contract for the fixer, not a patch: the
fixer must compare it with the confirmed specification and current code before
implementing it. The controller then reconciles findings and filters previously
accepted warnings without exposing history to the reviewer. Require the object to validate against
`../../schemas/review-result.schema.json`; when the host supports native structured
output, supply that schema to the reviewer.

Review and gate objects are exact: the final `json veriloop-review` or
`json veriloop-gate` object contains only the fields its schema defines. Keep role,
agent identity, transport status, strict-mode and independence evidence, checks,
changed files, and blockers in the controller's run record. Validate the received object
before interpreting its verdict. If it is schema-invalid, request one format-only
correction from the same completed role without rerunning implementation, review, or
probes, or changing the candidate; a second invalid object is a review failure or a
blocked gate. Never reinterpret an empty or malformed findings array as a pass.

### Check stop conditions in order

1. Success candidate: every loop-phase acceptance check passes and the verdict is pass
   or pass_with_warnings. Run the final gate below.
2. Iteration cap: iteration three ended without a successful gate. Stop and escalate
   with evidence.
3. No progress: any finding is recurred, or the failed count did not decrease from
   the previous iteration. Stop and ask for the specific human decision needed.

A user-authorized follow-up run does not erase the previous lack of progress. Before
restarting, state the repeated invariant, why the previous approach was insufficient,
and the changed repair approach or missing decision. Do not automatically open a new
run to bypass the cap; retain links to preceding runs in controller-only records and
in `run.json` `preceding_runs`. When the stop came from a recurring invariant, the
changed approach is the oracle described next or a design change the user chose.

### Escalate a recurring invariant to an oracle

Symptom repair converges only when the failure space is small. When the same invariant
produces Failed findings in two iterations, within one run or across runs of the same
specification, or a run stops with `no_progress` or `iteration_cap` on an invariant
that failed before, stop repairing that invariant case by case. Do not start another
repair iteration or follow-up run for it until the specification carries a confirmed
**invariant oracle**, or the user decides to change the design so that the invariant
holds by construction.

Draft the oracle with draft-spec as a specification delta; its required elements,
including the strength requirement over every historical Failed finding of that
invariant, are defined once in `skills/draft-spec/references/invariant-oracle.md`.

The oracle becomes loop-phase acceptance. The next worker first runs it and shows the
historical instances red with their repairs disabled, together with the divergences of
the current target, and then repairs the class until the oracle is green within budget.
Record each oracle in `run.json` `oracles` with its strength counts.

Once an oracle exists, reproduce any new Failed finding of the same invariant as an
oracle divergence (seed plus minimized input) before repairing it. If the oracle cannot
reproduce it, the finding exposes an oracle gap, either a missing generator dimension or
a flawed reference, and the repair extends the oracle first.

Reviewers judge the oracle's soundness from the target itself, as the bundled `veriloop`
skill's regression pass defines. Never pass reviewers or gates oracle results or the list
of historical findings. A useful gate probe disables or mutates a guarded behavior and
checks that the oracle notices.

### Final blind gate with late-bound probes

When a success candidate is reached, freeze it by recording the commit plus a digest
of the working-tree diff. Any target change invalidates the gate.

Create one additional gate subagent that is new to the run and uses the configured
gate model. Give it only the same allowlisted inputs as a blind reviewer plus the
frozen snapshot identifier. Do not reveal the iteration verdict, acceptance results,
prior findings, ledger, developer explanations, or previous gate probes.

The gate must inspect the frozen implementation first and then generate holdout probes
that did not exist in the developer brief:

- For executable code, run at least two safe probes from different categories:
  boundary or invalid inputs, state-transition ordering, failure injection,
  property/metamorphic behavior, differential behavior, or test-strength/mutation
  checks.
- For documentation or non-executable configuration, run at least one independent
  observable assertion.
- At least one probe must exercise an in-spec behavior not identical to a named
  acceptance check.

Prefer non-mutating commands. If a temporary test is required, use the isolated
temporary workspace path the controller issued and never edit the target worktree. A probe that cannot execute
is blocked, not passed. The gate must not fix code.

The gate holds only when the snapshot is unchanged, every holdout probe passes, and no
new Failed finding exists. Its report must include the snapshot, probe category,
command or assertion, captured evidence, and any new Failed finding.

Require a final `json veriloop-gate` object that validates against
`../../schemas/gate-result.schema.json` (verdict, snapshot, independence label, probes,
and findings), under the exact-object rule in the review step above. A schema-invalid
gate is blocked, not held. Each gate finding contains `severity: failed`, title,
relative file, line (`0` when no single line applies), captured evidence, and a bounded
`repair_plan`.

On failure, add the finding to the controller-owned ledger and give the fixer only the
Failed finding's invariant, minimal reproducible evidence, and its `repair_plan`;
withhold passed probes and the rest of the gate's reasoning. After fixing and blind review, create another entirely
new gate that generates new probes. Continue within the same three-iteration limit.

Warnings never keep the loop running by themselves.

### Fix

When failed findings remain, delegate the bundled apply-review-findings skill with
the Failed findings, their repair plans, minimal evidence, confirmed specification,
risk focus, and only the relevant ledger identities/dispositions. Loop mode overrides the
standalone reporting behavior of that skill: the fixer returns worker JSON only and
does not edit review reports or controller records. Require minimal
edits and verification against each finding's evidence. Then review again in a fresh
context.

For a blind-gate failure, pass only the minimal failure packet defined above, not the
full gate report. Never let the fixer read passed holdout probes. The fixer may reject
or adapt a repair plan when the specification or current code disproves an assumption,
but must preserve the finding's invariant and verify every stated verification case.

Validate the fixer result with the same worker protocol. Review the repaired target in
a fresh context only after a semantically valid `completed` result and passing
per-finding checks.

## 8. Archive and report

On every exit, archive the run's worker results, prose reviews with their JSON blocks,
gate results, and `run.json` into the next numbered `.agent-review/runs/NNN/`
directory. Write archives only after the run exits so no active reviewer can consume
them. Do not copy the specification into the archive. Artifact content remains excluded
from reports and later role briefs.

Do this with the bundled script rather than by hand:

    python3 ../../scripts/archive_run.py --agent-review .agent-review --run-json DRAFT.json \
      --worker RESULT.json --gate GATE.json --review REVIEW-N.md --staging DIR --delete-staging

(paths relative to this skill; repeat `--worker`, `--gate`, `--review`, and `--staging`
as needed). It allocates the next run number, copies and digest-verifies artifacts,
rewrites archived paths relative to the run directory, validates every result and the
run record, moves the run directory into place, and deletes staging only after all of
that succeeded. Exit 1 means nothing was archived: keep the staging directories, fix
the cause, and rerun it. Exit 3 means the archive is complete but staging cleanup
failed: do not archive again; remove the remaining staging files yourself.

Write `run.json` to conform to `../../schemas/run-result.schema.json`, using the exact
exit identifiers `goal_met`, `iteration_cap`, `no_progress`, and
`blind_context_unavailable`, plus `worker_blocked`, `worker_failed`, and
`worker_result_invalid` for worker termination exits. Include each criterion's phase,
`preceding_runs` for a follow-up run, and any `oracles`, `model_substitutions`, and
`worker_successions`. Validate it before reporting success; an invalid archive cannot
change the actual gate verdict but must be reported as an archival failure.

Report:

- exit reason: goal met, iteration cap, no progress, blind context unavailable, worker
  blocked/failed, or invalid worker result;
- worker termination: role, status, termination, failed/blocked check, and blocker;
- every acceptance criterion, exact check, Pass/Fail, and captured evidence;
- each iteration's verdict and failed/warning counts;
- every resolved finding as Pass;
- every remaining warning and its required disposition: accept, file an issue, or
  clean up now;
- every deferred post-deploy or manual criterion, and who closes it and how.

The controller alone writes loop reports and archives; reviewer/gate/fixer outputs
do not mutate these files. Keep prior run archives immutable and link preceding runs
from the latest report.

Persist `REVIEW.md` on every exit and `PRD.md` only on a `goal_met` exit, both in the
same directory as the confirmed specification (`IA.md`) and both written in Korean
whatever language the conversation uses. Read `references/exit-documents.md` before
writing either and follow it. `REVIEW.md` ends with exactly one `json veriloop-report`
summary block. `PRD.md` has exactly these ten `##` chapters, in this order:
`무엇인가`, `누가 쓰는가`, `어떤 문제를 푸는가`, `무엇을 하는가`, `어떻게 쓰는가`,
`어떻게 동작하는가`, `비기능 요구`, `검증`, `남은 일`, `이 문서의 한계`.

Validate both before reporting; a failed validation is an archival failure:

    python3 ../../scripts/check_review_report.py REVIEW.md --run-json <archived run.json>
    python3 ../../scripts/check_prd.py PRD.md --spec IA.md --run-json <archived run.json>

Record accepted warnings in the ledger. Do not create issues or apply warning-only
cleanup without the user's authorization. The text report remains the source of truth.
