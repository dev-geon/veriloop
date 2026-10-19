#!/usr/bin/env python3
"""Validate the single machine-readable summary block of a Veriloop REVIEW.md.

The block is the one fenced code block whose info string is `json veriloop-report`.
It is parsed as a whole JSON object, checked against review-report.schema.json and the
report semantics, and optionally tied to archived run.json files by SHA-256.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("contracts", ROOT / "evals/run_contract_evals.py")
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)
require = contracts.require
OPEN_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CLOSE_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*$")


def sanitize(message):
    """Drop document-controlled values that schema messages may quote."""
    message = re.sub(r"^(\$[^\s:]*): .* is outside enum$", r"\1: value is outside enum", message, flags=re.S)
    message = re.sub(r"^(\$[^\s:]*): unexpected keys .*$", r"\1: unexpected keys", message, flags=re.S)
    return " ".join(message.split())[:240]


def parse_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    data = json.loads(text, object_pairs_hook=pairs)
    require(isinstance(data, dict), "top-level JSON value is not an object")
    return data


def report_blocks(text):
    """Return the bodies of ``` fences tagged `json veriloop-report`, honouring fence nesting,
    and whether any non-blank line follows the last such block."""
    blocks, body, fence = [], [], None
    lines = text.splitlines()
    last_close = None
    for number, line in enumerate(lines):
        if fence is None:
            match = OPEN_FENCE.match(line)
            if not match:
                continue
            marker, info = match.groups()
            if marker[0] == "`" and "`" in info:
                continue  # not a fence opening (CommonMark forbids backticks in the info string)
            tagged = marker[0] == "`" and info.split()[:2] == ["json", "veriloop-report"]
            fence, body = (marker[0], len(marker), tagged), []
            continue
        match = CLOSE_FENCE.match(line)
        if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1]:
            if fence[2]:
                blocks.append("\n".join(body))
                last_close = number
            fence = None
        else:
            body.append(line)
    require(fence is None or not fence[2], "report block is not closed")
    trailing = last_close is not None and any(line.strip() for line in lines[last_close + 1:])
    return blocks, trailing


def check_semantics(report):
    runs = report["runs"]
    run_ids = [item["run"] for item in runs]
    require(len(run_ids) == len(set(run_ids)), "runs: run ids are not unique")
    for index, run_id in enumerate(run_ids):
        require(re.fullmatch(r".+/run-[0-9]{3,}", run_id) is not None, f"runs[{index}].run is not named <work id>/run-NNN")
    for index, item in enumerate(runs):
        digest = item["archive"]["sha256"]
        require(digest is None or re.fullmatch(r"[0-9a-f]{64}", digest) is not None, f"runs[{index}].archive.sha256 is not lowercase hex")
    current, last = report["current"], runs[-1]
    require(current["run"] == last["run"], "current.run is not the last run")
    require(current["exit_reason"] == last["exit_reason"], "current.exit_reason disagrees with the last run")
    require(current["gate"] == last["gate"], "current.gate disagrees with the last run")

    acceptance = report["acceptance"]
    criteria = [item["criterion"] for item in acceptance]
    require(len(criteria) == len(set(criteria)), "acceptance: criteria are not unique")
    deferred_refs = {item["ref"] for item in report["open_items"] if item["kind"] == "deferred_acceptance"}
    for index, item in enumerate(acceptance):
        if item["result"] == "deferred":
            require(item["phase"] != "loop", f"acceptance[{index}]: a loop-phase criterion cannot be deferred")
            require(item["criterion"] in deferred_refs, f"acceptance[{index}]: deferred result lacks a deferred_acceptance open item")

    findings = report["findings"]
    finding_ids = [item["id"] for item in findings]
    require(len(finding_ids) == len(set(finding_ids)), "findings: ids are not unique")
    for index, item in enumerate(findings):
        if item["severity"] == "failed":
            require(item["disposition"] is None, f"findings[{index}]: a failed finding cannot carry a disposition")
        elif item["status"] in {"open", "accepted"}:
            require(item["disposition"] is not None, f"findings[{index}]: an open or accepted warning needs a disposition")

    for index, oracle in enumerate(report.get("oracles", [])):
        require(oracle["rediscovered"] <= oracle["historical"], f"oracles[{index}]: rediscovered exceeds historical")

    if current["exit_reason"] == "goal_met":
        require(current["gate"] == "hold", "goal_met requires a held gate")
        for index, item in enumerate(acceptance):
            if item["phase"] == "loop":
                require(item["result"] == "pass", f"acceptance[{index}]: goal_met requires every loop-phase criterion to pass")
        for index, item in enumerate(findings):
            if item["severity"] == "failed":
                require(item["status"] == "pass", f"findings[{index}]: goal_met with an unresolved failed finding")
        iterations = report["runs"][-1]["iterations"]
        require(not iterations or iterations[-1]["verdict"] != "fail", "goal_met after a failing last iteration")
        for index, oracle in enumerate(report.get("oracles", [])):
            require(oracle["result"] == "pass", f"oracles[{index}]: goal_met requires a passing oracle")
            require(oracle["rediscovered"] == oracle["historical"], f"oracles[{index}]: oracle rediscovered fewer historical defects than recorded")


def check_run_json(report, path, index):
    label = f"--run-json[{index}]"
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    matches = [item for item in report["runs"] if item["archive"]["sha256"] == digest]
    require(matches, f"{label}: digest matches no archived run")
    run = parse_json(raw.decode("utf-8"))
    require(all(item["exit_reason"] == run.get("exit_reason") for item in matches), f"{label}: exit_reason disagrees with its report entry")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--run-json", action="append", default=[], type=Path)
    args = parser.parse_args()
    stage = "reading report"
    try:
        text = args.report.read_bytes().decode("utf-8-sig")
        stage = "locating report block"
        blocks, trailing = report_blocks(text)
        require(len(blocks) == 1, f"expected exactly one json veriloop-report block, found {len(blocks)}")
        require(not trailing, "the json veriloop-report block must be the last content of the document")
        stage = "parsing report block"
        report = parse_json(blocks[0])
        stage = "checking schema"
        schema = contracts.load_json(contracts.SCHEMA_DIR / "review-report.schema.json")
        contracts.validate_schema(report, schema, schema)
        stage = "checking semantics"
        check_semantics(report)
        for index, path in enumerate(args.run_json, start=1):
            stage = f"checking --run-json[{index}]"
            check_run_json(report, path, index)
    except Exception as error:
        # Never echo document content: report positions and fixed reasons only.
        if isinstance(error, contracts.EvalFailure):
            reason = sanitize(str(error))
        elif isinstance(error, json.JSONDecodeError):
            reason = f"{stage}: invalid JSON at line {error.lineno} column {error.colno}"
        else:
            reason = f"{stage}: {type(error).__name__}"
        print("INVALID: " + reason, file=sys.stderr)
        return 1
    print("VALID: review report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
