#!/usr/bin/env python3
"""Read-only validation of one reviewer result: raw JSON, or a report ending in a fenced JSON block."""
import argparse
import importlib.util
import re
import sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("contracts", ROOT / "evals/run_contract_evals.py")
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)
FINDINGS_SECTION = "### 지적사항"
FINDING_HEADING = re.compile(r"^#### \[(Failed|Warning)\] (.*?)\s*$")


def prose_lines(text):
    """Lines outside fenced blocks, so a heading quoted in an example is not a finding."""
    fence = None
    for line in contracts.LINE_BREAK.split(text):
        if fence is None:
            match = contracts.FENCE_OPEN.match(line)
            if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                fence = match.group(1)
            else:
                yield line
            continue
        match = contracts.FENCE_CLOSE.match(line)
        if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
            fence = None


def validate_prose_titles(text, data):
    """Prose finding headings name exactly the JSON titles, byte for byte, with no backticks."""
    headings = {"failed": [], "warning": []}
    listed = False
    for line in prose_lines(text):
        if line.strip() == FINDINGS_SECTION:
            listed = True
        match = FINDING_HEADING.match(line)
        if match:
            listed = True
            headings[match.group(1).lower()].append(match.group(2))
    titles = {"failed": [], "warning": []}
    for finding in data["findings"]:
        titles[finding["severity"]].append(finding["title"])
    for severity in titles:
        contracts.require(all("`" not in title for title in titles[severity] + headings[severity]),
                          f"{severity} finding title contains a backtick")
        if listed:
            contracts.require(sorted(headings[severity]) == sorted(titles[severity]),
                              f"{severity} finding headings disagree with the JSON titles")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--sha256", help="the digest the reviewer's result pointer named")
    args = parser.parse_args()
    try:
        raw = args.result.read_bytes()
        contracts.require_digest(raw, args.sha256)
        data = contracts.result_object(raw, contracts.REVIEW_FENCE_INFOS)
        contracts.validate_result("review", data)
        contracts.validate_review_semantics(data, "review")
        validate_prose_titles(raw.decode("utf-8"), data)
    except (ValueError, OSError, AssertionError, TypeError, KeyError, RecursionError) as error:
        print("INVALID: " + contracts.safe_error(error), file=sys.stderr)
        return 1
    print(f"VALID: {data['verdict']}, {len(data['findings'])} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
