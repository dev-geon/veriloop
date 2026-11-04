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
    args = parser.parse_args()
    try:
        raw = args.result.read_bytes()
        text = raw.decode("utf-8")
        if not text.lstrip().startswith("{"):
            block = contracts.review_result_text(text)
            contracts.require(block is not None, "no machine-readable JSON block")
            raw = block.encode("utf-8")
        data = contracts.parse_json_object(raw)
        contracts.validate_result("review", data)
        contracts.validate_review_semantics(data, "review")
    except (ValueError, OSError, AssertionError, TypeError, KeyError) as error:
        print("INVALID: " + contracts.safe_error(error), file=sys.stderr)
        return 1
    print(f"VALID: {data['verdict']}, {len(data['findings'])} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
