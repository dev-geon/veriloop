#!/usr/bin/env python3
"""Read-only worker payload validation using Veriloop's contract evaluator."""
import argparse
import importlib.util
import json
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
    parser.add_argument("--role", required=True, choices=["developer", "fixer"])
    parser.add_argument("--staging-root", required=True, type=Path)
    parser.add_argument("--criterion", action="append", default=[])
    args = parser.parse_args()
    try:
        raw = args.result.read_bytes()
        contracts.require(len(raw) <= contracts.WORKER_RESULT_MAX_BYTES, "payload exceeds 16 KiB")
        def pairs(items):
            result = {}
            for key, value in items:
                contracts.require(key not in result, "duplicate JSON key")
                result[key] = value
            return result
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
        contracts.validate_worker_semantics(data, args.role, "worker", staging_root=args.staging_root)
        titles = {check["criterion"] for check in data["checks"]}
        contracts.require(set(args.criterion) <= titles, "required criteria missing")
    except (ValueError, OSError, AssertionError, TypeError, KeyError) as error:
        # Do not echo worker-controlled values or sensitive payloads.
        print("INVALID: " + type(error).__name__ + "; inspect schema, criteria and artifact metadata locally", file=sys.stderr)
        return 1
    print("VALID: schema, semantics, payload size, criteria and artifacts")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
