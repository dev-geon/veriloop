#!/usr/bin/env python3
"""Record where a Veriloop draft or loop currently is, for hosts and tools that watch it.

The controller calls this when it enters a step. It writes one JSON file per run under
`.agent-review/progress/<id>.json` (atomically, with a step history) and keeps that
directory out of git. Progress is advisory: it never decides a verdict, and reviewers
and gates do not read it. The file conforms to schemas/progress.schema.json.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
sys.dont_write_bytecode = True

STEPS = {
    "draft": ["survey", "design", "interview", "draft", "preflight", "guess_hunt", "confirm"],
    "work": ["preflight", "develop", "review", "fix", "oracle", "gate", "archive"],
}
STATUSES = ["running", "waiting_user", "done", "stopped"]
EXITS = ["goal_met", "iteration_cap", "no_progress", "blind_context_unavailable",
         "worker_blocked", "worker_failed", "worker_result_invalid"]
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
HISTORY_LIMIT = 200
NOTE_LIMIT = 200


def fail(message):
    print(f"report_progress: {message}", file=sys.stderr)
    return 2


def relative_spec(value):
    if value is None:
        return None
    path = value.replace("\\", "/").strip()
    if not path or path.startswith("/") or ".." in path.split("/"):
        raise ValueError("--spec must be a repository-relative path without '..'")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-review", default=".agent-review", help="the repository's .agent-review directory")
    parser.add_argument("--id", required=True, help="progress id chosen once per draft or run, e.g. work-20261104T051200Z")
    parser.add_argument("--flow", required=True, choices=sorted(STEPS))
    parser.add_argument("--step", required=True)
    parser.add_argument("--status", default="running", choices=STATUSES)
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--spec", help="repository-relative path of IA.md, once known")
    parser.add_argument("--exit-reason", choices=EXITS)
    parser.add_argument("--note", default="", help="one short line for people watching; no findings or probes")
    args = parser.parse_args(argv)

    if not ID.match(args.id):
        return fail("--id may use letters, digits, '.', '_' and '-' (at most 80)")
    if args.step not in STEPS[args.flow]:
        return fail(f"--step for {args.flow} is one of {', '.join(STEPS[args.flow])}")
    if args.iteration is not None and (args.flow != "work" or not 1 <= args.iteration <= 3):
        return fail("--iteration is 1 to 3 and only for --flow work")
    if args.exit_reason and (args.flow != "work" or args.status not in ("done", "stopped")):
        return fail("--exit-reason needs --flow work and --status done or stopped")
    if args.flow == "work" and args.status == "done" and args.exit_reason not in (None, "goal_met"):
        return fail("a finished loop with another exit reason is --status stopped")
    try:
        spec = relative_spec(args.spec)
    except ValueError as error:
        return fail(str(error))
    note = " ".join(args.note.split())[:NOTE_LIMIT]

    root = Path(args.agent_review) / "progress"
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        return fail(f"{root} is not a plain directory")
    root.mkdir(parents=True, exist_ok=True)
    ignore = root / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# Veriloop live progress; local only.\n*\n", encoding="utf-8")

    target = root / f"{args.id}.json"
    previous = {}
    if target.exists():
        try:
            previous = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
        if previous.get("flow") not in (None, args.flow):
            return fail(f"{target.name} already records a {previous.get('flow')} flow")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    steps = STEPS[args.flow]
    record = {
        "progress_version": "1",
        "id": args.id,
        "flow": args.flow,
        "steps": steps,
        "step": args.step,
        "step_index": steps.index(args.step),
        "status": args.status,
        "iteration": args.iteration if args.iteration is not None else previous.get("iteration"),
        "max_iterations": 3 if args.flow == "work" else None,
        "spec_path": spec or previous.get("spec_path"),
        "exit_reason": args.exit_reason,
        "note": note,
        "started": previous.get("started") or now,
        "updated": now,
    }
    history = list(previous.get("history") or [])
    history.append({"at": now, "step": args.step, "status": args.status, "iteration": record["iteration"], "note": note})
    record["history"] = history[-HISTORY_LIMIT:]

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=root, prefix=f".{args.id}.", suffix=".tmp", delete=False) as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp = handle.name
    os.replace(temp, target)
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
