#!/usr/bin/env python3
"""Archive one finished Veriloop run into the next numbered .agent-review/runs/NNN/ directory.

The archive is built in runs/.NNN.partial and renamed into place only after every
worker, gate and run check passes. Any failure removes the partial directory and leaves
staging untouched. Worker results are rewritten to point at archived artifact copies;
gate results and review files are copied byte for byte.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("contracts", ROOT / "evals/run_contract_evals.py")
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)
require = contracts.require


def sanitize(message):
    """Drop document-controlled values that schema messages may quote."""
    message = re.sub(r"^(\$[^\s:]*): .* is outside enum$", r"\1: value is outside enum", message, flags=re.S)
    message = re.sub(r"^(\$[^\s:]*): unexpected keys .*$", r"\1: unexpected keys", message, flags=re.S)
    return " ".join(message.split())[:240]


def safe_reason(error, stage):
    if isinstance(error, contracts.EvalFailure):
        return f"{stage}: {sanitize(str(error))}"
    if isinstance(error, json.JSONDecodeError):
        return f"{stage}: invalid JSON at line {error.lineno} column {error.colno}"
    if isinstance(error, UnicodeDecodeError):
        return f"{stage}: not valid UTF-8"
    return stage


def parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    require(isinstance(data, dict), "top-level JSON value is not an object")
    return data


def basename(value):
    return value.replace("\\", "/").rsplit("/", 1)[-1]


def digest_matches(payload, artifact):
    return len(payload) == artifact["bytes"] and hashlib.sha256(payload).hexdigest() == artifact["sha256"]


def dump(data):
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def unique_names(paths, kind):
    seen = set()
    for path in paths:
        require(path.is_file(), f"{kind} input {path.name or '?'} is not a file")
        key = path.name.casefold()
        require(key not in seen, f"duplicate {kind} basename {path.name}")
        seen.add(key)


class Archiver:
    def __init__(self, args):
        self.args = args
        self.stage = "checking arguments"
        self.partial = None
        self.renamed = False

    def run(self):
        try:
            return self._run()
        except BaseException:
            if self.partial is not None and not self.renamed:
                shutil.rmtree(self.partial, ignore_errors=True)
            raise

    def _run(self):
        args = self.args
        agent_review = Path(args.agent_review).resolve()
        require(agent_review.is_dir(), "--agent-review is not a directory")
        runs = agent_review / "runs"
        self.staging = []
        for item in args.staging:
            path = Path(item).resolve()
            require(path.is_dir(), "a --staging path is not a directory")
            require(path != runs and path not in runs.parents, "a --staging directory contains the run archive")
            require(runs not in path.parents, "a --staging directory lies inside the run archive")
            self.staging.append(path)
        workers = [Path(item) for item in args.worker]
        gates = [Path(item) for item in args.gate]
        reviews = [Path(item) for item in args.review]
        unique_names(workers, "worker")
        unique_names(gates, "gate")
        unique_names(reviews, "review")
        stems = [path.stem.casefold() for path in workers]
        require(len(stems) == len(set(stems)), "worker file stems collide in artifacts/")

        self.stage = "allocating run number"
        runs.mkdir(exist_ok=True)
        numbers = [int(p.name) for p in runs.iterdir() if p.is_dir() and re.fullmatch(r"[0-9]+", p.name)]
        number = f"{max(numbers, default=0) + 1:03d}"
        final = runs / number
        require(not final.exists(), f"runs/{number} already exists")
        partial = runs / f".{number}.partial"
        require(not partial.exists(), f"runs/.{number}.partial already exists")
        partial.mkdir()
        self.partial = partial

        self.worker_results = []
        worker_files = [self.archive_worker(path) for path in workers]
        gate_files = [self.archive_gate(path) for path in gates]
        review_names = [self.copy_review(path) for path in reviews]
        self.review_results = {name: self.review_result(name) for name in review_names}

        self.stage = "validating run draft"
        run = parse_json(Path(args.run_json).read_bytes())
        run["worker_files"] = worker_files
        run["gate_files"] = gate_files
        copied = {name: f"reviews/{name}" for name in review_names}
        iterations = run.get("iterations")
        for index, iteration in enumerate(iterations if isinstance(iterations, list) else []):
            if isinstance(iteration, dict) and isinstance(iteration.get("review_file"), str):
                name = basename(iteration["review_file"])
                require(name in copied, f"iterations[{index}].review_file is not an archived review")
                iteration["review_file"] = copied[name]
                self.check_iteration(index, iteration, self.review_results[name])
        contracts.validate_result("run", run)
        self.check_run_semantics(run, worker_files)
        contracts.validate_result("run", run)

        self.stage = "writing run.json"
        payload = dump(run)
        with (partial / "run.json").open("xb") as handle:
            handle.write(payload)
        require(not final.exists(), f"runs/{number} appeared during archiving")
        partial.rename(final)
        self.renamed = True
        return final, hashlib.sha256(payload).hexdigest()

    def pick_staging(self, artifacts):
        if not artifacts:
            return None
        choices = {}
        for root in self.staging:
            resolved = []
            for artifact in artifacts:
                path = (root / artifact["path"]).resolve()
                if root not in path.parents or not path.is_file():
                    break
                resolved.append(path)
            else:
                choices.setdefault(tuple(resolved), root)
        require(choices, "no --staging directory contains every declared artifact")
        require(len(choices) == 1, "declared artifacts resolve ambiguously across --staging directories")
        return next(iter(choices.values()))

    def archive_worker(self, source):
        name = source.name
        self.stage = f"validating worker {name}"
        raw = source.read_bytes()
        require(len(raw) <= contracts.WORKER_RESULT_MAX_BYTES, "payload exceeds 16 KiB")
        data = parse_json(raw)
        contracts.validate_result("worker", data)
        label = f"workers/{name}"
        root = self.pick_staging(data["artifacts"])
        contracts.validate_worker_semantics(data, data.get("role"), label, staging_root=root)

        self.stage = f"copying artifacts of worker {name}"
        mapping = {}
        target_dir = self.partial / "artifacts" / source.stem
        seen = set()
        for index, artifact in enumerate(data["artifacts"]):
            origin = (root / artifact["path"]).resolve()
            require(origin.name not in {"", ".", ".."}, f"{label}.artifacts[{index}]: unusable file name")
            require(origin.name.casefold() not in seen, f"{label}.artifacts[{index}]: duplicate artifact basename")
            seen.add(origin.name.casefold())
            payload = origin.read_bytes()
            require(digest_matches(payload, artifact), f"{label}.artifacts[{index}]: digest or size changed before copy")
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / origin.name
            with target.open("xb") as handle:
                handle.write(payload)
            require(digest_matches(target.read_bytes(), artifact), f"{label}.artifacts[{index}]: digest or size changed after copy")
            mapping[artifact["path"]] = f"artifacts/{source.stem}/{origin.name}"

        for artifact in data["artifacts"]:
            artifact["path"] = mapping[artifact["path"]]
        for item in [*data["checks"], *data["tool_failures"]]:
            if item["artifact_path"] is not None:
                require(item["artifact_path"] in mapping, f"{label}: artifact reference is undeclared")
                item["artifact_path"] = mapping[item["artifact_path"]]

        self.stage = f"revalidating archived worker {name}"
        contracts.validate_worker_semantics(data, data.get("role"), label, staging_root=self.partial)
        self.worker_results.append(data)
        (self.partial / "workers").mkdir(exist_ok=True)
        with (self.partial / "workers" / name).open("xb") as handle:
            handle.write(dump(data))
        return f"workers/{name}"

    def archive_gate(self, source):
        name = source.name
        self.stage = f"validating gate {name}"
        raw = source.read_bytes()
        contracts.validate_result("gate", parse_json(raw))
        (self.partial / "gates").mkdir(exist_ok=True)
        with (self.partial / "gates" / name).open("xb") as handle:
            handle.write(raw)
        return f"gates/{name}"

    def copy_review(self, source):
        self.stage = f"copying review {source.name}"
        raw = source.read_bytes()
        (self.partial / "reviews").mkdir(exist_ok=True)
        with (self.partial / "reviews" / source.name).open("xb") as handle:
            handle.write(raw)
        return source.name

    def review_result(self, name):
        """The last fenced JSON block of an archived review, validated like the contract evals do."""
        self.stage = f"validating review {name}"
        text = (self.partial / "reviews" / name).read_bytes().decode("utf-8")
        blocks = re.findall(r"```json\s*(.*?)\s*```", text, flags=re.DOTALL)
        require(blocks, f"reviews/{name}: no machine-readable JSON block")
        result = parse_json(blocks[-1].encode("utf-8"))
        contracts.validate_result("review", result)
        contracts.validate_review_semantics(result, f"reviews/{name}")
        return result

    def check_iteration(self, index, iteration, review):
        findings = review["findings"]
        require(iteration.get("verdict") == review["verdict"], f"iterations[{index}]: verdict disagrees with its review")
        require(
            iteration.get("failed_count") == sum(item["severity"] == "failed" for item in findings),
            f"iterations[{index}]: failed_count disagrees with its review",
        )
        require(
            iteration.get("warning_count") == sum(item["severity"] == "warning" for item in findings),
            f"iterations[{index}]: warning_count disagrees with its review",
        )

    def check_run_semantics(self, run, worker_files):
        # Fail-closed: an incomplete worker ends the run and decides its exit reason.
        incomplete = [index for index, data in enumerate(self.worker_results) if data["status"] != "completed"]
        if incomplete:
            require(len(incomplete) == 1 and incomplete[0] == len(self.worker_results) - 1,
                    "work continued after an incomplete worker")
            data = self.worker_results[incomplete[0]]
            expected = ("worker_result_invalid" if data["termination"] == "invalid_result"
                        else "worker_blocked" if data["status"] == "blocked" else "worker_failed")
            require(run["exit_reason"] == expected, f"an incomplete worker requires exit_reason {expected}")
        archived = {basename(path): path for path in worker_files}
        for index, succession in enumerate(run.get("worker_successions", [])):
            name = basename(succession["successor"])
            require(name in archived, f"worker_successions[{index}].successor is not an archived worker result")
            succession["successor"] = archived[name]
        contracts.validate_run_extensions(run, run["exit_reason"], "run.json")
        if run["exit_reason"] == "goal_met":
            require(run["gate"]["status"] == "hold", "goal_met requires a held gate")
            for index, item in enumerate(run["acceptance"]):
                if item.get("phase", "loop") == "loop":
                    require(item["result"] == "pass", f"acceptance[{index}]: goal_met requires every loop-phase check to pass")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-review", required=True)
    parser.add_argument("--run-json", required=True)
    parser.add_argument("--worker", action="append", default=[])
    parser.add_argument("--gate", action="append", default=[])
    parser.add_argument("--review", action="append", default=[])
    parser.add_argument("--staging", action="append", default=[])
    parser.add_argument("--delete-staging", action="store_true")
    args = parser.parse_args()
    archiver = Archiver(args)
    try:
        final, digest = archiver.run()
    except Exception as error:
        # Never echo worker-controlled values, file contents or secrets.
        print("INVALID: " + type(error).__name__ + ": " + safe_reason(error, archiver.stage), file=sys.stderr)
        return 1
    print(f"ARCHIVED {final} run.json sha256={digest}")
    if args.delete_staging:
        try:
            for path in archiver.staging:
                if path.exists():
                    shutil.rmtree(path)
        except OSError as error:
            # Exit 3: archived; do not archive again, only finish removing staging.
            print("ERROR: " + type(error).__name__ + ": staging cleanup failed; the archive is complete", file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
