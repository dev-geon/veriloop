#!/usr/bin/env python3
"""Read-only validation of one final gate result, a whole raw JSON object."""
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
    parser.add_argument("--snapshot", help="the frozen snapshot identifier the gate was given")
    args = parser.parse_args()
    try:
        data = contracts.parse_json_object(args.result.read_bytes())
        contracts.validate_result("gate", data)
        contracts.validate_gate_verdict(data, "gate")
        if args.snapshot is not None:
            contracts.require(data["snapshot"] == args.snapshot, "gate used a different snapshot")
    except (ValueError, OSError, AssertionError, TypeError, KeyError) as error:
        print("INVALID: " + contracts.safe_error(error), file=sys.stderr)
        return 1
    print(f"VALID: {data['gate']}, {len(data['probes'])} probes, {len(data['findings'])} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
