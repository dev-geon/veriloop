---
name: initialize-review-loop
description: Initialize Veriloop in the current repository by creating optional model-group configuration, strict blind review defaults, and the findings ledger. Use when the user asks to set up, configure, initialize, or choose design, developer, fixer, reviewer, or gate models for the specification and review loop. Do not use merely to run a review or start a loop.
---

# Initialize Review Loop

Set up the optional .agent-review/ state used by run-review-loop. Every bundled
skill works without this initialization and inherits the current session model.

## Resolve model groups

Configure these roles through two model groups:

| Role | Responsibility |
|---|---|
| designer | Brainstorm and interview during specification confirmation |
| developer | Implement toward the confirmed specification and goal |
| fixer | Apply verified review findings |
| reviewer | Run the per-iteration five-pass review |
| gate | Independently confirm the success candidate |

The default group mapping is:

| Group | Roles | Responsibility |
|---|---|---|
| `design_review_gate` | `designer`, `reviewer`, `gate` | Shape and challenge the contract, then independently review and gate it |
| `worker` | `developer`, `fixer` | Change the target and run the assigned checks |

Accept `inherit` or an exact model identifier supported by the current host. The
group model and reasoning effort apply to every role in that group. Do not invent
provider-specific aliases, replace an unavailable model with another model, or assume
a model-strength ordering.

If the user supplied group or role/model pairs, use them. Otherwise ask one concise
question for the desired overrides; keeping both groups on inherit is the recommended
default. A role-specific legacy override may still be retained for compatibility, but
the new group setting is the normal configuration surface.
When the host exposes model availability, validate exact identifiers before writing.
If it does not, preserve the user's identifier and state that availability was not
validated.

## Write state

Create or update `.agent-review/config.json` with this shape:

    {
      "blind_mode": "strict",
      "model_groups": {
        "design_review_gate": {
          "model": "inherit",
          "reasoning_effort": "inherit"
        },
        "worker": {
          "model": "inherit",
          "reasoning_effort": "inherit"
        }
      }
    }

`run-review-loop` resolves `designer`, `reviewer`, and `gate` from
`design_review_gate`, and `developer` and `fixer` from `worker`. The older
`models` and `reasoning_efforts` maps remain accepted for existing repositories; when
both forms are present, an explicit role entry wins and the remaining roles use their
group. In a legacy-only file, `designer` inherits the legacy `reviewer` settings, then
the legacy `gate` settings, before falling back to the current session model. Do not
rewrite an existing role configuration unless the user asks to migrate it.

Two optional keys may be added when the user asks for them:

    {
      "fallback_models": {
        "design_review_gate": "<exact model id>",
        "worker": "<exact model id>"
      },
      "stall_minutes": 20
    }

`fallback_models` records substitutions the user authorizes in advance for a model
group whose configured model is unavailable or rate-limited; `run-review-loop` logs the
resolved role and group for every use. A role-specific fallback remains accepted for
backward compatibility. Omit a group or role to keep "stop and ask" for it.
`stall_minutes` is how long a worker may show no progress before it is treated as
stalled (default 20). Never fill either key by guessing.

Create .agent-review/ledger.json with {"findings": []} only when it is absent.
Never overwrite an existing ledger.

`strict` is the only persistent blind mode. Do not write a relaxed default. If a host
cannot create clean reviewer or gate contexts, `run-review-loop` must stop and request
explicit user approval for a one-run relaxation.

If the host provides a reliable strength comparison and the configured
`design_review_gate` group is weaker than the `worker` group, warn once without
changing the configuration. Otherwise skip the comparison instead of guessing.

Suggest ignoring the run archive and ledger when they are personal scratch state.
Explain that teams may instead commit config.json and a convention baseline because
those encode shared decisions. Do not edit ignore files unless the user asks.

Report strict blind mode, the final group and resolved role table, and the paths written
in the user's language.
