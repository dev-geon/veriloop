#!/usr/bin/env python3
"""Read-only validation of one reviewer result: raw JSON, or a report ending in a fenced JSON block."""
import argparse
import importlib.util
import sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("contracts", ROOT / "evals/run_contract_evals.py")
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)


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
    except (ValueError, OSError, AssertionError, TypeError, KeyError, RecursionError) as error:
        print("INVALID: " + contracts.safe_error(error), file=sys.stderr)
        return 1
    print(f"VALID: {data['verdict']}, {len(data['findings'])} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
