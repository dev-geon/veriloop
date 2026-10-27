#!/usr/bin/env python3
"""Validate the structure of a Veriloop PRD.md.

The product document has exactly ten `##` chapters with fixed Korean headings, in a fixed
order. Every chapter has a body written in Korean, and a chapter that does not apply says
`해당 없음` with a reason. With `--spec`, the `검증` chapter must report every `AC-<n>`
criterion of the specification with `Pass`, `Fail`, or `Deferred` and no unknown one.
With `--run-json`, the run must have exited `goal_met`.
"""
import argparse
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

CHAPTERS = [
    "무엇인가",
    "누가 쓰는가",
    "어떤 문제를 푸는가",
    "무엇을 하는가",
    "어떻게 쓰는가",
    "어떻게 동작하는가",
    "비기능 요구",
    "검증",
    "남은 일",
    "이 문서의 한계",
]
VERIFICATION = "검증"
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
H2 = re.compile(r"^ {0,3}##(?!#)[ \t]+(.*?)[ \t#]*$")
CRITERION = re.compile(r"(?<![A-Za-z0-9_-])AC-[0-9]+(?![0-9])")  # Korean particles may follow directly
RESULT = re.compile(r"(?<![A-Za-z])(Pass|Fail|Deferred)(?![A-Za-z])")
HANGUL = re.compile(r"[가-힣]")
NOT_APPLICABLE = re.compile(r"^[\s\W_]*해당\s*없음[\s\W_]*$")


def prose_lines(text):
    """Yield (line, inside_fence) so headings and criteria inside code fences are ignored."""
    fence = None
    for line in text.splitlines():
        match = FENCE.match(line)
        if fence is None and match:
            fence = (match.group(1)[0], len(match.group(1)))
            yield line, True
        elif fence is not None:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1] and not line.strip()[len(match.group(1)):].strip():
                fence = None
            yield line, True
        else:
            yield line, False


def chapters(text):
    found, current = [], None
    for line, fenced in prose_lines(text):
        match = None if fenced else H2.match(line)
        if match:
            current = [match.group(1).strip(), []]
            found.append(current)
        elif current is not None:
            current[1].append((line, fenced))
    return found


def check_structure(found):
    titles = [title for title, _ in found]
    for title in titles:
        require(title in CHAPTERS, "unexpected ## chapter (headings must be one of the ten fixed Korean chapters)")
    require(len(titles) == len(set(titles)), "a ## chapter appears more than once")
    missing = [title for title in CHAPTERS if title not in titles]
    require(not missing, "missing ## chapter: " + ", ".join(missing))
    require(titles == CHAPTERS, "## chapters are not in the required order")
    for title, body in found:
        text = "\n".join(line for line, _ in body).strip()
        require(text, f"chapter {title}: empty body")
        require(NOT_APPLICABLE.match(text) is None, f"chapter {title}: 해당 없음 without a reason")
        prose = "\n".join(line for line, fenced in body if not fenced)
        require(HANGUL.search(prose), f"chapter {title}: body is not written in Korean")


def spec_criteria(path):
    text = path.read_bytes().decode("utf-8-sig")
    return sorted({match.group(0) for line, fenced in prose_lines(text) if not fenced for match in CRITERION.finditer(line)},
                  key=lambda value: int(value[3:]))


def check_verification(found, criteria):
    body = next(body for title, body in found if title == VERIFICATION)
    reported = {}
    for line, fenced in body:
        if fenced:
            continue
        for match in CRITERION.finditer(line):
            reported.setdefault(match.group(0), False)
            if RESULT.search(line):
                reported[match.group(0)] = True
    unknown = sorted(set(reported) - set(criteria), key=lambda value: int(value[3:]))
    require(not unknown, "검증 cites criteria the specification does not define: " + ", ".join(unknown))
    missing = [item for item in criteria if item not in reported]
    require(not missing, "검증 does not report: " + ", ".join(missing))
    unresolved = [item for item in criteria if not reported[item]]
    require(not unresolved, "검증 reports without Pass, Fail, or Deferred on the same line: " + ", ".join(unresolved))


def check_run_json(path):
    run = json.loads(path.read_bytes().decode("utf-8"))
    require(isinstance(run, dict) and run.get("exit_reason") == "goal_met",
            "a product document is written only on a goal_met exit")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prd", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--run-json", type=Path)
    args = parser.parse_args()
    stage = "reading product document"
    note = ""
    try:
        text = args.prd.read_bytes().decode("utf-8-sig")
        stage = "checking chapters"
        found = chapters(text)
        check_structure(found)
        if args.spec is not None:
            stage = "reading specification"
            criteria = spec_criteria(args.spec)
            stage = "checking 검증"
            if criteria:
                check_verification(found, criteria)
            else:
                note = " (specification has no AC-<n> identifiers; criterion coverage not checked)"
        if args.run_json is not None:
            stage = "checking --run-json"
            check_run_json(args.run_json)
    except Exception as error:
        # Never echo document content: report fixed reasons, chapter names, and criterion ids only.
        if isinstance(error, contracts.EvalFailure):
            reason = " ".join(str(error).split())[:240]
        elif isinstance(error, json.JSONDecodeError):
            reason = f"{stage}: invalid JSON at line {error.lineno} column {error.colno}"
        else:
            reason = f"{stage}: {type(error).__name__}"
        print("INVALID: " + reason, file=sys.stderr)
        return 1
    print("VALID: product document" + note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
