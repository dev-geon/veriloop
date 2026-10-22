# Fixture review

The seeded query implementation fails the performance requirement.

```json
{
  "verdict": "fail",
  "findings": [
    {
      "severity": "failed",
      "title": "Empty fleet triggers one query per ship",
      "file": "evals/fixtures/sample_project.py",
      "line": 15,
      "confidence": "confirmed",
      "fix_hint": "Batch the lookup before aggregating totals",
      "repair_plan": {
        "invariant": "Fleet totals use one batched lookup rather than one query per ship",
        "root_cause": "The aggregation loop performs the external lookup once for each ship",
        "affected_paths": ["evals/fixtures/sample_project.py:fleet_total"],
        "implementation_steps": [
          "Collect the ship identifiers before querying",
          "Issue one batched lookup and aggregate the returned values"
        ],
        "verification_cases": [
          "Known callers still return the same fleet total",
          "A fleet of 100 ships performs one lookup"
        ],
        "non_goals": ["Do not change fleet total semantics"]
      }
    }
  ]
}
```
